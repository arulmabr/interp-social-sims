"""Model-free fingerprint D1-D7 for B2 (ICLR_PLAN.md B2). CPU only.

This is the co-primary layer. It makes no prospect-theory assumption, so it
still says something when the parametric model is wrong -- which is exactly the
case the two misspecified agents are there to create.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.estimator.agents import (
    AgentParams, choice_prob, latent_z_packed, pack, value)
from cv_bench.tasks.core import Trial

TRANSFER_BAND = (0.8, 1.25)


def _safe_ratio(a: float, b: float) -> float:
    return float(a / b) if abs(b) > 1e-12 else float("nan")


# -- D1 ---------------------------------------------------------------------

def d1_dominance_violations(trials: Sequence[Trial], choice: np.ndarray) -> float:
    """Share of catch trials on which the dominated option was chosen."""
    idx = [i for i, t in enumerate(trials) if t.is_catch and t.dominant is not None]
    if not idx:
        return float("nan")
    wrong = 0
    for i in idx:
        chose_risky = bool(choice[i])
        dominated_is_risky = trials[i].dominant == 0     # safe dominates -> risky is wrong
        if chose_risky == dominated_is_risky:
            wrong += 1
    return wrong / len(idx)


# -- D2 ---------------------------------------------------------------------

def _design(trials: Sequence[Trial],
            z_base: Optional[np.ndarray] = None) -> Tuple[np.ndarray, List[str]]:
    """Constant, format terms, payoff terms, and the baseline z itself.

    The baseline z column is what separates a temperature change from a
    preference change on this layer: raising tau rescales every z toward zero,
    so dz loads on z itself, while a preference change alters how dz depends on
    the payoff terms.
    """
    order = np.array([1.0 if t.fmt.option_order == 0 else -1.0 for t in trials])
    label = np.array([1.0 if t.fmt.label_set == "legacy" else 0.0 for t in trials])
    p = np.array([t.param_dict.get("p", 0.5) for t in trials])
    logxs = []
    for t in trials:
        pr = t.param_dict
        x, s = pr.get("x"), pr.get("s")
        logxs.append(np.log(x / s) if x and s and x > 0 and s > 0 else 0.0)
    logxs = np.array(logxs)
    loss = np.array([1.0 if t.family in ("sure_loss",) else 0.0 for t in trials])
    mixed = np.array([1.0 if t.family == "mixed" else 0.0 for t in trials])
    cols = [np.ones(len(trials)), order, label, logxs, p, loss, mixed]
    names = ["const", "order", "label", "log_x_over_s", "p", "loss_frame", "mixed_frame"]
    if z_base is not None:
        cols.append(np.asarray(z_base, dtype=float))
        names.append("z_base")
    return np.column_stack(cols), names


def d2_variance_decomposition(trials: Sequence[Trial],
                              dz: np.ndarray,
                              z_base: Optional[np.ndarray] = None) -> Dict[str, float]:
    """Split the variance of the change in z into action, format and payoff parts.

    An action bias is a constant shift, so it loads on `const`; a format bias
    loads on order and label; a genuine preference change loads on the payoff
    terms, because it changes how the reward level matters.
    """
    X, names = _design(trials, z_base)
    coef, *_ = np.linalg.lstsq(X, dz, rcond=None)
    total = float(np.var(dz))
    groups = {"action": ["const"], "format": ["order", "label"],
              "payoff": ["log_x_over_s", "p", "loss_frame", "mixed_frame"]}
    if z_base is not None:
        groups["scale"] = ["z_base"]
    out: Dict[str, float] = {}
    for g, cols in groups.items():
        idx = [names.index(c) for c in cols]
        contrib = X[:, idx] @ coef[idx]
        # A constant contributes to the mean, not the variance; report its
        # squared magnitude relative to the total spread so it is still visible.
        out[f"{g}_var"] = float(np.var(contrib)) if g != "action" else float(np.mean(contrib) ** 2)
    denom = sum(out.values()) or 1.0
    for g in groups:
        out[f"{g}_share"] = out[f"{g}_var"] / denom
    out["total_var"] = total
    out["mean_dz"] = float(np.mean(dz))
    return out


# -- D3 ---------------------------------------------------------------------

def d3_paired_shift(trials: Sequence[Trial], p_base: np.ndarray,
                    p_int: np.ndarray) -> float:
    """Change in the probability of taking the wider lottery on paired trials."""
    idx = [i for i, t in enumerate(trials) if t.family == "paired"]
    if not idx:
        return float("nan")
    return float(np.mean(p_int[idx]) - np.mean(p_base[idx]))


# -- D4 ---------------------------------------------------------------------

def certainty_equivalent(trials: Sequence[Trial], par: AgentParams) -> np.ndarray:
    """The agent's stated CE for each trial's risky option.

    CE is the sure amount whose value matches the gamble's, inverting v on the
    gain side. Trials whose gamble can lose are left as NaN: a negative CE is
    not what B1's stated-CE question asks for.
    """
    pk = pack(trials)
    u, _, _ = _risky_utility(pk, par)
    out = np.where(u >= 0, np.power(np.clip(u, 0, None), 1.0 / max(par.alpha, 1e-6)),
                   np.nan)
    can_lose = np.minimum(pk.risky_hi, pk.risky_lo) < 0
    return np.where(can_lose, np.nan, out)


def _risky_utility(pk, par):
    from cv_bench.estimator.agents import _utility_vec
    return _utility_vec(pk.risky_hi, pk.risky_lo, pk.risky_phi, pk.risky_sure, par)


def d4_ce_vs_choice(trials: Sequence[Trial],
                    truth_base: AgentParams, truth_int: AgentParams,
                    fitted_base: AgentParams, fitted_int: AgentParams) -> Dict[str, float]:
    """Stated-CE shift against the shift the choice-based fit predicts."""
    ce_b = certainty_equivalent(trials, truth_base)
    ce_i = certainty_equivalent(trials, truth_int)
    pred_b = certainty_equivalent(trials, fitted_base)
    pred_i = certainty_equivalent(trials, fitted_int)
    ok = np.isfinite(ce_b) & np.isfinite(ce_i) & np.isfinite(pred_b) & np.isfinite(pred_i)
    if ok.sum() < 5:
        return {"observed": float("nan"), "predicted": float("nan"),
                "ratio": float("nan"), "agree": float("nan")}
    obs = float(np.mean(ce_i[ok] - ce_b[ok]))
    pred = float(np.mean(pred_i[ok] - pred_b[ok]))
    ratio = _safe_ratio(obs, pred)
    agree = float(TRANSFER_BAND[0] <= ratio <= TRANSFER_BAND[1]) if np.isfinite(ratio) else 0.0
    # A shift of essentially zero in both is agreement, not a ratio of 0/0.
    if abs(obs) < 1e-3 and abs(pred) < 1e-3:
        ratio, agree = 1.0, 1.0
    return {"observed": obs, "predicted": pred, "ratio": ratio, "agree": agree}


# -- D5 ---------------------------------------------------------------------

def d5_format_transfer(trials: Sequence[Trial], dz: np.ndarray) -> Dict[str, float]:
    """Is the effect the same size in each format? The band is 0.8-1.25.

    A real preference change should survive relabelling and reordering; a format
    bias should not.

    The ratio is taken on the mean change in z, not on the change in choice
    probability. A probability difference is squashed by the logistic and is
    small -- a few points -- so the ratio of two of them is the ratio of two
    noisy small numbers and swings far outside the band on nothing but noise. It
    put a genuine preference shift outside the band about half the time. The
    plan's other diagnostics are stated on dz for the same reason.
    """
    def effect(mask: np.ndarray) -> float:
        if mask.sum() == 0:
            return float("nan")
        return float(np.mean(dz[mask]))

    legacy = np.array([t.fmt.label_set == "legacy" for t in trials])
    order0 = np.array([t.fmt.option_order == 0 for t in trials])
    # With no format variation there is nothing to transfer between, and a
    # silent NaN here would fail every trial's transfer criterion and make the
    # whole decision rule read "nothing is preference-like". Say so instead.
    if len(np.unique(legacy)) < 2 or len(np.unique(order0)) < 2:
        return {"in_band": float("nan"), "ratio_worst": float("nan"),
                "no_format_variation": 1.0}
    e_leg, e_neu = effect(legacy), effect(~legacy)
    e_o0, e_o1 = effect(order0), effect(~order0)
    # A ratio is meaningless when the denominator is essentially zero: no effect
    # in either format is perfect transfer, not a failure of it.
    if max(abs(e_leg), abs(e_neu), abs(e_o0), abs(e_o1)) < 1e-4:
        return {"effect_legacy": e_leg, "effect_neutral": e_neu,
                "effect_order0": e_o0, "effect_order1": e_o1,
                "ratio_label": 1.0, "ratio_order": 1.0,
                "ratio_worst": 1.0, "in_band": 1.0}
    r_label = _safe_ratio(e_neu, e_leg)
    r_order = _safe_ratio(e_o1, e_o0)
    ratios = [r for r in (r_label, r_order) if np.isfinite(r)]
    worst = min(ratios, key=lambda r: min(r, 1.0 / r) if r > 0 else -1) if ratios else float("nan")
    in_band = float(all(TRANSFER_BAND[0] <= r <= TRANSFER_BAND[1] for r in ratios)) \
        if ratios else 0.0
    return {"effect_legacy": e_leg, "effect_neutral": e_neu,
            "effect_order0": e_o0, "effect_order1": e_o1,
            "ratio_label": r_label, "ratio_order": r_order,
            "ratio_worst": worst, "in_band": in_band}


# -- D6 ---------------------------------------------------------------------

def d6_recall(trials: Sequence[Trial], par: AgentParams) -> Dict[str, float]:
    """Recall of x and s, and what a fact probe would decode.

    A belief-distorted agent perceives the gamble's x as kappa*x, so it both
    misreports x and has kappa decoded from its activations, while the sure
    amount s is unaffected. That asymmetry is what separates belief distortion
    from a preference change on this layer.
    """
    xs, ss = [], []
    for t in trials:
        pr = t.param_dict
        if "x" in pr and pr["x"] > 0:
            xs.append(pr["x"])
        if "s" in pr and pr["s"] > 0:
            ss.append(pr["s"])
    if not xs:
        return {"x_ratio": float("nan"), "s_ratio": float("nan"), "intact": float("nan")}
    x_ratio = float(par.kappa)          # reported x / true x
    s_ratio = 1.0                       # the sure amount is never distorted
    intact = float(abs(x_ratio - 1.0) < 0.05 and abs(s_ratio - 1.0) < 0.05)
    return {"x_ratio": x_ratio, "s_ratio": s_ratio, "intact": intact,
            "n_x": float(len(xs)), "n_s": float(len(ss))}


# -- D7 ---------------------------------------------------------------------

def switching_points(trials: Sequence[Trial], p_risky: np.ndarray) -> Dict[Tuple, float]:
    """Interpolated x where P(risky) crosses 0.5, per (p, s) cell, on sure-gain."""
    cells: Dict[Tuple, List[Tuple[float, float]]] = {}
    for t, q in zip(trials, p_risky):
        if t.family != "sure_gain":
            continue
        pr = t.param_dict
        cells.setdefault((pr["p"], pr["s"]), []).append((pr["x"], float(q)))
    out: Dict[Tuple, float] = {}
    for cell, pts in cells.items():
        agg: Dict[float, List[float]] = {}
        for x, q in pts:
            agg.setdefault(x, []).append(q)
        xs = sorted(agg)
        qs = [float(np.mean(agg[x])) for x in xs]
        cross = None
        for i in range(len(xs) - 1):
            if (qs[i] - 0.5) * (qs[i + 1] - 0.5) <= 0 and qs[i + 1] != qs[i]:
                frac = (0.5 - qs[i]) / (qs[i + 1] - qs[i])
                cross = xs[i] + frac * (xs[i + 1] - xs[i])
                break
        if cross is not None:
            out[cell] = cross
    return out


def d7_stake_stability(trials: Sequence[Trial], p_base: np.ndarray,
                       p_int: np.ndarray) -> Dict[str, float]:
    """Is the shift in the normalised switching point n*/s the same at every stake?

    A preference change scales with the stake; an additive bias does not.
    """
    sb = switching_points(trials, p_base)
    si = switching_points(trials, p_int)
    shifts: Dict[float, List[float]] = {}
    for cell in set(sb) & set(si):
        p, s = cell
        shifts.setdefault(s, []).append((si[cell] - sb[cell]) / s)
    per_stake = {s: float(np.mean(v)) for s, v in shifts.items() if v}
    if len(per_stake) < 2:
        return {"n_stakes": float(len(per_stake)), "cv": float("nan"),
                "mean_shift": float(np.mean(list(per_stake.values()))) if per_stake else float("nan")}
    vals = np.array(list(per_stake.values()))
    mean = float(np.mean(vals))
    cv = float(np.std(vals) / abs(mean)) if abs(mean) > 1e-6 else float("nan")
    return {"n_stakes": float(len(per_stake)), "cv": cv, "mean_shift": mean,
            **{f"shift_s{int(s)}": v for s, v in sorted(per_stake.items())}}


# -- the whole fingerprint --------------------------------------------------

def modelfree_classify(fp: Dict[str, object]) -> str:
    """Name the intervention from the model-free layer alone.

    Author item 3 requires this layer to classify the interventions correctly
    even on a base agent the parametric model is wrong about, so it may not lean
    on the parametric fit at all. The order matters: belief and format announce
    themselves on dedicated diagnostics, and only what survives those is sorted
    by where the variance of dz went.
    """
    if fp["D6_recall"].get("intact", 1.0) == 0.0:
        return "belief"
    if fp["D5_format"].get("in_band", 1.0) == 0.0:
        return "format"
    v = fp["D2_variance"]
    shares = {"action": v.get("action_share", 0.0),
              "payoff": v.get("payoff_share", 0.0),
              "scale": v.get("scale_share", 0.0)}
    top = max(shares, key=shares.get)
    return {"action": "action", "payoff": "preference", "scale": "noise"}[top]


def fingerprint(trials: Sequence[Trial],
                truth_base: AgentParams, truth_int: AgentParams,
                fitted_base: AgentParams, fitted_int: AgentParams,
                choice_int: np.ndarray,
                p_base: np.ndarray, p_int: np.ndarray,
                dz: np.ndarray,
                z_base: Optional[np.ndarray] = None) -> Dict[str, object]:
    return {
        "D1_dominance": d1_dominance_violations(trials, choice_int),
        "D2_variance": d2_variance_decomposition(trials, dz, z_base),
        "D3_paired_shift": d3_paired_shift(trials, p_base, p_int),
        "D4_ce": d4_ce_vs_choice(trials, truth_base, truth_int, fitted_base, fitted_int),
        "D5_format": d5_format_transfer(trials, dz),
        "D6_recall": d6_recall(trials, truth_int),
        "D7_stakes": d7_stake_stability(trials, p_base, p_int),
    }
