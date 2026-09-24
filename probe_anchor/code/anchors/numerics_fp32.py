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

os.environ.setdefault("HF_HOME", "${HF_HOME}")

import numpy as np
import torch

from cv_bench.estimator import checkpoint as CK
from cv_bench.tasks import core, risk

MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
DEFAULT_OUT = Path("${ICLR_RUNROOT}/trackB/b0_numerics")
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


# NOTE: there is deliberately no `free(model)` helper here. Passing the model to
# a function and deleting the parameter there only drops that function's local
# name; the caller still holds the reference and 282 GB stays resident, which is
# exactly how the first run OOMed when bf16 began loading on top of fp32. Each
# dtype now runs in its own process, so the operating system does the freeing.


def score_all(model, tok, trials: Sequence[core.Trial],
              intervention=None, heartbeat: Optional[Path] = None,
              tag: str = "", ckpt: Optional[Path] = None) -> np.ndarray:
    """Unbatched z for every trial (amendment item 5a). Resumable."""
    from cv_bench.readout import Readout
    ro = Readout(model, tok)
    key = CK.items_key([t.trial_id for t in trials],
                       [core.prompt_text(t) for t in trials])
    part = CK.Partial(ckpt, len(trials), chunk=25, n_cols=1, key=key) if ckpt else None
    start = part.n_done if part else 0
    if part and start:
        print(f"  resuming {tag}: {start}/{len(trials)} already done", flush=True)
    out = part.column(0) if part else np.empty(len(trials), dtype=np.float64)
    for i in range(start, len(trials)):
        res = ro.score(core.to_trial_spec(trials[i]), intervention=intervention)
        if part:
            part.append(res.logit_diff)
        else:
            out[i] = res.logit_diff
        if heartbeat is not None and i % 20 == 0:
            CK.heartbeat(heartbeat, stage=tag, done=i + 1, total=len(trials))
    if part:
        part.flush()
        out = part.column(0)
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


def run_dtype(dtype_name: str, args) -> None:
    """Score one dtype and write its z arrays. One process per dtype.

    Skipped outright if this dtype already finished, so a requeue after the
    fp32 stage does not pay 346 seconds to load fp32 again.
    """
    dtype = {"fp32": torch.float32, "bf16": torch.bfloat16}[dtype_name]
    args.out.mkdir(parents=True, exist_ok=True)
    if (args.out / f"z_{dtype_name}.npz").exists() and \
            (args.out / f"meta_{dtype_name}.json").exists():
        print(f"{dtype_name}: already complete, skipping", flush=True)
        return
    hb = args.out / f"heartbeat_{dtype_name}.json"
    trials = select_prompts(args.n_prompts, args.seed)
    print(f"{len(trials)} calibration-split trials, "
          f"{len({t.family for t in trials})} families, unbatched reads only", flush=True)

    t_start = datetime.now(timezone.utc)
    model, tok, devices = load(dtype)
    on_cpu = any(d.startswith("cpu") for d in devices)
    print(f"{dtype_name} loaded in "
          f"{(datetime.now(timezone.utc) - t_start).total_seconds():.0f}s; devices={devices}"
          + ("  *** CPU OFFLOAD IN USE - record as a deviation ***" if on_cpu else ""),
          flush=True)

    iv, kind, unit = build_dose(model, tok, trials, args.scale, args.direction, args.seed)
    z_base = score_all(model, tok, trials, None, hb, f"{dtype_name}_baseline",
                       ckpt=args.out / f"ckpt_{dtype_name}_baseline.npz")
    z_dose = score_all(model, tok, trials, iv, hb, f"{dtype_name}_dose",
                       ckpt=args.out / f"ckpt_{dtype_name}_dose.npz")

    np.savez(args.out / f"z_{dtype_name}.npz", baseline=z_base, dose=z_dose)
    (args.out / f"meta_{dtype_name}.json").write_text(json.dumps({
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "dtype": dtype_name, "devices": devices, "cpu_offload": bool(on_cpu),
        "norm_unit": unit, "dose_kind": kind, "scale": args.scale,
        "n_prompts": len(trials), "n_gpus": torch.cuda.device_count(),
        "trial_ids": [t.trial_id for t in trials],
    }, indent=2, sort_keys=True, default=float) + "\n")
    print(f"wrote z_{dtype_name}.npz", flush=True)


def compare(args) -> int:
    """Combine the two dtypes and report the errors."""
    fp = np.load(args.out / "z_fp32.npz")
    bf = np.load(args.out / "z_bf16.npz")
    meta_fp = json.loads((args.out / "meta_fp32.json").read_text())
    meta_bf = json.loads((args.out / "meta_bf16.json").read_text())
    if meta_fp["trial_ids"] != meta_bf["trial_ids"]:
        raise RuntimeError("the two dtypes scored different prompts; refusing to compare")

    d_fp = fp["dose"] - fp["baseline"]
    d_bf = bf["dose"] - bf["baseline"]
    results: Dict[str, object] = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL_ID, "layer": COMMON_LAYER,
        "n_prompts": meta_fp["n_prompts"], "scale": meta_fp["scale"],
        "dose_kind": meta_fp["dose_kind"],
        "cpu_offload_fp32": meta_fp["cpu_offload"],
        "cpu_offload_bf16": meta_bf["cpu_offload"],
        "n_gpus": meta_fp["n_gpus"],
        "error_in_z_baseline": summarise(bf["baseline"], fp["baseline"]),
        "error_in_z_dose": summarise(bf["dose"], fp["dose"]),
        "error_in_condition_difference": summarise(d_bf, d_fp),
        "effect_size_fp32": {"mean_abs_dz": float(np.mean(np.abs(d_fp))),
                             "sd_dz": float(np.std(d_fp, ddof=1))},
        "z_spread_fp32": {"sd": float(np.std(fp["baseline"], ddof=1)),
                          "min": float(fp["baseline"].min()),
                          "max": float(fp["baseline"].max())},
    }
    err = results["error_in_condition_difference"]["rms"]
    eff = results["effect_size_fp32"]["mean_abs_dz"]
    results["error_to_effect_ratio"] = float(err / eff) if eff > 1e-9 else None
    (args.out / "numerics_fp32.json").write_text(
        json.dumps(results, indent=2, sort_keys=True, default=float) + "\n")
    print(json.dumps(results, indent=2, sort_keys=True, default=float))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True, choices=("fp32", "bf16", "compare"))
    ap.add_argument("--n-prompts", type=int, default=200)
    ap.add_argument("--scale", type=float, default=0.5,
                    help="dose in units of the median residual norm")
    ap.add_argument("--direction", type=Path, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    if args.stage == "compare":
        return compare(args)
    run_dtype(args.stage, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
