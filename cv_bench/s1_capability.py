"""S1.5 — the capability (creativity) scores, judge by judge.

    python -m cv_bench.s1_capability

GATE_S0_RESPONSE.md §3 P5 and P10 are in force:
  * P5  — the legacy capability probe was trained on two distinct prompts; that
          is stated here with the prompts, the labels and the read position.
  * P10 — two capability datasets exist. This runs on the repository data and
          lists the values read off the PDF in a separate column marked
          "PDF, source unknown". The two are not reconciled, and neither is
          preferred. Judge agreement is reported within condition and within
          task beside the pooled 0.77.
"""
from __future__ import annotations

import collections
import csv
import json
import math
import re
import warnings
from typing import Dict, List

import numpy as np

from .s1_data import CREATIVITY, append_manifest, rel, spearman, write_csv

SCRIPT = "cv_bench/s1_capability.py"
MULTI = "torrance_four_dimension_length_controlled_v1"
SINGLE = "torrance_four_dimension_v1"

SAE_CONDS = ["baseline", "prompting", "high_temperature", "high_steering"]

# Values read off the PDF by the authors (GATE_S0_RESPONSE.md §4.2, re-checked at
# 300 dpi on 2026-09-20). Carried as data with an explicit provenance label; they
# are NOT reconciled with the repository values and NOT used in any computation.
PDF_READINGS = [
    dict(item="Fig. 5A high-temperature brick, gpt-5", pdf_value=2.9),
    dict(item="Fig. 5A high-temperature brick, claude-sonnet-4-6", pdf_value=1.5),
    dict(item="Fig. 5A high-temperature brick, gemini-2.5-pro", pdf_value=2.15),
    dict(item="Fig. 5A high-temperature brick, kimi-k2.6", pdf_value=2.1),
    dict(item="Fig. 5A high-temperature brick, deepseek-v4-pro", pdf_value=1.85),
    dict(item="Fig. 5A high-temperature brick, mean of five judges", pdf_value=2.1),
    dict(item="inline pair, steered vs unsteered (a)", pdf_value=5.57),
    dict(item="inline pair, steered vs unsteered (a) baseline", pdf_value=5.18),
    dict(item="inline pair, steered vs unsteered (b)", pdf_value=6.25),
    dict(item="inline pair, steered vs unsteered (b) baseline", pdf_value=5.23),
]


def _fmt(v):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 4)


def load_multi(source_file: str = "open_sae_creativity") -> List[dict]:
    out = []
    for r in csv.DictReader(open(CREATIVITY, newline="")):
        if r["eval_prompt_version"] != MULTI or r["source_file"] != source_file:
            continue
        try:
            y = float(r["final_score"])
        except (TypeError, ValueError):
            continue
        txt = r["response_text"] or ""
        out.append(dict(
            task=r["task"], condition=r["condition"], judge=r["evaluator_model"],
            resp=f"{r['task']}|{r['condition']}|{r['subject_id']}",
            score=y, words=len(re.findall(r"\b\w+\b", txt)),
            fluency=float(r["fluency"]), flexibility=float(r["flexibility"]),
            originality=float(r["originality"]), elaboration=float(r["elaboration"]),
        ))
    return out


def load_single() -> List[dict]:
    out = []
    for r in csv.DictReader(open(CREATIVITY, newline="")):
        if r["eval_prompt_version"] != SINGLE:
            continue
        try:
            y = float(r["final_score"])
        except (TypeError, ValueError):
            continue
        out.append(dict(task=r["task"], condition=r["condition"], score=y,
                        judge=r["evaluator_model"] or "gpt-5"))
    return out


# ---------------------------------------------------------------------------
# (a) condition ordering per judge
# ---------------------------------------------------------------------------
def s1_5a(rows: List[dict], single: List[dict]):
    tasks = sorted({r["task"] for r in rows})
    judges = sorted({r["judge"] for r in rows})
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["task"], r["condition"], r["judge"])].append(r["score"])
    sby = collections.defaultdict(list)
    for r in single:
        sby[(r["task"], r["condition"])].append(r["score"])

    out, manifest = [], []
    for task in tasks:
        for judge in judges + ["MEAN_of_5_judges", "single_judge_gpt5_original_rubric"]:
            rec = dict(task=task, judge=judge)
            means = {}
            for c in SAE_CONDS:
                if judge == "MEAN_of_5_judges":
                    per = [float(np.mean(by[(task, c, j)])) for j in judges if by[(task, c, j)]]
                    m = float(np.mean(per)) if per else float("nan")
                elif judge == "single_judge_gpt5_original_rubric":
                    v = sby[(task, c)]
                    m = float(np.mean(v)) if v else float("nan")
                else:
                    v = by[(task, c, judge)]
                    m = float(np.mean(v)) if v else float("nan")
                means[c] = m
                rec[f"mean_{c}"] = _fmt(m)
            order = [c for c in sorted(SAE_CONDS, key=lambda c: -means[c]) if np.isfinite(means[c])]
            rec["ranking_best_to_worst"] = " > ".join(order)
            rec["steering_minus_baseline"] = _fmt(means["high_steering"] - means["baseline"])
            rec["steering_above_baseline"] = str(means["high_steering"] > means["baseline"])
            rec["steering_is_top"] = str(bool(order) and order[0] == "high_steering")
            out.append(rec)
            if judge not in ("MEAN_of_5_judges", "single_judge_gpt5_original_rubric"):
                manifest.append((
                    f"S1.5a.{task[:18]}.{judge}.steering_minus_baseline",
                    _fmt(means["high_steering"] - means["baseline"]), SCRIPT, [rel(CREATIVITY)],
                    "five-judge length-controlled rubric, open_sae_creativity slice",
                ))
    write_csv("s1_5_condition_ordering.csv", out)
    append_manifest(manifest)
    return out


# ---------------------------------------------------------------------------
# (b) and (c) mixed-effects model, raw and length-residualised
# ---------------------------------------------------------------------------
def _mixed(rows: List[dict], task: str, value_key: str):
    """Crossed random intercepts for judge and response; fixed effect of condition.

    Returns (contrasts, sigma) where contrasts is a list of
    (cond_a, cond_b, estimate, lo, hi, p).
    """
    import pandas as pd
    import statsmodels.formula.api as smf

    df = pd.DataFrame([r for r in rows if r["task"] == task])
    if df.empty:
        return [], {}
    df = df.copy()
    df["y"] = df[value_key]
    df["grp"] = 1
    df["condition"] = pd.Categorical(df["condition"], categories=SAE_CONDS)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        md = smf.mixedlm(
            "y ~ C(condition, Treatment('baseline'))", df, groups=df["grp"],
            re_formula="0",
            vc_formula={"judge": "0 + C(judge)", "resp": "0 + C(resp)"},
        )
        fit = md.fit(reml=True, method="lbfgs", maxiter=2000)
    names = list(fit.params.index)
    cov = fit.cov_params()
    contrasts = []
    for i, a in enumerate(SAE_CONDS):
        for b in SAE_CONDS[i + 1:]:
            vec = np.zeros(len(names))
            for cond, sign in ((a, 1.0), (b, -1.0)):
                if cond == "baseline":
                    continue
                nm = f"C(condition, Treatment('baseline'))[T.{cond}]"
                if nm not in names:
                    continue
                vec[names.index(nm)] = sign
            est = float(vec @ fit.params.values)
            var = float(vec @ cov.values @ vec)
            se = math.sqrt(max(var, 0.0))
            lo, hi = est - 1.96 * se, est + 1.96 * se
            z = est / se if se > 0 else float("nan")
            p = float(2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))) if np.isfinite(z) else float("nan")
            contrasts.append((a, b, est, lo, hi, p))
    # fit.vcomp is a plain array in this statsmodels version; its order follows
    # the variance-component names the model was built with.
    vc = {}
    try:
        names_vc = list(getattr(md, "exog_vc").names)
    except Exception:
        names_vc = ["judge", "resp"]
    try:
        vc = {n: float(v) for n, v in zip(names_vc, np.atleast_1d(fit.vcomp))}
    except Exception:
        vc = {}
    vc["residual"] = float(fit.scale)
    return contrasts, vc


def s1_5bc(rows: List[dict]):
    import pandas as pd

    # length residualisation, per judge, on log word count
    df = pd.DataFrame(rows)
    df["logw"] = np.log(df["words"].clip(lower=1))
    lenrows = []
    resid = np.zeros(len(df))
    for judge, idx in df.groupby("judge").groups.items():
        sub = df.loc[idx]
        X = np.column_stack([np.ones(len(sub)), sub["logw"].values])
        y = sub["score"].values
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        pred = X @ beta
        ss = ((y - y.mean()) ** 2).sum()
        r2 = 1 - ((y - pred) ** 2).sum() / ss if ss > 0 else float("nan")
        resid[df.index.get_indexer(idx)] = y - pred
        lenrows.append(dict(judge=judge, n=len(sub), slope_per_log_word=_fmt(beta[1]),
                            intercept=_fmt(beta[0]), r_squared=_fmt(r2)))
    df["score_resid"] = resid
    write_csv("s1_5_length_regression.csv", lenrows)
    rows2 = df.to_dict("records")

    out, manifest = [], []
    for task in sorted({r["task"] for r in rows}):
        for value_key, tag in (("score", "raw"), ("score_resid", "length_residualised")):
            contrasts, vc = _mixed(rows2, task, value_key)
            for a, b, est, lo, hi, p in contrasts:
                out.append(dict(
                    task=task, model=tag, condition_a=a, condition_b=b,
                    estimate_a_minus_b=_fmt(est), ci_lo=_fmt(lo), ci_hi=_fmt(hi),
                    p_value=_fmt(p), excludes_zero=str(lo > 0 or hi < 0),
                    var_judge=_fmt(vc.get("judge")), var_response=_fmt(vc.get("resp")),
                    var_residual=_fmt(vc.get("residual")),
                ))
                if {a, b} == {"baseline", "high_steering"}:
                    manifest.append((
                        f"S1.5b.{task[:18]}.{tag}.steering_vs_baseline", _fmt(est), SCRIPT,
                        [rel(CREATIVITY)],
                        f"mixed model, crossed random intercepts for judge and response; "
                        f"95% CI [{_fmt(lo)},{_fmt(hi)}], p={_fmt(p)}",
                    ))
    write_csv("s1_5_mixed_effects.csv", out)
    append_manifest(manifest)
    return out, lenrows


# ---------------------------------------------------------------------------
# (d) inter-judge agreement, sliced the way P10 asks for
# ---------------------------------------------------------------------------
def s1_5d(rows: List[dict], all_multi: List[dict]):
    def pairwise(subset):
        by = collections.defaultdict(dict)
        for r in subset:
            by[r["resp"]][r["judge"]] = r["score"]
        judges = sorted({r["judge"] for r in subset})
        vals = []
        for i, a in enumerate(judges):
            for b in judges[i + 1:]:
                xs = [by[k][a] for k in by if a in by[k] and b in by[k]]
                ys = [by[k][b] for k in by if a in by[k] and b in by[k]]
                if len(xs) >= 3:
                    s = spearman(xs, ys)
                    if np.isfinite(s):
                        vals.append((f"{a}__vs__{b}", s, len(xs)))
        return vals

    out, manifest = [], []

    def add(scope, subset):
        v = pairwise(subset)
        if not v:
            return
        m = float(np.mean([s for _, s, _ in v]))
        out.append(dict(scope=scope, n_responses=len({r["resp"] for r in subset}),
                        n_pairs=len(v), mean_pairwise_spearman=_fmt(m),
                        min_pair=_fmt(min(s for _, s, _ in v)),
                        max_pair=_fmt(max(s for _, s, _ in v))))
        manifest.append((f"S1.5d.spearman.{scope}", _fmt(m), SCRIPT, [rel(CREATIVITY)],
                         f"mean pairwise Spearman over {len({r['resp'] for r in subset})} responses"))

    add("pooled_all_datasets_all_conditions_both_tasks", all_multi)
    add("pooled_open_sae_only", rows)
    add("pooled_open_sae_excluding_high_temperature",
        [r for r in rows if r["condition"] != "high_temperature"])
    for task in sorted({r["task"] for r in rows}):
        add(f"task={task[:22]}", [r for r in rows if r["task"] == task])
        for c in SAE_CONDS:
            add(f"task={task[:22]}|condition={c}",
                [r for r in rows if r["task"] == task and r["condition"] == c])
    for c in SAE_CONDS:
        add(f"condition={c}", [r for r in rows if r["condition"] == c])
    write_csv("s1_5_judge_agreement.csv", out)
    append_manifest(manifest)
    return out


# ---------------------------------------------------------------------------
# P10: the PDF column, carried and not reconciled
# ---------------------------------------------------------------------------
def s1_5_pdf_column(rows: List[dict], single: List[dict]):
    by = collections.defaultdict(list)
    for r in rows:
        by[(r["task"], r["condition"], r["judge"])].append(r["score"])
    brick = "detailed_ways_to_use_a_brick"
    judges = sorted({r["judge"] for r in rows})
    out = []
    for e in PDF_READINGS:
        repo = ""
        if "high-temperature brick" in e["item"]:
            j = e["item"].rsplit(", ", 1)[1]
            if j == "mean of five judges":
                per = [float(np.mean(by[(brick, "high_temperature", jj)])) for jj in judges]
                repo = _fmt(float(np.mean(per)))
            elif by[(brick, "high_temperature", j)]:
                repo = _fmt(float(np.mean(by[(brick, "high_temperature", j)])))
        out.append(dict(item=e["item"],
                        pdf_value_source_unknown=e["pdf_value"],
                        repo_value=repo or "no matching slice",
                        reconciled="no -- deliberately not reconciled (P10)"))
    write_csv("s1_5_pdf_vs_repo.csv", out)
    return out


# ---------------------------------------------------------------------------
# P5: the legacy capability probe, stated
# ---------------------------------------------------------------------------
def s1_5_p5():
    rows = [dict(
        prompt_index=1, role="class 0 (baseline)",
        verbatim="List very detailed ways you can use a brick. Each answer should be a paragraph.",
        n_samples=80,
        activation_read_at="final token of this prompt, via capture_activations, "
                           "a separate forward pass with no chat template and no steering"),
        dict(
        prompt_index=2, role="class 1 (creative persona)",
        verbatim=("You are a highly creative and unconventional thinker. Think outside the box. "
                  "Be imaginative. " + "List very detailed ways you can use a brick. "
                  "Each answer should be a paragraph."),
        n_samples=80,
        activation_read_at="final token of this prompt, same procedure")]
    write_csv("s1_5_capability_probe_prompts.csv", rows)
    append_manifest([(
        "S1.5.P5.capability_probe_distinct_prompts", 2, SCRIPT,
        ["Probes/experiments/_common.py", "Probes/tasks/prompts.py"],
        "labels are a median split of the GPT-5 judge score of the generated text, not of the "
        "prompt group; with the activation read at the final prompt token there are two distinct "
        "vectors, so an accuracy figure carries no information about creativity",
    )])
    return rows


def main() -> int:
    rows = load_multi("open_sae_creativity")
    all_multi = (rows + load_multi("revised_prompting_brick")
                 + load_multi("revised_prompting_stapler"))
    single = load_single()
    print(f"open_sae rows {len(rows)}; all multi-judge rows {len(all_multi)}; single {len(single)}")
    print(f"(a) {len(s1_5a(rows, single))} ordering rows")
    mx, lr = s1_5bc(rows)
    print(f"(b,c) {len(mx)} contrasts; {len(lr)} length regressions")
    print(f"(d) {len(s1_5d(rows, all_multi))} agreement scopes")
    print(f"P10 {len(s1_5_pdf_column(rows, single))} PDF rows")
    print(f"P5 {len(s1_5_p5())} prompt rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
