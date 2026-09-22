"""B3.3 pass 1, analysis: place the probe between the two poles.

EXPLORATORY, SELECTION SPLIT, NOT PRE-REGISTERED.

The comparison is made at matched behaviour, so any difference between two
conditions is about the *shape* of the change, not its size. The shape is read
two ways:

  * the model-free fingerprint (D1, D2, D3, D5, D7), which needs no model of the
    subject at all;
  * the parametric shares over preference / action / belief / format / noise,
    which need a fit but not a truth.

`resemblance` places each direction between the two poles, the bias adapter and
the readout anchor, in the D2 variance-decomposition space -- the one part of
the fingerprint that directly separates "a constant push" from "a change in how
the reward level matters". **The two random directions set the null band**: a
distance smaller than the random directions' own distance to a pole is not
evidence of resemblance, it is what an arbitrary direction gets for free.

D4 and D6 are "not available" here. `d4_ce_vs_choice` and `d6_recall` are
written for synthetic agents and take the intervened agent's TRUE parameters; a
real direction has none. Their model-side equivalents would need certainty
equivalents and fact recall elicited from the model, which is a prompt family
this repo does not have. Reporting a synthetic stand-in would be inventing a
number, so they are left out and said to be left out (CLAUDE.md rule 1).
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Sequence

import numpy as np

POLES = ("bias_adapter", "readout_anchor_L48")
D2_KEYS = ("const", "format", "payoff")


def _p(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=float)))


def _d2_vector(d2: Dict[str, float]) -> np.ndarray:
    """The share of the change's variance carried by each term."""
    v = np.array([float(d2.get(k, np.nan)) for k in D2_KEYS], dtype=float)
    s = np.nansum(v)
    return v / s if s > 0 else v


def analyse(out: Path, trials: Sequence) -> int:
    from cv_bench.estimator import fingerprint as FP
    from cv_bench.estimator import fit as FIT
    from cv_bench.estimator import decision as DEC
    from cv_bench.estimator.agents import AgentParams

    z = dict(np.load(out / "z_selection.npz"))
    doses = json.loads((out / "doses.json").read_text())
    dirs = {f"{m['name']}_L{m['layer']}": m
            for m in json.loads((out / "directions.json").read_text())}
    trials = list(trials)
    base = np.asarray(z["unmodified"], dtype=float)
    p_base = _p(base)

    theta0 = json.loads((Path(__file__).resolve().parents[2] /
                         "cv_bench" / "anchors" / "_theta0.json").read_text()) \
        if (Path(__file__).resolve().parents[2] / "cv_bench" / "anchors" /
            "_theta0.json").exists() else {"alpha": 0.88, "gamma": 0.61,
                                           "lambda": 2.25, "tau": 0.1186}
    init = AgentParams(alpha=theta0["alpha"], gamma=theta0["gamma"],
                       lam=theta0["lambda"], tau=theta0["tau"])

    d1_base = FP.d1_dominance_violations(trials, (base > 0).astype(int))
    rows: Dict[str, Dict[str, object]] = {}

    for cond, zc in z.items():
        if cond == "unmodified":
            continue
        zc = np.asarray(zc, dtype=float)
        dz = zc - base
        p_int = _p(zc)
        choice = (zc > 0).astype(int)

        fp = {
            "D1_dominance": float(FP.d1_dominance_violations(trials, choice)),
            "D2_variance": FP.d2_variance_decomposition(trials, dz, base),
            "D3_paired_shift": FP.d3_paired_shift(trials, p_base, p_int),
            "D4_ce": "not available - needs the intervened agent's true "
                     "parameters, or certainty equivalents elicited from the "
                     "model; neither exists for a real direction",
            "D5_format": FP.d5_format_transfer(trials, dz),
            "D6_recall": "not available - needs the intervened agent's true "
                         "parameters, or fact recall elicited from the model",
            "D7_stakes": FP.d7_stake_stability(trials, p_base, p_int),
        }
        try:
            fits = FIT.fit_all_models(trials, zc, init, observe="logit")
            shares = FIT.model_shares(fits)
        except Exception as exc:                     # a fit that will not run
            shares = {"error": f"{type(exc).__name__}: {exc}"}
        try:
            oof = DEC.out_of_frame_check(trials, zc, init, observe="logit")
        except Exception as exc:
            oof = {"error": f"{type(exc).__name__}: {exc}"}

        rows[cond] = {
            "role": dirs.get(cond, {}).get("role",
                                           "anchor" if cond == "bias_adapter" else "?"),
            "layer": dirs.get(cond, {}).get("layer"),
            "source": dirs.get(cond, {}).get("source", "B3.2 adapter_bias.pt"),
            "source_sha256": dirs.get(cond, {}).get("source_sha256", ""),
            "scale": doses["solved"].get(cond, {}).get("scale"),
            "matched": doses["solved"].get(cond, {}).get("matched", True),
            "achieved_shift": doses["solved"].get(cond, {}).get(
                "shift", doses.get("switch_bias", np.nan) - doses.get(
                    "switch_unmodified", np.nan)),
            "mean_dz": float(np.nanmean(dz)),
            "sd_dz": float(np.nanstd(dz, ddof=1)),
            "fingerprint": fp,
            "shares": shares,
            "out_of_frame": oof,
        }

    # -- resemblance, with the random directions as the null band -----------
    d2v = {c: _d2_vector(r["fingerprint"]["D2_variance"]) for c, r in rows.items()}
    res: Dict[str, Dict[str, float]] = {}
    for c, v in d2v.items():
        res[c] = {f"dist_to_{p}": float(np.linalg.norm(v - d2v[p]))
                  for p in POLES if p in d2v}
    randoms = [c for c in rows if c.startswith("random_")]
    null = {}
    for p in POLES:
        ds = [res[c].get(f"dist_to_{p}") for c in randoms
              if res.get(c, {}).get(f"dist_to_{p}") is not None]
        null[p] = float(np.min(ds)) if ds else float("nan")

    verdicts = {}
    for c in rows:
        if c in POLES or c.startswith("random_"):
            continue
        db = res[c].get(f"dist_to_{POLES[0]}", np.nan)
        dr = res[c].get(f"dist_to_{POLES[1]}", np.nan)
        closer = POLES[0] if db < dr else POLES[1]
        beats_null = (min(db, dr) < null[closer]) if np.isfinite(null[closer]) else False
        verdicts[c] = {
            "dist_bias": db, "dist_readout": dr, "closer_to": closer,
            "null_band_min_random_distance": null[closer],
            "resemblance_beats_random": bool(beats_null),
            "verdict": (f"resembles {closer}" if beats_null else
                        "neither - inside the random-direction band"),
        }

    payload = {
        "status": "EXPLORATORY, selection split, not pre-registered. Gate B2 "
                  "stands failed, so no direction is certified preference-like.",
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_trials": len(trials), "theta0": theta0,
        "baseline_dominance": float(d1_base),
        "target_shift": doses.get("target_shift"),
        "conditions": rows, "resemblance": verdicts, "null_band": null,
    }
    (out / "b33_analysis.json").write_text(json.dumps(payload, indent=2, default=str))
    print(json.dumps(verdicts, indent=2, default=str))
    print(f"\nwrote {out/'b33_analysis.json'}")
    return 0
