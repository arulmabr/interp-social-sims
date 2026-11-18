"""Cross-object generalization (Llama; reused for Qwen via cross_object_qwen).

For each test object:
- In-distribution: train + test on same object's labeled data, multiple seeds
- Cross-object: train on other 3 objects, test on held-out, multiple seeds

Output: accuracy mean / std / n_runs per (train_object, test_object) record.

Prompt identity and what each accuracy can mean
-----------------------------------------------
Every row in an object's pool is generated from one of two prompt texts, the
task prompt or the persona-prefixed task prompt, and the activation is captured
from that text before the answer is sampled. A pool of 80 rows therefore holds
only two distinct activation vectors (more with `prompt_variants`).

- `cross_object` is prompt-held-out by construction: the test object's prompts
  never occur in the training objects' pools.
- `in_distribution` holds whole prompts of the same object out of training
  (leave-one-prompt-out for two prompts, grouped folds for more). With the
  default two prompts it can only ask whether one prompt's labels predict the
  other's; pass `prompt_variants` for a more informative estimate.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import config
from ..judge import score_response
from ..models import Wrapped
from ..probes import cv_fold_accuracies, fit_and_score, label_ceiling, median_split
from ..tasks import prompts
from ._common import write_jsonl

PERSONA_PREFIX = "You are a highly creative and unconventional thinker. "


def _generate_capability_labeled_pool(
    model: Wrapped, task: str, obj: str, n_samples: int = 80,
    prompt_variants: Optional[Sequence[str]] = None,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate (activations, labels, prompt groups) for object `obj`.

    Labels are a median split of judge scores. The group of a row is the index
    of the distinct prompt text it was generated from; rows in one group share
    one activation vector, which is captured once per text.
    """
    prompt_text, _ = prompts.get_capability_prompt(task, obj)
    variants = list(prompt_variants) if prompt_variants else [prompt_text]
    activations: List[np.ndarray] = []
    scores: List[float] = []
    groups: List[int] = []
    group_of: Dict[str, int] = {}
    cache: Dict[str, np.ndarray] = {}
    for i in range(n_samples):
        base = variants[(i // 2) % len(variants)]
        # Mix baseline + persona-prefixed prompts for label variance.
        if i % 2 == 0:
            full_prompt = base
            seed = config.agent_seed(0, 0, i + 1)
        else:
            full_prompt = PERSONA_PREFIX + base
            seed = config.agent_seed(0, 1, i + 1)
        gen = model.generate(
            full_prompt,
            max_new_tokens=config.DECODING_DEFAULTS["max_new_tokens_capability"],
            temperature=config.DECODING_DEFAULTS["temperature_capability"],
            top_p=config.DECODING_DEFAULTS["top_p"],
            seed=seed,
        )
        if full_prompt not in cache:
            group_of[full_prompt] = len(group_of)
            cache[full_prompt] = model.capture_activations(full_prompt, model.cfg.probe_layer)
        activations.append(cache[full_prompt])
        groups.append(group_of[full_prompt])
        s = score_response(gen.text, task=task, judge_name=config.CAPABILITY["judge_hf_id_or_provider"])
        scores.append(s["creativity_score"] if s else 5.0)
    X = np.stack(activations, axis=0)
    y = median_split(scores)
    return X, y, np.asarray(groups)


def _row(model: Wrapped, train_object: str, test_object: str, split_type: str,
         accs: List[float], **extra) -> Dict:
    row = {
        "model": model.cfg.name,
        "probe_layer": model.cfg.probe_layer,
        "construct": "divergent_creativity_probe",
        "train_object": train_object,
        "test_object": test_object,
        "split_type": split_type,
        "metric": "accuracy",
        "mean_score": round(float(np.mean(accs)), 4) if accs else None,
        "std_score": round(float(np.std(accs)), 6) if accs else None,
        "n_runs": int(len(accs)),
    }
    row.update(extra)
    return row


def run(model: Wrapped, outdir: Path,
        prompt_variants: Optional[Dict[str, Sequence[str]]] = None) -> Dict:
    """`prompt_variants` maps an object to alternative task wordings for it."""
    out = outdir / "cross_object_llama"
    out.mkdir(parents=True, exist_ok=True)
    # Cross-object seed is model-specific (Llama and Qwen splits differ).
    is_qwen = model.cfg is config.QWEN
    seed_base = (
        config.SEED["cross_object_qwen"] if is_qwen
        else config.SEED["cross_object_llama"]
    )
    # n_runs is derived per object: attempt a fixed seed budget, keep only the
    # seeds that produce a well-posed fit (see config.CROSS_OBJECT).
    max_attempts = config.CROSS_OBJECT["max_seed_attempts"]
    min_train_acc = config.CROSS_OBJECT["min_train_accuracy"]
    task = "divergent_creativity"
    pools: Dict[str, Tuple[np.ndarray, np.ndarray, np.ndarray]] = {}
    for obj in config.CROSS_OBJECT["objects"]:
        pools[obj] = _generate_capability_labeled_pool(
            model, task, obj,
            prompt_variants=(prompt_variants or {}).get(obj))

    rows: List[Dict] = []

    def _both_classes(y: np.ndarray) -> bool:
        return int(np.unique(y).size) >= 2

    for obj in config.CROSS_OBJECT["objects"]:
        Xo, yo, go = pools[obj]
        n = len(yo)
        n_prompts = int(np.unique(go).size)
        ceiling = label_ceiling(yo, go)

        # In-distribution: whole prompts of this object held out of training.
        fold_scores, scheme, used = cv_fold_accuracies(
            Xo, yo, go, C=1.0, n_folds=5, random_state=seed_base)
        rows.append(_row(model, obj, obj, "in_distribution", fold_scores,
                         prompt_held_out=True, n_distinct_prompts=n_prompts,
                         cv_scheme=scheme, n_folds=int(used),
                         label_ceiling=round(float(ceiling), 4)))
        print(f"[cross_object {obj}] in-distribution prompt-held-out "
              f"{np.mean(fold_scores):.3f} ({scheme}, {n_prompts} prompts), "
              f"label ceiling {ceiling:.3f}", flush=True)

        # Cross-object: train on union of other 3 objects, test on `obj`. The
        # train pool and test set are fixed, so we bootstrap-resample the train
        # pool per seed; same sanity filter, same derived n_runs. The test
        # object's prompts never occur in the training pool, so this is
        # prompt-held-out by construction.
        Xs, ys, gs = [], [], []
        for o in config.CROSS_OBJECT["objects"]:
            if o == obj:
                continue
            Xs.append(pools[o][0])
            ys.append(pools[o][1])
            gs.append(pools[o][2])
        Xtr = np.concatenate(Xs, axis=0)
        ytr = np.concatenate(ys, axis=0)
        m = len(ytr)
        accs_cross: List[float] = []
        rng_cross = np.random.RandomState(seed_base + 1)
        for attempt in range(max_attempts):
            boot = rng_cross.randint(0, m, size=m)
            if not _both_classes(ytr[boot]):
                continue
            train_acc, test_acc = fit_and_score(
                Xtr[boot], ytr[boot], Xo, yo, random_state=attempt
            )
            if train_acc < min_train_acc:
                continue
            accs_cross.append(test_acc)
        rows.append(_row(model, "others", obj, "cross_object", accs_cross,
                         prompt_held_out=True,
                         n_distinct_prompts_train=int(sum(np.unique(g).size for g in gs)),
                         n_distinct_prompts_test=n_prompts))

    write_jsonl(rows, out / f"{model.cfg.name.lower().split('-')[0]}_cross_object.jsonl")
    return {"n_rows": len(rows)}
