"""The B2 decision rule and the Gate B2 check (ICLR_PLAN.md B2). CPU only.

Under the scheduling amendment (item 5) Gate B2 is an automatic check: it is
evaluated exactly as the plan writes it, with plan v4's thresholds. Pass means
continue and report; fail means stop that branch and report, iterating on the
synthetic grid only and never on the thresholds.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.estimator import fit as FIT
from cv_bench.estimator.agents import AgentParams, MDC
from cv_bench.estimator.fingerprint import TRANSFER_BAND
from cv_bench.tasks.core import Trial

#: Plan v4 thresholds. AUTHOR DECISIONS, frozen at B6; never changed at a gate.
PREFERENCE_SHARE_MIN = 0.80
DOMINANCE_TOLERANCE = 0.02          # "within 2 points of baseline"
GATE_CLASSIFICATION_MIN = 0.95
GATE_RMSE_FRACTION = 0.5            # RMSE at most half the minimum detectable change


def out_of_frame_check(trials: Sequence[Trial],
                       choices: np.ndarray,
                       init: AgentParams,
                       dominated_policy: str = "exclude",
                       seed: int = 0,
                       template_offsets: Optional[Dict[str, float]] = None,
                       observe: str = "choice",
                       sigma: float = 1.0) -> Dict[str, float]:
    """Fit on core frames, predict the held-out frames (A2).

    Parameters the core frame cannot identify -- lambda above all (BD10) -- are
    held at baseline for this prediction, exactly as the plan directs, and would
    be re-estimated on the held-out frames only as a secondary analysis.
    """
    choices = np.asarray(choices, dtype=float if observe == "logit" else int)
    core = np.array([t.frame_role == "core" for t in trials])
    if core.sum() < 20 or (~core).sum() < 20:
        return {"preference": float("nan"), "action": float("nan"),
                "belief": float("nan"), "preference_wins": float("nan")}

    tr = [t for t, c in zip(trials, core) if c]
    te = [t for t, c in zip(trials, core) if not c]
    ctr, cte = choices[core], choices[~core]
    pk_te = FIT.pack(te)

    out: Dict[str, float] = {}
    for name, free in (("preference", ("alpha", "gamma")),   # lambda held at baseline
                       ("action", ("action",)),
                       ("belief", ("kappa",))):
        par, lapse, _ = FIT.fit(tr, ctr, free, init,
                                dominated_policy=dominated_policy, seed=seed,
                                template_offsets=template_offsets,
                                observe=observe, sigma=sigma)
        off_te = None
        if template_offsets:
            off_te = np.array([template_offsets.get(t.fmt.template_id, 0.0)
                               for t in te], dtype=float)
        out[name] = FIT.log_likelihood(pk_te, cte, par, lapse=lapse, offset=off_te,
                                       observe=observe, sigma=sigma)
    out["preference_wins"] = float(
        out["preference"] > out["action"] and out["preference"] > out["belief"])
    return out


def decide(shares: Dict[str, float],
           fingerprint: Dict[str, object],
           baseline_dominance: float,
           out_of_frame: Dict[str, float],
           bootstrap: Optional[Dict[str, float]] = None) -> Dict[str, object]:
    """Apply the decision rule. A direction is preference-like only if all hold."""
    d5_probe = fingerprint["D5_format"]
    if d5_probe.get("no_format_variation"):
        raise ValueError(
            "the decision rule needs format variation: D5's transfer ratio is "
            "undefined when every trial shares one label set and option order. "
            "Expand formats with core.expand_formats before running B2.")

    d1 = float(fingerprint["D1_dominance"])
    d4 = fingerprint["D4_ce"]
    d5 = fingerprint["D5_format"]
    d6 = fingerprint["D6_recall"]

    action_rejected = True
    if bootstrap is not None and np.isfinite(bootstrap.get("p_a_better", np.nan)):
        # "the action model is rejected": preference beats it on held-out levels
        # in the great majority of cluster-bootstrap draws.
        action_rejected = bool(bootstrap["p_a_better"] >= 0.95)

    criteria = {
        "preference_share": bool(shares.get("preference", 0.0) >= PREFERENCE_SHARE_MIN),
        "action_rejected": bool(action_rejected),
        "dominance_intact": bool(np.isfinite(d1) and
                                 abs(d1 - baseline_dominance) <= DOMINANCE_TOLERANCE),
        "out_of_frame": bool(out_of_frame.get("preference_wins", 0.0) == 1.0),
        "transfer_in_band": bool(d5.get("in_band", 0.0) == 1.0),
        "recall_intact": bool(d6.get("intact", 0.0) == 1.0),
        "ce_agrees": bool(d4.get("agree", 0.0) == 1.0),
    }
    return {"criteria": criteria,
            "preference_like": bool(all(criteria.values())),
            "preference_share": float(shares.get("preference", float("nan")))}


def parameter_rmse(records: Sequence[Dict[str, object]]) -> Dict[str, float]:
    """RMSE of each preference parameter over the preference-shift agents.

    Each record carries the true and fitted value of the parameter that agent
    actually moved, so the RMSE is per parameter and not mixed across them.
    """
    by_param: Dict[str, List[float]] = {}
    for r in records:
        pname = r.get("shifted_param")
        if not pname:
            continue
        by_param.setdefault(pname, []).append(
            float(r["fitted_value"]) - float(r["true_value"]))
    return {p: float(np.sqrt(np.mean(np.square(e)))) for p, e in by_param.items()}


def gate_b2(rmse: Dict[str, float],
            classifications: Dict[str, List[bool]],
            misspecified_ok: Optional[Dict[str, bool]] = None) -> Dict[str, object]:
    """Evaluate Gate B2 exactly as ICLR_PLAN.md writes it.

    Pass requires all of:
      * parameter RMSE at most half of each minimum detectable change;
      * at least 95% of preference-shift agents classified preference-like;
      * at least 95% of action, belief and noise agents -- matched on
        behavioural effect size -- classified as not preference-like;
      * the two misspecified agents handled on the model-free layer.
    """
    rmse_ok: Dict[str, object] = {}
    for pname, bound in MDC.items():
        limit = GATE_RMSE_FRACTION * bound
        got = rmse.get(pname)
        rmse_ok[pname] = {"rmse": got, "limit": limit,
                          "pass": bool(got is not None and np.isfinite(got) and got <= limit)}

    pref_rates: Dict[str, float] = {}
    for name, flags in classifications.items():
        if not flags:
            continue
        pref_rates[name] = float(np.mean(flags))

    pref_agents = {k: v for k, v in pref_rates.items() if k.startswith("pref_")}
    non_pref = {k: v for k, v in pref_rates.items()
                if k in ("action", "belief", "noise", "format")}

    pref_pass = all(v >= GATE_CLASSIFICATION_MIN for v in pref_agents.values()) \
        if pref_agents else False
    non_pref_pass = all((1.0 - v) >= GATE_CLASSIFICATION_MIN for v in non_pref.values()) \
        if non_pref else False
    miss_pass = all(misspecified_ok.values()) if misspecified_ok else False

    overall = (all(v["pass"] for v in rmse_ok.values())
               and pref_pass and non_pref_pass and miss_pass)
    return {
        "rmse": rmse_ok,
        "preference_agents_classified_preference_like": pref_agents,
        "non_preference_agents_classified_preference_like": non_pref,
        "misspecified_handled": misspecified_ok or {},
        "preference_pass": bool(pref_pass),
        "non_preference_pass": bool(non_pref_pass),
        "misspecified_pass": bool(miss_pass),
        "rmse_pass": bool(all(v["pass"] for v in rmse_ok.values())),
        "PASS": bool(overall),
    }
