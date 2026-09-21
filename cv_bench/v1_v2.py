"""V1 and V2 -- which scoring pass produced Figure 5, and who the judges were.

Both are CPU-only searches over data already in the repository.

**V1.** The built PDF reports 5.57 / 5.18 and 6.25 / 5.23 for its steered-versus-
unsteered pairs, and the repository's own scoring gives numbers 2.8-3.6 points
lower, in the same direction for every judge. Something produced the PDF's
values. V1 enumerates every combination of scoring pass, evaluation prompt
version, condition, task, score column and judge subset in `CREATIVITY`, and
reports which combinations land within tolerance of each PDF reading. If none
does, that is the finding: the built paper used a scoring pass this repository
does not contain.

**V2.** Who scored what. Per scoring pass, the evaluator models present, how many
responses each scored, which parse statuses occurred, and whether the five-judge
set the paper describes is the set that actually appears. The review asks
separately about the archival verifiability of the judge citations; the model
identifiers found here are the evidence for that patch.

    python -m cv_bench.v1_v2
"""
from __future__ import annotations

import collections
import csv
import itertools
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.s1_data import CREATIVITY, append_manifest, rel, write_csv
from cv_bench.s1_capability import PDF_READINGS, MULTI, SINGLE

SCRIPT = "cv_bench/v1_v2.py"
SCORE_COLS = ["final_score", "originality", "flexibility", "elaboration", "fluency"]
TOL = 0.005          # the PDF quotes two decimals


def load() -> List[dict]:
    return list(csv.DictReader(open(CREATIVITY, newline="")))


def _f(v) -> Optional[float]:
    try:
        x = float(v)
        return x if np.isfinite(x) else None
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# V1
# ---------------------------------------------------------------------------
def v1_search(rows: List[dict]) -> Tuple[List[dict], List[dict]]:
    """Every (pass, version, condition, task, column, judge subset) mean."""
    judges = sorted({r["evaluator_model"] for r in rows if r["evaluator_model"]})
    subsets: List[Tuple[str, Tuple[str, ...]]] = [("all", tuple(judges))]
    for j in judges:
        subsets.append((f"only:{j}", (j,)))
        subsets.append((f"drop:{j}", tuple(k for k in judges if k != j)))

    cells: List[dict] = []
    keyed = collections.defaultdict(list)
    for r in rows:
        keyed[(r["source_file"], r["eval_prompt_version"], r["condition"],
               r["task"])].append(r)

    for (src, ver, cond, task), rs in sorted(keyed.items()):
        for col in SCORE_COLS:
            for name, subset in subsets:
                vals = [_f(r[col]) for r in rs if r["evaluator_model"] in subset]
                vals = [v for v in vals if v is not None]
                if len(vals) < 5:
                    continue
                cells.append(dict(source_file=src, eval_prompt_version=ver,
                                  condition=cond, task=task, score_column=col,
                                  judges=name, n=len(vals),
                                  mean=round(float(np.mean(vals)), 4)))

    targets = [p for p in PDF_READINGS if "inline pair" in p["item"]
               or "mean of five" in p["item"] or "Fig. 5A" in p["item"]]
    matches: List[dict] = []
    for t in targets:
        hits = [c for c in cells if abs(c["mean"] - t["pdf_value"]) <= TOL]
        if hits:
            for h in hits:
                matches.append(dict(pdf_item=t["item"], pdf_value=t["pdf_value"],
                                    matched="yes", **h))
        else:
            near = min(cells, key=lambda c: abs(c["mean"] - t["pdf_value"]))
            matches.append(dict(pdf_item=t["item"], pdf_value=t["pdf_value"],
                                matched="no",
                                nearest_gap=round(abs(near["mean"] - t["pdf_value"]), 4),
                                **near))
    return cells, matches


# ---------------------------------------------------------------------------
# V2
# ---------------------------------------------------------------------------
def v2_judges(rows: List[dict]) -> List[dict]:
    out: List[dict] = []
    by_pass = collections.defaultdict(list)
    for r in rows:
        by_pass[(r["source_file"], r["eval_prompt_version"])].append(r)
    for (src, ver), rs in sorted(by_pass.items()):
        judges = collections.Counter(r["evaluator_model"] for r in rs)
        status = collections.Counter(r["parse_status"] for r in rs)
        modes = collections.Counter(r["structured_output_mode"] for r in rs)
        has_api = sum(1 for r in rs if (r.get("api_response_id") or "").strip())
        out.append(dict(source_file=src, eval_prompt_version=ver, n_rows=len(rs),
                        n_judges=len(judges),
                        judges="; ".join(f"{k}({v})" for k, v in sorted(judges.items())),
                        parse_status="; ".join(f"{k}={v}" for k, v in sorted(status.items())),
                        structured_output_mode="; ".join(sorted(modes)),
                        rows_with_api_response_id=has_api,
                        five_judges=bool(len(judges) == 5)))
    return out


def v1_pairs(cells: List[dict]) -> List[dict]:
    """The coherent test: one cell for the steered value, one for its baseline.

    The PDF quotes two pairs. A pair is only evidence if both halves come from
    the SAME scoring pass, evaluation prompt version, task, score column and
    judge subset, and differ only in the condition. Matching the two numbers in
    unrelated cells is not a reproduction; it is a coincidence, and the rate of
    those is measured below.
    """
    want = [("inline pair (a)", 5.57, 5.18), ("inline pair (b)", 6.25, 5.23)]
    by = {}
    for c in cells:
        by.setdefault((c["source_file"], c["eval_prompt_version"], c["task"],
                       c["score_column"], c["judges"]), {})[c["condition"]] = c
    out = []
    for name, hi, lo in want:
        found = False
        for key, conds in sorted(by.items()):
            base = conds.get("baseline")
            if base is None or abs(base["mean"] - lo) > TOL:
                continue
            for cond, cell in conds.items():
                if cond == "baseline" or abs(cell["mean"] - hi) > TOL:
                    continue
                found = True
                out.append(dict(pair=name, steered_value=hi, baseline_value=lo,
                                matched="yes", source_file=key[0],
                                eval_prompt_version=key[1], task=key[2],
                                score_column=key[3], judges=key[4],
                                steered_condition=cond))
        if not found:
            out.append(dict(pair=name, steered_value=hi, baseline_value=lo,
                            matched="no", source_file="", eval_prompt_version="",
                            task="", score_column="", judges="",
                            steered_condition=""))
    return out


def coincidence_rate(cells: List[dict], targets: Sequence[float],
                     tol: float = TOL) -> dict:
    """How many single-value hits would this many cells give by chance?

    The cell means are not uniform, so the expectation is estimated from the
    empirical density: for each target, the share of cells within `tol` of a
    value drawn from the same distribution, shifted. Reported so that a count of
    exact matches is read against what a search this wide produces anyway.
    """
    means = np.array([c["mean"] for c in cells], dtype=float)
    rng = np.random.default_rng(0)
    draws = rng.choice(means, size=min(len(means), 2000), replace=False)
    exp = 0.0
    for t in targets:
        exp += float(np.mean(np.abs(draws - t) <= tol)) * len(means)
    return dict(n_cells=len(means), n_targets=len(targets), tol=tol,
                expected_hits_by_chance=round(exp, 1))


def main() -> int:
    rows = load()
    cells, matches = v1_search(rows)
    pairs = v1_pairs(cells)
    chance = coincidence_rate(cells, [p["pdf_value"] for p in PDF_READINGS])
    judges = v2_judges(rows)

    write_csv("v1_fig5_search.csv", matches,
              ["pdf_item", "pdf_value", "matched", "nearest_gap", "source_file",
               "eval_prompt_version", "condition", "task", "score_column",
               "judges", "n", "mean"])
    write_csv("v1_all_cells.csv", cells,
              ["source_file", "eval_prompt_version", "condition", "task",
               "score_column", "judges", "n", "mean"])
    write_csv("v1_fig5_pairs.csv", pairs,
              ["pair", "steered_value", "baseline_value", "matched", "source_file",
               "eval_prompt_version", "task", "score_column", "judges",
               "steered_condition"])
    write_csv("v2_judges.csv", judges,
              ["source_file", "eval_prompt_version", "n_rows", "n_judges", "judges",
               "parse_status", "structured_output_mode", "rows_with_api_response_id",
               "five_judges"])

    n_hit = sum(1 for m in matches if m["matched"] == "yes")
    n_items = len({m["pdf_item"] for m in matches})
    print(f"V1: searched {len(cells)} cells against {n_items} PDF readings; "
          f"{n_hit} exact matches")
    for m in matches:
        if m["matched"] == "yes":
            print(f"  MATCH {m['pdf_value']:>6} = {m['source_file']}/{m['condition']}"
                  f"/{m['task'][:18]}/{m['score_column']}/{m['judges']} "
                  f"(n={m['n']})")
        else:
            print(f"  none  {m['pdf_value']:>6}  nearest {m['mean']} "
                  f"(gap {m['nearest_gap']}) at {m['source_file']}/{m['condition']}"
                  f"/{m['score_column']}/{m['judges']}")
    print(f"  expected by chance at this search width: "
          f"{chance['expected_hits_by_chance']} hits "
          f"({chance['n_cells']} cells, {chance['n_targets']} targets, "
          f"tol +/-{chance['tol']})")
    print()
    print("V1 paired test -- both halves from the same pass, task, column and judges:")
    for p in pairs:
        if p["matched"] == "yes":
            print(f"  MATCH {p['pair']}: {p['source_file']}/{p['task'][:18]}/"
                  f"{p['score_column']}/{p['judges']} "
                  f"({p['steered_condition']} vs baseline)")
        else:
            print(f"  NONE  {p['pair']}: no cell has baseline "
                  f"{p['baseline_value']} with any condition at {p['steered_value']}")
    print()
    print("V2: judges per scoring pass")
    for j in judges:
        print(f"  {j['source_file']:26s} {j['eval_prompt_version'][:34]:34s} "
              f"n={j['n_rows']:5d} judges={j['n_judges']} "
              f"api_ids={j['rows_with_api_response_id']}")
        print(f"      {j['judges']}")

    n_pair = sum(1 for p in pairs if p["matched"] == "yes")
    ent = [("V1.pair_matches", n_pair,
            "PDF pairs reproduced coherently (same pass, task, column, judges)",
            [rel(CREATIVITY)], SCRIPT),
           ("V1.expected_hits_by_chance", chance["expected_hits_by_chance"],
            "single-value hits expected from a search this wide",
            [rel(CREATIVITY)], SCRIPT),
           (f"V1.matches", n_hit,
            f"PDF readings reproduced exactly by some cell of {len(cells)} searched",
            [rel(CREATIVITY)], SCRIPT),
           (f"V2.n_judge_sets", len({j['judges'] for j in judges}),
            "distinct evaluator-model sets across scoring passes",
            [rel(CREATIVITY)], SCRIPT)]
    append_manifest(ent)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
