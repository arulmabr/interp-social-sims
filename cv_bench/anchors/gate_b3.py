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


def empirical_floor(run: Path, other: str) -> tuple[float, float, int]:
    """SD of the CONTRAST residual, measured rather than assumed.

    `hypot(sd_ref, sd_other)` is the floor only when the two adapters' cloning
    residuals are independent. That holds when each is trained from its own
    initialisation and fails by design once the shifted adapter is started from
    the reference adapter's weights -- the whole point of pairing is to make the
    residuals correlate so they cancel here. Assuming independence would hide
    exactly the improvement the paired run exists to produce, so when the
    per-row residuals are on disk the contrast SD is taken from them directly.

    Returns (contrast SD, correlation between the two residuals, n).
    """
    fr, fo = run / "residuals_reference.npz", run / f"residuals_{other}.npz"
    if not (fr.exists() and fo.exists()):
        return float("nan"), float("nan"), 0
    a = np.load(fr, allow_pickle=False)["residual"]
    b = np.load(fo, allow_pickle=False)["residual"]
    ok = np.isfinite(a) & np.isfinite(b)
    a, b = a[ok], b[ok]
    if a.size < 10:
        return float("nan"), float("nan"), int(a.size)
    return (float((b - a).std(ddof=1)),
            float(np.corrcoef(a, b)[0, 1]), int(a.size))


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
        indep = math.hypot(resid["reference"], resid[other])
        emp, rho, n_emp = empirical_floor(run, other)
        floor = emp if np.isfinite(emp) else indep
        se = floor / math.sqrt(n)
        lo, hi = est - 1.96 * se, est + 1.96 * se
        out["contrasts"][other] = {
            "truth": truth, "estimate": est,
            "recovery_ratio": float(c["recovery_ratio"]),
            "trial_correlation": float(c["correlation"]),
            "noise_floor_sd": floor,
            "noise_floor_source": ("measured from the per-row residuals"
                                   if np.isfinite(emp) else
                                   "assumed independent (no residual files)"),
            "noise_floor_if_independent": indep,
            "residual_correlation": rho,
            "n_residual_rows": n_emp,
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
        if np.isfinite(c.get("residual_correlation", float("nan"))):
            print(f"     residual corr    {c['residual_correlation']:+.4f}  "
                  f"(independent would give {c['noise_floor_if_independent']:.4f})")
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


# ---------------------------------------------------------------------------
# GATE B3, as amended by the authors on 22 Sept (BD51).
#
# The planted change is a CURVATURE shift: alpha moves, so its effect on z
# varies with the payoff and changes sign across it. The mean of dz therefore
# does not measure it -- a perfectly faithful adapter can show mean dz near
# zero -- and the sign flip in BD50 was that failure mode, not a broken adapter.
# The gate is evaluated with the estimator instead:
#
#   (a) the fitted alpha difference between the shifted and reference adapters
#       is within one MDC of the planted shift;
#   (b) the contrast is classified preference-like under the decision rule:
#       preference share >= 0.8 and the action model rejected at 0.95 on the
#       cluster bootstrap (BD12).
#
# The slope of measured-on-planted contrast with its intercept, and the mean dz,
# are reported beside it for the record but decide nothing.
def estimator_gate(run: Path, trials, init=None) -> Dict[str, object]:
    from cv_bench.estimator import fit as FIT
    from cv_bench.estimator.agents import AgentParams
    from cv_bench.estimator.decision import MDC, PREFERENCE_SHARE_MIN

    d = json.loads((run / "b3_lora.json").read_text())
    th = d["theta0"]
    if init is None:
        init = AgentParams(alpha=th["alpha"], gamma=th["gamma"],
                           lam=th["lambda"], tau=d["tau"])
    # the shifted adapter is alpha0 + n * MDC; n is 1 for the original anchor
    # and 3 for the second one, and is recorded by the run itself
    planted = float(d.get("preference_mdc_multiple", 1.0)) * MDC["alpha"]
    trials = list(trials)

    z = {}
    for a in ("reference", "preference"):
        z[a] = np.load(run / f"residuals_{a}.npz", allow_pickle=False)["z_model"]
    za = np.load(run / "residuals_preference.npz", allow_pickle=False)["z_agent"]
    zar = np.load(run / "residuals_reference.npz", allow_pickle=False)["z_agent"]

    fits_par, tpl = {}, None
    for a in ("reference", "preference"):
        par, _, _ = FIT.fit(trials, z[a], ("alpha", "gamma", "tau"), init,
                            observe="logit", free_templates=True)
        fits_par[a] = par
        if a == "reference":
            tpl = dict(FIT.fit.last_template_offsets)

    achieved = float(fits_par["preference"].alpha - fits_par["reference"].alpha)
    within = bool(abs(achieved - planted) <= MDC["alpha"])

    fits = FIT.fit_all_models(trials, z["preference"], fits_par["reference"],
                              observe="logit", template_offsets=tpl)
    shares = FIT.model_shares(fits)
    boot = FIT.cluster_bootstrap(trials, fits, "preference", "action",
                                 n_boot=400, seed=0)
    share_ok = bool(shares.get("preference", 0.0) >= PREFERENCE_SHARE_MIN)
    action_rejected = bool(boot.get("p_a_better", float("nan")) >= 0.95)

    ok = np.isfinite(za) & np.isfinite(zar) & np.isfinite(z["preference"]) & np.isfinite(z["reference"])
    dza, dzm = (za - zar)[ok], (z["preference"] - z["reference"])[ok]
    slope, icpt = np.polyfit(dza, dzm, 1)

    return {
        "gate": "PASS" if (within and share_ok and action_rejected) else "FAIL",
        "criteria": {"alpha_within_one_mdc": within,
                     "preference_share_ge_0.8": share_ok,
                     "action_model_rejected": action_rejected},
        "planted_alpha_shift": planted,
        "achieved_alpha_shift": achieved,          # item 4: the anchor's known value
        "alpha_error_in_mdc": abs(achieved - planted) / MDC["alpha"],
        "fitted_alpha": {a: float(p.alpha) for a, p in fits_par.items()},
        "fitted_gamma": {a: float(p.gamma) for a, p in fits_par.items()},
        "preference_share": float(shares.get("preference", float("nan"))),
        "shares": {k: float(v) for k, v in shares.items()},
        "p_preference_beats_action": float(boot.get("p_a_better", float("nan"))),
        "for_the_record": {"slope_measured_on_planted": float(slope),
                           "slope_intercept": float(icpt),
                           "mean_dz": float(dzm.mean()),
                           "planted_mean_dz": float(dza.mean())},
        "n": int(ok.sum()),
    }


# ---------------------------------------------------------------------------
# The social counterpart (B7, BD54/BD55).
#
# Same two criteria as `estimator_gate`, read against the Fehr-Schmidt
# responder instead of the prospect-theory agent: the fitted `beta_adv`
# difference is within one ultimatum MDC of the planted shift, and the contrast
# is classified preference-like. The preference family is `beta_adv` alone,
# which is what SOCIAL_FREE_SETS encodes.
#
# The synthetic check in reports/B7_RECOVERY.md predicts criterion (b) fails
# here, because the planted effect never changes sign across the offer grid and
# the region where it differs from a constant push is saturated. It is run
# anyway and reported either way, which is rule 5.
def estimator_gate_social(run: Path, trials, init=None) -> Dict[str, object]:
    from cv_bench.estimator import fit as FIT
    from cv_bench.estimator.agents import AgentParams, BETA0
    from cv_bench.estimator.decision import PREFERENCE_SHARE_MIN
    from cv_bench.estimator.social_mdc import social_mdc

    d = json.loads((run / "b3_lora.json").read_text())
    mdc = float(social_mdc()["mdc_beta_adv"])
    if init is None:
        init = AgentParams(tau=d["tau"], beta_adv=BETA0)
    planted = float(d.get("preference_mdc_multiple", 1.0)) * mdc
    trials = list(trials)

    z = {a: np.load(run / f"residuals_{a}.npz", allow_pickle=False)["z_model"]
         for a in ("reference", "preference")}
    za = np.load(run / "residuals_preference.npz", allow_pickle=False)["z_agent"]
    zar = np.load(run / "residuals_reference.npz", allow_pickle=False)["z_agent"]

    fits_par, tpl = {}, None
    for a in ("reference", "preference"):
        par, _, _ = FIT.fit(trials, z[a], ("beta_adv", "tau"), init,
                            observe="logit", free_templates=True)
        fits_par[a] = par
        if a == "reference":
            tpl = dict(FIT.fit.last_template_offsets)

    # A reduction in beta_adv is the planted preference change (BD54), so the
    # achieved shift is reference minus preference, positive when it worked.
    achieved = float(fits_par["reference"].beta_adv - fits_par["preference"].beta_adv)
    within = bool(abs(achieved - planted) <= mdc)

    fits = FIT.fit_all_models(trials, z["preference"], fits_par["reference"],
                              observe="logit", template_offsets=tpl,
                              free_sets=FIT.SOCIAL_FREE_SETS)
    shares = FIT.model_shares(fits)
    boot = FIT.cluster_bootstrap(trials, fits, "preference", "action",
                                 n_boot=400, seed=0)
    share_ok = bool(shares.get("preference", 0.0) >= PREFERENCE_SHARE_MIN)
    action_rejected = bool(boot.get("p_a_better", float("nan")) >= 0.95)

    ok = (np.isfinite(za) & np.isfinite(zar)
          & np.isfinite(z["preference"]) & np.isfinite(z["reference"]))
    dza, dzm = (za - zar)[ok], (z["preference"] - z["reference"])[ok]
    slope, icpt = np.polyfit(dza, dzm, 1)

    return {
        "gate": "PASS" if (within and share_ok and action_rejected) else "FAIL",
        "criteria": {"beta_adv_within_one_mdc": within,
                     "preference_share_ge_0.8": share_ok,
                     "action_model_rejected": action_rejected},
        "mdc_beta_adv": mdc,
        "planted_beta_shift": planted,
        "achieved_beta_shift": achieved,
        "beta_error_in_mdc": abs(achieved - planted) / mdc,
        "fitted_beta_adv": {a: float(p.beta_adv) for a, p in fits_par.items()},
        "fitted_tau": {a: float(p.tau) for a, p in fits_par.items()},
        "preference_share": float(shares.get("preference", float("nan"))),
        "shares": {k: float(v) for k, v in shares.items()},
        "p_preference_beats_action": float(boot.get("p_a_better", float("nan"))),
        "for_the_record": {"slope_measured_on_planted": float(slope),
                           "slope_intercept": float(icpt),
                           "mean_dz": float(dzm.mean()),
                           "planted_mean_dz": float(dza.mean())},
        "n": int(ok.sum()),
    }
