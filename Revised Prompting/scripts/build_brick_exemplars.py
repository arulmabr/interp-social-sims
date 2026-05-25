#!/usr/bin/env python3
"""Build held-out, human-rated *brick* few-shot exemplars from the Ocsai AUT data.

Source: massivetexts/ocsai (MIT), data/ocsai1/finetune-gt_main2_prepared_train.jsonl
Each record looks like:
    {"prompt": "AUT Prompt:<object>\\nResponse:<text>\\nScore:\\n",
     "completion": "<human originality score>"}

We keep object == "brick", dedupe, and select the highest human-originality
responses as few-shot exemplars. The selection criterion (human originality) is
INDEPENDENT of the downstream GPT judge, which is what avoids the
selection/evaluation circularity for the creativity task.

Run:
    python scripts/build_brick_exemplars.py            # downloads from GitHub
    python scripts/build_brick_exemplars.py --source data/ocsai_brick_aut.jsonl
"""

from __future__ import annotations

import argparse
import json
import re
import urllib.request
from pathlib import Path

DEFAULT_SOURCE = (
    "https://raw.githubusercontent.com/massivetexts/ocsai/main/"
    "data/ocsai1/finetune-gt_main2_prepared_train.jsonl"
)
REPO_ROOT = Path(__file__).resolve().parents[1]
PROMPT_RE = re.compile(r"AUT Prompt:(?P<obj>.*?)\nResponse:(?P<resp>.*?)\nScore:", re.S)

# The Ocsai data anonymizes the object word, which sometimes leaves an
# ungrammatical dangling article (e.g. "Crush a into a fine powder", "holes in
# a and create"). Drop those so the vendored exemplars read as clean, complete
# human responses. This filter is independent of the GPT judge (no circularity).
BROKEN_RE = re.compile(r"\b(a|an)\s+(into|and|or|to|in|on|with|for|by)\b", re.IGNORECASE)


def iter_records(source: str):
    if source.startswith("http"):
        with urllib.request.urlopen(source) as handle:
            for line in handle:
                line = line.decode("utf-8").strip()
                if line:
                    yield json.loads(line)
    else:
        with open(source, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if line:
                    yield json.loads(line)


def parse(record: dict) -> tuple[str, str, float] | None:
    match = PROMPT_RE.search(record.get("prompt", ""))
    if not match:
        return None
    try:
        score = float(record.get("completion"))
    except (TypeError, ValueError):
        return None
    response = re.sub(r"\s+", " ", match.group("resp")).strip()
    return match.group("obj").strip(), response, score


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", default=DEFAULT_SOURCE, help="URL or local path to the Ocsai jsonl.")
    parser.add_argument("--object", default="brick")
    parser.add_argument("--num", type=int, default=8, help="Number of exemplars to keep.")
    parser.add_argument("--min-words", type=int, default=2, help="Drop responses shorter than this.")
    parser.add_argument("--out", default=str(REPO_ROOT / "data" / "brick_exemplars.json"))
    parser.add_argument("--subset-out", default=str(REPO_ROOT / "data" / "ocsai_brick_aut.jsonl"))
    args = parser.parse_args()

    subset: list[dict] = []
    unique: list[tuple[str, float]] = []
    seen: set[str] = set()
    for record in iter_records(args.source):
        parsed = parse(record)
        if parsed is None:
            continue
        obj, response, score = parsed
        if obj.lower() != args.object.lower():
            continue
        subset.append(record)
        key = response.lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append((response, score))

    unique.sort(key=lambda item: item[1], reverse=True)
    eligible = [
        (r, s)
        for r, s in unique
        if len(r.split()) >= args.min_words and not BROKEN_RE.search(r)
    ]
    exemplars = [{"response": r, "originality": s} for r, s in eligible[: args.num]]

    Path(args.subset_out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.subset_out, "w", encoding="utf-8") as handle:
        for record in subset:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    payload = {
        "object": args.object,
        "source": "massivetexts/ocsai data/ocsai1/finetune-gt_main2_prepared_train.jsonl (MIT)",
        "citation": (
            "Organisciak, Acar, Dumas & Berthiaume (2023), "
            "Beyond semantic distance, Thinking Skills and Creativity 49:101356"
        ),
        "selection": (
            f"top human-originality responses (independent of the GPT judge); "
            f"deduped; >= {args.min_words} words"
        ),
        "n_object_total": len(subset),
        "n_unique": len(unique),
        "score_min": min((s for _, s in unique), default=None),
        "score_max": max((s for _, s in unique), default=None),
        "exemplars": exemplars,
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    print(
        f"{args.object}: {len(subset)} records | {len(unique)} unique | "
        f"score range {payload['score_min']}-{payload['score_max']}"
    )
    print(f"selected {len(exemplars)} exemplars -> {args.out}")
    for item in exemplars:
        print(f"  [{item['originality']}] {item['response'][:90]}")


if __name__ == "__main__":
    main()
