"""B10.3 - the creativity readout, built on generation rather than on a choice.

A readout is any scalar computed from the model's own probabilities. For the
creativity task it is

    z = mean per-token log P(a high-originality response | prompt)
      - mean per-token log P(a low-originality response  | prompt)

The model is never asked to choose. It is given the paper's own prompt and z is
read off the probabilities it assigns to two real responses from the paper's own
data. Pairs are drawn from the top and bottom quarter of judged originality
within a task, from responses scored by at least three judges.

    python -m cv_bench.anchors.creativity_pairs --out <dir>
"""
from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import statistics as st
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

CSV = Path("/home/guna23/shrey/risk/cleaned/creativity_evals_combined.csv")
PROMPT = {
    "detailed_ways_to_use_a_brick":
        "List creative uses for a brick. Give several distinct ideas.",
    "improve_the_stapler_with_many_specific_enhancements":
        "Suggest improvements to the stapler. Give several distinct enhancements.",
}
MIN_JUDGES = 3


def _plain(s: str) -> str:
    """The response as prose, whichever way the stack formatted it."""
    try:
        v = ast.literal_eval(s)
        if isinstance(v, list):
            return " ".join(str(x).strip() for x in v if isinstance(x, str))
    except Exception:
        pass
    return s.strip()


def build(seed: int = 0, max_pairs: int = 60) -> Dict[str, object]:
    csv.field_size_limit(10 ** 7)
    per = defaultdict(lambda: {"o": [], "txt": None})
    for r in csv.DictReader(CSV.open(newline="")):
        if r["source_file"].startswith("revised_prompting"):
            continue                      # the other stack formats answers differently
        try:
            o = float(r["originality"])
        except ValueError:
            continue
        k = (r["task"], r["condition"], r["source_file"],
             r["source_row_index"], r["agent_index"])
        per[k]["o"].append(o)
        per[k]["txt"] = _plain(r["response_text"])

    out: Dict[str, object] = {"prompt": PROMPT, "min_judges": MIN_JUDGES, "tasks": {}}
    import random
    rng = random.Random(seed)
    for task in sorted(PROMPT):
        items = [(st.mean(d["o"]), d["txt"], k[1])
                 for k, d in per.items()
                 if k[0] == task and len(d["o"]) >= MIN_JUDGES and d["txt"]]
        if len(items) < 20:
            continue
        items.sort(key=lambda t: t[0])
        q = st.quantiles([t[0] for t in items], n=4)
        low = [t for t in items if t[0] <= q[0]]
        high = [t for t in items if t[0] >= q[2]]
        rng.shuffle(low)
        rng.shuffle(high)
        n = min(len(low), len(high), max_pairs)
        pairs = []
        for i in range(n):
            lo, hi = low[i], high[i]
            pairs.append({
                "low_text": lo[1], "high_text": hi[1],
                "low_originality": lo[0], "high_originality": hi[0],
                "d_originality": hi[0] - lo[0],
                "low_condition": lo[2], "high_condition": hi[2],
                "low_words": len(re.findall(r"[A-Za-z']+", lo[1])),
                "high_words": len(re.findall(r"[A-Za-z']+", hi[1]))})
        out["tasks"][task] = {
            "n_pairs": len(pairs),
            "mean_d_originality": st.mean(p["d_originality"] for p in pairs),
            "mean_low_words": st.mean(p["low_words"] for p in pairs),
            "mean_high_words": st.mean(p["high_words"] for p in pairs),
            "pairs": pairs}
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-pairs", type=int, default=60)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    d = build(max_pairs=a.max_pairs)
    (a.out / "creativity_pairs.json").write_text(json.dumps(d))
    for task, t in d["tasks"].items():
        print(f"{task[:40]:<42} pairs {t['n_pairs']:3d}  "
              f"mean originality gap {t['mean_d_originality']:+.2f}  "
              f"words {t['mean_low_words']:.0f} against {t['mean_high_words']:.0f}")
    print(f"wrote {a.out / 'creativity_pairs.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
