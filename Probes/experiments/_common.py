"""Shared helpers for figure runners: JSONL I/O, probe training data, etc."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import numpy as np
from tqdm import tqdm

from .. import config
from ..models import Wrapped
from ..probes import Probe, median_split, train_probe
from ..tasks import preference, prompts, capability as cap_task


# =========================================================================
# JSONL I/O
# =========================================================================
def write_jsonl(rows: Iterable[Dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")


def read_jsonl(path: Path) -> List[Dict]:
    if not path.exists():
        return []
    out = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


# =========================================================================
# Probe training: preference (lottery / ultimatum)
# =========================================================================
def build_preference_probe(
    model: Wrapped,
    game: str,
    n_samples_per_param: int = 8,
    layer_sweep: bool = True,
) -> Probe:
    """Generate labeled trials, capture activations, train probe.

    Labels come from each agent's ACTUAL choice on the trial, not from a
    median split of the stimulus parameter:

      * lottery   -> Risky = 1 (high risk-taking),  Safe   = 0 (low)
      * ultimatum -> Accept = 1 (high acceptance),  Reject = 0 (low)

    Rationale: a risk-seeking agent takes the gamble even when the risky
    reward is small -- i.e. it switches early, at a *low* switching point --
    so its risky choices are the positive ("high risk-taking") class. The
    previous implementation median-split the offered reward and labelled
    above-median (large-reward, risk-averse-requiring) contexts as "high",
    which inverted the trait *and* keyed the probe to reward magnitude rather
    than the agent's disposition. Labelling by the observed choice fixes both.
    """
    if game == "lottery":
        params = config.LOTTERY["reward_grid_tokens"]
        prompt_fn = prompts.lottery_prompt
        parse_fn = prompts.parse_lottery_choice
    else:
        params = config.ULTIMATUM["offer_grid_tokens"]
        prompt_fn = prompts.ultimatum_prompt
        parse_fn = prompts.parse_ultimatum_choice

    # Layer candidates to sweep.
    if layer_sweep:
        lo, hi = model.cfg.layer_sweep_range
        candidate_layers = list(range(lo, hi + 1, 2))
    else:
        candidate_layers = [model.cfg.probe_layer]

    # Seed base kept distinct from the evaluation sweeps so probe-training
    # trials never coincide with the calibration / psychometric trials.
    seed_base = config.SEED.get("probe_data", 100_000)

    # For every (param, sample): let the agent make its choice, then label the
    # captured activations by that choice. Unparseable generations are skipped.
    activations: Dict[int, List[np.ndarray]] = {layer: [] for layer in candidate_layers}
    labels: List[int] = []

    for param_idx, p in enumerate(tqdm(params, desc=f"Probe data ({game})")):
        prompt = prompt_fn(p)
        for sample in range(n_samples_per_param):
            gen = model.generate(
                prompt,
                max_new_tokens=config.DECODING_DEFAULTS["max_new_tokens_choice"],
                temperature=config.DECODING_DEFAULTS["temperature_choice"],
                top_p=config.DECODING_DEFAULTS["top_p"],
                seed=config.agent_seed(seed_base, param_idx, sample + 1),
            )
            choice = parse_fn(gen.text)
            if choice is None:
                continue  # unparseable -> no ground-truth label, drop the trial
            for layer in candidate_layers:
                h = model.capture_activations(prompt, layer)
                activations[layer].append(h)
            labels.append(int(choice))

    y = np.asarray(labels, dtype=int)
    if y.size == 0 or np.unique(y).size < 2:
        raise ValueError(
            f"Preference probe ({game}) needs both choice classes present; got "
            f"labels={np.unique(y).tolist()} from {y.size} parseable trials. "
            "Increase n_samples_per_param or widen the reward/offer grid."
        )
    acts_by_layer = {layer: np.stack(activations[layer], axis=0) for layer in candidate_layers}
    return train_probe(
        activations_by_layer=acts_by_layer,
        labels=y,
        candidate_layers=candidate_layers,
        random_state=0,
    )


# =========================================================================
# Probe training: capability
# =========================================================================
def build_capability_probe(
    model: Wrapped,
    task: str,
    obj: str,
    n_samples_baseline: int = 80,
    n_samples_persona: int = 80,
    judge_score_fn=None,
    layer_sweep: bool = True,
) -> Probe:
    """Generate creative outputs at two persona settings, score with judge,
    median-split on score, train probe on the captured activations.

    `judge_score_fn(text, task) -> creativity_score in [1,10]` is required.
    """
    if judge_score_fn is None:
        from ..judge import score_response
        def judge_score_fn(text, task=task):
            res = score_response(text, task=task)
            return res["creativity_score"] if res else 5.0

    prompt_text, _ = prompts.get_capability_prompt(task, obj)

    if layer_sweep:
        lo, hi = model.cfg.layer_sweep_range
        candidate_layers = list(range(lo, hi + 1, 2))
    else:
        candidate_layers = [model.cfg.probe_layer]

    activations: Dict[int, List[np.ndarray]] = {layer: [] for layer in candidate_layers}
    scores: List[float] = []

    # Baseline samples
    for i in tqdm(range(n_samples_baseline), desc=f"Baseline ({task}, {obj})"):
        seed = config.agent_seed(0, 0, i + 1)
        gen = model.generate(
            prompt_text,
            max_new_tokens=config.DECODING_DEFAULTS["max_new_tokens_capability"],
            temperature=config.DECODING_DEFAULTS["temperature_capability"],
            top_p=config.DECODING_DEFAULTS["top_p"],
            seed=seed,
        )
        for layer in candidate_layers:
            h = model.capture_activations(prompt_text, layer)
            activations[layer].append(h)
        scores.append(float(judge_score_fn(gen.text)))

    # High-creativity persona samples
    persona_prefix = (
        "You are a highly creative and unconventional thinker. "
        "Think outside the box. Be imaginative. "
    )
    for i in tqdm(range(n_samples_persona), desc=f"Persona ({task}, {obj})"):
        seed = config.agent_seed(0, 1, i + 1)
        gen = model.generate(
            persona_prefix + prompt_text,
            max_new_tokens=config.DECODING_DEFAULTS["max_new_tokens_capability"],
            temperature=config.DECODING_DEFAULTS["temperature_capability"],
            top_p=config.DECODING_DEFAULTS["top_p"],
            seed=seed,
        )
        for layer in candidate_layers:
            h = model.capture_activations(persona_prefix + prompt_text, layer)
            activations[layer].append(h)
        scores.append(float(judge_score_fn(gen.text)))

    y = median_split(scores)
    acts_by_layer = {layer: np.stack(activations[layer], axis=0) for layer in candidate_layers}
    return train_probe(
        activations_by_layer=acts_by_layer,
        labels=y,
        candidate_layers=candidate_layers,
        random_state=0,
    )


# =========================================================================
# Evaluators that the lambda solver calls
# =========================================================================
def make_lottery_switching_point_evaluator(
    model: Wrapped, probe: Probe, n_agents_eval: int = 12,
    rewards=None, seed_base=None,
):
    """Returns a function: lambda -> achieved switching point.

    Uses a smaller agent count during calibration to save compute. `rewards`
    and `seed_base` default to the Llama grid/seed; pass the Qwen grid + seed
    when calibrating Qwen so the sweep matches that model's figure grid.
    """
    from ..calibration import switching_point_from_rows
    if rewards is None:
        rewards = config.LOTTERY["reward_grid_tokens"]
    if seed_base is None:
        seed_base = config.SEED["psychometric_llama"]

    def eval_at(lam: float) -> float:
        rows = preference.sweep_lottery(
            model=model, rewards=rewards, n_agents=n_agents_eval,
            seed_base=seed_base, probe=probe, lambda_value=lam,
        )
        return switching_point_from_rows(rows, "risky_reward_tokens", "parsed_choice", 0.5)

    return eval_at


def make_ultimatum_threshold_evaluator(
    model: Wrapped, probe: Probe, n_agents_eval: int = 12,
    offers=None, seed_base=None,
):
    from ..calibration import switching_point_from_rows
    if offers is None:
        offers = config.ULTIMATUM["offer_grid_tokens"]
    if seed_base is None:
        seed_base = config.SEED["psychometric_llama"]

    def eval_at(lam: float) -> float:
        rows = preference.sweep_ultimatum(
            model=model, offers=offers, n_agents=n_agents_eval,
            seed_base=seed_base, probe=probe, lambda_value=lam,
        )
        return switching_point_from_rows(rows, "offer_amount_tokens", "parsed_choice", 0.5)

    return eval_at


def make_creativity_evaluator(
    model: Wrapped, probe: Probe, task: str, obj: str, judge_score_fn, n_agents_eval: int = 8,
):
    """lambda -> achieved mean creativity score across n_agents."""

    def eval_at(lam: float) -> float:
        scores = []
        for i in range(1, n_agents_eval + 1):
            seed = config.agent_seed(0, int(lam * 100), i)
            row = cap_task.run_capability_trial(
                model, task=task, obj=obj, agent_id=i, seed=seed,
                probe=probe, lambda_value=lam,
            )
            s = judge_score_fn(row["response"])
            scores.append(s)
        return float(np.mean(scores))

    return eval_at
