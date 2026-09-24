"""B3.1 gradient anchor (ICLR_PLAN.md B3.1). Author item 6.

The gradient of z with respect to the residual stream at the intervention
layer, at the final prompt token, averaged over calibration-split core prompts.

The gradient is taken with respect to **the output of `model.model.layers[L]`**,
because that is exactly the tensor `steer.SteeringHook` adds to. A gradient
taken anywhere else would not be the direction that a dose actually moves, and
the anchor would be measuring something the intervention cannot do.

Three versions are saved, per the plan's "within one format, and averaged over
option orders and label sets":
  legacy_one_format   one template, one option order, legacy labels
  legacy_both_orders  averaged over both option orders, legacy labels
  all_formats         averaged over orders and label sets

`all_formats` is computed but flagged: the Friday session found the unsteered
readout ignores the payoff under neutral A/B labels, so until that work lands
the neutral half of this average is of unknown quality. Prefer the legacy
versions until then (author item 7).

No anchor is scored with the decision rule until Gate B2 passes (author item 6).
This job only computes and saves directions.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

os.environ.setdefault("HF_HOME", "${HF_HOME}")

import hashlib

import numpy as np
import torch

from cv_bench.estimator import checkpoint as CK
from cv_bench.tasks import core, risk

MODELS = {"llama70b": "meta-llama/Llama-3.3-70B-Instruct",
          "llama8b": "meta-llama/Llama-3.1-8B-Instruct"}
DEFAULT_OUT = Path("${ICLR_RUNROOT}/trackB/b3_gradient")
LAYERS = (48, 50)
STEM = "Answer:"


def core_trials(label_sets: Sequence[str], orders: Sequence[int],
                templates: Optional[Sequence[str]] = None,
                max_content: Optional[int] = None,
                domain: str = "risk") -> List[core.Trial]:
    """Calibration-split core-frame trials in the requested formats.

    Core is sure-gain at p in {0.25, 0.5, 0.75}; the plan averages the anchor
    over calibration-split core prompts. For the social domain the counterpart
    is the ultimatum responder on the calibration split, with the catch trials
    left out for the same reason dominated gambles are (B7).
    """
    if domain == "social":
        from cv_bench.tasks import social
        # The responder's calibration split alone gives 12 usable prompts once
        # the catch trials are dropped, too few to average a direction over.
        # Discovery is added, which is not used by the cloning check, so no set
        # that any later number depends on is touched. Test stays locked.
        content = [t for t in social.generate_responder(splits=("disc", "cal"))
                   if not t.is_catch]
    else:
        content = [t for t in risk.generate_risk(splits=("cal",), include_catch=False)
                   if t.frame_role == "core"]
    if max_content:
        content = sorted(content, key=lambda t: t.content_id)[:max_content]
    out = [t for t in core.expand_formats(content, response_formats=("mc",),
                                          label_sets=tuple(label_sets))
           if t.fmt.option_order in orders
           and (templates is None or t.fmt.template_id in templates)]
    return sorted(out, key=lambda t: t.trial_id)


def load(model_key: str):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mid = MODELS[model_key]
    tok = AutoTokenizer.from_pretrained(mid)
    model = AutoModelForCausalLM.from_pretrained(
        mid, torch_dtype=torch.bfloat16, device_map="auto", low_cpu_mem_usage=True)
    model.eval()
    # Only the residual stream needs a gradient. Leaving the parameters
    # requiring grad would allocate a gradient buffer the size of the model.
    for p in model.parameters():
        p.requires_grad_(False)
    # But with every parameter frozen nothing downstream requires grad either,
    # so the autograd graph is never built and retain_grad raises. Making the
    # input embeddings' output require grad rebuilds the graph through the
    # layers without allocating a single parameter gradient.
    model.enable_input_require_grads()
    return model, tok


def assert_labels_distinguishable(ro, trial) -> None:
    """The two labels must differ at the token the readout actually scores.

    If their first-token id sets overlap, z is a difference of two identical
    log-probabilities and is identically zero, so every gradient is zero and
    every reading is uninformative -- silently. This turns that into an error.
    """
    spec = core.to_trial_spec(trial, stem=core.stem_for(trial))
    neg = set(ro.label_token_ids(spec.negative))
    pos = set(ro.label_token_ids(spec.positive))
    if not neg or not pos or (neg & pos):
        raise ValueError(
            f"labels {spec.negative!r} and {spec.positive!r} share first-token ids "
            f"{sorted(neg & pos)} under stem {core.stem_for(trial)!r}: z would be "
            "identically zero. Choose a stem that moves the scored position onto "
            "the part of the label that differs (cv_bench.tasks.core.STEM_BY_LABEL_SET)."
        )


def z_gradient(model, tok, ro, trial: core.Trial, layer: int) -> Optional[np.ndarray]:
    """d z / d (residual stream at `layer`, final prompt token).

    z is the readout's logit difference, built the same way `readout._from_logits`
    builds it, so the direction is the gradient of the quantity actually reported.
    """
    assert_labels_distinguishable(ro, trial)
    spec = core.to_trial_spec(trial, stem=core.stem_for(trial))
    text = ro.render(spec)
    enc = tok(text, return_tensors="pt").to(model.device)

    captured: Dict[str, torch.Tensor] = {}

    def hook(_module, _inp, output):
        hs = output[0] if isinstance(output, tuple) else output
        hs.retain_grad()
        captured["hs"] = hs
        return output

    handle = model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.enable_grad():
            out = model(**enc, use_cache=False)
            logits = out.logits[0, -1, :].float()
            logprobs = torch.log_softmax(logits, dim=-1)
            probs = logprobs.exp()
            ids_pos = ro.label_token_ids(spec.positive)
            ids_neg = ro.label_token_ids(spec.negative)
            if not ids_pos or not ids_neg:
                return None
            eps = 1e-30
            p_pos = probs[ids_pos].sum()
            p_neg = probs[ids_neg].sum()
            z = torch.log(p_pos + eps) - torch.log(p_neg + eps)
            model.zero_grad(set_to_none=True)
            z.backward()
        hs = captured.get("hs")
        if hs is None or hs.grad is None:
            return None
        return hs.grad[0, -1, :].detach().float().cpu().numpy()
    finally:
        handle.remove()


def average_gradient(model, tok, ro, trials: Sequence[core.Trial], layer: int,
                     heartbeat: Optional[Path] = None,
                     tag: str = "", ckpt: Optional[Path] = None) -> Dict[str, object]:
    """Mean gradient over `trials`, resumable at chunk granularity.

    The running sum and the count are checkpointed rather than every individual
    gradient: one 8192-float vector per chunk instead of one per prompt, and the
    mean is the only thing the anchor needs.
    """
    hidden = int(model.config.hidden_size)
    key = CK.items_key([t.trial_id for t in trials],
                       [core.prompt_text(t) for t in trials])
    part = CK.Partial(ckpt, len(trials), chunk=20, n_cols=hidden + 2, key=key) \
        if ckpt else None
    start = part.n_done if part else 0
    if part and start:
        print(f"  resuming {tag}: {start}/{len(trials)} already done", flush=True)

    acc = np.zeros(hidden); n = 0; norms: List[float] = []
    if part and start:
        rows = part.data[:start]
        used = rows[:, hidden + 1] > 0
        acc = rows[used, :hidden].sum(axis=0)
        norms = list(rows[used, hidden])
        n = int(used.sum())

    for i in range(start, len(trials)):
        g = z_gradient(model, tok, ro, trials[i], layer)
        ok = g is not None and np.all(np.isfinite(g))
        if ok:
            acc = acc + g
            norms.append(float(np.linalg.norm(g)))
            n += 1
        if part:
            row = np.zeros(hidden + 2)
            if ok:
                row[:hidden] = g
                row[hidden] = float(np.linalg.norm(g))
                row[hidden + 1] = 1.0
            part.append(row)
        if heartbeat is not None and i % 20 == 0:
            CK.heartbeat(heartbeat, stage=tag, done=i + 1, total=len(trials))
    if part:
        part.flush()
    if n == 0:
        return {"n": 0, "vector": None}
    mean = acc / n
    return {"n": n, "vector": mean,
            "norm_of_mean": float(np.linalg.norm(mean)),
            "mean_of_norms": float(np.mean(norms)),
            "coherence": float(np.linalg.norm(mean) / np.mean(norms))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b", choices=list(MODELS))
    ap.add_argument("--layers", type=int, nargs="+", default=list(LAYERS))
    ap.add_argument("--max-content", type=int, default=None)
    ap.add_argument("--domain", default="risk", choices=("risk", "social"),
                    help="social builds the anchor on ultimatum responder prompts (B7)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    hb = args.out / "heartbeat.json"

    # Author item 4: the two option orders are computed separately so their sum
    # and difference are available. g1 + g2 is the order-invariant anchor Track B
    # uses; g1 - g2 is a position-bias direction by construction and joins the
    # controls; legacy_one_format is what the Friday session loads for G4b.
    labels = ("accept_reject",) if args.domain == "social" else ("legacy",)
    versions = {
        "legacy_order0": core_trials(labels, (0,), None, args.max_content, args.domain),
        "legacy_order1": core_trials(labels, (1,), None, args.max_content, args.domain),
        "legacy_one_format": core_trials(labels, (0,), ("t_cal_0",),
                                         args.max_content, args.domain),
    }
    versions = {k: v for k, v in versions.items() if v}
    for k, v in versions.items():
        print(f"{k}: {len(v)} prompts", flush=True)

    t0 = datetime.now(timezone.utc)
    model, tok = load(args.model)
    from cv_bench.readout import Readout
    ro = Readout(model, tok)
    print(f"loaded in {(datetime.now(timezone.utc) - t0).total_seconds():.0f}s", flush=True)

    summary: Dict[str, object] = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODELS[args.model], "stem": STEM, "position": "last",
        "gradient_wrt": "output of model.model.layers[L], the tensor SteeringHook adds to",
        "split": "cal", "frame_role": "core", "domain": args.domain,
        "all_formats_caveat": ("includes neutral A/B labels, where the Friday session "
                               "found the unsteered readout ignores the payoff; prefer "
                               "the legacy versions until that work lands"),
        "versions": {},
    }

    for layer in args.layers:
        for name, trials in versions.items():
            key = f"L{layer}_{name}"
            vec_path = args.out / f"grad_{key}.npy"
            meta_path = args.out / f"grad_{key}.meta.json"
            # Skip only if the saved vector was computed on THESE prompts.
            # Checking file existence alone is what let a rerun on corrected
            # prompts return the previous run's vectors in 32 seconds (BD33's
            # bug, recurring here): the words changed, the filenames did not.
            want_key = CK.items_key([t.trial_id for t in trials],
                                    [core.prompt_text(t) for t in trials])
            if vec_path.exists() and meta_path.exists():
                prev = json.loads(meta_path.read_text())
                if prev.get("items_key") == want_key:
                    summary["versions"][key] = prev
                    print(f"{key}: already on disk for these prompts, skipping",
                          flush=True)
                    continue
                print(f"{key}: on disk but for different prompts, recomputing",
                      flush=True)
            res = average_gradient(model, tok, ro, trials, layer, hb,
                                   f"L{layer}:{name}",
                                   ckpt=args.out / f"ckpt_{key}.npz")
            if res["n"] == 0:
                summary["versions"][key] = {"n": 0, "error": "no usable gradients"}
                print(f"{key}: NO USABLE GRADIENTS", flush=True)
                continue
            vec = res.pop("vector")
            np.save(vec_path, vec)
            # A hash so another session can verify it loaded the same direction
            # rather than a stale or partly written copy.
            res["sha256"] = hashlib.sha256(vec_path.read_bytes()).hexdigest()
            res["shape"] = list(np.asarray(vec).shape)
            res["dtype"] = str(np.asarray(vec).dtype)
            res["file"] = vec_path.name
            res["items_key"] = want_key
            meta_path.write_text(json.dumps(res, indent=2, sort_keys=True,
                                            default=float) + "\n")
            summary["versions"][key] = res
            print(f"{key}: n={res['n']} |mean|={res['norm_of_mean']:.4f} "
                  f"mean|g|={res['mean_of_norms']:.4f} coherence={res['coherence']:.3f}",
                  flush=True)

    # Derived directions, per layer: the order-invariant sum and the
    # position-bias difference. Both come free from g1 and g2.
    for layer in args.layers:
        p1 = args.out / f"grad_L{layer}_legacy_order0.npy"
        p2 = args.out / f"grad_L{layer}_legacy_order1.npy"
        if not (p1.exists() and p2.exists()):
            continue
        g1, g2 = np.load(p1), np.load(p2)
        cos12 = float(g1 @ g2 / (np.linalg.norm(g1) * np.linalg.norm(g2)))
        summary["versions"][f"L{layer}_cos_g1_g2"] = cos12
        print(f"L{layer}: cos(g1, g2) = {cos12:+.4f}", flush=True)
        for name, vec, what in (
                ("legacy_sum", g1 + g2, "order-invariant anchor (g1 + g2)"),
                ("legacy_diff", g1 - g2, "position-bias direction (g1 - g2), a control")):
            vp = args.out / f"grad_L{layer}_{name}.npy"
            np.save(vp, vec)
            summary["versions"][f"L{layer}_{name}"] = {
                "derived_from": [p1.name, p2.name], "role": what,
                "norm": float(np.linalg.norm(vec)),
                "sha256": hashlib.sha256(vp.read_bytes()).hexdigest(),
                "shape": list(vec.shape), "dtype": str(vec.dtype), "file": vp.name,
            }

    # cosine matrix across everything saved
    saved = sorted(p for p in args.out.glob("grad_*.npy"))
    if len(saved) > 1:
        names = [p.stem.replace("grad_", "") for p in saved]
        vecs = [np.load(p) for p in saved]
        cos = {}
        for i, a in enumerate(names):
            for j, b in enumerate(names):
                if i < j:
                    u, v = vecs[i], vecs[j]
                    cos[f"{a}|{b}"] = float(u @ v / (np.linalg.norm(u) * np.linalg.norm(v)))
        summary["cosines"] = cos

    # A loading contract for the Friday session (author item 3): G4b should load
    # this direction rather than build a second one, so what it is and how to
    # apply it has to travel with the file.
    summary["how_to_load"] = {
        "numpy": ("vec = np.load('grad_L50_legacy_sum.npy')       # Track B's anchor\n"
                  "vec = np.load('grad_L50_legacy_one_format.npy')  # what G4b loads"),
        "apply": ("cv_bench.steer.Intervention(layer=L, vectors=vec, scale=s, "
                  "positions='last', mode='add', norm_unit=median_residual_norm(...))"),
        "note": ("the vector is the gradient of z with respect to the OUTPUT of "
                 "model.model.layers[L], which is the tensor SteeringHook adds to; "
                 "Intervention normalises it, so only its direction is used"),
        "prefer": "the legacy_* versions until the neutral-label readout work lands",
        "roles": {
            "legacy_sum": "order-invariant anchor; what Track B uses as the B3.1 anchor",
            "legacy_diff": "position-bias direction by construction; a control, not an anchor",
            "legacy_one_format": "what the Friday session loads for G4b",
            "legacy_order0/1": "the per-order gradients g1 and g2 the others derive from",
        },
        "verify": "sha256 of each .npy is in versions[<key>]['sha256']",
    }
    (args.out / "b3_gradient.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, default=float) + "\n")
    print("\n" + json.dumps(summary, indent=2, sort_keys=True, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
