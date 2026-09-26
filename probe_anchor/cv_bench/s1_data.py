"""Shared loaders and statistics for the S1 analyses of existing results.

Read-only. CPU only. No model, no network, no test split (none exists yet).

Every S1 curve is reduced to one representation:

    Curve(stack, game, condition, dose, xs, ys, n_per_x, trials)

`trials` is the list of (x, outcome) pairs, so an interval can be resampled at
either the trial level or the reward level.
"""
from __future__ import annotations

import collections
import csv
import json
import math
import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
csv.field_size_limit(10_000_000)

# The combined logs are the repository's own, so walk up to whichever ancestor
# holds cleaned/. ROOT itself satisfies this when run from the repository root.
REPO = next((p for p in [ROOT, *ROOT.parents] if (p / "cleaned").is_dir()), ROOT)

BEHAVIOURAL = REPO / "cleaned/behavioral_games_combined.csv"
PROBE_JSON = REPO / "Probes/raw_data/probe_results_final.json"
CREATIVITY = REPO / "cleaned/creativity_evals_combined.csv"

# The sure amount in the legacy lottery, in tokens. Everything below it is a
# strictly dominated gamble; everything below twice it loses in expectation.
SURE_AMOUNT = 50.0
PIE = 100.0

# Which conditions belong to which inference stack. Stack names are used as a
# hard barrier: nothing in S1 compares across them (GATE_S0_RESPONSE P2).
HOSTED_LOTTERY = {"baseline", "barely_prompting", "slightly_prompting", "lite_steering", "steering"}
HOSTED_ULTIMATUM = {"baseline", "prompting", "steering"}
VLLM = {
    "baseline_rp", "persona", "cot", "fewshot",
    "fewshot_cot_dose000", "fewshot_cot_dose025", "fewshot_cot_dose050",
    "fewshot_cot_dose075", "fewshot_cot_dose100",
}

# The unsteered / unprompted reference within each stack. `None` means the
# stack has no such condition in the repository, which is itself a finding.
BASELINE_OF = {
    "hosted": "baseline",
    "vllm": "baseline_rp",
    "probe-llama-l48": None,
    "probe-llama-l50": None,
    "probe-qwen-l17": None,
}

STACK_LABEL = {
    "hosted": "Goodfire hosted API",
    "vllm": "local vLLM",
    "probe-llama-l48": "local probe, Llama L48",
    "probe-llama-l50": "local probe, Llama L50",
    "probe-qwen-l17": "local probe, Qwen L17",
}


@dataclass
class Curve:
    stack: str
    game: str                     # "lottery" | "ultimatum"
    condition: str
    trials: List[Tuple[float, int]] = field(default_factory=list)

    @property
    def xs(self) -> List[float]:
        return sorted({x for x, _ in self.trials})

    def by_x(self) -> "collections.OrderedDict[float, List[int]]":
        d = collections.defaultdict(list)
        for x, y in self.trials:
            d[x].append(y)
        return collections.OrderedDict(sorted(d.items()))

    @property
    def key(self) -> str:
        return f"{self.stack}|{self.game}|{self.condition}"

    @property
    def n(self) -> int:
        return len(self.trials)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------
def load_behavioural() -> List[Curve]:
    """Stacks A and B, from the combined behavioural CSV."""
    out: Dict[Tuple[str, str, str], Curve] = {}
    for r in csv.DictReader(open(BEHAVIOURAL, newline="")):
        game = r["game"]
        cond = r["treatment_condition"]
        if cond in VLLM:
            stack = "vllm"
        elif (game == "lottery" and cond in HOSTED_LOTTERY) or (
            game == "ultimatum" and cond in HOSTED_ULTIMATUM
        ):
            stack = "hosted"
        else:
            continue
        ans = (r["answer.safe_risky_choice"] if game == "lottery"
               else r["answer.ultimatum_response"]) or ""
        ans = ans.strip().lower()
        if game == "lottery":
            if ans.startswith("risky"):
                y = 1
            elif ans.startswith("safe"):
                y = 0
            else:
                continue
        else:
            if ans.startswith("accept"):
                y = 1
            elif ans.startswith("reject"):
                y = 0
            else:
                continue
        k = (stack, game, cond)
        out.setdefault(k, Curve(stack, game, cond))
        out[k].trials.append((float(r["offer_amount"]), y))
    return [out[k] for k in sorted(out)]


PROBE_KEYS = {
    "figure_7_psychometric_curves_llama": "probe-llama-l48",
    "figure_7_psychometric_curves_llama_layer50": "probe-llama-l50",
    "figure_14_psychometric_curves_qwen": "probe-qwen-l17",
}


def load_probe() -> List[Curve]:
    """Stack C, from the per-agent rows of the psychometric figure keys.

    One curve per calibrated target. There is no lambda = 0 curve anywhere.
    """
    d = json.loads(PROBE_JSON.read_text())
    out: Dict[Tuple[str, str, str], Curve] = {}
    for fig_key, stack in PROBE_KEYS.items():
        for r in d[fig_key].get("per_agent_rows", []):
            c = r.get("parsed_choice")
            if c not in (0, 1):
                continue
            game = r["game"]
            x = r.get("risky_reward_tokens") if game == "lottery" else r.get("offer_amount_tokens")
            if x is None:
                continue
            cond = f"target{int(r['target_switching_point_tokens'])}"
            k = (stack, game, cond)
            out.setdefault(k, Curve(stack, game, cond))
            out[k].trials.append((float(x), int(c)))
    return [out[k] for k in sorted(out)]


def probe_lambda_table() -> Dict[Tuple[str, str, str], float]:
    """(stack, game, conditionname) -> calibrated lambda, from the same rows."""
    d = json.loads(PROBE_JSON.read_text())
    out = {}
    for fig_key, stack in PROBE_KEYS.items():
        for r in d[fig_key].get("data", []):
            lam = r.get("lambda_calibrated")
            if lam is None:
                continue
            out[(stack, r["game"], f"target{int(r['target_switching_point_tokens'])}")] = float(lam)
    return out


def all_curves() -> List[Curve]:
    return load_behavioural() + load_probe()


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def wilson(k: int, n: int, z: float = 1.959963985) -> Tuple[float, float, float]:
    """(point, lo, hi). Wilson score interval; (nan, nan, nan) when n == 0."""
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    p = k / n
    d = 1.0 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def interp_crossing(xs: Sequence[float], ys: Sequence[float], thr: float = 0.5) -> Optional[float]:
    """Linear interpolation of the first crossing of `thr`. None if never crossed.

    This is the legacy definition (`Probes/calibration.py::switching_point_from_rows`)
    and is reported beside the logistic fit so the two are comparable.
    """
    for i in range(len(xs) - 1):
        if (ys[i] - thr) * (ys[i + 1] - thr) <= 0 and ys[i] != ys[i + 1]:
            return xs[i] + (thr - ys[i]) * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
    return None


def aggregate(trials: Sequence[Tuple[float, int]]):
    """Reduce trials to per-level binomial counts: (xs, successes, totals).

    A logistic in x is a function of these counts alone, so every fit and every
    bootstrap draw below works on ~35 rows instead of ~1,400 trials. The
    estimates are identical; only the cost changes.
    """
    d = collections.defaultdict(lambda: [0, 0])
    for x, y in trials:
        d[x][0] += int(y)
        d[x][1] += 1
    xs = np.array(sorted(d), dtype=float)
    k = np.array([d[x][0] for x in xs], dtype=float)
    n = np.array([d[x][1] for x in xs], dtype=float)
    return xs, k, n


def _fit_agg(xs: np.ndarray, k: np.ndarray, n: np.ndarray, scale: float = 100.0):
    """IRLS for P(y=1)=sigmoid(b0 + b1*x/scale) on binomial counts."""
    if n.sum() == 0 or k.sum() == 0 or k.sum() == n.sum():
        return float("nan"), float("nan"), float("nan")
    X = np.column_stack([np.ones_like(xs), xs / scale])
    b = np.zeros(2)
    for _ in range(60):
        eta = np.clip(X @ b, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(n * p * (1 - p), 1e-9, None)
        g = X.T @ (k - n * p)
        H = X.T @ (X * w[:, None]) + 1e-6 * np.eye(2)
        try:
            step = np.linalg.solve(H, g)
        except np.linalg.LinAlgError:
            return float("nan"), float("nan"), float("nan")
        b = b + step
        if np.max(np.abs(step)) < 1e-10:
            break
    if abs(b[1]) < 1e-8:
        return float(b[0]), float(b[1]), float("nan")
    return float(b[0]), float(b[1]), float(-b[0] / b[1] * scale)


def fit_logistic(trials: Sequence[Tuple[float, int]], scale: float = 100.0):
    """Two-parameter logistic fit. Returns (b0, b1_per_scale, switching point)."""
    xs, k, n = aggregate(trials)
    return _fit_agg(xs, k, n, scale=scale)


def bootstrap_switch(
    trials: Sequence[Tuple[float, int]],
    n_boot: int = 2000,
    cluster: bool = True,
    seed: int = 0,
    scale: float = 100.0,
) -> Tuple[float, float, float, int]:
    """(point, lo, hi, n_valid) for the logistic switching point.

    `cluster=True` resamples reward levels with replacement, keeping each level's
    trials together. That is the interval the plan asks for: the 40 agents at one
    reward level are i.i.d. draws from one prompt, so they are not independent
    evidence about where the curve sits.

    `cluster=False` is the ordinary trial bootstrap, drawn here as a multinomial
    over levels followed by a binomial within each — the same distribution as
    resampling the 1,400 trials directly, at a fraction of the cost.
    """
    xs, k, n = aggregate(trials)
    _, _, point = _fit_agg(xs, k, n, scale=scale)
    rng = np.random.default_rng(seed)
    N = int(n.sum())
    p_hat = np.divide(k, n, out=np.zeros_like(k), where=n > 0)
    draws = []
    for _ in range(n_boot):
        if cluster:
            pick = rng.integers(0, len(xs), size=len(xs))
            _, _, s = _fit_agg(xs[pick], k[pick], n[pick], scale=scale)
        else:
            nb = rng.multinomial(N, n / N).astype(float)
            kb = rng.binomial(nb.astype(int), p_hat).astype(float)
            _, _, s = _fit_agg(xs, kb, nb, scale=scale)
        if np.isfinite(s):
            draws.append(s)
    if len(draws) < 50:
        return point, float("nan"), float("nan"), len(draws)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi), len(draws)


def bootstrap_switch_diff(
    a: Sequence[Tuple[float, int]],
    b: Sequence[Tuple[float, int]],
    n_boot: int = 2000,
    seed: int = 0,
    scale: float = 100.0,
) -> Tuple[float, float, float]:
    """(difference, lo, hi) for switch(a) - switch(b), reward levels resampled in common."""
    xa, ka, na = aggregate(a)
    xb, kb, nb = aggregate(b)
    _, _, sa = _fit_agg(xa, ka, na, scale=scale)
    _, _, sb = _fit_agg(xb, kb, nb, scale=scale)
    point = sa - sb
    shared = np.intersect1d(xa, xb)
    if shared.size == 0:
        return point, float("nan"), float("nan")
    ia = np.searchsorted(xa, shared)
    ib = np.searchsorted(xb, shared)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        pick = rng.integers(0, shared.size, size=shared.size)
        _, _, s1 = _fit_agg(shared[pick], ka[ia][pick], na[ia][pick], scale=scale)
        _, _, s2 = _fit_agg(shared[pick], kb[ib][pick], nb[ib][pick], scale=scale)
        if np.isfinite(s1) and np.isfinite(s2):
            draws.append(s1 - s2)
    if len(draws) < 50:
        return point, float("nan"), float("nan")
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    x = np.asarray(xs, float)
    y = np.asarray(ys, float)
    if x.size < 3:
        return float("nan")

    def rank(v):
        order = np.argsort(v, kind="mergesort")
        r = np.empty(len(v), float)
        r[order] = np.arange(len(v), dtype=float)
        # average ties
        _, inv, cnt = np.unique(v, return_inverse=True, return_counts=True)
        sums = np.zeros(len(cnt))
        np.add.at(sums, inv, r)
        return (sums / cnt)[inv]

    rx, ry = rank(x), rank(y)
    if rx.std() == 0 or ry.std() == 0:
        return float("nan")
    return float(np.corrcoef(rx, ry)[0, 1])


# ---------------------------------------------------------------------------
# Output plumbing
# ---------------------------------------------------------------------------
OUT_DIR = ROOT / "results/S/s1"
MANIFEST = ROOT / "MANIFEST.csv"


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def write_csv(name: str, rows: List[Dict], fieldnames: Optional[List[str]] = None) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    p = OUT_DIR / name
    if not rows:
        p.write_text("")
        return p
    fieldnames = fieldnames or list(rows[0].keys())
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return p


def append_manifest(entries: List[Tuple[str, object, str, List[str], str]]) -> None:
    """entries: (id, value, script, inputs, note)."""
    sha = git_sha()
    new = not MANIFEST.exists()
    with open(MANIFEST, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["id", "value", "script", "inputs", "git_sha", "note"])
        for vid, value, script, inputs, note in entries:
            w.writerow([vid, json.dumps(value), script, ";".join(inputs), sha, note])


def rel(p: Path) -> str:
    return os.path.relpath(p, ROOT)


# ---------------------------------------------------------------------------
# GATE_S0_RESPONSE.md §3 P12 and P13
#
# P12 resets what counts as the primary interval for the *sampled* legacy data.
# The reward levels are a fixed design and the randomness lives in the sampled
# responses, so forty draws at one level are forty independent observations of
# that level's choice probability (not forty agents). The primary statistics are
# therefore a permutation test of the condition label stratified by level, and a
# bootstrap that holds the levels fixed and resamples responses within them. The
# level-resampling interval stays, as a sensitivity column: with a coarse grid
# and a steep curve only two or three levels carry information about where the
# curve sits, so that interval largely reflects which of them a draw includes.
# B6's "resample levels, never trials" rule is for logit readouts, which have no
# trial noise; it does not apply here.
# ---------------------------------------------------------------------------
def grid_step(trials: Sequence[Tuple[float, int]]) -> float:
    """The spacing of the reward grid, so a shift can be given in grid steps."""
    xs = np.array(sorted({x for x, _ in trials}), dtype=float)
    if xs.size < 2:
        return float("nan")
    d = np.diff(xs)
    d = d[d > 0]
    return float(np.min(d)) if d.size else float("nan")


def _paired_levels(a, b):
    xa, ka, na = aggregate(a)
    xb, kb, nb = aggregate(b)
    shared = np.intersect1d(xa, xb)
    ia = np.searchsorted(xa, shared)
    ib = np.searchsorted(xb, shared)
    return shared, ka[ia], na[ia], kb[ib], nb[ib]


def permutation_shift_test(
    a: Sequence[Tuple[float, int]],
    b: Sequence[Tuple[float, int]],
    n_perm: int = 5000,
    seed: int = 11,
    scale: float = 100.0,
) -> Tuple[float, float, int]:
    """(observed shift, two-sided p, n_valid) for switch(a) - switch(b).

    The condition label is permuted *within* each reward level, which for binomial
    counts is an exact hypergeometric relabelling: at a level with kA+kB positives
    among nA+nB responses, a permutation redraws how many of them fall to A.
    """
    xs, ka, na, kb, nb = _paired_levels(a, b)
    if xs.size == 0:
        return float("nan"), float("nan"), 0
    _, _, sa = _fit_agg(xs, ka, na, scale=scale)
    _, _, sb = _fit_agg(xs, kb, nb, scale=scale)
    obs = sa - sb
    if not np.isfinite(obs):
        return float("nan"), float("nan"), 0
    rng = np.random.default_rng(seed)
    ntot = (na + nb).astype(int)
    ktot = (ka + kb).astype(int)
    nA = na.astype(int)
    extreme, valid = 0, 0
    for _ in range(n_perm):
        kA = rng.hypergeometric(ktot, ntot - ktot, nA).astype(float)
        kB = ktot.astype(float) - kA
        _, _, s1 = _fit_agg(xs, kA, na, scale=scale)
        _, _, s2 = _fit_agg(xs, kB, nb, scale=scale)
        d = s1 - s2
        if np.isfinite(d):
            valid += 1
            if abs(d) >= abs(obs) - 1e-12:
                extreme += 1
    if valid < 50:
        return obs, float("nan"), valid
    # add-one correction: a permutation p is never exactly 0
    return obs, float((extreme + 1) / (valid + 1)), valid


def bootstrap_shift_within_level(
    a: Sequence[Tuple[float, int]],
    b: Sequence[Tuple[float, int]],
    n_boot: int = 4000,
    seed: int = 12,
    scale: float = 100.0,
) -> Tuple[float, float, float, int]:
    """(shift, lo, hi, n_valid) with the reward levels held fixed.

    Responses are resampled within each level, which is the sampling scheme that
    actually generated the data: the grid was chosen, the answers were drawn.
    """
    xs, ka, na, kb, nb = _paired_levels(a, b)
    if xs.size == 0:
        return float("nan"), float("nan"), float("nan"), 0
    _, _, sa = _fit_agg(xs, ka, na, scale=scale)
    _, _, sb = _fit_agg(xs, kb, nb, scale=scale)
    point = sa - sb
    pa = np.divide(ka, na, out=np.zeros_like(ka), where=na > 0)
    pb = np.divide(kb, nb, out=np.zeros_like(kb), where=nb > 0)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        kA = rng.binomial(na.astype(int), pa).astype(float)
        kB = rng.binomial(nb.astype(int), pb).astype(float)
        _, _, s1 = _fit_agg(xs, kA, na, scale=scale)
        _, _, s2 = _fit_agg(xs, kB, nb, scale=scale)
        d = s1 - s2
        if np.isfinite(d):
            draws.append(d)
    if len(draws) < 50:
        return point, float("nan"), float("nan"), len(draws)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi), len(draws)


def bootstrap_switch_within_level(
    trials: Sequence[Tuple[float, int]],
    n_boot: int = 4000,
    seed: int = 13,
    scale: float = 100.0,
) -> Tuple[float, float, float, int]:
    """(switch, lo, hi, n_valid), levels fixed, responses resampled within level."""
    xs, k, n = aggregate(trials)
    _, _, point = _fit_agg(xs, k, n, scale=scale)
    p_hat = np.divide(k, n, out=np.zeros_like(k), where=n > 0)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        kb = rng.binomial(n.astype(int), p_hat).astype(float)
        _, _, s = _fit_agg(xs, kb, n, scale=scale)
        if np.isfinite(s):
            draws.append(s)
    if len(draws) < 50:
        return point, float("nan"), float("nan"), len(draws)
    lo, hi = np.percentile(draws, [2.5, 97.5])
    return point, float(lo), float(hi), len(draws)


def staircase_excess(
    trials: Sequence[Tuple[float, int]],
    game: str,
    n_boot: int = 4000,
    seed: int = 14,
    scale: float = 100.0,
):
    """P13: the catch-trial rate, the rate a clean translation would imply, and the gap.

    A curve that moved as a pure translation is a step at its switching point, so
    on the catch levels it predicts a rate fixed by arithmetic:

      lottery   -- dominated levels are x < 50; a step at s takes the gamble on
                   every such level with x >= s
      ultimatum -- catch levels are x >= 50; a step at threshold s rejects every
                   such level with x < s

    The excess is observed minus implied. Zero means the whole catch-trial rate is
    the switching point restated. Positive means responses the switching point does
    not account for.
    """
    xs, k, n = aggregate(trials)
    if game == "lottery":
        catch = xs < SURE_AMOUNT
        implied_of = lambda s: (float(np.mean(xs[catch] >= s)) if catch.any() and np.isfinite(s)
                                else float("nan"))
        obs_k, obs_n = k[catch].sum(), n[catch].sum()
    else:
        catch = xs >= PIE / 2
        implied_of = lambda s: (float(np.mean(xs[catch] < s)) if catch.any() and np.isfinite(s)
                                else float("nan"))
        obs_k, obs_n = (n[catch] - k[catch]).sum(), n[catch].sum()   # reject = 1 - accept
    if obs_n == 0:
        return {}
    _, _, s_hat = _fit_agg(xs, k, n, scale=scale)
    # The implied rate is a step at the fitted switching point, so the fit has to
    # describe the curve. Where the logistic lands outside the observed grid it is
    # extrapolating -- probe-llama-l50 lottery target30 returns -13.0 against an
    # interpolated crossing of 32.9, because that curve is non-monotone in the tail
    # -- and the implied rate it produces is an artefact of the extrapolation.
    inside = bool(np.isfinite(s_hat) and xs.min() <= s_hat <= xs.max())
    if not inside:
        return dict(n_catch_levels=int(catch.sum()), n_catch_trials=int(obs_n),
                    observed_rate=float(obs_k / obs_n), switching_point=s_hat,
                    fit_inside_grid=False, implied_rate=float("nan"),
                    excess=float("nan"), excess_ci_lo=float("nan"),
                    excess_ci_hi=float("nan"), n_bootstrap=0)
    observed = float(obs_k / obs_n)
    implied = implied_of(s_hat)
    p_hat = np.divide(k, n, out=np.zeros_like(k), where=n > 0)
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        kb = rng.binomial(n.astype(int), p_hat).astype(float)
        _, _, s = _fit_agg(xs, kb, n, scale=scale)
        if not np.isfinite(s) or not (xs.min() <= s <= xs.max()):
            continue
        if game == "lottery":
            o = float(kb[catch].sum() / obs_n)
        else:
            o = float((n[catch] - kb[catch]).sum() / obs_n)
        draws.append(o - implied_of(s))
    out = dict(n_catch_levels=int(catch.sum()), n_catch_trials=int(obs_n),
               observed_rate=observed, switching_point=s_hat, fit_inside_grid=True,
               implied_rate=implied,
               excess=observed - implied if np.isfinite(implied) else float("nan"))
    if len(draws) >= 50:
        lo, hi = np.percentile(draws, [2.5, 97.5])
        out.update(excess_ci_lo=float(lo), excess_ci_hi=float(hi), n_bootstrap=len(draws))
    else:
        out.update(excess_ci_lo=float("nan"), excess_ci_hi=float("nan"),
                   n_bootstrap=len(draws))
    return out
