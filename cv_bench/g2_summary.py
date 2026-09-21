"""G2's main result: the unsteered choice curve under each arm and each coding.

FRIDAY amendment (22 Sept), item 1. For every (model, arm, coding) the table
carries the four numbers that decide whether the arm produced usable data:

  no-answer rate          the share of trials with no codable choice
  switching point         lottery, logistic, within-level 95% interval
  ultimatum threshold     the same on the offer grid
  P(risky | n < 50)       the dominated-choice rate
  P(reject | offer >= 50) the hyper-fair rejection rate

and sets them beside the hosted (A) and vLLM (B) baselines, which are the two
stacks the paper's behavioural figures come from.

Two coding rules are carried side by side throughout, because they disagree:
  legacy  Probes/tasks/prompts.py, the LAST mention of either label
  strict  the FIRST option the response actually states; `no_answer` and
          `unclear` are outcomes, never forced to a choice
The agreement between them is reported per arm; it is the quantity the standing
gate on excess numbers refers to.
"""
from __future__ import annotations

import collections
import json
import math
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.s1_data import (
    SURE_AMOUNT, PIE, aggregate, _fit_agg, bootstrap_switch_within_level,
    interp_crossing, load_behavioural, wilson, write_csv, append_manifest, rel,
)

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
G2DIR = RUNROOT / "g2_lambda0"
REPO = Path(__file__).resolve().parents[1]

MODELS = ["llama", "qwen"]
ARMS = ["legacy", "chat", "chat64"]
GAMES = ["lottery", "ultimatum"]

ARM_LABEL = {
    "legacy": "legacy exactly (raw string, 12 new tokens)",
    "chat": "chat template (12 new tokens)",
    "chat64": "chat template, max_new_tokens=64 (a departure)",
}


# ---------------------------------------------------------------------------
# loading and coding
# ---------------------------------------------------------------------------
def load_arm(model: str, arm: str, game: str) -> List[dict]:
    p = G2DIR / f"{model}_{arm}_{game}.jsonl"
    return [json.loads(l) for l in open(p)]


def coded_trials(rows: Sequence[dict], coding: str) -> List[Tuple[float, int]]:
    """(level, choice) for rows this coding assigns a choice to."""
    out = []
    for r in rows:
        if coding == "legacy":
            c = r["legacy_code"]
            if c in (0, 1):
                out.append((float(r["param_value"]), int(c)))
        else:
            c = r.get("strict_choice")
            if c in (0, 1):
                out.append((float(r["param_value"]), int(c)))
    return out


def uncoded_counts(rows: Sequence[dict], coding: str) -> Dict[str, int]:
    """How many trials this coding could not turn into a choice, and why."""
    if coding == "legacy":
        n_na = sum(1 for r in rows if r["legacy_code"] not in (0, 1))
        return dict(no_answer=n_na, unclear=0, uncoded=n_na)
    c = collections.Counter(r["strict_code"] for r in rows)
    return dict(no_answer=c.get("no_answer", 0), unclear=c.get("unclear", 0),
                uncoded=c.get("no_answer", 0) + c.get("unclear", 0))


def coding_agreement(rows: Sequence[dict]) -> Dict[str, object]:
    """Do the two rules agree, on the rows where both produce a choice?"""
    both = agree = 0
    for r in rows:
        a, b = r["legacy_code"], r.get("strict_choice")
        if a in (0, 1) and b in (0, 1):
            both += 1
            agree += int(a == b)
    p, lo, hi = wilson(agree, both) if both else (float("nan"),) * 3
    return dict(n_both_coded=both, n_agree=agree, agreement=p,
                agreement_lo=lo, agreement_hi=hi)


# ---------------------------------------------------------------------------
# the four numbers
# ---------------------------------------------------------------------------
def curve_numbers(trials: Sequence[Tuple[float, int]], game: str) -> Dict[str, object]:
    """Switching point (with its validity gates) and the catch-trial rate."""
    out: Dict[str, object] = dict(n_coded=len(trials))
    if not trials:
        return out
    xs, k, n = aggregate(trials)
    rates = np.divide(k, n, out=np.full_like(k, np.nan), where=n > 0)
    out["n_levels"] = int(len(xs))
    out["grid_min"], out["grid_max"] = float(xs.min()), float(xs.max())

    # observed crossing: the legacy definition, no model
    crossed = interp_crossing([float(v) for v in xs], [float(v) for v in rates])
    out["crosses_half_on_grid"] = crossed is not None
    out["interp_crossing"] = crossed

    # logistic + within-level interval, gated on landing inside the grid
    point, lo, hi, nb = bootstrap_switch_within_level(trials)
    inside = bool(np.isfinite(point) and xs.min() <= point <= xs.max())
    out.update(switch=point, switch_lo=lo, switch_hi=hi, n_boot_valid=nb,
               fit_inside_grid=inside)

    # catch-trial rate
    if game == "lottery":
        sel = [(x, y) for x, y in trials if x < SURE_AMOUNT]
        kk = sum(y for _, y in sel)                       # risky on a dominated level
        label = "P(risky|n<50)"
    else:
        sel = [(x, y) for x, y in trials if x >= PIE / 2]
        kk = sum(1 - y for _, y in sel)                   # reject on a fair-or-better offer
        label = "P(reject|offer>=50)"
    p, clo, chi = wilson(kk, len(sel)) if sel else (float("nan"),) * 3
    out.update(catch_label=label, catch_k=kk, catch_n=len(sel),
               catch_rate=p, catch_lo=clo, catch_hi=chi)
    return out


def baseline_rows() -> List[Dict[str, object]]:
    """Stacks A and B, unsteered, through the same functions."""
    rows = []
    want = {("hosted", "baseline"), ("vllm", "baseline_rp")}
    for c in load_behavioural():
        if (c.stack, c.condition) not in want:
            continue
        r = dict(source="published", model="Llama-3.3-70B-Instruct", stack=c.stack,
                 arm=c.condition, coding="as published", game=c.game,
                 n_trials=c.n, no_answer=0, unclear=0, uncoded=0, no_answer_rate=0.0)
        r.update(curve_numbers(c.trials, c.game))
        rows.append(r)
    return rows


def build() -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for model in MODELS:
        for arm in ARMS:
            for game in GAMES:
                raw = load_arm(model, arm, game)
                agree = coding_agreement(raw)
                for coding in ("legacy", "strict"):
                    unc = uncoded_counts(raw, coding)
                    r = dict(source="G2", model=model, stack=f"G2/{arm}", arm=arm,
                             coding=coding, game=game, n_trials=len(raw),
                             no_answer=unc["no_answer"], unclear=unc["unclear"],
                             uncoded=unc["uncoded"],
                             no_answer_rate=unc["uncoded"] / len(raw) if raw else float("nan"))
                    r.update(curve_numbers(coded_trials(raw, coding), game))
                    r.update(agree)
                    rows.append(r)
    rows.extend(baseline_rows())
    return rows


FIELDS = ["source", "model", "stack", "arm", "coding", "game", "n_trials",
          "no_answer", "unclear", "uncoded", "no_answer_rate", "n_coded",
          "n_levels", "grid_min", "grid_max", "crosses_half_on_grid",
          "interp_crossing", "switch", "switch_lo", "switch_hi",
          "fit_inside_grid", "n_boot_valid", "catch_label", "catch_k",
          "catch_n", "catch_rate", "catch_lo", "catch_hi",
          "n_both_coded", "n_agree", "agreement", "agreement_lo", "agreement_hi"]


def main() -> int:
    rows = build()
    for r in rows:
        for f in FIELDS:
            r.setdefault(f, "")
    p = write_csv("g2_summary.csv", rows, FIELDS)
    print(f"wrote {p} ({len(rows)} rows)")

    ent = []
    for r in rows:
        if r["source"] != "G2":
            continue
        tag = f"G2.{r['model']}.{r['arm']}.{r['coding']}.{r['game']}"
        ent.append((f"{tag}.no_answer_rate", round(float(r["no_answer_rate"]), 4),
                    "share of trials with no codable choice",
                    [rel(G2DIR / f"{r['model']}_{r['arm']}_{r['game']}.jsonl")],
                    "cv_bench/g2_summary.py"))
        if r["n_coded"]:
            ent.append((f"{tag}.catch_rate", round(float(r["catch_rate"]), 4),
                        r["catch_label"],
                        [rel(G2DIR / f"{r['model']}_{r['arm']}_{r['game']}.jsonl")],
                        "cv_bench/g2_summary.py"))
            if r["fit_inside_grid"]:
                ent.append((f"{tag}.switch", round(float(r["switch"]), 2),
                            "logistic switching point, within-level 95% CI "
                            f"[{float(r['switch_lo']):.1f}, {float(r['switch_hi']):.1f}]",
                            [rel(G2DIR / f"{r['model']}_{r['arm']}_{r['game']}.jsonl")],
                            "cv_bench/g2_summary.py"))
    append_manifest(ent)
    print(f"manifest += {len(ent)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
