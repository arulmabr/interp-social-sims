"""B10 - the anchor question asked of the creativity arm, on its own task.

The two vector anchors cannot reach this arm. They measure the balance between
two answer words and a written paragraph has none, which is why BD57 withdrew
the pairwise redesign: it would have measured ranking rather than generation.

What can be carried over is the **question** the anchors exist to ask. On the
decision games it is whether an intervention changed what the agent wants or
merely pushed the word it emits. Here it is whether an intervention changed what
the model produced or merely changed surface properties that judges reward.

That question is answerable without any new run, because the judges scored four
separate dimensions rather than one number:

    fluency       how many ideas were produced
    flexibility   how many distinct kinds of idea
    originality   how unusual they were
    elaboration   how much detail each carried

The first three are content. A change that raises the reported score while
moving only elaboration is the creativity counterpart of a push. A change that
raises originality and flexibility is the counterpart of a real shift.

Computable text measures are reported beside them so the judges are not the only
witness.

    python -m cv_bench.anchors.creativity_decomp [--write-manifest]
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import statistics as st
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

CSV = Path("/home/guna23/shrey/risk/cleaned/creativity_evals_combined.csv")
DIMS = ("fluency", "flexibility", "originality", "elaboration", "final_score")
CONTENT = ("fluency", "flexibility", "originality")
BASE = "baseline"

#: The two inference stacks format their answers differently, so they are never
#: differenced against each other. The hosted stack returns a quoted list of
#: ideas; the local prompting ladder returns free prose. Each condition is
#: compared with the baseline of its own stack (STACK_AUDIT.md).
STACK_BASE = {"A": "baseline", "B": "baseline_rp"}
_QUOTED = re.compile(r"""(?<![A-Za-z])['"]([^'"]{25,})['"]""")
_SENT = re.compile(r"[.!?]+\s")


def stack_of(row: dict) -> str:
    return "B" if row["source_file"].startswith("revised_prompting") else "A"


def text_measures(s: str, stack: str) -> Dict[str, float]:
    """Judge-independent properties, counted the way that stack's format allows."""
    words = re.findall(r"[A-Za-z']+", s)
    if stack == "A":
        ideas = float(len(_QUOTED.findall(s)))
    else:
        ideas = float(len(_SENT.findall(s)) + 1) if s.strip() else 0.0
    return {"words": float(len(words)),
            "ideas": ideas,
            "words_per_idea": float(len(words) / ideas) if ideas else float("nan"),
            "distinct_word_ratio": float(len({w.lower() for w in words}) / len(words))
            if words else float("nan")}


def load() -> List[dict]:
    csv.field_size_limit(10 ** 7)
    return list(csv.DictReader(CSV.open(newline="")))


def analyse(rows: List[dict]) -> Dict[str, object]:
    out: Dict[str, object] = {"tasks": {}}
    for task in sorted({r["task"] for r in rows}):
        sub = [r for r in rows if r["task"] == task]
        out["tasks"][task] = {}
        for stack in ("A", "B"):
            part = [r for r in sub if stack_of(r) == stack]
            base_name = STACK_BASE[stack]
            if not any(r["condition"] == base_name for r in part):
                continue
            judged = defaultdict(lambda: defaultdict(list))
            textm = defaultdict(lambda: defaultdict(list))
            seen = set()
            for r in part:
                c = r["condition"]
                for d in DIMS:
                    try:
                        judged[c][d].append(float(r[d]))
                    except (ValueError, KeyError):
                        pass
                key = (c, r["source_file"], r["source_row_index"], r["agent_index"])
                if key not in seen:
                    seen.add(key)
                    for k, v in text_measures(r["response_text"], stack).items():
                        textm[c][k].append(v)
            base_j = {d: st.mean(judged[base_name][d]) for d in DIMS if judged[base_name][d]}
            base_t = {k: st.mean([x for x in v if x == x])
                      for k, v in textm[base_name].items() if any(x == x for x in v)}
            conds = {}
            for c in sorted(judged):
                if c == base_name:
                    continue
                rec = {f"d_{d}": st.mean(judged[c][d]) - base_j[d]
                       for d in DIMS if judged[c][d] and d in base_j}
                for k, v in textm[c].items():
                    good = [x for x in v if x == x]
                    if good and k in base_t:
                        rec[f"d_{k}"] = st.mean(good) - base_t[k]
                rec["n_judged"] = len(judged[c]["final_score"])
                rec["n_responses"] = len(textm[c].get("words", []))
                rec["content_change"] = sum(rec.get(f"d_{d}", 0.0) for d in CONTENT) / len(CONTENT)
                rec["elaboration_change"] = rec.get("d_elaboration", float("nan"))
                rec["reported_change"] = rec.get("d_final_score", float("nan"))
                conds[c] = rec
            out["tasks"][task][stack] = {"baseline": base_name,
                                         "baseline_means": base_j,
                                         "baseline_text": base_t,
                                         "conditions": conds}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json-out", type=Path, default=Path("reports/b10_creativity_decomp.json"))
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)

    r = analyse(load())
    a.json_out.parent.mkdir(parents=True, exist_ok=True)
    a.json_out.write_text(json.dumps(r, indent=2, sort_keys=True))

    for task, per in r["tasks"].items():
        for stack, t in per.items():
            print(f"\n{task}   stack {stack}   baseline {t['baseline']} "
                  f"at {t['baseline_means']['final_score']:.2f}")
            print(f"{'condition':<18}{'reported':>10}{'content':>10}{'elabor':>10}"
                  f"{'words':>10}{'ideas':>9}")
            for c, v in sorted(t["conditions"].items(),
                               key=lambda kv: -kv[1]["reported_change"]):
                print(f"{c:<18}{v['reported_change']:>+10.3f}{v['content_change']:>+10.3f}"
                      f"{v['elaboration_change']:>+10.3f}"
                      f"{v.get('d_words', float('nan')):>+10.1f}"
                      f"{v.get('d_ideas', float('nan')):>+9.2f}")

    if a.write_manifest:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        with open("MANIFEST_B.csv", "a", newline="") as fh:
            for task, per in r["tasks"].items():
                tag = "brick" if "brick" in task else "stapler"
                for stack, t in per.items():
                  for c, v in t["conditions"].items():
                    for k in ("reported_change", "content_change", "elaboration_change",
                              "d_originality", "d_words", "d_ideas"):
                        if k in v:
                            fh.write(f'B10.{tag}.stack{stack}.{c}.{k},{v[k]},'
                                     f'cv_bench/anchors/creativity_decomp.py,'
                                     f'cleaned/creativity_evals_combined.csv,{sha},'
                                     f'"change from baseline"\n')
        print("\nmanifest rows written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
