"""Checks on B2-cal's saved reads before the 70B LoRA is trained.

Author instruction 2, 22 Sept. All three run as queries on the reads already on
disk; no GPU and no new model call.

(a) Provenance. Every row behind theta0, the noise estimates and the slope
    table must be a legacy-label row read under the "Answer:" stem. A
    neutral-label row would carry z identically zero -- "Option A" and
    "Option B" share their first token -- and would drag the fit toward zero
    without failing anything.

(b) The slope test, done within cells. The first version pooled over p, and in
    the B1 grid x and p are negatively correlated at every stake (x is a log
    grid around s/p, so large x goes with small p). Pooling therefore turns a
    dislike of low-probability gambles into a negative slope on log x, and it
    is why s = 50 looked different: the legacy p = 0.5 cell dominates it. The
    honest tests are within a cell.

(c) The CPT fit's residual per (s, p) cell, with gamma treated as provisional.
    gamma = 1.50 under the Tversky-Kahneman form is S-shaped weighting, which
    underweights small probabilities; 0.61 is the inverse-S of plan v4.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.estimator import fit as FIT
from cv_bench.estimator.agents import (
    ALPHA0, GAMMA0, LAMBDA0, AgentParams, latent_z_packed, pack)
from cv_bench.estimator.b2_cal import calibration_trials
from cv_bench.tasks import core

DEFAULT_IN = Path("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB/b2_cal")


def load_reads(indir: Path) -> Tuple[List[core.Trial], np.ndarray, np.ndarray]:
    d = np.load(indir / "z_baseline.npz", allow_pickle=False)
    z, mass, ids = d["z"], d["mass"], [str(x) for x in d["trial_ids"]]
    trials = calibration_trials()
    if [t.trial_id for t in trials] != ids:
        raise RuntimeError("saved reads do not correspond to the current trial list")
    return trials, z, mass


# -- (a) provenance ---------------------------------------------------------

def check_provenance(trials: Sequence[core.Trial], z: np.ndarray) -> Dict[str, object]:
    label_sets = sorted({t.fmt.label_set for t in trials})
    stems = sorted({core.stem_for(t) for t in trials})
    neutral = [i for i, t in enumerate(trials) if t.fmt.label_set != "legacy"]
    exact_zero = [i for i in range(len(z)) if z[i] == 0.0]
    return {
        "label_sets_present": label_sets,
        "stems_present": stems,
        "n_rows": len(trials),
        "n_non_legacy_rows": len(neutral),
        "n_rows_with_z_exactly_zero": len(exact_zero),
        "response_formats": sorted({t.fmt.response_format for t in trials}),
        "splits": sorted({t.split for t in trials}),
        "CLEAN": bool(label_sets == ["legacy"] and stems == ["Answer:"]
                      and not neutral and not exact_zero),
    }


# -- (b) the slope test, within cells --------------------------------------

def _cells(trials, z, keys=("s", "p"), with_order=True):
    out: Dict[Tuple, List[Tuple[float, float]]] = defaultdict(list)
    for t, zi in zip(trials, z):
        if t.family != "sure_gain":
            continue
        pr = t.param_dict
        if pr.get("x", 0) <= 0 or pr.get("s", 0) <= 0 or not np.isfinite(zi):
            continue
        key = tuple(pr[k] for k in keys)
        if with_order:
            key = key + (t.fmt.option_order,)
        out[key].append((float(np.log(pr["x"])), float(zi)))
    return out


def slope_within_cells(trials, z) -> Dict[str, object]:
    """Is mean z monotone in x inside every (s, p, order) cell?"""
    cells = _cells(trials, z, ("s", "p"), with_order=True)
    rows = []
    for key, pts in sorted(cells.items()):
        if len(pts) < 4:
            continue
        agg: Dict[float, List[float]] = defaultdict(list)
        for lx, zi in pts:
            agg[round(lx, 6)].append(zi)
        xs = sorted(agg)
        means = [float(np.mean(agg[x])) for x in xs]
        slope = float(np.polyfit(xs, means, 1)[0])
        diffs = np.diff(means)
        rows.append({
            "s": key[0], "p": key[1], "order": key[2], "n_levels": len(xs),
            "slope": slope,
            "monotone_increasing": bool(np.all(diffs >= -1e-9)),
            "frac_steps_increasing": float(np.mean(diffs > 0)),
            "z_first": means[0], "z_last": means[-1],
        })
    neg = [r for r in rows if r["slope"] < 0]
    return {
        "n_cells": len(rows),
        "n_cells_slope_negative": len(neg),
        "n_cells_monotone_increasing": sum(r["monotone_increasing"] for r in rows),
        "mean_slope": float(np.mean([r["slope"] for r in rows])) if rows else float("nan"),
        "negative_cells": neg[:12],
        "cells": rows,
    }


def slope_at_half(trials, z) -> Dict[str, object]:
    """Mean z against log x at p = 0.5, per s. The range-normalisation test."""
    out = {}
    for t_s in sorted({t.param_dict["s"] for t in trials if t.family == "sure_gain"}):
        pts = []
        for t, zi in zip(trials, z):
            pr = t.param_dict
            if (t.family == "sure_gain" and pr.get("p") == 0.5
                    and pr.get("s") == t_s and pr.get("x", 0) > 0 and np.isfinite(zi)):
                pts.append((float(np.log(pr["x"])), float(zi)))
        if len(pts) < 4:
            continue
        agg: Dict[float, List[float]] = defaultdict(list)
        for lx, zi in pts:
            agg[round(lx, 6)].append(zi)
        xs = sorted(agg); means = [float(np.mean(agg[x])) for x in xs]
        out[f"s{int(t_s)}"] = {
            "slope": float(np.polyfit(xs, means, 1)[0]),
            "n_levels": len(xs),
            "monotone_increasing": bool(np.all(np.diff(means) >= -1e-9)),
            "z_first": means[0], "z_last": means[-1],
        }
    vals = [v["slope"] for v in out.values()]
    return {"per_s": out,
            "all_positive": bool(all(v > 0 for v in vals)) if vals else False,
            "cv": float(np.std(vals, ddof=1) / abs(np.mean(vals)))
            if len(vals) > 1 and abs(np.mean(vals)) > 1e-9 else float("nan")}


def joint_regression(trials, z) -> Dict[str, object]:
    """z on log x, log p and log s with per-cell intercepts.

    Per-cell intercepts absorb everything constant within an (s, p, order)
    cell, so the log x coefficient is the within-cell effect of the reward
    level and cannot be contaminated by the x-p correlation across cells.
    """
    rows, cells = [], []
    for t, zi in zip(trials, z):
        pr = t.param_dict
        if t.family != "sure_gain" or not np.isfinite(zi):
            continue
        if pr.get("x", 0) <= 0 or pr.get("s", 0) <= 0 or pr.get("p", 0) <= 0:
            continue
        rows.append((np.log(pr["x"]), np.log(pr["p"]), np.log(pr["s"]), zi))
        cells.append((pr["s"], pr["p"], t.fmt.option_order))
    if len(rows) < 20:
        return {"n": len(rows), "error": "too few rows"}
    arr = np.array(rows)
    uniq = sorted(set(cells)); idx = {c: i for i, c in enumerate(uniq)}
    D = np.zeros((len(rows), len(uniq)))
    for r, c in enumerate(cells):
        D[r, idx[c]] = 1.0
    # log s and log p are constant within a cell, so with per-cell intercepts
    # only log x is identified; both are reported from the no-intercept fit.
    X_cell = np.column_stack([arr[:, 0:1], D])
    beta_cell, *_ = np.linalg.lstsq(X_cell, arr[:, 3], rcond=None)
    X_flat = np.column_stack([np.ones(len(rows)), arr[:, 0], arr[:, 1], arr[:, 2]])
    beta_flat, *_ = np.linalg.lstsq(X_flat, arr[:, 3], rcond=None)
    return {
        "n": len(rows), "n_cells": len(uniq),
        "within_cell_log_x": float(beta_cell[0]),
        "pooled": {"const": float(beta_flat[0]), "log_x": float(beta_flat[1]),
                   "log_p": float(beta_flat[2]), "log_s": float(beta_flat[3])},
        "note": ("the pooled log_x coefficient is the one the first, "
                 "under-specified slope table reported; the within-cell "
                 "coefficient is the one that answers the question"),
    }


# -- (c) CPT residual per cell ---------------------------------------------

def cpt_residuals(trials, z, par: AgentParams) -> Dict[str, object]:
    pred = latent_z_packed(pack(list(trials)), par)
    res = z - pred
    by: Dict[Tuple, List[float]] = defaultdict(list)
    for t, r in zip(trials, res):
        pr = t.param_dict
        if t.family == "sure_gain" and np.isfinite(r):
            by[(pr["s"], pr["p"])].append(float(r))
    cells = {f"s{int(k[0])}_p{k[1]}": {"mean_residual": float(np.mean(v)),
                                       "sd": float(np.std(v)), "n": len(v)}
             for k, v in sorted(by.items())}
    return {"rmse": float(np.sqrt(np.nanmean(res ** 2))),
            "mean_abs": float(np.nanmean(np.abs(res))),
            "per_cell": cells}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--in-dir", type=Path, default=DEFAULT_IN)
    ap.add_argument("--refit", action="store_true",
                    help="refit theta0 from the saved reads under current bounds")
    args = ap.parse_args(argv)

    trials, z, mass = load_reads(args.in_dir)
    prov = check_provenance(trials, z)
    print("(a) provenance:", json.dumps(prov, sort_keys=True), flush=True)

    cal = json.loads((args.in_dir / "b2_cal.json").read_text())
    fitted = AgentParams(alpha=cal["fitted"]["alpha"], gamma=cal["fitted"]["gamma"],
                         lam=LAMBDA0, tau=cal["fitted"]["tau"])

    # Refit from the saved reads under the current bounds. The stored fit was
    # produced with gamma capped at 1.60 and landed exactly on it, so it
    # describes the cap rather than the model; this says where the optimiser
    # actually wants to sit, and whether it rails again.
    refit = None
    if args.refit:
        ok = np.isfinite(z) & (mass > 0.5)
        use = [t for t, k in zip(trials, ok) if k]
        sigma = max(float(cal["numerical_noise"]["sd_mean"]), 1e-3)
        par, _, ll = FIT.fit(use, z[ok], ("alpha", "gamma", "tau"),
                             AgentParams(), free_templates=True,
                             observe="logit", sigma=sigma, seed=0, restarts=6)
        b = FIT.BOUNDS
        railed = {n: bool(abs(getattr(par, {"gamma": "gamma", "alpha": "alpha",
                                            "tau": "tau"}[n]) - b[n][1]) < 1e-3
                          or abs(getattr(par, n) - b[n][0]) < 1e-3)
                  for n in ("alpha", "gamma", "tau")}
        refit = {"alpha": par.alpha, "gamma": par.gamma, "tau": par.tau,
                 "loglik": ll, "bounds": {k: list(v) for k, v in b.items()
                                          if k in ("alpha", "gamma", "tau")},
                 "railed": railed,
                 "note": ("a parameter sitting on its bound is not an estimate; "
                          "it is reported as unidentified rather than quoted")}
        print(f"refit under wider bounds: alpha={par.alpha:.4f} "
              f"gamma={par.gamma:.4f} tau={par.tau:.4f}  railed={railed}", flush=True)
        fitted = par

    within = slope_within_cells(trials, z)
    half = slope_at_half(trials, z)
    joint = joint_regression(trials, z)
    resid = cpt_residuals(trials, z, fitted)

    print(f"(b) within-cell: {within['n_cells']} cells, "
          f"{within['n_cells_slope_negative']} with negative slope, "
          f"{within['n_cells_monotone_increasing']} monotone increasing, "
          f"mean slope {within['mean_slope']:.4f}", flush=True)
    print(f"    p=0.5 per s: {({k: round(v['slope'], 4) for k, v in half['per_s'].items()})}"
          f"  all_positive={half['all_positive']}", flush=True)
    print(f"    joint: within-cell log x = {joint.get('within_cell_log_x', float('nan')):.4f}; "
          f"pooled = {({k: round(v, 4) for k, v in joint.get('pooled', {}).items()})}", flush=True)
    print(f"(c) CPT residual rmse={resid['rmse']:.4f} mean|r|={resid['mean_abs']:.4f}", flush=True)

    out = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "provenance": prov, "within_cell": within, "at_p_half": half,
           "joint_regression": joint, "cpt_residual": resid,
           "fitted_used": fitted.as_dict(), "refit": refit,
           "gamma_note": ("gamma 1.50 under the Tversky-Kahneman form is S-shaped "
                          "weighting, which UNDERweights small probabilities; plan "
                          "v4's 0.61 is the inverse-S that overweights them. "
                          "Provisional until (b) is settled."),
           "VERDICT_clean": bool(prov["CLEAN"] and within["n_cells_slope_negative"] == 0)}
    (args.in_dir / "b2_cal_check.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, default=float) + "\n")
    print(f"\nVERDICT clean={out['VERDICT_clean']}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
