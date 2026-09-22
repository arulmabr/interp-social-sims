"""GATE B3 — evaluate the anchors of B3.2 against the go-or-pivot rule.

`ICLR_PLAN.md:186` states the rule: proceed if the gradient and bias-adapter
anchors fail the rule and **the preference adapter passes with the estimated
shift within the minimum detectable change of the truth**. If the preference
anchor fails, fix cloning or the estimator.

A5 is explicit that the anchors are the **contrasts against the reference
adapter**, not the adapters themselves. So a gate verdict needs the contrast's
uncertainty, and that is set by how tightly each adapter clones. At correlation
r on a clone set whose model-side readings have SD s, the cloning residual has
SD `s * sqrt(1 - r^2)`; a contrast of two independently trained adapters carries
the two residuals added in quadrature. That quantity is the noise floor the
preference signal has to clear, and on both stacks it does not.

Everything here is read from files written by the run:

  b3_lora.json            cloning r / slope / n, and the contrasts
  ckpt_read_<adapter>.npz the 240 model-side z readings on the clone set

Nothing is re-typed from a log. Run:

    python -m cv_bench.anchors.gate_b3 --run-dir $TRACKB_SHARE/trackB/b3_lora_70b
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Dict

import numpy as np

ADAPTERS = ("reference", "preference", "bias")

# The mean |dz| produced by shifting CPT alpha by exactly its minimum
# detectable change, from the B2 calibration run (cvb_mvcal: "target effect
# (CPT alpha at its MDC): 0.0176"). The gate's phrase "within the minimum
# detectable change of the truth" is applied in these units.
MDC_DZ = 0.0176


def residual_sd(run: Path, adapter: str, r: float) -> tuple[float, float]:
    """Cloning residual SD for one adapter, from its own read file."""
    z = np.load(run / f"ckpt_read_{adapter}.npz")["data"].ravel()
    z = z[np.isfinite(z)]
    sd = float(z.std(ddof=1))
    return sd, sd * math.sqrt(max(0.0, 1.0 - r * r))


def evaluate(run: Path) -> Dict[str, object]:
    d = json.loads((run / "b3_lora.json").read_text())
    cl, co = d["cloning"], d["contrasts"]
    n = int(cl["reference"]["n"])

    sd, resid = {}, {}
    for a in ADAPTERS:
        sd[a], resid[a] = residual_sd(run, a, cl[a]["correlation"])

    out: Dict[str, object] = {
        "model": d.get("model"), "steps": d.get("steps"), "n_clone": n,
        "cloning": {a: {"r": cl[a]["correlation"], "slope": cl[a]["slope"],
                        "pass": bool(cl[a]["PASS"]), "z_sd": sd[a],
                        "residual_sd": resid[a]} for a in ADAPTERS},
        "all_cloning_pass": bool(d.get("all_cloning_pass")),
        "mdc_dz": MDC_DZ, "contrasts": {},
    }

    for other in ("preference", "bias"):
        c = co[f"{other}_minus_reference"]
        truth = float(c["agent_mean_dz"])
        est = float(c["model_mean_dz"])
        floor = math.hypot(resid["reference"], resid[other])
        se = floor / math.sqrt(n)
        lo, hi = est - 1.96 * se, est + 1.96 * se
        out["contrasts"][other] = {
            "truth": truth, "estimate": est,
            "recovery_ratio": float(c["recovery_ratio"]),
            "trial_correlation": float(c["correlation"]),
            "noise_floor_sd": floor,
            "buried_x": floor / truth if truth else float("inf"),
            "se": se, "ci_lo": lo, "ci_hi": hi,
            "ci_contains_truth": bool(lo <= truth <= hi),
            "ci_contains_zero": bool(lo <= 0.0 <= hi),
            "abs_err_in_mdc": abs(est - truth) / MDC_DZ,
            "ci_halfwidth_in_mdc": (1.96 * se) / MDC_DZ,
        }

    p = out["contrasts"]["preference"]
    # The rule asks for an estimate within one MDC of the truth. That is only
    # meaningful if the estimate is resolved at all: an interval several MDC
    # wide can straddle the truth by luck while also straddling zero.
    resolved = not p["ci_contains_zero"] and p["ci_halfwidth_in_mdc"] <= 1.0
    close = p["abs_err_in_mdc"] <= 1.0
    out["preference_anchor_passes"] = bool(resolved and close)
    out["preference_point_estimate_within_mdc"] = bool(close)
    out["preference_estimate_resolved"] = bool(resolved)
    out["gate_b3"] = "PASS" if out["preference_anchor_passes"] else "FAIL"
    out["gate_b3_route"] = ("B3.3 and B4" if out["preference_anchor_passes"]
                            else "fix cloning or the estimator (ICLR_PLAN.md:186)")
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True, type=Path)
    ap.add_argument("--json-out", type=Path, default=None)
    a = ap.parse_args(argv)

    r = evaluate(a.run_dir)
    print(f"model {r['model']}   steps {r['steps']}   clone n={r['n_clone']}")
    print(f"{'adapter':<12}{'r':>9}{'slope':>9}{'z_sd':>9}{'resid SD':>10}{'clones':>8}")
    for k, v in r["cloning"].items():
        print(f"{k:<12}{v['r']:>9.4f}{v['slope']:>9.4f}{v['z_sd']:>9.3f}"
              f"{v['residual_sd']:>10.4f}{'yes' if v['pass'] else 'NO':>8}")
    print()
    for k, c in r["contrasts"].items():
        print(f"{k} - reference")
        print(f"   true signal        {c['truth']:.4f}")
        print(f"   noise floor SD     {c['noise_floor_sd']:.4f}   "
              f"-> signal buried {c['buried_x']:.1f}x")
        print(f"   estimate           {c['estimate']:.4f}  "
              f"95% CI [{c['ci_lo']:+.4f}, {c['ci_hi']:+.4f}]")
        print(f"   |est-truth|        {c['abs_err_in_mdc']:.2f} MDC     "
              f"CI half-width {c['ci_halfwidth_in_mdc']:.2f} MDC")
        print(f"   contains truth {c['ci_contains_truth']}   "
              f"contains zero {c['ci_contains_zero']}")
        print()
    print(f"preference point estimate within 1 MDC : {r['preference_point_estimate_within_mdc']}")
    print(f"preference estimate resolved           : {r['preference_estimate_resolved']}")
    print(f"GATE B3 = {r['gate_b3']}  ->  {r['gate_b3_route']}")

    if a.json_out:
        a.json_out.parent.mkdir(parents=True, exist_ok=True)
        a.json_out.write_text(json.dumps(r, indent=2, sort_keys=True))
        print(f"\nwrote {a.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
