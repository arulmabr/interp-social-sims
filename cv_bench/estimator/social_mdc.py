"""The ultimatum MDC, fixed by matching the risk side's behavioural size (BD55).

One MDC on the risk side is a shift of alpha of 0.10. What that is worth in
behaviour is a move of the lottery switching point, measured here rather than
quoted. The same fraction of the ultimatum offer grid is the target, and the
reduction in `beta_adv` that achieves it is the ultimatum MDC.

Nothing here reads a model output. The inputs are the trial grid, the reference
parameters and the risk MDC, all of which were fixed before any adapter ran.

    python -m cv_bench.estimator.social_mdc [--write-manifest]
"""
from __future__ import annotations

import argparse
import subprocess
from typing import Dict

import numpy as np

from cv_bench.estimator import agents as A
from cv_bench.estimator.fingerprint import switching_points
from cv_bench.tasks import core, risk

LEGACY_CELL = (0.5, 50.0)


def risk_behavioural_size() -> Dict[str, float]:
    """How far one MDC of alpha moves the lottery switching point."""
    content = [t for t in risk.generate_risk(splits=("disc", "sel", "cal"),
                                             families=("sure_gain",))
               if (t.param_dict.get("p"), t.param_dict.get("s")) == LEGACY_CELL]
    trials = list(core.expand_formats(content, response_formats=("mc",),
                                      label_sets=("legacy",)))
    ref = A.AgentParams(tau=A.TAU0)
    pref = A.AgentParams(tau=A.TAU0, alpha=A.ALPHA0 + A.MDC["alpha"])
    s_ref = switching_points(trials, A.choice_prob(A.latent_z_batch(trials, ref)))
    s_pref = switching_points(trials, A.choice_prob(A.latent_z_batch(trials, pref)))
    xs = [t.param_dict["x"] for t in trials]
    span = float(max(xs) - min(xs))
    a, b = s_ref[LEGACY_CELL], s_pref[LEGACY_CELL]
    return {"switch_reference": float(a), "switch_preference": float(b),
            "shift_tokens": float(a - b), "grid_span_tokens": span,
            "shift_as_grid_fraction": float((a - b) / span)}


def beta_for_threshold(target_share: float) -> float:
    """Invert threshold(b) = b / (1 + 2b)."""
    t = float(target_share)
    return t / (1.0 - 2.0 * t)


def social_mdc() -> Dict[str, float]:
    r = risk_behavioural_size()
    t0 = A.social_threshold(A.AgentParams())
    t1 = t0 - r["shift_as_grid_fraction"]          # offer grid spans 0..1 of the pie
    b1 = beta_for_threshold(t1)
    out = dict(r)
    out.update({
        "threshold_reference_share": float(t0),
        "threshold_shifted_share": float(t1),
        "beta_adv_reference": float(A.BETA0),
        "beta_adv_shifted": float(b1),
        "mdc_beta_adv": float(A.BETA0 - b1),
    })
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)
    v = social_mdc()
    for k in sorted(v):
        print(f"{k:30s} {v[k]:.6f}")
    if a.write_manifest:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        rows = [
            ("B7.risk.switch.reference", v["switch_reference"], "reference agent, legacy cell"),
            ("B7.risk.switch.preference_1mdc", v["switch_preference"], "alpha + 0.10"),
            ("B7.risk.shift_as_grid_fraction", v["shift_as_grid_fraction"],
             "one risk MDC as a fraction of the reward grid"),
            ("B7.social.threshold.reference", v["threshold_reference_share"],
             "offer share at indifference, beta_adv 0.60"),
            ("B7.social.beta_adv.shifted", v["beta_adv_shifted"],
             "beta_adv after one ultimatum MDC"),
            ("B7.mdc.beta_adv", v["mdc_beta_adv"],
             "DECLARED before any adapter ran (BD55)"),
        ]
        with open("MANIFEST_B.csv", "a", newline="") as fh:
            for i, val, note in rows:
                fh.write(f'{i},{val},cv_bench/estimator/social_mdc.py,'
                         f'cv_bench/tasks/risk.py|cv_bench/estimator/agents.py,'
                         f'{sha},"{note}"\n')
        print(f"wrote {len(rows)} rows to MANIFEST_B.csv")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
