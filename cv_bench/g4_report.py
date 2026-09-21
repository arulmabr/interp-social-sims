"""G4's curves, under every coding, with the denominators attached.

Author instruction, 22 Sept, item 4: every free-generation crossing is reported
under all three codings and beside the readout, and an agreement figure is only
ever reported with (a) the number of trials on which both codings produced a
choice, (b) that number as a share of all trials, and (c) the no-answer rates.

The reason is the measurement itself. On G2's chat64 arm the legacy and strict
rules agree on 0.591 of trials; on G4's as-written arm they agree on 0.982. The
second number is not reassurance about the first. Twelve new tokens leave no
room to reason, so there is one label in the text and both rules read it; 64
tokens leave room to restate the options and not to conclude, so one rule reads
the first mention and the other the last. An agreement rate without its
denominator and its no-answer rate cannot tell those two situations apart.

Three codings:
  legacy   the last mention of either label   (Probes/tasks/prompts.py)
  strict   the first mention
  phrase   the label following an explicit decision phrase, else no_answer

    python -m cv_bench.g4_report
"""
from __future__ import annotations

import collections
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.s1_data import (SURE_AMOUNT, PIE, aggregate, _fit_agg, interp_crossing,
                              bootstrap_switch_within_level, staircase_excess,
                              wilson, write_csv, append_manifest, rel)
from cv_bench.instr import LABELS, decision_code, phrase_code
from cv_bench.g4 import legacy_code_of, strict_code_of

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
G4 = RUNROOT / "g4"
SCRIPT = "cv_bench/g4_report.py"
CODINGS = ("legacy", "strict", "phrase")


def code_all(text: str, game: str) -> Dict[str, Optional[int]]:
    lc = legacy_code_of(text, game)
    sc = strict_code_of(text, game)
    pc = phrase_code(text, game)["choice"]
    return dict(legacy=None if lc < 0 else lc,
                strict=None if sc < 0 else sc,
                phrase=pc)


def load_cells(variant: str, layer: int) -> List[dict]:
    p = G4 / f"sampled_{variant}_L{layer}.jsonl"
    if not p.exists():
        return []
    out = []
    for line in open(p):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def readout_curve(variant: str, layer: int, direction: str, game: str,
                  dose_id: int) -> Dict[float, float]:
    p = G4 / f"readout_{variant}_L{layer}.jsonl"
    if not p.exists():
        return {}
    out = {}
    for line in open(p):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        if (r.get("direction") == direction and r["game"] == game
                and r["dose_id"] == dose_id and "p_positive" in r):
            out[float(r["value"])] = float(r["p_positive"])
    return out


def curve_row(trials: Sequence[Tuple[float, int]], game: str) -> dict:
    if not trials:
        return dict(n_coded=0)
    xs, k, n = aggregate(trials)
    rates = np.divide(k, n, out=np.full_like(k, np.nan), where=n > 0)
    crossed = interp_crossing([float(v) for v in xs], [float(v) for v in rates])
    point, lo, hi, nb = bootstrap_switch_within_level(trials)
    inside = bool(np.isfinite(point) and xs.min() <= point <= xs.max())
    exc = staircase_excess(trials, game) or {}
    return dict(n_coded=len(trials), n_levels=int(len(xs)),
                interp_crossing=crossed, crosses_half_on_grid=crossed is not None,
                switch=point, switch_lo=lo, switch_hi=hi, fit_inside_grid=inside,
                excess=exc.get("excess"), excess_lo=exc.get("lo"),
                excess_hi=exc.get("hi"), excess_valid=bool(exc.get("fit_inside_grid")))


def build() -> Tuple[List[dict], List[dict]]:
    curves: List[dict] = []
    agree: List[dict] = []
    for variant in ("as_written", "reconstruction"):
        for layer in (48, 50):
            cells = load_cells(variant, layer)
            if not cells:
                continue
            groups = collections.defaultdict(list)
            for c in cells:
                if c.get("skipped"):
                    continue
                groups[(c.get("direction", "probe"), c["game"], c["dose_id"])].append(c)

            for (direction, game, dose_id), cs in sorted(groups.items()):
                per = {cd: [] for cd in CODINGS}
                counts = {cd: collections.Counter() for cd in CODINGS}
                pair = collections.Counter()
                n_trials = 0
                dose = cs[0].get("dose")
                anchor = cs[0].get("anchor", "")
                for c in cs:
                    gens = c.get("raw_generations") or []
                    for g in gens:
                        n_trials += 1
                        cd = code_all(g, game)
                        for name in CODINGS:
                            v = cd[name]
                            counts[name]["coded" if v is not None else "no_answer"] += 1
                            if v is not None:
                                per[name].append((float(c["value"]), int(v)))
                        for a in CODINGS:
                            for b in CODINGS:
                                if a >= b:
                                    continue
                                if cd[a] is not None and cd[b] is not None:
                                    pair[(a, b, "both")] += 1
                                    pair[(a, b, "same")] += int(cd[a] == cd[b])

                base = dict(variant=variant, layer=layer, direction=direction,
                            game=game, dose_id=dose_id, dose=dose, anchor=anchor,
                            n_trials=n_trials)
                for name in CODINGS:
                    row = dict(base, coding=name,
                               no_answer=counts[name]["no_answer"],
                               no_answer_rate=(counts[name]["no_answer"] / n_trials
                                               if n_trials else float("nan")))
                    row.update(curve_row(per[name], game))
                    curves.append(row)

                rd = readout_curve(variant, layer, direction, game, dose_id)
                if rd:
                    xs = sorted(rd)
                    curves.append(dict(base, coding="readout", no_answer=0,
                                       no_answer_rate=0.0, n_coded=len(xs),
                                       n_levels=len(xs),
                                       interp_crossing=interp_crossing(
                                           [float(v) for v in xs],
                                           [rd[v] for v in xs]),
                                       crosses_half_on_grid=interp_crossing(
                                           [float(v) for v in xs],
                                           [rd[v] for v in xs]) is not None))

                for a in CODINGS:
                    for b in CODINGS:
                        if a >= b:
                            continue
                        both = pair[(a, b, "both")]
                        same = pair[(a, b, "same")]
                        p, plo, phi = wilson(same, both) if both else (float("nan"),) * 3
                        agree.append(dict(base, coding_a=a, coding_b=b,
                                          n_both_coded=both,
                                          share_of_trials=(both / n_trials
                                                           if n_trials else float("nan")),
                                          n_agree=same, agreement=p,
                                          agreement_lo=plo, agreement_hi=phi,
                                          no_answer_rate_a=(counts[a]["no_answer"] / n_trials
                                                            if n_trials else float("nan")),
                                          no_answer_rate_b=(counts[b]["no_answer"] / n_trials
                                                            if n_trials else float("nan"))))
    return curves, agree


CFIELDS = ["variant", "layer", "direction", "game", "dose_id", "dose", "anchor",
           "coding", "n_trials", "no_answer", "no_answer_rate", "n_coded",
           "n_levels", "interp_crossing", "crosses_half_on_grid", "switch",
           "switch_lo", "switch_hi", "fit_inside_grid", "excess", "excess_lo",
           "excess_hi", "excess_valid"]
AFIELDS = ["variant", "layer", "direction", "game", "dose_id", "dose", "anchor",
           "coding_a", "coding_b", "n_trials", "n_both_coded", "share_of_trials",
           "n_agree", "agreement", "agreement_lo", "agreement_hi",
           "no_answer_rate_a", "no_answer_rate_b"]


def main() -> int:
    curves, agree = build()
    if not curves:
        print("[g4_report] no G4 cells on disk yet")
        return 0
    for r in curves:
        for f in CFIELDS:
            r.setdefault(f, "")
    write_csv("g4_curves.csv", curves, CFIELDS)
    write_csv("g4_agreement.csv", agree, AFIELDS)
    print(f"wrote g4_curves.csv ({len(curves)} rows) and "
          f"g4_agreement.csv ({len(agree)} rows)")

    ent = []
    for r in agree:
        if r["coding_a"] == "legacy" and r["coding_b"] == "strict" and r["n_both_coded"]:
            tag = (f"G4.{r['variant']}.L{r['layer']}.{r['direction']}.{r['game']}"
                   f".d{r['dose_id']}")
            src = [rel(G4 / f"sampled_{r['variant']}_L{r['layer']}.jsonl")]
            ent.append((f"{tag}.agreement", round(float(r["agreement"]), 4),
                        f"legacy vs strict on {r['n_both_coded']} trials where both "
                        f"code ({r['share_of_trials']:.3f} of {r['n_trials']})",
                        src, SCRIPT))
    if ent:
        append_manifest(ent)
        print(f"manifest += {len(ent)} rows")

    # a readable summary of the probe direction at dose 0 and the largest dose
    print(f"\n{'variant':15s} {'L':>3s} {'game':9s} {'dose':>7s} {'coding':8s} "
          f"{'no-ans':>7s} {'cross':>8s} {'n both':>7s} {'agree':>6s}")
    seen = set()
    for r in curves:
        if r["direction"] != "probe" or r["coding"] == "readout":
            continue
        key = (r["variant"], r["layer"], r["game"], r["dose_id"])
        a = next((x for x in agree if all(x[k] == r[k] for k in
                  ("variant", "layer", "game", "dose_id", "direction"))
                  and x["coding_a"] == "legacy" and x["coding_b"] == "strict"), None)
        print(f"{r['variant']:15s} {r['layer']:>3d} {r['game']:9s} "
              f"{(r['dose'] if r['dose'] != '' else 0):7.4f} {r['coding']:8s} "
              f"{r['no_answer_rate']:7.3f} "
              f"{(r['interp_crossing'] if r['interp_crossing'] else float('nan')):8.1f} "
              f"{(a['n_both_coded'] if a else 0):7d} "
              f"{(a['agreement'] if a else float('nan')):6.3f}")
        seen.add(key)
        if len(seen) > 12:
            print("  ...")
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
