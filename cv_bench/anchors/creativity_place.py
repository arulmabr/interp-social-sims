"""B10.7 - place the creativity SAE features and probe against the LoRA anchor.

The gradient anchor is a direction, so a cosine can be taken with it directly.
An adapter is a change of weights and has no direction, so the LoRA anchor is
represented by its displacement: the mean change in the residual stream when the
same prompts are run under the shifted adapter instead of the reference one.
`creativity_disp.py` measures that; this script does the arithmetic.

Convention matches the lottery and ultimatum tables: a signed cosine for each
named direction, and a null band from 2,000 randomly drawn live dictionary
features put through the identical comparison, reported as absolute cosine.

    python -m cv_bench.anchors.creativity_place --dir <dir> --out <json>
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch

SAE_REPO = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"
SAE_FILE = "Llama-3.3-70B-Instruct-SAE-l50.pt"
SAE_REVISION = "128ee921ecd1b8b3a87d776cbcc357c0855da134"
SAE_FEATURES = {13142: "enabling creative expression",
                20117: "thinking outside the box",
                4992: "professional innovation"}
LAYERS = (48, 50)
POLES = ("bias", "preference")
NULL_DRAWS = 2000


def cos(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    if na < 1e-12 or nb < 1e-12:
        return float("nan")
    return float(a @ b / (na * nb))


def decoder() -> np.ndarray:
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(SAE_REPO, SAE_FILE, revision=SAE_REVISION)
    st = torch.load(p, map_location="cpu", weights_only=True)
    return st["decoder_linear.weight"].float().numpy()  # float32: 65536 columns


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--merge", type=Path, default=None,
                    help="existing placement json whose gradient columns are kept")
    a = ap.parse_args(argv)

    anchors = {}
    for pole in POLES:
        for L in LAYERS:
            fp = a.dir / f"creativity_displacement_{pole}_L{L}.npy"
            if not fp.exists():
                raise SystemExit(f"missing displacement: {fp}")
            anchors[f"lora_{pole}_L{L}"] = np.load(fp).astype(np.float64)
    for k, v in anchors.items():
        print(f"{k}: |displacement| = {np.linalg.norm(v):.4f}", flush=True)

    D = decoder()
    rows = {}
    for idx, label in SAE_FEATURES.items():
        rows[f"SAE {idx}, {label}"] = D[:, idx].astype(np.float64)
    for L in LAYERS:
        rows[f"creativity probe, layer {L}"] = np.load(
            a.dir / f"creativity_probe_L{L}.npy").astype(np.float64)

    out = {}
    if a.merge and a.merge.exists():
        out = json.loads(a.merge.read_text())
    for name, v in rows.items():
        cell = out.setdefault(name, {})
        for k, g in anchors.items():
            cell[k] = cos(v, g)

    norms = np.linalg.norm(D, axis=0)
    live = np.flatnonzero(norms > 1e-8)
    rng = np.random.default_rng(0)
    null = defaultdict(list)
    for i in rng.choice(live, size=min(NULL_DRAWS, live.size), replace=False):
        v = D[:, i].astype(np.float64)
        for k, g in anchors.items():
            null[k].append(abs(cos(v, g)))
    nb = out.setdefault("_null", {})
    for k, vals in null.items():
        nb[k] = {"p95": float(np.nanpercentile(vals, 95)),
                 "p99": float(np.nanpercentile(vals, 99))}
    out["_dead_features"] = int(D.shape[1] - live.size)
    out["_null_draws"] = int(min(NULL_DRAWS, live.size))

    a.out.write_text(json.dumps(out, indent=2, sort_keys=True))
    print(f"\nwrote {a.out}", flush=True)
    for name in rows:
        for k in anchors:
            band = nb[k]["p95"]
            v = out[name][k]
            flag = "above null" if abs(v) > band else "inside null"
            print(f"  {name:<40} {k:<22} {v:+.4f}   p95 {band:.4f}   {flag}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
