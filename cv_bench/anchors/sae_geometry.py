"""Place the SAE steering directions against the decomposed readout anchor (B8).

The pilot measures each SAE vector's cosine against one undecomposed readout
gradient and finds values of 0.068 to 0.073. Track B splits that gradient into
the part common to both option orders, which is about the answer, and the part
that flips with the order, which on a letter-answer format is about which letter
is emitted. Asking which of those two an SAE vector aligns with is a sharper
question than asking how close it is to their sum.

Pure geometry on CPU. The SAE checkpoint is the pinned public file; no Goodfire
service is contacted and no model is run.

    python -m cv_bench.anchors.sae_geometry --grad-dir <dir> --pilot <dir>
"""
from __future__ import annotations

import argparse
import csv
import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np

SAE_REPO = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"
SAE_FILE = "Llama-3.3-70B-Instruct-SAE-l50.pt"
SAE_REVISION = "128ee921ecd1b8b3a87d776cbcc357c0855da134"
#: The features the paper names for each game (Appendix A.1.3 and A.2.3).
PAPER_FEATURES = {"lottery_184": [(184, 1.0)], "lottery_4237": [(4237, 1.0)],
                  "ultimatum_31935": [(31935, 1.0)]}


def decoder() -> np.ndarray:
    import torch
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(SAE_REPO, SAE_FILE, revision=SAE_REVISION)
    st = torch.load(p, map_location="cpu", weights_only=True)
    D = st["decoder_linear.weight"].float().numpy()   # (d_model, n_features)
    assert D.shape[0] == 8192, D.shape
    return D


def build(D: np.ndarray, combo: List[tuple]) -> np.ndarray:
    v = np.zeros(D.shape[0], dtype=np.float64)
    for idx, coeff in combo:
        v += float(coeff) * D[:, int(idx)]
    return v


def cos(a: np.ndarray, b: np.ndarray) -> float:
    n = np.linalg.norm(a) * np.linalg.norm(b)
    return float(a @ b / n) if n > 0 else float("nan")


def pilot_combos(pilot: Path) -> Dict[str, List[tuple]]:
    """The fitted ten-feature vectors, per target and seed, plus the readout fit."""
    out: Dict[str, List[tuple]] = {}
    f = pilot / "selected_feature_coefficients.csv"
    if f.exists():
        g = defaultdict(list)
        for r in csv.DictReader(f.open()):
            key = f"sae10_{r['target']}_seed{r['seed']}"
            g[key].append((int(r["feature"]),
                           float(r["decoder_coefficient_at_selected_dose"])))
        out.update(g)
    rg = pilot / "readout_geometry.json"
    if rg.exists():
        d = json.loads(rg.read_text())
        out["readout_sparse_fit"] = list(zip(d["features"], d["coefficients"]))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--grad-dir", required=True, type=Path,
                    help="holds pilot_grad_L{48,50}_{sum,diff}.npy")
    ap.add_argument("--pilot", required=True, type=Path,
                    help="the pilot's decision evidence directory")
    ap.add_argument("--json-out", type=Path, default=Path("reports/b8_sae_geometry.json"))
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)

    D = decoder()
    print(f"decoder {D.shape}", flush=True)
    fitted = pilot_combos(a.pilot)
    # Missing pilot inputs used to drop rows silently, which looked like a
    # smaller result rather than an absent one.
    missing = [f for f in ("selected_feature_coefficients.csv", "readout_geometry.json")
               if not (a.pilot / f).exists()]
    if missing:
        raise SystemExit(f"missing pilot inputs in {a.pilot}: {', '.join(missing)}")
    combos = {**PAPER_FEATURES, **fitted}
    print(f"{len(combos)} directions ({len(fitted)} fitted by the pilot)", flush=True)
    poles = {}
    for L in (48, 50):
        for part in ("sum", "diff"):
            p = a.grad_dir / f"pilot_grad_L{L}_{part}.npy"
            if p.exists():
                poles[f"L{L}_{part}"] = np.load(p).astype(np.float64)
        # The bias anchor carries no direction in its file. Its activation-space
        # displacement, measured by `bias_direction.py`, is the pole (A5).
        for other in ("bias", "preference"):
            p = a.grad_dir / f"displacement_{other}_L{L}.npy"
            if p.exists():
                poles[f"L{L}_{other}"] = np.load(p).astype(np.float64)
    if not poles:
        raise SystemExit(f"no gradient vectors in {a.grad_dir}")

    rng = np.random.default_rng(0)
    out: Dict[str, Dict[str, float]] = {}
    for name, combo in combos.items():
        v = build(D, combo)
        out[name] = {f"cos_{k}": cos(v, g) for k, g in poles.items()}
        out[name]["n_features"] = len(combo)
        out[name]["norm"] = float(np.linalg.norm(v))
    # A null from random single features, the same construction, 200 draws.
    null = defaultdict(list)
    norms = np.linalg.norm(D, axis=0)
    live = np.flatnonzero(norms > 1e-8)          # dead features have no direction
    for i in rng.choice(live, size=min(2000, live.size), replace=False):
        v = D[:, int(i)]
        for k, g in poles.items():
            null[k].append(abs(cos(v, g)))
    out["_null_abs_cos_random_feature"] = {
        k: {"n": int(len(v)), "mean": float(np.nanmean(v)),
            "p95": float(np.nanpercentile(v, 95)),
            "p99": float(np.nanpercentile(v, 99))}
        for k, v in null.items()}
    out["_dead_features"] = int(D.shape[1] - live.size)

    a.json_out.parent.mkdir(parents=True, exist_ok=True)
    a.json_out.write_text(json.dumps(out, indent=2, sort_keys=True))

    keys = sorted(poles)
    print(f"{'direction':<30}" + "".join(f"{k:>13}" for k in keys))
    for name in sorted(k for k in out if not k.startswith("_")):
        print(f"{name:<30}" + "".join(f"{out[name]['cos_'+k]:>+13.4f}" for k in keys))
    n = out["_null_abs_cos_random_feature"]
    print(f"{'random feature, 95th pct |cos|':<30}"
          + "".join(f"{n[k]['p95']:>13.4f}" for k in keys))

    if a.write_manifest:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        with open("MANIFEST_B.csv", "a", newline="") as fh:
            for name in sorted(k for k in out if not k.startswith("_")):
                for k in keys:
                    fh.write(f'B8.saegeom.{name}.cos_{k},{out[name]["cos_"+k]},'
                             f'cv_bench/anchors/sae_geometry.py,'
                             f'{SAE_REPO}@{SAE_REVISION}|pilot_grad_*.npy,{sha},'
                             f'"SAE direction against the decomposed readout anchor"\n')
        print("manifest rows written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
