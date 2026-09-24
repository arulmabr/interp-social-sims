"""Synthetic agents for the B2 recovery study (ICLR_PLAN.md B2). CPU only.

Cumulative prospect theory with v(x) = x^alpha on gains and -lambda(-x)^alpha on
losses, the Tversky-Kahneman weighting function with parameter gamma, and a
logit choice rule carrying temperature, action bias, position bias and label
bias. The utility difference is normalised by the trial's utility range
(contextual utility) so curvature and temperature do not trade off freely.

Two agents are deliberately *not* prospect theory -- mean-variance utility and an
arbitrary monotone choice curve -- so the diagnostics are exercised where the
parametric model is wrong.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.tasks.core import Lottery, Trial

#: Reference agent, the theta0 of B3.2.
ALPHA0, GAMMA0, LAMBDA0 = 0.88, 0.61, 2.25

#: Minimum detectable changes, fixed in plan v4.
MDC: Dict[str, float] = {"alpha": 0.10, "gamma": 0.10, "lambda": 0.30}

#: Choice-rule defaults. These are simulation settings for B2; the thresholds
#: that use them are AUTHOR DECISIONS and are frozen at B6.
TAU0 = 0.25
#: Weight on disadvantageous inequity for the social responder (BD54). The
#: responder's threshold is beta_adv / (1 + 2*beta_adv) as a share of the pie.
BETA0 = 0.60
ACTION0 = 0.0
POSITION0 = 0.0
LABEL0 = 0.0
KAPPA0 = 1.0


@dataclass(frozen=True)
class AgentParams:
    alpha: float = ALPHA0
    gamma: float = GAMMA0
    lam: float = LAMBDA0
    tau: float = TAU0
    action: float = ACTION0          # constant pull toward the risky option
    position: float = POSITION0      # pull toward whichever option is shown second
    label: float = LABEL0            # pull toward the risky option under legacy labels
    kappa: float = KAPPA0            # belief distortion: the *gamble's* x perceived as kappa*x
    kind: str = "cpt"                # "cpt" | "mean_variance" | "monotone"
    mv_b: float = 0.35               # mean-SD risk penalty (dimensionless)
    mono_scale: float = 120.0        # scale of the arbitrary monotone curve
    beta_adv: float = BETA0          # social: weight on being worse off than the proposer

    def as_dict(self) -> Dict[str, float]:
        return {"alpha": self.alpha, "gamma": self.gamma, "lambda": self.lam,
                "tau": self.tau, "action": self.action, "position": self.position,
                "label": self.label, "kappa": self.kappa,
                "beta_adv": self.beta_adv}


# --------------------------------------------------------------------------
# prospect theory
# --------------------------------------------------------------------------

def value(x: np.ndarray, alpha: float, lam: float) -> np.ndarray:
    """v(x) = x^alpha for gains, -lambda(-x)^alpha for losses."""
    x = np.asarray(x, dtype=float)
    out = np.empty_like(x)
    pos, neg = x >= 0, x < 0
    out[pos] = np.power(x[pos], alpha)
    out[neg] = -lam * np.power(-x[neg], alpha)
    return out


def weight(p: np.ndarray, gamma: float) -> np.ndarray:
    """Tversky-Kahneman: w(p) = p^g / (p^g + (1-p)^g)^(1/g)."""
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    num = np.power(p, gamma)
    den = np.power(num + np.power(1.0 - p, gamma), 1.0 / gamma)
    return num / den


def _amounts(lot: Lottery, par: AgentParams) -> List[Tuple[float, float]]:
    """Live (probability, perceived amount) pairs.

    The belief distortion applies to the *gamble's* reward level, which is what
    B1 calls x, and not to the sure amount s. Scaling every amount in a trial by
    kappa would be unidentifiable: with a power value function it multiplies
    both the utility difference and the contextual utility range by kappa^alpha,
    leaving the normalised difference -- and so every choice -- unchanged. A
    distortion that cannot change any behaviour is not an agent type, so the
    scaling is confined to uncertain lotteries. It is therefore identified on
    trials that set a sure amount against a gamble, and not on paired trials,
    where both sides scale together.
    """
    live = [(p, a) for p, a in lot.outcomes if p > 0]
    if len(live) == 1:
        return live
    return [(p, par.kappa * a) for p, a in live]


def cpt_utility(lot: Lottery, par: AgentParams) -> float:
    """Rank- and sign-dependent CPT utility of a lottery.

    Two-outcome gambles are the only shapes B1 generates. For an all-gain or
    all-loss gamble the extreme outcome carries w(p) and the other the
    remainder; for a mixed gamble each side is weighted separately, which is the
    1992 form.
    """
    live = _amounts(lot, par)
    if len(live) == 1:
        return float(value(np.array([live[0][1]]), par.alpha, par.lam)[0])

    (p1, a1), (p2, a2) = sorted(live, key=lambda t: -t[1])   # a1 >= a2
    v1, v2 = value(np.array([a1, a2]), par.alpha, par.lam)

    if a1 >= 0 and a2 >= 0:                 # all gains: best outcome weighted
        w1 = weight(np.array([p1]), par.gamma)[0]
        return float(w1 * v1 + (1.0 - w1) * v2)
    if a1 <= 0 and a2 <= 0:                 # all losses: worst outcome weighted
        w2 = weight(np.array([p2]), par.gamma)[0]
        return float(w2 * v2 + (1.0 - w2) * v1)
    # mixed: each sign weighted on its own probability
    wg = weight(np.array([p1]), par.gamma)[0]
    wl = weight(np.array([p2]), par.gamma)[0]
    return float(wg * v1 + wl * v2)


def mean_variance_utility(lot: Lottery, par: AgentParams) -> float:
    """Mean minus a multiple of the standard deviation.

    The textbook mean-*variance* form is not scale-invariant: variance grows as
    the square of the stake while the mean grows linearly, so with a constant
    penalty the same agent is nearly risk-neutral at $20 and wildly risk-averse
    at $500. Across B1's 25x stake range that produced z running to -90 with an
    SD of 10.3 against CPT's 1.7, and -- worse -- it let one term dominate z, so
    changing that term was indistinguishable from changing the temperature and
    the model-free layer read a preference shift as noise. Penalising the
    standard deviation keeps both terms linear in the stake, makes `mv_b`
    dimensionless, and leaves the family just as non-prospect-theoretic.
    """
    live = _amounts(lot, par)
    xs = np.array([a for _, a in live]); ps = np.array([p for p, _ in live])
    mean = float(np.sum(ps * xs))
    var = float(np.sum(ps * (xs - mean) ** 2))
    return mean - par.mv_b * float(np.sqrt(max(var, 0.0)))


def monotone_utility(lot: Lottery, par: AgentParams) -> float:
    """An arbitrary monotone choice curve: expected tanh of the scaled outcome.

    Monotone in every outcome, so it is a coherent preference, but it is not a
    member of the prospect-theory family at any parameter value.
    """
    live = _amounts(lot, par)
    xs = np.array([a for _, a in live]); ps = np.array([p for p, _ in live])
    return float(np.sum(ps * np.tanh(xs / par.mono_scale)))


def utility(lot: Lottery, par: AgentParams) -> float:
    if par.kind == "cpt":
        return cpt_utility(lot, par)
    if par.kind == "mean_variance":
        return mean_variance_utility(lot, par)
    if par.kind == "monotone":
        return monotone_utility(lot, par)
    raise ValueError(f"unknown agent kind {par.kind!r}")


def _to_utility_scale(amounts: np.ndarray, par: AgentParams) -> np.ndarray:
    """Put raw amounts on the same scale as the family's utility.

    The contextual-utility range has to be measured in the units the utility
    difference is measured in, or the normalisation is a unit conversion rather
    than a normalisation. The monotone family's utility is a tanh, bounded in
    [-1, 1]; dividing its differences by a range in dollars crushed z by about
    two orders of magnitude and left that agent indifferent on every trial
    (z sd 0.0073, P(risky) spread 0.01), which made it useless as the
    misspecified base it exists to be.
    """
    if par.kind == "cpt":
        return value(amounts, par.alpha, par.lam)
    if par.kind == "monotone":
        return np.tanh(amounts / par.mono_scale)
    return np.asarray(amounts, dtype=float)      # mean-variance is in amount units


# --------------------------------------------------------------------------
# the social responder (BD54)
# --------------------------------------------------------------------------
# Prospect theory cannot express this choice. `social.py` renders the responder
# as two degenerate lotteries, so a risk agent sees a sure `offer` against a
# sure 0 and accepts every positive offer. What makes a low offer rejectable is
# the split, which lives in the trial's params and never reaches the Lottery.

def social_split(trial: Trial) -> Optional[Tuple[float, float]]:
    """(pie, offer) for a responder trial, else None."""
    if trial.domain != "social" or not trial.family.endswith("responder"):
        return None
    d = trial.param_dict
    if "pie" not in d or "offer" not in d:
        return None
    return float(d["pie"]), float(d["offer"])


def fehr_schmidt_z(pie: np.ndarray, offer: np.ndarray,
                   par: AgentParams) -> np.ndarray:
    """Accept-minus-reject logit for an inequity-averse responder.

    Accepting leaves the responder with `offer` and the proposer with
    `pie - offer`, so the responder is behind by `pie - 2*offer` whenever the
    offer is under half. Rejecting gives both nothing, which is equal but
    worthless. Dividing by the pie is the social counterpart of contextual
    utility and makes the agent scale invariant across pies.
    """
    seen = par.kappa * offer          # belief: the offer as the responder reads it
    behind = np.maximum(pie - 2.0 * seen, 0.0)
    u_accept = seen - par.beta_adv * behind
    return u_accept / np.where(pie > 1e-9, pie, 1.0) / max(par.tau, 1e-9)


def social_threshold(par: AgentParams) -> float:
    """The offer share at which the responder is indifferent, ignoring biases."""
    b = par.beta_adv
    return float(b / (1.0 + 2.0 * b))


def utility_range(trial: Trial, par: AgentParams) -> float:
    """Contextual utility: the spread of value across everything on offer."""
    amounts = [a for lot in trial.canonical for _, a in _amounts(lot, par)]
    vs = _to_utility_scale(np.array(amounts, dtype=float), par)
    spread = float(vs.max() - vs.min())
    return spread if spread > 1e-9 else 1.0


# --------------------------------------------------------------------------
# the choice rule
# --------------------------------------------------------------------------

def latent_z(trial: Trial, par: AgentParams) -> float:
    """z, the risky-minus-safe logit, before any noise.

    Positive means a pull toward the risky (canonical index 1) option, whatever
    order the options were presented in.
    """
    split = social_split(trial)
    if split is not None:
        pie, offer = split
        z = float(fehr_schmidt_z(np.array(pie), np.array(offer), par))
    else:
        safe, risky = trial.canonical
        diff = utility(risky, par) - utility(safe, par)
        z = diff / utility_range(trial, par) / max(par.tau, 1e-9)
    z += par.action
    # Position bias pulls toward whatever is shown second; under option_order 1
    # the risky option is shown first, so the pull is away from it.
    z += par.position * (1.0 if trial.fmt.option_order == 0 else -1.0)
    # Label bias pulls toward the option labelled "Risky Option".
    z += par.label * (1.0 if trial.fmt.label_set == "legacy" else 0.0)
    return float(z)


def latent_z_batch(trials: Sequence[Trial], par: AgentParams) -> np.ndarray:
    return np.array([latent_z(t, par) for t in trials], dtype=float)


def choice_prob(z: np.ndarray, lapse: float = 0.0) -> np.ndarray:
    """P(risky) from z, optionally with a lapse rate mixing toward 0.5."""
    p = 1.0 / (1.0 + np.exp(-np.clip(z, -60, 60)))
    if lapse > 0:
        p = (1.0 - lapse) * p + lapse * 0.5
    return p


def draw_template_offsets(trials: Sequence[Trial], sd: float,
                          rng: np.random.Generator) -> Dict[str, float]:
    """One offset per instruction template.

    A template effect is a property of the *template*, not of the run, so the
    same draw must be used for the baseline and the intervention condition. If
    it were redrawn, the difference between two independent draws would appear
    in every trial as a constant shift -- which is precisely the signature of an
    action bias, and would make a genuine preference shift look like one.
    """
    return {tid: rng.normal(0.0, sd)
            for tid in sorted({t.fmt.template_id for t in trials})}


def simulate(trials: Sequence[Trial],
             par: AgentParams,
             rng: np.random.Generator,
             template_noise_sd: float = 0.0,
             numerical_noise_sd: float = 0.0,
             lapse: float = 0.0,
             template_offsets: Optional[Dict[str, float]] = None) -> Dict[str, np.ndarray]:
    """Simulate one agent over a trial list.

    Two noise components, added independently to z:

    * ``template_noise_sd`` -- the SD of z across instruction templates. It is a
      *template-level* effect, so one draw is shared by every trial using the
      same template, which is what makes it different from trial noise.
    * ``numerical_noise_sd`` -- independent per-trial noise standing for the
      numerical non-determinism measured on the 70B in bf16 (SD about 0.094 in z
      across batch compositions; amendment item 5). It is drawn per trial
      because reordering a batch perturbs each row on its own.
    """
    z = latent_z_packed(pack(trials), par)

    offsets = template_offsets
    if offsets is None and template_noise_sd > 0:
        offsets = draw_template_offsets(trials, template_noise_sd, rng)
    if offsets:
        z = z + np.array([offsets[t.fmt.template_id] for t in trials])

    if numerical_noise_sd > 0:
        z = z + rng.normal(0.0, numerical_noise_sd, size=len(trials))

    p = choice_prob(z, lapse=lapse)
    choice = (rng.random(len(trials)) < p).astype(int)
    return {"z": z, "p_risky": p, "choice": choice,
            "template_offsets": offsets or {}}


# --------------------------------------------------------------------------
# the agent zoo
# --------------------------------------------------------------------------

def agent_zoo(action_effect: float = 0.6,
              format_effect: float = 0.6,
              kappa_effect: float = 1.35,
              tau_ratio: float = 1.6) -> Dict[str, AgentParams]:
    """Every agent type B2 requires.

    The non-preference agents are matched on *behavioural effect size* rather
    than on parameter size: Gate B2 asks that they be rejected even when they
    move behaviour as much as a preference shift does, which is the only
    comparison that means anything. `match_effect_sizes` does the matching.
    """
    base = AgentParams()
    zoo: Dict[str, AgentParams] = {
        "baseline": base,
        "pref_alpha": replace(base, alpha=ALPHA0 + MDC["alpha"]),
        "pref_gamma": replace(base, gamma=GAMMA0 + MDC["gamma"]),
        "pref_lambda": replace(base, lam=LAMBDA0 + MDC["lambda"]),
        "action": replace(base, action=action_effect),
        "format": replace(base, position=format_effect, label=format_effect),
        "belief": replace(base, kappa=kappa_effect),
        "noise": replace(base, tau=TAU0 * tau_ratio),
        "mean_variance": replace(base, kind="mean_variance"),
        "monotone": replace(base, kind="monotone"),
    }
    return zoo


PREFERENCE_AGENTS = ("pref_alpha", "pref_gamma", "pref_lambda")
NON_PREFERENCE_AGENTS = ("action", "format", "belief", "noise")
MISSPECIFIED_AGENTS = ("mean_variance", "monotone")


def behavioural_effect(trials, par: AgentParams,
                       base: Optional[AgentParams] = None,
                       pk: Optional["Packed"] = None) -> float:
    """Mean absolute change in P(risky) against the baseline agent.

    This is the currency in which non-preference agents are matched to
    preference shifts, so that Gate B2's 95% rejection requirement is a fair
    test. `pk` lets a caller that evaluates this thousands of times -- the
    effect-size bisection does -- pack the trials once instead of once per call.
    """
    base = base or AgentParams()
    if pk is None:
        pk = trials if isinstance(trials, Packed) else pack(trials)
    z0 = latent_z_packed(pk, base)
    z1 = latent_z_packed(pk, par)
    return float(np.mean(np.abs(choice_prob(z1) - choice_prob(z0))))


def match_effect_sizes(trials: Sequence[Trial],
                       target: float,
                       tol: float = 0.002,
                       max_iter: int = 40) -> Dict[str, AgentParams]:
    """Scale each non-preference agent until it moves behaviour by `target`.

    Bisection on the one parameter that defines each agent. Returns the matched
    zoo entries only.
    """
    base = AgentParams()
    knobs = {
        "action": ("action", 0.0, 6.0),
        "format": ("format", 0.0, 6.0),
        "belief": ("kappa", 1.0, 6.0),
        "noise": ("tau", TAU0, TAU0 * 25.0),
    }
    out: Dict[str, AgentParams] = {}
    for name, (knob, lo, hi) in knobs.items():
        def make(v: float) -> AgentParams:
            if knob == "action":
                return replace(base, action=v)
            if knob == "format":
                return replace(base, position=v, label=v)
            if knob == "kappa":
                return replace(base, kappa=v)
            return replace(base, tau=v)

        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            eff = behavioural_effect(trials, make(mid), base)
            if abs(eff - target) < tol:
                break
            if eff < target:
                lo = mid
            else:
                hi = mid
        out[name] = make(0.5 * (lo + hi))
    return out


# --------------------------------------------------------------------------
# vectorised path
# --------------------------------------------------------------------------
# The scalar `latent_z` above is the readable definition and the thing the tests
# check against. Every B1 lottery has at most two outcomes, so the same
# computation packs into flat arrays and runs about a hundred times faster,
# which is what makes the full recovery study a minutes-long CPU job rather than
# a day-long one. `latent_z_packed` is asserted to agree with `latent_z`.

@dataclass(frozen=True)
class Packed:
    """Trials as flat arrays: for each option, the high and low outcome."""
    safe_hi: np.ndarray
    safe_lo: np.ndarray
    safe_phi: np.ndarray
    safe_sure: np.ndarray
    risky_hi: np.ndarray
    risky_lo: np.ndarray
    risky_phi: np.ndarray
    risky_sure: np.ndarray
    order_sign: np.ndarray
    legacy: np.ndarray
    n: int
    #: Social responder trials carry the split, which the option pair loses.
    #: `pie` is 0 and `is_social` False on every risk trial (BD54).
    pie: np.ndarray = None           # type: ignore[assignment]
    offer: np.ndarray = None         # type: ignore[assignment]
    is_social: np.ndarray = None     # type: ignore[assignment]


def _pack_option(lot: Lottery) -> Tuple[float, float, float, bool]:
    live = [(p, a) for p, a in lot.outcomes if p > 0]
    if len(live) == 1:
        a = live[0][1]
        return a, a, 1.0, True
    (p1, a1), (p2, a2) = sorted(live, key=lambda t: -t[1])
    return a1, a2, p1, False


def pack(trials: Sequence[Trial]) -> Packed:
    s_hi, s_lo, s_p, s_sure = [], [], [], []
    r_hi, r_lo, r_p, r_sure = [], [], [], []
    order, legacy = [], []
    pie, offer, social = [], [], []
    for t in trials:
        safe, risky = t.canonical
        a, b, p, sure = _pack_option(safe)
        s_hi.append(a); s_lo.append(b); s_p.append(p); s_sure.append(sure)
        a, b, p, sure = _pack_option(risky)
        r_hi.append(a); r_lo.append(b); r_p.append(p); r_sure.append(sure)
        order.append(1.0 if t.fmt.option_order == 0 else -1.0)
        legacy.append(1.0 if t.fmt.label_set == "legacy" else 0.0)
        sp = social_split(t)
        social.append(sp is not None)
        pie.append(sp[0] if sp else 0.0)
        offer.append(sp[1] if sp else 0.0)
    f = lambda v: np.asarray(v, dtype=float)
    return Packed(f(s_hi), f(s_lo), f(s_p), np.asarray(s_sure, dtype=bool),
                  f(r_hi), f(r_lo), f(r_p), np.asarray(r_sure, dtype=bool),
                  f(order), f(legacy), len(trials),
                  f(pie), f(offer), np.asarray(social, dtype=bool))


def _utility_vec(hi: np.ndarray, lo: np.ndarray, phi: np.ndarray,
                 sure: np.ndarray, par: AgentParams) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Utility of each option, and the perceived amounts for the range."""
    k = np.where(sure, 1.0, par.kappa)          # kappa spares the sure amount
    a_hi, a_lo = hi * k, lo * k
    plo = 1.0 - phi

    if par.kind == "mean_variance":
        mean = phi * a_hi + plo * a_lo
        var = phi * (a_hi - mean) ** 2 + plo * (a_lo - mean) ** 2
        return mean - par.mv_b * np.sqrt(np.clip(var, 0.0, None)), a_hi, a_lo
    if par.kind == "monotone":
        u = phi * np.tanh(a_hi / par.mono_scale) + plo * np.tanh(a_lo / par.mono_scale)
        return u, a_hi, a_lo

    v_hi = value(a_hi, par.alpha, par.lam)
    v_lo = value(a_lo, par.alpha, par.lam)
    w_hi = weight(phi, par.gamma)
    w_lo = weight(plo, par.gamma)

    all_gain = (a_hi >= 0) & (a_lo >= 0)
    all_loss = (a_hi <= 0) & (a_lo <= 0)
    u = np.where(
        all_gain, w_hi * v_hi + (1.0 - w_hi) * v_lo,
        np.where(all_loss, w_lo * v_lo + (1.0 - w_lo) * v_hi,
                 w_hi * v_hi + w_lo * v_lo))
    return u, a_hi, a_lo


def latent_z_packed(pk: Packed, par: AgentParams) -> np.ndarray:
    u_safe, s_hi, s_lo = _utility_vec(pk.safe_hi, pk.safe_lo, pk.safe_phi,
                                      pk.safe_sure, par)
    u_risky, r_hi, r_lo = _utility_vec(pk.risky_hi, pk.risky_lo, pk.risky_phi,
                                       pk.risky_sure, par)
    amounts = np.stack([s_hi, s_lo, r_hi, r_lo])
    vals = _to_utility_scale(amounts, par)
    spread = vals.max(axis=0) - vals.min(axis=0)
    spread = np.where(spread > 1e-9, spread, 1.0)

    z = (u_risky - u_safe) / spread / max(par.tau, 1e-9)
    if pk.is_social is not None and pk.is_social.any():
        z = np.where(pk.is_social, fehr_schmidt_z(pk.pie, pk.offer, par), z)
    z = z + par.action + par.position * pk.order_sign + par.label * pk.legacy
    return z


# --------------------------------------------------------------------------
# bases crossed with interventions (author item 3)
# --------------------------------------------------------------------------
# The two misspecified agents are *base* agents, not interventions. A
# mean-variance agent is not "an intervention that looks odd"; it is a different
# model of the underlying subject, on which the same five interventions can be
# applied. Treating them as interventions asked the wrong question -- whether
# they look like a preference shift -- when the question is whether the
# diagnostics still work when the parametric model is wrong about the subject.

BASES: Tuple[str, ...] = ("cpt", "mean_variance", "monotone")
#: The social base is not crossed with the risk bases; it applies to responder
#: trials only and carries its own preference knob (BD54).
SOCIAL_BASE = "fehr_schmidt"
INTERVENTIONS: Tuple[str, ...] = ("preference", "action", "belief", "noise", "format")

#: On the CPT base a "preference shift" has three possible parameters and Gate
#: B2 needs alpha and gamma separately for their RMSE bars, so the CPT base runs
#: one cell per parameter. Lambda is kept for its own secondary gate and is not
#: part of Gate B2 (logs/B_DEVIATIONS.md).
CPT_PREFERENCE_CELLS: Dict[str, str] = {
    "preference_alpha": "alpha",
    "preference_gamma": "gamma",
    "preference_lambda": "lam",
}
CPT_GATE_PREFERENCE: Tuple[str, ...] = ("preference_alpha", "preference_gamma")
MISSPECIFIED_BASES: Tuple[str, ...] = ("mean_variance", "monotone")

#: The parameter each family expresses a preference change through. CPT shifts
#: alpha, which is what the first preference anchor of B3.2 shifts; the other
#: families have no alpha, so each shifts its own shape parameter.
PREFERENCE_KNOB: Dict[str, str] = {
    "cpt": "alpha", "mean_variance": "mv_b", "monotone": "mono_scale",
    "fehr_schmidt": "beta_adv",
}


def base_scale_report(trials) -> Dict[str, Dict[str, float]]:
    """How steep each base agent's choice function is, on one grid.

    A base agent has to be a plausible subject. One that is indifferent
    everywhere passes every specificity check for free (BD22); one that is
    saturated everywhere is just as useless, and worse, if a single term
    dominates its z then a change in that term is indistinguishable from a
    temperature change and the model-free layer cannot tell a preference shift
    from noise. Both failures are scaling, not modelling.
    """
    pk = trials if isinstance(trials, Packed) else pack(trials)
    out: Dict[str, Dict[str, float]] = {}
    for b in BASES:
        z = latent_z_packed(pk, base_params(b))
        p = choice_prob(z)
        out[b] = {"z_sd": float(z.std()), "z_min": float(z.min()),
                  "z_max": float(z.max()),
                  "p_spread": float(p.max() - p.min()),
                  "p_mean": float(p.mean())}
    return out


def calibrate_mean_variance_b(trials, lo: float = 0.01, hi: float = 0.95,
                              max_iter: int = 60) -> float:
    """The variance penalty that puts the mean-variance base on CPT's scale.

    At `mv_b = 0.01` the variance term swamped the mean term: z ran to -90 with
    an SD of 10.3 against CPT's 1.7, and mean P(risky) was 0.29 rather than
    about a half. That is not just an implausible subject. It is why a
    *preference* change in that family was indistinguishable from a temperature
    change: when one term dominates z, scaling that term is scaling z, so dz
    comes out proportional to z and the model-free layer reads it as noise.
    Matching the SD to CPT's puts the mean and variance terms on comparable
    footing and restores the distinction.
    """
    pk = trials if isinstance(trials, Packed) else pack(trials)
    target = float(latent_z_packed(pk, base_params("cpt")).std())
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        sd = float(latent_z_packed(pk, replace(AgentParams(), kind="mean_variance",
                                               mv_b=mid)).std())
        if abs(sd - target) < 0.01:
            return mid
        if sd < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def base_params(base: str) -> AgentParams:
    """The unmodified agent of each family."""
    if base == "cpt":
        return AgentParams()
    if base in ("mean_variance", "monotone"):
        return replace(AgentParams(), kind=base)
    raise ValueError(f"unknown base {base!r}")


def _set(par: AgentParams, knob: str, value: float) -> AgentParams:
    return replace(par, **{knob: value})


def _solve_for_effect(trials, par0: AgentParams, knob: str,
                      lo: float, hi: float, target: float,
                      tol: float = 0.0015, max_iter: int = 48,
                      pk: Optional["Packed"] = None) -> float:
    """Bisect `knob` until the agent moves behaviour by `target` against `par0`.

    Matching on behavioural effect size rather than on parameter size is what
    makes the comparison between a preference shift and a bias fair: Gate B2
    asks the rule to reject a bias that moves behaviour as much as a preference
    shift does.
    """
    for _ in range(max_iter):
        mid = 0.5 * (lo + hi)
        eff = behavioural_effect(trials, _set(par0, knob, mid), par0, pk=pk)
        if abs(eff - target) < tol:
            return mid
        if eff < target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def build_crossed_zoo(trials, target_effect: Optional[float] = None,
                      base: Optional[AgentParams] = None
                      ) -> Tuple[Dict[Tuple[str, str], AgentParams],
                                 Dict[str, AgentParams],
                                 Dict[str, float]]:
    """Every (base, intervention) pair, matched on behavioural effect size.

    The target effect is CPT's alpha shift at its minimum detectable change, so
    every cell of the grid moves behaviour by about the same amount and any
    difference in how it is classified is a difference in *kind*, not in size.

    Returns (crossed, bases, effects).
    """
    pk = trials if isinstance(trials, Packed) else pack(trials)
    cpt0 = base_params("cpt")
    if target_effect is None:
        target_effect = behavioural_effect(
            trials, replace(cpt0, alpha=ALPHA0 + MDC["alpha"]), cpt0, pk=pk)

    # With a fitted theta0 the CPT base is that agent, not the plan's defaults;
    # the other two families keep their own shapes and are rescaled to it.
    bases = {b: base_params(b) for b in BASES}
    if base is not None:
        bases["cpt"] = replace(base, kind="cpt")
        cpt0 = bases["cpt"]
    crossed: Dict[Tuple[str, str], AgentParams] = {}
    effects: Dict[str, float] = {}

    #: search ranges per family for the preference knob
    pref_range = {"cpt": (ALPHA0, ALPHA0 + 0.60),
                  "mean_variance": (AgentParams().mv_b, AgentParams().mv_b * 2.5),
                  "monotone": (AgentParams().mono_scale, AgentParams().mono_scale * 6.0)}

    for base, par0 in bases.items():
        # The CPT base gets one preference cell per parameter, at the plan's
        # minimum detectable change rather than matched on effect size: those
        # are the shifts Gate B2's RMSE bars are written about.
        ivs = list(INTERVENTIONS)
        if base == "cpt":
            ivs = [i for i in ivs if i != "preference"] + list(CPT_PREFERENCE_CELLS)
        for iv in ivs:
            if iv in CPT_PREFERENCE_CELLS:
                field = CPT_PREFERENCE_CELLS[iv]
                mdc_key = {"alpha": "alpha", "gamma": "gamma", "lam": "lambda"}[field]
                par = _set(par0, field, float(getattr(par0, field)) + MDC[mdc_key])
            elif iv == "preference":
                knob = PREFERENCE_KNOB[base]
                lo, hi = pref_range[base]
                val = _solve_for_effect(trials, par0, knob, lo, hi, target_effect, pk=pk)
                par = _set(par0, knob, val)
            elif iv == "action":
                val = _solve_for_effect(trials, par0, "action", 0.0, 8.0, target_effect, pk=pk)
                par = _set(par0, "action", val)
            elif iv == "belief":
                val = _solve_for_effect(trials, par0, "kappa", 1.0, 8.0, target_effect, pk=pk)
                par = _set(par0, "kappa", val)
            elif iv == "noise":
                val = _solve_for_effect(trials, par0, "tau", TAU0, TAU0 * 40.0,
                                        target_effect, pk=pk)
                par = _set(par0, "tau", val)
            elif iv == "format":
                val = _solve_for_effect(trials, par0, "position", 0.0, 8.0, target_effect, pk=pk)
                par = replace(par0, position=val, label=val)
            else:
                raise ValueError(iv)
            crossed[(base, iv)] = par
            effects[f"{base}/{iv}"] = behavioural_effect(trials, par, par0, pk=pk)

    effects["_target"] = float(target_effect)
    return crossed, bases, effects
