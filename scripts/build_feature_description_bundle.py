#!/usr/bin/env python3
"""Build an offline feature-index to description lookup from released outputs."""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEURONPEDIA_MODEL = "llama3.3-70b-it"
DEFAULT_NEURONPEDIA_SOURCE = "50-resid-post-gf"
NEURONPEDIA_API_TEMPLATE = (
    "https://www.neuronpedia.org/api/feature/"
    "{model}/{source}/{feature_index}"
)
FALLBACK_LABEL_RE = re.compile(r"^feature_\d+$")


@dataclass(frozen=True)
class OutputSpec:
    """One released Open-SAE output folder to include in the lookup."""

    dataset_kind: str
    base_dir: Path


OUTPUT_SPECS = [
    OutputSpec(
        dataset_kind="creativity",
        base_dir=REPO_ROOT / "data/processed/creativity/open_sae_response_only_frequency",
    ),
    OutputSpec(
        dataset_kind="safe_risky",
        base_dir=REPO_ROOT / "data/processed/games/safe_risky/open_sae_calibration",
    ),
    OutputSpec(
        dataset_kind="ultimatum",
        base_dir=REPO_ROOT / "data/processed/games/ultimatum/open_sae_full",
    ),
    OutputSpec(
        dataset_kind="trust",
        base_dir=REPO_ROOT / "data/processed/games/trust/open_sae_full",
    ),
]


def relative_path(path: Path) -> str:
    """Return a stable repo-relative path string."""

    return str(path.relative_to(REPO_ROOT))


def read_metadata(base_dir: Path) -> dict[str, Any]:
    """Read Open-SAE metadata when present."""

    metadata_path = base_dir / "open_sae_metadata.json"
    if not metadata_path.exists():
        return {}
    return json.loads(metadata_path.read_text(encoding="utf-8"))


def label_source_for(label: str) -> str:
    """Classify whether a label is a cached description or feature-id fallback."""

    if FALLBACK_LABEL_RE.match(label.strip()):
        return "feature_index_fallback"
    return "cached_neuronpedia"


def clean_cell(value: Any) -> str:
    """Normalize optional CSV cells for deterministic output."""

    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def iter_rows_for_file(
    *,
    spec: OutputSpec,
    metadata: dict[str, Any],
    filename: str,
    rank_scope: str,
) -> list[dict[str, Any]]:
    """Load one top-feature CSV and convert it to lookup rows."""

    path = spec.base_dir / filename
    if not path.exists():
        return []

    frame = pd.read_csv(path)
    required = {
        "task",
        "condition",
        "rank",
        "feature_index",
        "feature_label",
        "mean_activation",
        "n_response_units",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{relative_path(path)} missing required columns: {missing}")

    neuronpedia_model = metadata.get("neuronpedia_model", DEFAULT_NEURONPEDIA_MODEL)
    neuronpedia_source = metadata.get("neuronpedia_source", DEFAULT_NEURONPEDIA_SOURCE)

    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        feature_index = int(record["feature_index"])
        feature_label = clean_cell(record.get("feature_label"))
        rows.append(
            {
                "dataset_kind": spec.dataset_kind,
                "task": clean_cell(record.get("task")),
                "condition": clean_cell(record.get("condition")),
                "reward": clean_cell(record.get("reward")),
                "rank_scope": rank_scope,
                "rank": int(record["rank"]),
                "feature_index": feature_index,
                "feature_label": feature_label,
                "mean_activation": float(record["mean_activation"]),
                "n_response_units": int(record["n_response_units"]),
                "source_output": relative_path(spec.base_dir),
                "neuronpedia_model": neuronpedia_model,
                "neuronpedia_source": neuronpedia_source,
                "label_source": label_source_for(feature_label),
                "neuronpedia_api_url": NEURONPEDIA_API_TEMPLATE.format(
                    model=neuronpedia_model,
                    source=neuronpedia_source,
                    feature_index=feature_index,
                ),
            }
        )
    return rows


def build_lookup_rows() -> list[dict[str, Any]]:
    """Build all lookup rows from released condition and reward top-feature files."""

    rows: list[dict[str, Any]] = []
    for spec in OUTPUT_SPECS:
        metadata = read_metadata(spec.base_dir)
        rows.extend(
            iter_rows_for_file(
                spec=spec,
                metadata=metadata,
                filename="open_sae_condition_top_features.csv",
                rank_scope="condition",
            )
        )
        rows.extend(
            iter_rows_for_file(
                spec=spec,
                metadata=metadata,
                filename="open_sae_condition_reward_top_features.csv",
                rank_scope="condition_reward",
            )
        )

    rows.sort(
        key=lambda row: (
            row["dataset_kind"],
            row["task"],
            row["condition"],
            row["rank_scope"],
            int(row["reward"]) if str(row["reward"]).isdigit() else -1,
            row["rank"],
            row["feature_index"],
        )
    )
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows as a deterministic CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "dataset_kind",
        "task",
        "condition",
        "reward",
        "rank_scope",
        "rank",
        "feature_index",
        "feature_label",
        "mean_activation",
        "n_response_units",
        "source_output",
        "neuronpedia_model",
        "neuronpedia_source",
        "label_source",
        "neuronpedia_api_url",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: Any) -> str:
    """Escape a value for a compact Markdown table."""

    return clean_cell(value).replace("|", "\\|").replace("\n", " ")


def format_top_table(rows: list[dict[str, Any]], dataset_kind: str) -> str:
    """Format condition-level top features for one dataset."""

    selected = [
        row
        for row in rows
        if row["dataset_kind"] == dataset_kind
        and row["rank_scope"] == "condition"
        and int(row["rank"]) <= 5
    ]
    lines = [
        "| Condition | Rank | Feature index | Description | Mean activation |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for row in selected:
        lines.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["condition"]),
                    markdown_cell(row["rank"]),
                    markdown_cell(row["feature_index"]),
                    markdown_cell(row["feature_label"]),
                    f"{float(row['mean_activation']):.3f}",
                ]
            )
            + " |"
        )
    return "\n".join(lines)


def write_summary(path: Path, rows: list[dict[str, Any]], lookup_path: Path) -> None:
    """Write a short public summary focused on safe-risk/lottery and ultimatum."""

    path.parent.mkdir(parents=True, exist_ok=True)
    counts = pd.DataFrame(rows).groupby("dataset_kind").size().to_dict()
    text = f"""# Feature Description Summary

Generated from `{relative_path(lookup_path)}`.

The stable identifier is `feature_index`. `feature_label` is a cached Neuronpedia
description attached to the Goodfire Open-SAE feature. The label is an
interpretability aid, not the historical hosted Goodfire Ember label string.

## Coverage

| Dataset | Lookup rows |
| --- | ---: |
| creativity | {counts.get("creativity", 0)} |
| safe_risky / lottery | {counts.get("safe_risky", 0)} |
| ultimatum | {counts.get("ultimatum", 0)} |
| trust | {counts.get("trust", 0)} |

## Safe-Risk / Lottery Top Descriptions

{format_top_table(rows, "safe_risky")}

## Ultimatum Top Descriptions

{format_top_table(rows, "ultimatum")}
"""
    path.write_text(text, encoding="utf-8")


def check_rows(rows: list[dict[str, Any]]) -> None:
    """Validate the generated lookup against release expectations."""

    if not rows:
        raise AssertionError("Feature description lookup is empty")
    datasets = {row["dataset_kind"] for row in rows}
    for required in {"safe_risky", "ultimatum"}:
        if required not in datasets:
            raise AssertionError(f"Missing {required} rows in feature description lookup")
    missing_labels = [row for row in rows if not str(row["feature_label"]).strip()]
    if missing_labels:
        raise AssertionError(f"{len(missing_labels)} lookup rows have empty labels")
    fallback_labels = [
        row for row in rows if row["label_source"] == "feature_index_fallback"
    ]
    if fallback_labels:
        raise AssertionError(f"{len(fallback_labels)} lookup rows use feature-index fallbacks")
    bad_urls = [
        row
        for row in rows
        if not str(row["neuronpedia_api_url"]).startswith("https://www.neuronpedia.org/api/feature/")
    ]
    if bad_urls:
        raise AssertionError(f"{len(bad_urls)} lookup rows have invalid Neuronpedia URLs")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=REPO_ROOT / "data/processed/feature_description_lookup.csv",
    )
    parser.add_argument(
        "--summary",
        type=Path,
        default=REPO_ROOT / "reports/FEATURE_DESCRIPTION_SUMMARY.md",
    )
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_lookup_rows()
    write_csv(args.output, rows)
    write_summary(args.summary, rows, args.output)
    if args.check:
        check_rows(rows)
    print(
        json.dumps(
            {
                "lookup_rows": len(rows),
                "output": relative_path(args.output),
                "summary": relative_path(args.summary),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
