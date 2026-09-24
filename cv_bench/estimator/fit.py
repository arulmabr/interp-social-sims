"""Parametric decomposition for B2 (ICLR_PLAN.md B2). CPU only.

Nested extensions of a baseline fit: `preference` frees (alpha, gamma, lambda),
`action` frees the action bias, `format` frees position and label bias, `belief`
frees kappa, `noise` frees tau. Shares come from predictive log-likelihood on
held-out reward levels, and action against preference is compared by a paired
cluster bootstrap over reward level x template with the Vuong statistic beside it.
"""

from __future__ import annotations

from dataclasses import replace
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
from scipy.optimize import minimize

from cv_bench.estimator.agents import (
    AgentParams, Packed, choice_prob, latent_z_packed, pack)
from cv_bench.tasks.core import Trial

#: Which parameters each nested model frees, relative to the baseline fit.
FREE_SETS: Dict[str, Tuple[str, ...]] = {
    "baseline": (),
    "preference": ("alpha", "gamma", "lam"),
    "action": ("action",),
    "format": ("position", "label"),
    "belief": ("kappa",),
    "noise": ("tau",),
}

#: The same five families for the social responder (BD54). Preference is the
#: inequity weight rather than the three prospect-theory shape parameters;
#: everything else carries over unchanged, because action, format and noise
#: enter the latent the same way in both domains and belief is the offer as
#: the responder reads it.
SOCIAL_FREE_SETS: Dict[str, Tuple[str, ...]] = {
    "baseline": (),
    "preference": ("beta_adv",),
    "action": ("action",),
    "format": ("position", "label"),
    "belief": ("kappa",),
    "noise": ("tau",),
}

BOUNDS: Dict[str, Tuple[float, float]] = {
    # gamma's upper bound was 1.60 and the B2-cal refit landed exactly on it,
    # which makes the value a statement about the bound rather than about the
    # model. Widened so the optimiser can say where it actually wants to be; if
    # it rails again the parameter is genuinely unidentified and is reported as
    # such rather than quoted. These are optimiser bounds, not pre-registered
    # thresholds -- no gate criterion moves.
    "alpha": (0.20, 2.50), "gamma": (0.25, 4.00), "lam": (0.50, 6.00),
    "tau": (0.02, 4.00), "action": (-6.0, 6.0), "position": (-6.0, 6.0),
    "label": (-6.0, 6.0), "kappa": (0.20, 5.00), "lapse": (0.0, 0.40),
    # Social. beta_adv is a weight on being behind, so it is non-negative; the
    # upper bound is well clear of any threshold the 0..1 offer grid can show,
    # since threshold = b/(1+2b) approaches 0.5 from below as b grows.
    "beta_adv": (0.0, 8.00),
}


# --------------------------------------------------------------------------
# reward levels and clusters
# --------------------------------------------------------------------------

def reward_level_rank(trials: Sequence[Trial]) -> np.ndarray:
    """Rank of each trial's reward level within its own cell.

    A cell is (family, p, s) where those exist, so the rank is the position of
    the trial's x on that cell's grid. Used to hold out alternate levels.
    """
    keys: Dict[Tuple, List[float]] = {}
    for t in trials:
        pr = t.param_dict
        cell = (t.family, pr.get("p"), pr.get("s"), pr.get("m"), pr.get("L"))
        level = pr.get("x", pr.get("d2", pr.get("ratio", pr.get("offer", 0.0))))
        keys.setdefault(cell, []).append(float(level))
    order = {cell: {v: i for i, v in enumerate(sorted(set(vs)))}
             for cell, vs in keys.items()}
    out = []
    for t in trials:
        pr = t.param_dict
        cell = (t.family, pr.get("p"), pr.get("s"), pr.get("m"), pr.get("L"))
        level = pr.get("x", pr.get("d2", pr.get("ratio", pr.get("offer", 0.0))))
        out.append(order[cell][float(level)])
    return np.array(out, dtype=int)


def heldout_mask(trials: Sequence[Trial]) -> np.ndarray:
    """Alternate reward levels within each cell are held out for prediction."""
    return (reward_level_rank(trials) % 2) == 1


def cluster_ids(trials: Sequence[Trial]) -> np.ndarray:
    """Clusters for the bootstrap: reward level x template."""
    rank = reward_level_rank(trials)
    tpl = {tid: i for i, tid in enumerate(sorted({t.fmt.template_id for t in trials}))}
    return np.array([r * 1000 + tpl[t.fmt.template_id] for r, t in zip(rank, trials)])


# --------------------------------------------------------------------------
# likelihood
# --------------------------------------------------------------------------

def _apply(par: AgentParams, free: Sequence[str], vec: np.ndarray) -> AgentParams:
    kw = {name: float(v) for name, v in zip(free, vec) if name != "lapse"}
    return replace(par, **kw) if kw else par


def template_index(trials: Sequence[Trial]) -> Tuple[np.ndarray, List[str]]:
    """Per-trial template index and the template ids, in a stable order."""
    ids = sorted({t.fmt.template_id for t in trials})
    lookup = {tid: i for i, tid in enumerate(ids)}
    return np.array([lookup[t.fmt.template_id] for t in trials], dtype=int), ids


def log_likelihood(pk: Packed, observed: np.ndarray,
                   par: AgentParams, lapse: float = 0.0,
                   offset: Optional[np.ndarray] = None,
                   observe: str = "choice", sigma: float = 1.0) -> float:
    """Log-likelihood of `observed` under `par`.

    Two observation modes, because the two response formats give different data.
    ``choice`` treats each row as one Bernoulli draw, which is what a sampled
    generation gives. ``logit`` treats each row as a noisy reading of z itself,
    which is what the logit readout gives and what the plan's own notation
    assumes when it writes "z the risky-minus-safe logit and dz its change".
    Fitting binary choices when z is what the instrument returns throws away
    most of the information in the measurement.
    """
    z = latent_z_packed(pk, par)
    if offset is not None:
        z = z + offset
    if observe == "logit":
        r = np.asarray(observed, dtype=float) - z
        return float(-0.5 * np.sum(r * r) / max(sigma, 1e-9) ** 2)
    p = np.clip(choice_prob(z, lapse=lapse), 1e-9, 1 - 1e-9)
    return float(np.sum(observed * np.log(p) + (1 - observed) * np.log(1 - p)))


def fit(trials: Sequence[Trial],
        choices: np.ndarray,
        free: Sequence[str],
        init: AgentParams,
        dominated_policy: str = "exclude",
        dominated: Optional[np.ndarray] = None,
        restarts: int = 3,
        seed: int = 0,
        free_templates: bool = False,
        template_offsets: Optional[Dict[str, float]] = None,
        observe: str = "choice",
        sigma: float = 1.0) -> Tuple[AgentParams, float, float]:
    """Maximum likelihood over `free`. Returns (params, lapse, log-likelihood).

    ``dominated_policy`` is fixed in advance by BD9: "exclude" drops the flagged
    dominated trials from the likelihood entirely, "lapse" keeps them and frees
    a lapse rate in the choice rule.

    ``free_templates`` adds one intercept per instruction template, the first
    held at zero for identifiability. Without it the template-level variation
    the plan asks B2 to simulate is unmodelled misfit, and the comparison
    between nested models is decided by which one best absorbs that misfit
    rather than by the effect under study. ``template_offsets`` supplies
    already-estimated intercepts instead, which is how the baseline condition's
    estimates are carried into the intervention fits.
    """
    trials = list(trials)
    choices = np.asarray(choices, dtype=float if observe == "logit" else int)
    if dominated is None:
        dominated = np.array([t.dominant is not None for t in trials])

    free = list(free)
    if dominated_policy == "exclude":
        keep = ~dominated
        use_trials = [t for t, k in zip(trials, keep) if k]
        use_choices = choices[keep]
    elif dominated_policy == "lapse":
        use_trials, use_choices = trials, choices
        if "lapse" not in free:
            free = free + ["lapse"]
    else:
        raise ValueError(f"unknown dominated_policy {dominated_policy!r}")

    pk = pack(use_trials)
    tpl_idx, tpl_ids = template_index(use_trials)

    fixed_offset = None
    if template_offsets:
        fixed_offset = np.array([template_offsets.get(t.fmt.template_id, 0.0)
                                 for t in use_trials], dtype=float)

    n_tpl_free = (len(tpl_ids) - 1) if free_templates else 0
    if not free and not n_tpl_free:
        return init, 0.0, log_likelihood(pk, use_choices, init, offset=fixed_offset,
                                         observe=observe, sigma=sigma)
    if len(use_trials) == 0:
        return init, 0.0, float("-nan")

    bounds = [BOUNDS[name] for name in free] + [(-4.0, 4.0)] * n_tpl_free
    start = []
    for name in free:
        if name == "lapse":
            start.append(0.02)
        else:
            start.append(float(getattr(init, name)))
    start += [0.0] * n_tpl_free

    def offsets_from(vec: np.ndarray) -> Optional[np.ndarray]:
        if not n_tpl_free:
            return fixed_offset
        vals = np.concatenate([[0.0], vec[len(free):]])
        off = vals[tpl_idx]
        return off if fixed_offset is None else off + fixed_offset

    def nll(vec: np.ndarray) -> float:
        lapse = 0.0
        if "lapse" in free:
            lapse = float(vec[free.index("lapse")])
        par = _apply(init, free, vec[:len(free)])
        val = -log_likelihood(pk, use_choices, par, lapse=lapse,
                              offset=offsets_from(vec), observe=observe, sigma=sigma)
        return val if np.isfinite(val) else 1e12

    rng = np.random.default_rng(seed)
    best = None
    for r in range(max(1, restarts)):
        x0 = np.array(start, dtype=float)
        if r > 0:
            lo = np.array([b[0] for b in bounds]); hi = np.array([b[1] for b in bounds])
            x0 = np.clip(x0 + rng.normal(0, 0.15, size=len(x0)) * (hi - lo), lo, hi)
        res = minimize(nll, x0, method="L-BFGS-B", bounds=bounds)
        if best is None or res.fun < best.fun:
            best = res

    lapse = float(best.x[free.index("lapse")]) if "lapse" in free else 0.0
    par = _apply(init, free, best.x[:len(free)])
    if n_tpl_free:
        vals = np.concatenate([[0.0], best.x[len(free):]])
        fit.last_template_offsets = {tid: float(v) for tid, v in zip(tpl_ids, vals)}
    else:
        fit.last_template_offsets = dict(template_offsets or {})
    return par, lapse, float(-best.fun)


# --------------------------------------------------------------------------
# model comparison
# --------------------------------------------------------------------------

def pointwise_ll(pk: Packed, observed: np.ndarray,
                 par: AgentParams, lapse: float = 0.0,
                 offset: Optional[np.ndarray] = None,
                 observe: str = "choice", sigma: float = 1.0) -> np.ndarray:
    z = latent_z_packed(pk, par)
    if offset is not None:
        z = z + offset
    if observe == "logit":
        r = np.asarray(observed, dtype=float) - z
        return -0.5 * (r * r) / max(sigma, 1e-9) ** 2
    p = np.clip(choice_prob(z, lapse=lapse), 1e-9, 1 - 1e-9)
    return observed * np.log(p) + (1 - observed) * np.log(1 - p)


def fit_all_models(trials: Sequence[Trial],
                   choices: np.ndarray,
                   init: AgentParams,
                   dominated_policy: str = "exclude",
                   seed: int = 0,
                   template_offsets: Optional[Dict[str, float]] = None,
                   observe: str = "choice",
                   sigma: float = 1.0,
                   free_sets: Optional[Dict[str, Tuple[str, ...]]] = None,
                   ) -> Dict[str, Dict[str, object]]:
    """Fit every nested model on the training levels, score on the held-out ones."""
    free_sets = FREE_SETS if free_sets is None else free_sets
    trials = list(trials)
    choices = np.asarray(choices, dtype=float if observe == "logit" else int)
    held = heldout_mask(trials)
    tr = [t for t, h in zip(trials, held) if not h]
    te = [t for t, h in zip(trials, held) if h]
    ctr, cte = choices[~held], choices[held]

    out: Dict[str, Dict[str, object]] = {}
    for name, free in free_sets.items():
        par, lapse, ll_train = fit(tr, ctr, free, init,
                                   dominated_policy=dominated_policy, seed=seed,
                                   template_offsets=template_offsets,
                                   observe=observe, sigma=sigma)
        dom_te = np.array([t.dominant is not None for t in te])
        if dominated_policy == "exclude":
            keep = ~dom_te
            te_use = [t for t, k in zip(te, keep) if k]
            cte_use = cte[keep]
        else:
            te_use, cte_use = te, cte
        off_te = None
        if template_offsets:
            off_te = np.array([template_offsets.get(t.fmt.template_id, 0.0)
                               for t in te_use], dtype=float)
        pw = pointwise_ll(pack(te_use), cte_use, par, lapse=lapse, offset=off_te,
                          observe=observe, sigma=sigma)
        out[name] = {"params": par, "lapse": lapse, "ll_train": ll_train,
                     "ll_test": float(np.sum(pw)), "pointwise": pw,
                     "n_free": len(free) + (1 if dominated_policy == "lapse" else 0)}
    return out


def model_shares(fits: Dict[str, Dict[str, object]]) -> Dict[str, float]:
    """Akaike-style weights over predictive log-likelihood on held-out levels.

    The baseline is excluded: the question is which *kind of change* explains
    the intervention, not whether anything changed at all.
    """
    names = [n for n in fits if n != "baseline"]
    lls = np.array([fits[n]["ll_test"] for n in names], dtype=float)
    lls = np.where(np.isfinite(lls), lls, -1e12)
    w = np.exp(lls - lls.max())
    w = w / w.sum()
    return {n: float(v) for n, v in zip(names, w)}


def vuong(fits: Dict[str, Dict[str, object]], a: str, b: str) -> Dict[str, float]:
    """Vuong statistic for non-nested model `a` against `b` on held-out levels."""
    pa = np.asarray(fits[a]["pointwise"], dtype=float)
    pb = np.asarray(fits[b]["pointwise"], dtype=float)
    n = min(len(pa), len(pb))
    d = pa[:n] - pb[:n]
    sd = float(np.std(d, ddof=1))
    if sd < 1e-12 or n < 2:
        return {"statistic": 0.0, "n": float(n)}
    return {"statistic": float(np.mean(d) * np.sqrt(n) / sd), "n": float(n)}


def cluster_bootstrap(trials: Sequence[Trial],
                      fits: Dict[str, Dict[str, object]],
                      a: str, b: str,
                      n_boot: int = 400,
                      seed: int = 0) -> Dict[str, float]:
    """Paired cluster bootstrap of the held-out LL difference, a minus b.

    Clusters are reward level x template, so a template that happens to be easy
    does not count as independent evidence at every reward level.
    """
    held = heldout_mask(list(trials))
    te = [t for t, h in zip(trials, held) if h]
    dom = np.array([t.dominant is not None for t in te])
    pa = np.asarray(fits[a]["pointwise"], dtype=float)
    pb = np.asarray(fits[b]["pointwise"], dtype=float)
    if len(pa) != len(te):                 # the exclude policy dropped dominated rows
        te = [t for t, d in zip(te, dom) if not d]
    if len(pa) != len(te):
        return {"mean": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan"),
                "p_a_better": float("nan")}
    cl = cluster_ids(te)
    uniq = np.unique(cl)
    idx_by_cluster = {c: np.flatnonzero(cl == c) for c in uniq}
    d = pa - pb
    rng = np.random.default_rng(seed)
    draws = np.empty(n_boot)
    for i in range(n_boot):
        pick = rng.choice(uniq, size=len(uniq), replace=True)
        sel = np.concatenate([idx_by_cluster[c] for c in pick])
        draws[i] = float(np.sum(d[sel]))
    return {"mean": float(np.mean(draws)),
            "ci_lo": float(np.percentile(draws, 2.5)),
            "ci_hi": float(np.percentile(draws, 97.5)),
            "p_a_better": float(np.mean(draws > 0))}
