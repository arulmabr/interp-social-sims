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

BEHAVIOURAL = ROOT / "cleaned/behavioral_games_combined.csv"
PROBE_JSON = ROOT / "Probes/raw_data/probe_results_final.json"
CREATIVITY = ROOT / "cleaned/creativity_evals_combined.csv"

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
    "hosted": "A: hosted Goodfire/EDSL",
    "vllm": "B: local vLLM bf16",
    "probe-llama-l48": "C: local HF probe, Llama L48",
    "probe-llama-l50": "C: local HF probe, Llama L50",
    "probe-qwen-l17": "C: local HF probe, Qwen L17",
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
