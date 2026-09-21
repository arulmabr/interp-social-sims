"""B2-cal: calibrate the synthetic agents against the real model.

Author item 1, 22 Sept. The B2 agents were scaled without a model, so the power
numbers the recovery study reported are numbers about an assumed choice
function, not about this one. If the real z is as steep as the Friday session's
diagnostics suggest -- around -9.7 at one prompt, crossing near n = 242 -- then
an alpha shift of 0.10 is worth tenths of a logit near indifference rather than
the 0.011 the uncalibrated agents gave, and the whole power picture changes.

This job reads the unmodified model and returns the four things the recovery
study needs to be rerun at the real scale:

  1. theta0 and the temperature, fitted to the observed z;
  2. the template-level noise, as the spread of template intercepts;
  3. the numerical noise floor, measured **in this run** -- D50 found it was
     0.094 in one 70B run and 0.000 in another from identical code, so it is not
     a property of the model and may not be quoted from a different allocation;
  4. whether the slope of z against log x is constant across sure amounts, which
     is what the contextual-utility normalisation assumes.

Legacy labels only (author item 7): the Friday session found the unsteered
readout ignores the payoff under neutral A/B labels, so the neutral half waits
for that work to land. The stem is `Answer:`, which D47 measured at valid mass
1.0000 on both games with the legacy labels.

The report also carries the readout-versus-free-generation comparison item 7
asks for.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")

import numpy as np
import torch

from cv_bench.estimator import checkpoint as CK
from cv_bench.tasks import core, risk

MODELS = {"llama70b": "meta-llama/Llama-3.3-70B-Instruct",
          "llama8b": "meta-llama/Llama-3.1-8B-Instruct"}
DEFAULT_OUT = Path("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB/b2_cal")
STEM = "Answer:"


def calibration_trials(max_content: Optional[int] = None) -> List[core.Trial]:
    """Calibration-split risk trials, legacy labels, multiple choice.

    Both option orders and both calibration templates are kept: the template
    intercepts and the order term are two of the quantities being measured.
    """
    content = [t for t in risk.generate_risk(splits=("cal",))]
    if max_content:
        content = sorted(content, key=lambda t: t.content_id)[:max_content]
    out = [t for t in core.expand_formats(content, response_formats=("mc",),
                                          label_sets=("legacy",))]
    return sorted(out, key=lambda t: t.trial_id)


def load(model_key: str):
    from transformers import AutoModelForCausalLM, AutoTokenizer
    mid = MODELS[model_key]
    tok = AutoTokenizer.from_pretrained(mid)
    model = AutoModelForCausalLM.from_pretrained(
        mid, torch_dtype=torch.bfloat16, device_map="auto", low_cpu_mem_usage=True)
    model.eval()
    return model, tok


def read_z(ro, trials: Sequence[core.Trial], heartbeat: Optional[Path] = None,
           tag: str = "", ckpt: Optional[Path] = None) -> Tuple[np.ndarray, np.ndarray]:
    """Unbatched z and valid mass for each trial (amendment item 5a).

    Resumable: with `ckpt` the loop starts at the first item not already on
    disk, so a preemption on `ou_bcs_low` costs at most one chunk of reads
    rather than the whole pass.
    """
    key = CK.items_key([t.trial_id for t in trials])
    part = CK.Partial(ckpt, len(trials), chunk=50, n_cols=2, key=key)
    if part.n_done:
        print(f"  resuming {tag}: {part.n_done}/{len(trials)} already done", flush=True)
    for i in range(part.n_done, len(trials)):
        res = ro.score(core.to_trial_spec(trials[i], stem=STEM))
        part.append([res.logit_diff, res.valid_mass])
        if heartbeat is not None and i % 50 == 0:
            CK.heartbeat(heartbeat, stage=tag, done=i + 1, total=len(trials))
    part.flush()
    z, mass = part.columns()
    return z, mass


def numerical_noise(ro, trials: Sequence[core.Trial], repeats: int,
                    out: Optional[Path] = None) -> Dict[str, float]:
    """Re-read the same prompts and report the spread, measured in this run.

    Identical input, identical code: anything that moves is numerical. D50 found
    this floor is not stable across allocations, so it is measured here rather
    than quoted.
    """
    reads = np.stack([
        read_z(ro, trials, tag=f"noise{r}",
               ckpt=(out / f"ckpt_noise_{r}.npz") if out else None)[0]
        for r in range(repeats)])
    per_prompt_sd = reads.std(axis=0, ddof=1) if repeats > 1 else np.zeros(len(trials))
    return {"repeats": repeats, "n_prompts": len(trials),
            "sd_mean": float(np.mean(per_prompt_sd)),
            "sd_max": float(np.max(per_prompt_sd)),
            "max_abs_range": float(np.max(reads.max(axis=0) - reads.min(axis=0))),
            "all_identical": bool(np.all(reads.max(axis=0) == reads.min(axis=0)))}


def slope_against_log_x(trials: Sequence[core.Trial], z: np.ndarray) -> Dict[str, object]:
    """Is dz/dlog(x) the same at every sure amount?

    Contextual utility assumes the choice function has one shape that the stake
    only rescales. If the slope moves with s, that assumption is wrong on this
    model and the normalisation is doing something other than what it is for.
    """
    by_s: Dict[float, List[Tuple[float, float]]] = defaultdict(list)
    for t, zi in zip(trials, z):
        if t.family != "sure_gain":
            continue
        p = t.param_dict
        if p["x"] > 0 and p["s"] > 0 and np.isfinite(zi):
            by_s[p["s"]].append((float(np.log(p["x"] / p["s"])), float(zi)))
    slopes: Dict[str, float] = {}
    for s, pts in sorted(by_s.items()):
        if len(pts) < 4:
            continue
        xs = np.array([a for a, _ in pts]); ys = np.array([b for _, b in pts])
        if xs.std() < 1e-9:
            continue
        slopes[f"s{int(s)}"] = float(np.polyfit(xs, ys, 1)[0])
    vals = np.array(list(slopes.values()))
    return {"slopes": slopes,
            "mean": float(vals.mean()) if len(vals) else float("nan"),
            "sd": float(vals.std(ddof=1)) if len(vals) > 1 else float("nan"),
            "cv": float(vals.std(ddof=1) / abs(vals.mean()))
            if len(vals) > 1 and abs(vals.mean()) > 1e-9 else float("nan"),
            "constant_across_stakes": bool(
                len(vals) > 1 and float(vals.std(ddof=1) / abs(vals.mean())) < 0.25)
            if len(vals) > 1 and abs(vals.mean()) > 1e-9 else False}


CHOICE_RE = re.compile(r"\b(safe|risky)\b", re.I)


def free_generation(model, tok, ro, trials: Sequence[core.Trial],
                    max_new_tokens: int = 24) -> Dict[str, object]:
    """Does the forced-answer readout agree with what the model actually says?

    Author item 7. Greedy decoding, first stated option wins, and an output that
    states neither is counted rather than dropped.
    """
    agree = 0; n = 0; no_answer = 0
    rows: List[Dict[str, object]] = []
    for t in trials:
        spec = core.to_trial_spec(t, stem=None)          # no stem: let it talk
        text = ro.render(spec)
        enc = tok(text, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            out = model.generate(**enc, max_new_tokens=max_new_tokens,
                                 do_sample=False,
                                 pad_token_id=tok.eos_token_id)
        gen = tok.decode(out[0, enc["input_ids"].shape[1]:], skip_special_tokens=True)
        m = CHOICE_RE.search(gen)
        said = m.group(1).lower() if m else None
        readout = ro.score(core.to_trial_spec(t, stem=STEM))
        read_risky = readout.logit_diff > 0
        if said is None:
            no_answer += 1
        else:
            n += 1
            agree += int((said == "risky") == read_risky)
        rows.append({"trial_id": t.trial_id, "generated": gen.strip()[:120],
                     "parsed": said, "readout_logit_diff": float(readout.logit_diff)})
    return {"n_compared": n, "n_no_answer": no_answer, "n_total": len(trials),
            "agreement": float(agree / n) if n else float("nan"),
            "examples": rows[:20]}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b", choices=list(MODELS))
    ap.add_argument("--max-content", type=int, default=None)
    ap.add_argument("--noise-prompts", type=int, default=40)
    ap.add_argument("--noise-repeats", type=int, default=5)
    ap.add_argument("--gen-prompts", type=int, default=100)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    hb = args.out / "heartbeat.json"
    trials = calibration_trials(args.max_content)
    print(f"{len(trials)} calibration rows (legacy labels, multiple choice, "
          f"stem {STEM!r}), unbatched", flush=True)

    t0 = datetime.now(timezone.utc)
    model, tok = load(args.model)
    from cv_bench.readout import Readout
    ro = Readout(model, tok)
    print(f"loaded in {(datetime.now(timezone.utc) - t0).total_seconds():.0f}s", flush=True)

    z, mass = read_z(ro, trials, hb, "baseline", ckpt=args.out / "ckpt_baseline.npz")
    np.savez(args.out / "z_baseline.npz", z=z, mass=mass,
             trial_ids=np.array([t.trial_id for t in trials]))
    print(f"baseline read: z mean {z.mean():.3f} sd {z.std():.3f} "
          f"min {z.min():.3f} max {z.max():.3f}; valid mass mean {mass.mean():.4f}",
          flush=True)

    noise = numerical_noise(ro, trials[:args.noise_prompts], args.noise_repeats,
                            out=args.out)
    print(f"numerical noise this run: sd_mean {noise['sd_mean']:.5f} "
          f"sd_max {noise['sd_max']:.5f}", flush=True)

    gen_path = args.out / "free_generation.json"
    if gen_path.exists():
        gen = json.loads(gen_path.read_text())
        print("  resuming: free-generation comparison already on disk", flush=True)
    else:
        gen = free_generation(model, tok, ro, trials[:args.gen_prompts])
        gen_path.write_text(json.dumps(gen, indent=2, sort_keys=True, default=float) + "\n")
    print(f"readout vs free generation: agreement {gen['agreement']}, "
          f"no answer {gen['n_no_answer']}/{gen['n_total']}", flush=True)

    # -- fit theta0 and the temperature at the real scale ------------------
    from cv_bench.estimator import agents as A, fit as FIT
    ok = np.isfinite(z) & (mass > 0.5)
    fit_trials = [t for t, k in zip(trials, ok) if k]
    sigma = max(noise["sd_mean"], 1e-3)
    par, _, ll = FIT.fit(fit_trials, z[ok], ("alpha", "gamma", "tau"),
                         A.AgentParams(), free_templates=True,
                         observe="logit", sigma=sigma, seed=0, restarts=5)
    tpl = dict(FIT.fit.last_template_offsets)
    tpl_vals = np.array(list(tpl.values()))

    results = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODELS[args.model], "stem": STEM,
        "label_set": "legacy", "response_format": "mc", "split": "cal",
        "n_rows": len(trials), "n_used": int(ok.sum()),
        "unbatched": True,
        "z_observed": {"mean": float(z.mean()), "sd": float(z.std(ddof=1)),
                       "min": float(z.min()), "max": float(z.max())},
        "valid_mass": {"mean": float(mass.mean()), "min": float(mass.min())},
        "fitted": {"alpha": float(par.alpha), "gamma": float(par.gamma),
                   "tau": float(par.tau), "loglik": float(ll)},
        "template_offsets": tpl,
        "template_noise_sd": float(tpl_vals.std(ddof=1)) if len(tpl_vals) > 1 else 0.0,
        "numerical_noise": noise,
        "slope_vs_log_x": slope_against_log_x(trials, z),
        "readout_vs_free_generation": gen,
    }
    (args.out / "b2_cal.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=float) + "\n")
    print("\n" + json.dumps({k: v for k, v in results.items()
                             if k != "readout_vs_free_generation"},
                            indent=2, sort_keys=True, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
