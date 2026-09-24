"""The permutation null for G4's lottery direction geometry.

`g4b_geometry.csv` reports each direction's cosine with the choice probe in
multiples of `1/sqrt(d)`. That is the cosine between two *independent*
directions in d dimensions, and none of these are independent: the choice
probe, the reward probe, the difference of means, the first component and the
ridge are all estimated from the same activation matrix, so they lie in its
span, at most 44 dimensions for the lottery's 45 levels, and are close to one
another before any choice signal is involved.

G4u established this on the ultimatum game, where the two largest bars sat
inside their own permutation null. The lottery panel could not be tested the
same way because G4 saved the fitted directions and not the matrix they were
fitted from.

This module saves that matrix and runs the test.

    python -m cv_bench.g4null --phase collect    # GPU, ~45 levels x 8 samples
    python -m cv_bench.g4null --phase verify     # CPU, refit must match G4
    python -m cv_bench.g4null --phase null       # CPU, the permutation null

The collection reuses G4's own helpers and its seeding, so the activations and
codes are the ones G4 fitted on. `verify` is the check that this is true: it
refits from the saved arrays and requires the result to match
`probe_reconstruction_L{layer}.json`'s `direction_raw` to 1e-6 in cosine. The
null is not trusted unless verify passes.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "${HF_HOME}")
os.environ.setdefault("HF_HUB_OFFLINE", "1")

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "${ICLR_RUNROOT}"))
OUT = RUNROOT / "g4null"
G4DIR = RUNROOT / "g4"
G4BDIR = RUNROOT / "g4b"
PERM_N = 200


def _unit(v) -> np.ndarray:
    v = np.asarray(v, dtype=float)
    return v / (np.linalg.norm(v) + 1e-12)


def collect(layer: int, game: str = "lottery", model_key: str = "llama",
            variant: str = "reconstruction") -> Path:
    """Save the (X, y, levels) G4's phase_train builds, and nothing else.

    The loop is G4's, including `torch.manual_seed(int(v))` per level and
    PROBE_SAMPLES draws, so the arrays are the ones the reported probe was fit
    on. No probe is written and no existing file is touched.
    """
    import torch
    from cv_bench.g4 import (PROBE_SAMPLES, chosen_cap, decision_code,
                             grids_for, legacy_code_of, render, variant_cfg)
    from cv_bench.s21_fix import load

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{game}_inputs_L{layer}.npz"
    if path.exists():
        print(f"[g4null] already collected: {path}", flush=True)
        return path

    model, tok = load(model_key, "bf16")
    cfg = variant_cfg(variant, chosen_cap(), None)
    grabbed: Dict[str, "torch.Tensor"] = {}

    def hook(_m, _i, out):
        h = out[0] if isinstance(out, tuple) else out
        grabbed["h"] = h.detach()

    handle = model.model.layers[layer].register_forward_hook(hook)
    acts: List[np.ndarray] = []
    labels: List[int] = []
    levels: List[int] = []
    drops = 0
    try:
        grid = grids_for(model_key)[0 if game == "lottery" else 1]
        for v in grid:
            text = render(tok, game, v, cfg)
            enc = tok(text, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                model(**enc, use_cache=False)
            h = grabbed["h"][0].float()[-1].cpu().numpy()
            torch.manual_seed(int(v))
            with torch.inference_mode():
                out = model.generate(**enc, max_new_tokens=cfg["max_new_tokens"],
                                     do_sample=True, temperature=0.7, top_p=0.95,
                                     num_return_sequences=PROBE_SAMPLES,
                                     pad_token_id=tok.pad_token_id)
            for row in out:
                gen = tok.decode(row[enc["input_ids"].shape[1]:],
                                 skip_special_tokens=True)
                if variant == "as_written":
                    c = legacy_code_of(gen, game)
                else:
                    dd = decision_code(gen, game)
                    c = -1 if dd["choice"] is None else dd["choice"]
                if c < 0:
                    drops += 1
                    continue
                acts.append(h)
                labels.append(c)
                levels.append(int(v))
    finally:
        handle.remove()

    X = np.stack(acts, 0).astype(np.float32)
    np.savez(path, X=X, y=np.asarray(labels, dtype=int),
             levels=np.asarray(levels, dtype=float))
    (OUT / f"{game}_inputs_L{layer}.json").write_text(json.dumps(dict(
        game=game, layer=layer, variant=variant, model=model_key,
        n_kept=len(labels), n_dropped=drops, n_levels=len(grid),
        classes=sorted(set(labels)), probe_samples=PROBE_SAMPLES,
        note="inputs to G4's phase_train fit, saved so the null can refit"), indent=1))
    print(f"[g4null] {game} L{layer}: X{X.shape}, {len(labels)} kept, "
          f"{drops} dropped -> {path}", flush=True)
    return path


def _fit(X: np.ndarray, y: np.ndarray, levels: np.ndarray) -> Dict[str, np.ndarray]:
    """G4's phase_train fit, exactly, in raw space."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    sc = StandardScaler().fit(X)
    Z = sc.transform(X)
    to_raw = lambda w: _unit(_unit(w) / np.clip(sc.scale_, 1e-8, None))
    out: Dict[str, np.ndarray] = {}

    lr = LogisticRegression(penalty="l2", C=1.0, max_iter=2000).fit(Z, y)
    out["probe"] = to_raw(lr.coef_[0])

    y_rw = (levels > np.median(levels)).astype(int)
    if len(set(y_rw.tolist())) == 2:
        out["reward"] = to_raw(LogisticRegression(
            penalty="l2", C=1.0, max_iter=2000).fit(Z, y_rw).coef_[0])

    out["diffmean"] = to_raw(Z[y == 1].mean(0) - Z[y == 0].mean(0))
    Zc = Z - Z.mean(0, keepdims=True)
    out["pca1"] = to_raw(np.linalg.svd(Zc, full_matrices=False)[2][0])
    t = np.log(levels.astype(float))
    t = t - t.mean()
    # dual form: (Z'Z + I)^-1 Z' == Z'(ZZ' + I)^-1, an n x n solve rather than d x d
    out["ridge_logn"] = to_raw(Z.T @ np.linalg.solve(Z @ Z.T + np.eye(Z.shape[0]), t))
    return out


def verify(layer: int, game: str = "lottery") -> float:
    """Refit from the saved arrays and compare to what G4 reported."""
    z = np.load(OUT / f"{game}_inputs_L{layer}.npz")
    got = _fit(z["X"].astype(np.float64), z["y"], z["levels"])["probe"]
    probe = json.loads((G4DIR / f"probe_reconstruction_L{layer}.json").read_text())
    want = _unit(probe["games"][game]["direction_raw"])
    c = float(np.dot(got, want))
    print(f"[g4null] verify {game} L{layer}: cosine with G4's direction_raw = {c:.8f}",
          flush=True)
    return c


def null(layer: int, game: str = "lottery", n: int = PERM_N,
         seed: int = 0) -> List[dict]:
    """Permute the choice labels, refit everything, n times."""
    z = np.load(OUT / f"{game}_inputs_L{layer}.npz")
    X = z["X"].astype(np.float64)
    y, levels = z["y"], z["levels"]
    obs = _fit(X, y, levels)
    extra: Dict[str, np.ndarray] = {}
    g = G4BDIR / f"fallback_gradient_L{layer}_{game}.npy"
    if g.exists():
        extra["gradient"] = _unit(np.load(g).astype(float))
    rng = np.random.default_rng(seed)
    for i, s in enumerate((40810, 40811)):
        extra[f"rand{i}"] = _unit(np.random.default_rng(s).normal(size=X.shape[1]))
    obs.update(extra)

    acc: Dict[str, List[float]] = {}
    for _ in range(n):
        d = _fit(X, rng.permutation(y), levels)
        d.update(extra)
        ref = d["probe"]
        for k, v in d.items():
            if k != "probe":
                acc.setdefault(k, []).append(abs(float(np.dot(ref, v))))

    ns = 1.0 / np.sqrt(X.shape[1])
    recs = []
    for k, vals in acc.items():
        o = abs(float(np.dot(obs["probe"], obs[k])))
        p95 = float(np.percentile(vals, 95))
        recs.append(dict(layer=layer, game=game, reference="choice_probe",
                         direction=k, abs_cosine=round(o, 5),
                         multiples_of_null=round(o / ns, 2),
                         perm_null_mean=round(float(np.mean(vals)) / ns, 2),
                         perm_null_p95=round(p95 / ns, 2),
                         clears_perm_null=bool(o > p95), perm_n=len(vals),
                         d=X.shape[1], n_rows=int(X.shape[0]),
                         n_levels=int(len(set(levels.tolist())))))
    return recs


if __name__ == "__main__":
    import csv
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", required=True,
                    choices=["collect", "verify", "null", "all"])
    ap.add_argument("--layer", type=int, default=50)
    ap.add_argument("--game", default="lottery")
    ap.add_argument("--perm", type=int, default=PERM_N)
    a = ap.parse_args()
    if a.phase in ("collect", "all"):
        collect(a.layer, a.game)
    if a.phase in ("verify", "all"):
        c = verify(a.layer, a.game)
        if c < 1 - 1e-6:
            raise SystemExit(f"[g4null] refit does not reproduce G4's direction "
                             f"(cosine {c:.8f}); the null would not be about the "
                             f"reported bars, so it is not written")
    if a.phase in ("null", "all"):
        recs = null(a.layer, a.game, a.perm)
        p = OUT / f"g4null_{a.game}.csv"
        with open(p, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
            w.writeheader(); w.writerows(recs)
        for r in recs:
            print(f"  {r['direction']:14s} {r['multiples_of_null']:7.1f}x  "
                  f"null p95 {r['perm_null_p95']:7.1f}x  "
                  f"{'CLEARS' if r['clears_perm_null'] else 'inside'}", flush=True)
        print(f"[g4null] wrote {p}", flush=True)
