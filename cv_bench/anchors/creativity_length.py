"""B10.2 - hypothesis 6 of the extension plan, for the creativity arm.

The plan does not ask for the two vector anchors here. It asks whether the
creativity effects survive once length is removed:

    "Length already explains up to 43 percent of one judge's variance... What we
     do not know is whether the effects of prompting, of SAE steering and of the
     probe survive once length is partialled out... Scores are therefore
     residualized on length, and agreement is recomputed within each subset."

So each judge's score is regressed on the log word count of the response it was
given, and every condition comparison is repeated on what is left over. Judge
agreement is recomputed the same way. Conditions from different inference stacks
are never compared with each other, because the two stacks do not even format
their answers alike.

    python -m cv_bench.anchors.creativity_length [--write-manifest]
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import re
import subprocess
from collections import defaultdict
from itertools import combinations
from pathlib import Path
from typing import Dict, List

import numpy as np

CSV = Path("/home/guna23/shrey/risk/cleaned/creativity_evals_combined.csv")
STACK_BASE = {"A": "baseline", "B": "baseline_rp"}


def stack_of(row: dict) -> str:
    return "B" if row["source_file"].startswith("revised_prompting") else "A"


def spearman(a: List[float], b: List[float]) -> float:
    if len(a) < 3:
        return float("nan")
    ra, rb = _rank(a), _rank(b)
    ra, rb = np.array(ra), np.array(rb)
    sa, sb = ra.std(), rb.std()
    return float(np.mean((ra - ra.mean()) * (rb - rb.mean())) / (sa * sb)) if sa and sb else float("nan")


def _rank(v: List[float]) -> List[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    out = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def load() -> List[dict]:
    csv.field_size_limit(10 ** 7)
    rows = []
    for r in csv.DictReader(CSV.open(newline="")):
        try:
            r["_score"] = float(r["final_score"])
        except ValueError:
            continue
        w = len(re.findall(r"[A-Za-z']+", r["response_text"]))
        if w < 5:
            continue
        r["_logw"] = math.log(w)
        r["_stack"] = stack_of(r)
        r["_resp"] = (r["condition"], r["source_file"], r["source_row_index"],
                      r["agent_index"])
        rows.append(r)
    return rows


def analyse(rows: List[dict]) -> Dict[str, object]:
    out: Dict[str, object] = {"length_share": {}, "tasks": {}, "agreement": {}}

    # -- how much of each judge's variance length explains, per task -------
    resid: Dict[tuple, float] = {}
    for task in sorted({r["task"] for r in rows}):
        for judge in sorted({r["evaluator_model"] for r in rows}):
            sub = [r for r in rows if r["task"] == task and r["evaluator_model"] == judge]
            if len(sub) < 20:
                continue
            x = np.array([r["_logw"] for r in sub])
            y = np.array([r["_score"] for r in sub])
            b, a = np.polyfit(x, y, 1)
            pred = a + b * x
            ss_res = float(((y - pred) ** 2).sum())
            ss_tot = float(((y - y.mean()) ** 2).sum())
            out["length_share"][f"{'brick' if 'brick' in task else 'stapler'}|{judge}"] = {
                "r2": 1.0 - ss_res / ss_tot if ss_tot else float("nan"),
                "slope_per_log_word": float(b), "n": len(sub)}
            for r, p in zip(sub, pred):
                resid[(id(r),)] = r["_score"] - float(p)

    for r in rows:
        r["_resid"] = resid.get((id(r),), float("nan"))

    # -- condition effects, raw and residualised, each stack on its own base
    for task in sorted({r["task"] for r in rows}):
        tag = "brick" if "brick" in task else "stapler"
        out["tasks"][tag] = {}
        for stack in ("A", "B"):
            part = [r for r in rows if r["task"] == task and r["_stack"] == stack]
            base = STACK_BASE[stack]
            if not any(r["condition"] == base for r in part):
                continue
            by = defaultdict(lambda: {"raw": [], "res": [], "logw": []})
            for r in part:
                by[r["condition"]]["raw"].append(r["_score"])
                by[r["condition"]]["res"].append(r["_resid"])
                by[r["condition"]]["logw"].append(r["_logw"])
            bm = {k: float(np.nanmean(v)) for k, v in by[base].items()}
            conds = {}
            for c, v in sorted(by.items()):
                if c == base:
                    continue
                conds[c] = {
                    "d_reported": float(np.nanmean(v["raw"])) - bm["raw"],
                    "d_length_removed": float(np.nanmean(v["res"])) - bm["res"],
                    "d_log_words": float(np.nanmean(v["logw"])) - bm["logw"],
                    "n": len(v["raw"])}
            out["tasks"][tag][stack] = {"baseline": base,
                                        "baseline_reported": bm["raw"],
                                        "conditions": conds}

    # -- judge agreement, raw and residualised, within each condition ------
    for task in sorted({r["task"] for r in rows}):
        tag = "brick" if "brick" in task else "stapler"
        for cond in sorted({r["condition"] for r in rows if r["task"] == task}):
            sub = [r for r in rows if r["task"] == task and r["condition"] == cond]
            byj = defaultdict(dict)
            for r in sub:
                byj[r["evaluator_model"]][r["_resp"]] = r
            js = sorted(byj)
            pr_raw, pr_res = [], []
            for a, b in combinations(js, 2):
                shared = sorted(set(byj[a]) & set(byj[b]))
                if len(shared) < 10:
                    continue
                pr_raw.append(spearman([byj[a][k]["_score"] for k in shared],
                                       [byj[b][k]["_score"] for k in shared]))
                pr_res.append(spearman([byj[a][k]["_resid"] for k in shared],
                                       [byj[b][k]["_resid"] for k in shared]))
            if pr_raw:
                out["agreement"][f"{tag}|{cond}"] = {
                    "mean_spearman_reported": float(np.nanmean(pr_raw)),
                    "mean_spearman_length_removed": float(np.nanmean(pr_res)),
                    "n_pairs": len(pr_raw), "n_judges": len(js)}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-out", type=Path, default=Path("reports/b10_creativity_length.json"))
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)

    r = analyse(load())
    a.json_out.parent.mkdir(parents=True, exist_ok=True)
    a.json_out.write_text(json.dumps(r, indent=2, sort_keys=True))

    print("share of each judge's score that length explains")
    for k, v in sorted(r["length_share"].items(), key=lambda kv: -kv[1]["r2"]):
        print(f"  {k:<34}{v['r2']*100:>6.1f}%   n={v['n']}")
    for tag, per in r["tasks"].items():
        for stack, t in per.items():
            print(f"\n{tag}, stack {stack}, against {t['baseline']} "
                  f"at {t['baseline_reported']:.2f}")
            print(f"{'condition':<18}{'reported':>11}{'length removed':>17}{'log words':>12}")
            for c, v in sorted(t["conditions"].items(), key=lambda kv: -kv[1]["d_length_removed"]):
                print(f"{c:<18}{v['d_reported']:>+11.3f}{v['d_length_removed']:>+17.3f}"
                      f"{v['d_log_words']:>+12.3f}")
    print("\njudge agreement within each condition")
    print(f"{'subset':<30}{'reported':>11}{'length removed':>17}")
    for k, v in sorted(r["agreement"].items()):
        print(f"{k:<30}{v['mean_spearman_reported']:>+11.3f}"
              f"{v['mean_spearman_length_removed']:>+17.3f}")

    if a.write_manifest:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        with open("MANIFEST_B.csv", "a", newline="") as fh:
            for k, v in r["length_share"].items():
                fh.write(f'B10.2.length_r2.{k.replace("|",".")},{v["r2"]},'
                         f'cv_bench/anchors/creativity_length.py,'
                         f'cleaned/creativity_evals_combined.csv,{sha},'
                         f'"share of judge variance explained by log length"\n')
            for tag, per in r["tasks"].items():
                for stack, t in per.items():
                    for c, v in t["conditions"].items():
                        for f in ("d_reported", "d_length_removed"):
                            fh.write(f'B10.2.{tag}.stack{stack}.{c}.{f},{v[f]},'
                                     f'cv_bench/anchors/creativity_length.py,'
                                     f'cleaned/creativity_evals_combined.csv,{sha},'
                                     f'"hypothesis 6, length partialled out"\n')
            for k, v in r["agreement"].items():
                for f in ("mean_spearman_reported", "mean_spearman_length_removed"):
                    fh.write(f'B10.2.agreement.{k.replace("|",".")}.{f},{v[f]},'
                             f'cv_bench/anchors/creativity_length.py,'
                             f'cleaned/creativity_evals_combined.csv,{sha},'
                             f'"judge agreement within subset"\n')
        print("\nmanifest rows written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
