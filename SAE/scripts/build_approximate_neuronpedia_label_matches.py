#!/usr/bin/env python3
"""Build approximate Neuronpedia explanation matches for old Goodfire labels."""

from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
NEURONPEDIA_MODEL = "llama3.3-70b-it"
NEURONPEDIA_SOURCE = "50-resid-post-gf"
NEURONPEDIA_EXPLANATION_SEARCH_URL = "https://www.neuronpedia.org/api/explanation/search"
NEURONPEDIA_FEATURE_URL = (
    "https://www.neuronpedia.org/api/feature/"
    f"{NEURONPEDIA_MODEL}/{NEURONPEDIA_SOURCE}/{{feature_index}}"
)
EXPECTED_OLD_ONLY_LABELS = 101


def release_path(path: Path | str) -> str:
    """Return a repo-relative path when possible."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def neuronpedia_feature_url(feature_index: int | str) -> str:
    """Return the Neuronpedia feature URL for one feature index."""

    return NEURONPEDIA_FEATURE_URL.format(feature_index=int(feature_index))


def confidence_bucket(score: float) -> str:
    """Return a coarse confidence bucket for semantic label search."""

    if score >= 0.70:
        return "high_semantic_similarity"
    if score >= 0.60:
        return "medium_semantic_similarity"
    return "low_semantic_similarity"


def old_only_label_summary(crosswalk_path: Path) -> list[dict[str, Any]]:
    """Summarize old-label-only paper rows by label."""

    frame = pd.read_csv(crosswalk_path)
    old_only = frame[frame["mapping_status"] == "old_label_only_no_feature_index"].copy()
    rows: list[dict[str, Any]] = []
    for label, group in old_only.groupby("old_goodfire_label", sort=True):
        sources = sorted({str(value) for value in group["source"].dropna()})
        tasks = sorted({str(value) for value in group["task"].dropna()})
        conditions = sorted({str(value) for value in group["condition"].dropna()})
        rows.append(
            {
                "old_goodfire_label": label,
                "paper_row_count": len(group),
                "paper_sources": ";".join(sources),
                "paper_tasks": ";".join(tasks),
                "paper_conditions": ";".join(conditions),
            }
        )
    return rows


def search_neuronpedia(query: str, *, timeout: float) -> dict[str, Any]:
    """Call Neuronpedia's explanation-search endpoint for one query."""

    body = {
        "modelId": NEURONPEDIA_MODEL,
        "layers": [NEURONPEDIA_SOURCE],
        "query": query,
        "offset": 0,
    }
    request = urllib.request.Request(
        NEURONPEDIA_EXPLANATION_SEARCH_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "social-sim-open-sae-release-audit",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.load(response)


def compact_search_response(response: dict[str, Any]) -> dict[str, Any]:
    """Keep only fields needed to reproduce the approximate match table."""

    compact_results: list[dict[str, Any]] = []
    for result in response.get("results", []) or []:
        compact_results.append(
            {
                "modelId": result.get("modelId", NEURONPEDIA_MODEL),
                "layer": result.get("layer", NEURONPEDIA_SOURCE),
                "index": result.get("index", ""),
                "description": result.get("description", ""),
                "explanationModelName": result.get("explanationModelName", ""),
                "typeName": result.get("typeName", ""),
                "cosine_similarity": result.get("cosine_similarity", ""),
            }
        )
    return {
        "request": response.get("request", {}),
        "results": compact_results,
    }


def load_cache(cache_path: Path) -> dict[str, dict[str, Any]]:
    """Load cached Neuronpedia search responses."""

    if not cache_path.exists():
        return {}
    cache: dict[str, dict[str, Any]] = {}
    with cache_path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            cache[str(record["query"])] = record
    return cache


def write_cache(cache_path: Path, cache: dict[str, dict[str, Any]]) -> None:
    """Write compact Neuronpedia search responses as JSONL."""

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as handle:
        for query in sorted(cache):
            record = dict(cache[query])
            if record.get("status") == "ok":
                record["response"] = compact_search_response(record.get("response", {}))
            handle.write(json.dumps(record, sort_keys=True) + "\n")


def get_search_record(
    query: str,
    *,
    cache: dict[str, dict[str, Any]],
    refresh: bool,
    timeout: float,
    delay_seconds: float,
) -> dict[str, Any]:
    """Return a cached or live Neuronpedia search response."""

    if not refresh and query in cache:
        return cache[query]
    try:
        response = compact_search_response(search_neuronpedia(query, timeout=timeout))
        record = {
            "query": query,
            "status": "ok",
            "response": response,
            "error": "",
        }
    except Exception as exc:
        record = {
            "query": query,
            "status": "error",
            "response": {},
            "error": f"{type(exc).__name__}: {exc}",
        }
    cache[query] = record
    if delay_seconds:
        time.sleep(delay_seconds)
    return record


def rows_from_result(
    label_summary: dict[str, Any],
    search_record: dict[str, Any],
    *,
    top_k: int,
) -> list[dict[str, Any]]:
    """Flatten one Neuronpedia search response into top-k match rows."""

    old_label = str(label_summary["old_goodfire_label"])
    output_rows: list[dict[str, Any]] = []
    if search_record.get("status") != "ok":
        output_rows.append(
            {
                **label_summary,
                "candidate_rank": "",
                "candidate_feature_index": "",
                "candidate_neuronpedia_label": "",
                "candidate_cosine_similarity": "",
                "candidate_confidence_bucket": "search_error",
                "candidate_explanation_model": "",
                "candidate_explanation_type": "",
                "candidate_neuronpedia_api_url": "",
                "match_status": "approximate_search_error",
                "search_query": old_label,
                "search_endpoint": NEURONPEDIA_EXPLANATION_SEARCH_URL,
                "search_error": search_record.get("error", ""),
            }
        )
        return output_rows

    results = search_record.get("response", {}).get("results", [])[:top_k]
    for rank, result in enumerate(results, start=1):
        feature_index = int(result["index"])
        score = float(result.get("cosine_similarity", 0.0))
        output_rows.append(
            {
                **label_summary,
                "candidate_rank": rank,
                "candidate_feature_index": feature_index,
                "candidate_neuronpedia_label": result.get("description", ""),
                "candidate_cosine_similarity": score,
                "candidate_confidence_bucket": confidence_bucket(score),
                "candidate_explanation_model": result.get("explanationModelName", ""),
                "candidate_explanation_type": result.get("typeName", ""),
                "candidate_neuronpedia_api_url": neuronpedia_feature_url(feature_index),
                "match_status": "approximate_neuronpedia_explanation_search",
                "search_query": old_label,
                "search_endpoint": NEURONPEDIA_EXPLANATION_SEARCH_URL,
                "search_error": "",
            }
        )
    return output_rows


def build_matches(
    *,
    crosswalk_path: Path,
    cache_path: Path,
    refresh: bool,
    top_k: int,
    timeout: float,
    delay_seconds: float,
) -> list[dict[str, Any]]:
    """Build approximate Neuronpedia matches for all old-only labels."""

    summaries = old_only_label_summary(crosswalk_path)
    cache = load_cache(cache_path)
    rows: list[dict[str, Any]] = []
    for summary in summaries:
        query = str(summary["old_goodfire_label"])
        record = get_search_record(
            query,
            cache=cache,
            refresh=refresh,
            timeout=timeout,
            delay_seconds=delay_seconds,
        )
        rows.extend(rows_from_result(summary, record, top_k=top_k))
    write_cache(cache_path, cache)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write output rows as CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    seen: set[str] = set()
    for row in rows:
        for key in row:
            if key not in seen:
                fieldnames.append(key)
                seen.add(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_report(path: Path, *, rows: list[dict[str, Any]], output_path: Path) -> None:
    """Write a Markdown report summarizing approximate matches."""

    frame = pd.DataFrame(rows)
    ok = frame[frame["match_status"] == "approximate_neuronpedia_explanation_search"].copy()
    top1 = ok[ok["candidate_rank"].astype(str) == "1"].copy()
    old_label_count = frame["old_goodfire_label"].nunique()
    buckets = Counter(top1["candidate_confidence_bucket"]) if not top1.empty else Counter()
    source_counts = Counter()
    for value in top1.get("paper_sources", []):
        for source in str(value).split(";"):
            if source:
                source_counts[source] += 1

    lines = [
        "# Approximate Neuronpedia Matches for Old Goodfire Labels",
        "",
        f"Generated from `{release_path(output_path)}`.",
        "",
        "This table is intentionally approximate. It maps historical Goodfire",
        "natural-language labels that lack recoverable SAE indices to current",
        "Neuronpedia explanation-search candidates for the Goodfire Llama 3.3 70B",
        "SAE source. These rows are semantic label suggestions, not feature",
        "identity claims.",
        "",
        "## Method",
        "",
        "- Input labels: old Goodfire labels from",
        "  `data/processed/paper_activation_label_crosswalk.csv` with",
        "  `mapping_status=old_label_only_no_feature_index`.",
        f"- Search endpoint: `{NEURONPEDIA_EXPLANATION_SEARCH_URL}`.",
        f"- Search model/source: `{NEURONPEDIA_MODEL}` / `{NEURONPEDIA_SOURCE}`.",
        "- Query: the old Goodfire label string.",
        "- Ranking signal: Neuronpedia explanation-search cosine similarity.",
        "- Stable feature identity remains unavailable unless a `feature_index` is",
        "  recovered from historical metadata.",
        "",
        "## Coverage",
        "",
        f"- Old-label-only Goodfire labels searched: {old_label_count:,}",
        f"- Approximate candidate rows: {len(ok):,}",
        f"- Top-1 confidence buckets: {dict(sorted(buckets.items()))}",
        f"- Top-1 labels by paper source: {dict(sorted(source_counts.items()))}",
        "",
        "## Top-1 Candidate Examples",
        "",
        "| Old Goodfire label | Candidate feature | Neuronpedia description | Similarity | Confidence |",
        "| --- | ---: | --- | ---: | --- |",
    ]
    if not top1.empty:
        ranked = top1.sort_values(
            ["candidate_cosine_similarity", "paper_row_count"],
            ascending=[False, False],
        ).head(20)
        for row in ranked.to_dict("records"):
            lines.append(
                "| "
                + " | ".join(
                    [
                        str(row["old_goodfire_label"]).replace("|", "\\|"),
                        str(int(row["candidate_feature_index"])),
                        str(row["candidate_neuronpedia_label"]).replace("|", "\\|"),
                        f"{float(row['candidate_cosine_similarity']):.3f}",
                        str(row["candidate_confidence_bucket"]),
                    ]
                )
                + " |"
            )
    lines.extend(
        [
            "",
            "## Interpretation Rule",
            "",
            "Use `paper_activation_label_crosswalk.csv` for exact mappings. Use this",
            "approximate table only for human-readable label replacement or appendix",
            "triage. Do not use approximate candidates as evidence that the old",
            "Goodfire activation row and the Neuronpedia feature are the same SAE",
            "feature.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def check_outputs(rows: list[dict[str, Any]], *, top_k: int) -> None:
    """Validate approximate-match outputs."""

    frame = pd.DataFrame(rows)
    if frame["old_goodfire_label"].nunique() != EXPECTED_OLD_ONLY_LABELS:
        raise AssertionError(
            "Expected "
            f"{EXPECTED_OLD_ONLY_LABELS} old-only labels, found "
            f"{frame['old_goodfire_label'].nunique()}"
        )
    if len(frame) != EXPECTED_OLD_ONLY_LABELS * top_k:
        raise AssertionError(
            f"Expected {EXPECTED_OLD_ONLY_LABELS * top_k} approximate rows, found {len(frame)}"
        )
    if set(frame["match_status"]) != {"approximate_neuronpedia_explanation_search"}:
        raise AssertionError(f"Unexpected approximate match statuses: {set(frame['match_status'])}")
    if frame["candidate_feature_index"].isna().any():
        raise AssertionError("Approximate match rows must have candidate feature indices")
    if frame["candidate_neuronpedia_label"].fillna("").str.strip().eq("").any():
        raise AssertionError("Approximate match rows must have candidate labels")
    if not frame["candidate_neuronpedia_api_url"].str.startswith(
        "https://www.neuronpedia.org/api/feature/"
    ).all():
        raise AssertionError("Approximate match rows contain invalid Neuronpedia URLs")
    if not ((frame["candidate_cosine_similarity"] >= 0) & (frame["candidate_cosine_similarity"] <= 1)).all():
        raise AssertionError("Approximate match similarity scores should be in [0, 1]")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--crosswalk",
        type=Path,
        default=REPO_ROOT / "data/processed/paper_activation_label_crosswalk.csv",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data/processed/paper_activation_neuronpedia_approx_matches.csv",
    )
    parser.add_argument(
        "--cache",
        type=Path,
        default=REPO_ROOT / "data/processed/paper_activation_neuronpedia_approx_search_cache.jsonl",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "reports/PAPER_ACTIVATION_NEURONPEDIA_APPROX_MATCHES.md",
    )
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--refresh-neuronpedia", action="store_true")
    parser.add_argument("--neuronpedia-timeout", type=float, default=20.0)
    parser.add_argument("--delay-seconds", type=float, default=0.05)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Build approximate Neuronpedia label matches."""

    args = parse_args()
    if not args.crosswalk.exists():
        raise FileNotFoundError(args.crosswalk)
    rows = build_matches(
        crosswalk_path=args.crosswalk,
        cache_path=args.cache,
        refresh=args.refresh_neuronpedia,
        top_k=args.top_k,
        timeout=args.neuronpedia_timeout,
        delay_seconds=args.delay_seconds,
    )
    write_csv(args.output, rows)
    write_report(args.report, rows=rows, output_path=args.output)
    if args.check:
        check_outputs(rows, top_k=args.top_k)
    frame = pd.DataFrame(rows)
    print(
        json.dumps(
            {
                "old_only_labels": int(frame["old_goodfire_label"].nunique()),
                "approximate_rows": len(frame),
                "top_k": args.top_k,
                "output": release_path(args.output),
                "cache": release_path(args.cache),
                "report": release_path(args.report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
