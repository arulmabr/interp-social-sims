"""fp32 against bf16 on the 70B: how big is numerical error next to an effect?

Amendment item 5(c). The Friday session measured SD ~0.094 in z across batch
compositions on the 70B in bf16, with a largest batched-vs-unbatched gap of 0.5,
and about 1e-5 in fp32. This job asks the question that matters for B3: is the
bf16 error small compared with the *difference between conditions* that an
anchor dose produces, or comparable to it?

Everything is read **unbatched** (amendment item 5a), so batch composition is
not a variable here; what is left is the dtype.

One job, 4 GPUs, about 200 calibration-split prompts spanning the grid, at
baseline and at one dose, in fp32 and then in bf16.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")

import numpy as np
import torch

from cv_bench.tasks import core, risk

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
DEFAULT_OUT = Path("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB/b0_numerics")
COMMON_LAYER = 50          # the common layer of S3.1


def select_prompts(n: int, seed: int = 0) -> List[core.Trial]:
    """About `n` calibration-split trials spanning the grid.

    Stratified by family and then thinned evenly, so the sample spans p, s, the
    reward level and the format rather than clustering in one corner.
    """
    trials = [t for t in core.expand_formats(list(risk.generate_risk()))
              if t.split == "cal"]
    by_family: Dict[str, List[core.Trial]] = {}
    for t in trials:
        by_family.setdefault(t.family, []).append(t)
    per = max(1, n // max(1, len(by_family)))
    out: List[core.Trial] = []
    for family, group in sorted(by_family.items()):
        group = sorted(group, key=lambda t: t.trial_id)
        step = max(1, len(group) // per)
        out.extend(group[::step][:per])
    return sorted(out, key=lambda t: t.trial_id)[:n]


def load(dtype: torch.dtype):
    """Load across the visible GPUs, spilling to CPU only if it will not fit.

    fp32 weights for this model are about 282 GB against 320 GB on four 80 GB
    cards, which leaves under 10 GB a card for activations. `max_memory` caps
    each GPU below its ceiling and offers host memory as the overflow, so a
    tight fit degrades into a slow run rather than an OOM. Whether anything
    actually landed on the CPU is reported, because it would be a deviation.
    """
    from transformers import AutoModelForCausalLM, AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    n = torch.cuda.device_count()
    per_gpu = int(torch.cuda.get_device_properties(0).total_memory / 2**30) - 6
    max_memory = {i: f"{per_gpu}GiB" for i in range(n)}
    max_memory["cpu"] = "400GiB"
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=dtype, device_map="auto",
        max_memory=max_memory, low_cpu_mem_usage=True)
    model.eval()
    devices = sorted({str(p.device) for p in model.parameters()})
    return model, tok, devices


def free(model) -> None:
    del model
    gc.collect()
    torch.cuda.empty_cache()


def score_all(model, tok, trials: Sequence[core.Trial],
              intervention=None, heartbeat: Optional[Path] = None,
              tag: str = "") -> np.ndarray:
    """Unbatched z for every trial (amendment item 5a)."""
    from cv_bench.readout import Readout
    ro = Readout(model, tok)
    out = np.empty(len(trials), dtype=np.float64)
    for i, t in enumerate(trials):
        spec = core.to_trial_spec(t)
        res = ro.score(spec, intervention=intervention)
        out[i] = res.logit_diff
        if heartbeat is not None and i % 20 == 0:
            heartbeat.write_text(json.dumps(
                {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "stage": tag, "done": i + 1, "total": len(trials)}) + "\n")
    return out


def build_dose(model, tok, trials: Sequence[core.Trial], scale: float,
               direction_path: Optional[Path], seed: int):
    """The intervention applied as 'one anchor dose'.

    If `direction_path` is given it is used and labelled as the real anchor.
    Otherwise a reproducible random direction at matched norm stands in, because
    B3.1's gradient anchor does not exist yet. The number this job reports --
    how bf16 error compares with the size of a condition difference -- does not
    depend on which direction moves the model, but the stand-in is labelled in
    the output so it can never be mistaken for an anchor result.
    """
    from cv_bench.steer import Intervention, median_residual_norm

    hidden = int(model.config.hidden_size)
    if direction_path is not None:
        vec = np.load(direction_path).astype(np.float32).reshape(-1)
        kind = f"anchor from {direction_path.name}"
    else:
        rng = np.random.default_rng(seed)
        vec = rng.normal(size=hidden).astype(np.float32)
        kind = "matched-norm random stand-in (B3.1 anchor not yet built)"

    prompts = [core.prompt_text(t) for t in trials[:32]]
    unit = median_residual_norm(model, tok, prompts, COMMON_LAYER)
    iv = Intervention(layer=COMMON_LAYER, vectors=vec, scale=scale,
                      positions="last", mode="add", norm_unit=float(unit))
    return iv, kind, float(unit)


def summarise(a: np.ndarray, b: np.ndarray) -> Dict[str, float]:
    d = np.asarray(a, float) - np.asarray(b, float)
    return {"mean": float(np.mean(d)), "sd": float(np.std(d, ddof=1)),
            "mae": float(np.mean(np.abs(d))), "max_abs": float(np.max(np.abs(d))),
            "rms": float(np.sqrt(np.mean(d ** 2)))}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n-prompts", type=int, default=200)
    ap.add_argument("--scale", type=float, default=0.5,
                    help="dose in units of the median residual norm")
    ap.add_argument("--direction", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    hb = args.out / "heartbeat.json"
    trials = select_prompts(args.n_prompts, args.seed)
    print(f"{len(trials)} calibration-split trials, "
          f"{len({t.family for t in trials})} families, unbatched reads only")

    results: Dict[str, object] = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL_ID, "layer": COMMON_LAYER,
        "n_prompts": len(trials), "scale": args.scale,
        "n_gpus": torch.cuda.device_count(),
        "trial_ids": [t.trial_id for t in trials],
    }

    z: Dict[str, np.ndarray] = {}
    dose_kind = None
    for dtype_name, dtype in (("fp32", torch.float32), ("bf16", torch.bfloat16)):
        print(f"\n--- loading {dtype_name} ---", flush=True)
        t_start = datetime.now(timezone.utc)
        model, tok, devices = load(dtype)
        on_cpu = any(d.startswith("cpu") for d in devices)
        results[f"devices_{dtype_name}"] = devices
        results[f"cpu_offload_{dtype_name}"] = bool(on_cpu)
        print(f"loaded in {(datetime.now(timezone.utc) - t_start).total_seconds():.0f}s; "
              f"devices={devices}"
              + ("  *** CPU OFFLOAD IN USE - record as a deviation ***" if on_cpu else ""),
              flush=True)

        iv, kind, unit = build_dose(model, tok, trials, args.scale, args.direction, args.seed)
        dose_kind = kind
        results[f"norm_unit_{dtype_name}"] = unit

        z[f"{dtype_name}_baseline"] = score_all(model, tok, trials, None, hb,
                                                f"{dtype_name}_baseline")
        z[f"{dtype_name}_dose"] = score_all(model, tok, trials, iv, hb,
                                            f"{dtype_name}_dose")
        np.savez(args.out / f"z_{dtype_name}.npz", **{k: v for k, v in z.items()
                                                      if k.startswith(dtype_name)})
        free(model)

    results["dose_kind"] = dose_kind
    results["error_in_z_baseline"] = summarise(z["bf16_baseline"], z["fp32_baseline"])
    results["error_in_z_dose"] = summarise(z["bf16_dose"], z["fp32_dose"])
    d_fp32 = z["fp32_dose"] - z["fp32_baseline"]
    d_bf16 = z["bf16_dose"] - z["bf16_baseline"]
    results["error_in_condition_difference"] = summarise(d_bf16, d_fp32)
    results["effect_size_fp32"] = {"mean_abs_dz": float(np.mean(np.abs(d_fp32))),
                                   "sd_dz": float(np.std(d_fp32, ddof=1))}
    err = results["error_in_condition_difference"]["rms"]
    eff = results["effect_size_fp32"]["mean_abs_dz"]
    results["error_to_effect_ratio"] = float(err / eff) if eff > 1e-9 else None

    (args.out / "numerics_fp32.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=float) + "\n")
    print("\n" + json.dumps({k: v for k, v in results.items()
                             if k != "trial_ids"}, indent=2, sort_keys=True, default=float))
    return 0


if __name__ == "__main__":
    sys.exit(main())
