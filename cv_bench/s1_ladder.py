"""S1.7 — the prompting ladder, and the prompt appendix it needs.

    python -m cv_bench.s1_ladder

The ladder ran on the local vLLM stack. The paper's Figs. 3 and 5 ran on the
hosted Goodfire stack. Everything here is reported on the local stack's own axes,
with the Goodfire baseline shown only as a separately labelled reference line in
the figure, never averaged in and never differenced against.

Also writes `paper_patches/appendix_prompts.md`: the verbatim chain-of-thought
trigger and the few-shot demonstrations for each task, which the paper promises
and does not contain.
"""
from __future__ import annotations

import collections
import csv
import json
import re
from pathlib import Path
from typing import Dict, List

import numpy as np

from .s1_data import (
    BEHAVIOURAL, ROOT, append_manifest, bootstrap_switch, fit_logistic,
    interp_crossing, load_behavioural, rel, write_csv,
)

SCRIPT = "cv_bench/s1_ladder.py"
LADDER = ["baseline_rp", "persona", "cot", "fewshot",
          "fewshot_cot_dose000", "fewshot_cot_dose025", "fewshot_cot_dose050",
          "fewshot_cot_dose075", "fewshot_cot_dose100"]
DOSE = {"fewshot_cot_dose000": 0.00, "fewshot_cot_dose025": 0.25,
        "fewshot_cot_dose050": 0.50, "fewshot_cot_dose075": 0.75,
        "fewshot_cot_dose100": 1.00}
CREATIVITY = ROOT / "cleaned/creativity_evals_combined.csv"
MULTI = "torrance_four_dimension_length_controlled_v1"


def _fmt(v):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 4)


def _prompts() -> Dict[tuple, dict]:
    """One verbatim record per (game, condition), taken at the 50-token cell."""
    out = {}
    for r in csv.DictReader(open(BEHAVIOURAL, newline="")):
        if r["treatment_condition"] not in LADDER:
            continue
        if float(r["offer_amount"]) != 50.0:
            continue
        k = (r["game"], r["treatment_condition"])
        if k in out:
            continue
        g = "safe_risky_choice" if r["game"] == "lottery" else "ultimatum_response"
        out[k] = dict(
            system=r[f"prompt.{g}_system_prompt"],
            user=r[f"prompt.{g}_user_prompt"],
            temperature=r["model.temperature"],
            service=r["model.inference_service"],
        )
    return out


# ---------------------------------------------------------------------------
def s1_7_behaviour():
    curves = {(c.stack, c.game, c.condition): c for c in load_behavioural()}
    rows, manifest = [], []
    for game in ("lottery", "ultimatum"):
        for cond in LADDER:
            c = curves.get(("vllm", game, cond))
            if c is None:
                continue
            bx = c.by_x()
            xs, ys = list(bx), [float(np.mean(bx[x])) for x in bx]
            pt, lo, hi, _ = bootstrap_switch(c.trials, n_boot=1000, cluster=True, seed=7)
            # Same rule as S1.3: report a switching point only where the measured
            # curve actually crosses 0.5 inside the grid.
            crossed = interp_crossing(xs, ys) is not None
            if not crossed:
                pt = lo = hi = float("nan")
            base = curves[("vllm", game, "baseline_rp")]
            bbx = base.by_x()
            rows.append(dict(
                stack="vllm", game=game, condition=cond,
                rho=DOSE.get(cond, ""),
                crosses_half_on_grid=str(crossed),
                n_trials=c.n,
                switching_point_interp=_fmt(interp_crossing(xs, ys)),
                switching_point_logistic=_fmt(pt),
                ci_lo=_fmt(lo), ci_hi=_fmt(hi),
                p_positive_at_grid_min=_fmt(ys[0]), p_positive_at_grid_max=_fmt(ys[-1]),
                same_stack_baseline_switching_point=_fmt(
                    interp_crossing(list(bbx), [float(np.mean(bbx[x])) for x in bbx])),
            ))
            manifest.append((
                f"S1.7.vllm.{game}.{cond}.switch", _fmt(pt), SCRIPT, [rel(BEHAVIOURAL)],
                f"logistic switching point on the local vLLM stack; cluster bootstrap "
                f"95% CI [{_fmt(lo)},{_fmt(hi)}]",
            ))
    write_csv("s1_7_ladder_behaviour.csv", rows)
    append_manifest(manifest)
    return rows


def s1_7_creativity():
    by = collections.defaultdict(list)
    for r in csv.DictReader(open(CREATIVITY, newline="")):
        if r["eval_prompt_version"] != MULTI:
            continue
        if not r["source_file"].startswith("revised_prompting"):
            continue
        try:
            y = float(r["final_score"])
        except (TypeError, ValueError):
            continue
        by[(r["source_file"], r["condition"], r["evaluator_model"])].append(y)
    judges = sorted({k[2] for k in by})
    rows = []
    for src in sorted({k[0] for k in by}):
        for cond in sorted({k[1] for k in by if k[0] == src}):
            rec = dict(source_file=src, condition=cond)
            per = []
            for j in judges:
                v = by[(src, cond, j)]
                rec[f"mean_{j}"] = _fmt(float(np.mean(v))) if v else ""
                if v:
                    per.append(float(np.mean(v)))
            rec["mean_of_5_judges"] = _fmt(float(np.mean(per))) if per else ""
            rec["n_responses"] = len(by[(src, cond, judges[0])]) if by[(src, cond, judges[0])] else 0
            rows.append(rec)
    write_csv("s1_7_ladder_creativity.csv", rows)
    return rows


# ---------------------------------------------------------------------------
def appendix_prompts():
    p = _prompts()
    out = ["# appendix_prompts.md",
           "",
           "Verbatim prompts for the prompting ladder (`cot`, `fewshot`, `fewshot_cot` and its",
           "rho sweep). The paper's abstract refers to these conditions; no appendix contains them.",
           "Extracted by `cv_bench/s1_ladder.py` from",
           "`cleaned/behavioral_games_combined.csv`, at the 50-token cell of each condition.",
           "",
           "All of these ran on the **local vLLM stack**: Llama-3.3-70B-Instruct, bfloat16,",
           "tensor-parallel 2, temperature 0.7, top-p 1.0, no system prompt except in `persona`.",
           "They did **not** run on the hosted Goodfire stack that produced Figures 3 and 5.",
           "",
           "> Draft for the authors. Every quantitative claim that cites these prompts must carry its",
           "> `MANIFEST.csv` id.",
           ""]
    for game in ("lottery", "ultimatum"):
        out += [f"## {game.title()}", ""]
        for cond in LADDER:
            r = p.get((game, cond))
            if not r:
                continue
            out += [f"### `{cond}`" + (f"  (rho = {DOSE[cond]:.2f})" if cond in DOSE else ""), ""]
            if r["system"]:
                out += ["System prompt:", "", "```text", r["system"], "```", ""]
            else:
                out += ["System prompt: *(none)*", ""]
            out += ["User prompt:", "", "```text", r["user"].strip(), "```", ""]
    tgt = ROOT / "paper_patches/appendix_prompts.md"
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_text("\n".join(out) + "\n")
    return tgt


def exemplar_counts():
    """How many demonstrations each few-shot prompt carries, and what they show."""
    p = _prompts()
    rows, manifest = [], []
    for (game, cond), r in sorted(p.items()):
        u = r["user"]
        if "Here are example responses" not in u:
            continue
        qs = re.findall(r"\nQ: (.*?)\nA: (.*?)(?=\n\nQ: |\n\nYou are |\n\n$|$)", u, re.S)
        if game == "lottery":
            pos = sum(1 for _, a in qs if re.search(r"Final answer:\s*risky", a, re.I))
            amounts = [float(m) for q, _ in qs
                       for m in re.findall(r"risky gives (\d+) tokens", q)]
            dominated = sum(1 for q, a in qs
                            if re.search(r"risky gives (\d+) tokens", q)
                            and float(re.search(r"risky gives (\d+) tokens", q).group(1)) < 50
                            and re.search(r"Final answer:\s*risky", a, re.I))
        else:
            pos = sum(1 for _, a in qs if re.search(r"Final answer:\s*accept", a, re.I))
            amounts = [float(m) for q, _ in qs
                       for m in re.findall(r"offers you (\d+) tokens", q)]
            dominated = sum(1 for q, a in qs
                            if re.search(r"offers you (\d+) tokens", q)
                            and float(re.search(r"offers you (\d+) tokens", q).group(1)) >= 50
                            and re.search(r"Final answer:\s*reject", a, re.I))
        rows.append(dict(
            game=game, condition=cond, rho=DOSE.get(cond, ""),
            n_demonstrations=len(qs),
            n_demonstrating_risky_or_accept=pos,
            fraction_risky_or_accept=_fmt(pos / len(qs)) if qs else "",
            demonstrated_amounts=";".join(str(int(a)) for a in amounts),
            n_demonstrations_that_are_catch_trials=dominated,
        ))
        manifest.append((
            f"S1.7.exemplars.{game}.{cond}.fraction_positive",
            _fmt(pos / len(qs)) if qs else "", SCRIPT, [rel(BEHAVIOURAL)],
            f"{pos} of {len(qs)} demonstrations end in the risky/accept answer; "
            f"{dominated} of them demonstrate a dominated or catch-trial choice",
        ))
    write_csv("s1_7_exemplars.csv", rows)
    append_manifest(manifest)
    return rows


def main() -> int:
    b = s1_7_behaviour()
    print(f"ladder behaviour rows {len(b)}")
    c = s1_7_creativity()
    print(f"ladder creativity rows {len(c)}")
    e = exemplar_counts()
    print(f"exemplar rows {len(e)}")
    t = appendix_prompts()
    print(f"wrote {rel(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
