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
    mv_b: float = 0.01               # mean-variance risk penalty
    mono_scale: float = 120.0        # scale of the arbitrary monotone curve

    def as_dict(self) -> Dict[str, float]:
        return {"alpha": self.alpha, "gamma": self.gamma, "lambda": self.lam,
                "tau": self.tau, "action": self.action, "position": self.position,
                "label": self.label, "kappa": self.kappa}


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
    live = _amounts(lot, par)
    xs = np.array([a for _, a in live]); ps = np.array([p for p, _ in live])
    mean = float(np.sum(ps * xs))
    var = float(np.sum(ps * (xs - mean) ** 2))
    return mean - par.mv_b * var


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


def utility_range(trial: Trial, par: AgentParams) -> float:
    """Contextual utility: the spread of value across everything on offer."""
    amounts = [a for lot in trial.canonical for _, a in _amounts(lot, par)]
    vs = value(np.array(amounts), par.alpha, par.lam) if par.kind == "cpt" \
        else np.array(amounts, dtype=float)
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


def behavioural_effect(trials: Sequence[Trial], par: AgentParams,
                       base: Optional[AgentParams] = None) -> float:
    """Mean absolute change in P(risky) against the baseline agent.

    This is the currency in which non-preference agents are matched to
    preference shifts, so that Gate B2's 95% rejection requirement is a fair test.
    """
    base = base or AgentParams()
    z0 = latent_z_batch(trials, base)
    z1 = latent_z_batch(trials, par)
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
    for t in trials:
        safe, risky = t.canonical
        a, b, p, sure = _pack_option(safe)
        s_hi.append(a); s_lo.append(b); s_p.append(p); s_sure.append(sure)
        a, b, p, sure = _pack_option(risky)
        r_hi.append(a); r_lo.append(b); r_p.append(p); r_sure.append(sure)
        order.append(1.0 if t.fmt.option_order == 0 else -1.0)
        legacy.append(1.0 if t.fmt.label_set == "legacy" else 0.0)
    f = lambda v: np.asarray(v, dtype=float)
    return Packed(f(s_hi), f(s_lo), f(s_p), np.asarray(s_sure, dtype=bool),
                  f(r_hi), f(r_lo), f(r_p), np.asarray(r_sure, dtype=bool),
                  f(order), f(legacy), len(trials))


def _utility_vec(hi: np.ndarray, lo: np.ndarray, phi: np.ndarray,
                 sure: np.ndarray, par: AgentParams) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Utility of each option, and the perceived amounts for the range."""
    k = np.where(sure, 1.0, par.kappa)          # kappa spares the sure amount
    a_hi, a_lo = hi * k, lo * k
    plo = 1.0 - phi

    if par.kind == "mean_variance":
        mean = phi * a_hi + plo * a_lo
        var = phi * (a_hi - mean) ** 2 + plo * (a_lo - mean) ** 2
        return mean - par.mv_b * var, a_hi, a_lo
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
    if par.kind == "cpt":
        vals = value(amounts, par.alpha, par.lam)
    else:
        vals = amounts
    spread = vals.max(axis=0) - vals.min(axis=0)
    spread = np.where(spread > 1e-9, spread, 1.0)

    z = (u_risky - u_safe) / spread / max(par.tau, 1e-9)
    z = z + par.action + par.position * pk.order_sign + par.label * pk.legacy
    return z
