#!/usr/bin/env python3
"""Extract saved Goodfire controller steering provenance for creativity outputs."""

from __future__ import annotations

import argparse
import ast
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = REPO_ROOT / "data/raw/creativity/product_innovation_20251102_202650/high_steering.csv"
DEFAULT_OUTPUT = REPO_ROOT / "data/processed/creativity/steering_provenance/steering_features.csv"
DEFAULT_REPORT = REPO_ROOT / "data/processed/creativity/steering_provenance/STEERING_PROVENANCE.md"
EXPECTED_FEATURES = {13142, 20117, 4992}
EXPECTED_MODEL = "meta-llama/Llama-3.3-70B-Instruct"


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def relative_path(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def parse_controller(value: Any) -> dict[str, Any]:
    text = safe_text(value)
    if not text:
        return {}
    parsed = ast.literal_eval(text)
    if not isinstance(parsed, dict):
        raise ValueError("model.controller did not parse to a dict")
    return parsed


def iter_controller_features(frame: pd.DataFrame, source: Path) -> list[dict[str, Any]]:
    occurrences: list[dict[str, Any]] = []
    for row_index, row in frame.iterrows():
        controller = parse_controller(row.get("model.controller"))
        for intervention in controller.get("interventions", []):
            features = intervention.get("features", {}).get("features", [])
            for feature in features:
                feature_index = int(feature["index_in_sae"])
                occurrences.append(
                    {
                        "source_file": relative_path(source),
                        "source_row_index": int(row_index),
                        "feature_index": feature_index,
                        "old_goodfire_label": safe_text(feature.get("label")),
                        "uuid": safe_text(feature.get("uuid")),
                        "mode": safe_text(intervention.get("mode")),
                        "nudge_value": float(intervention.get("value")),
                        "max_activation_strength": float(feature.get("max_activation_strength")),
                        "controller_name": safe_text(controller.get("name")),
                        "source_model": safe_text(row.get("model.model")),
                        "inference_service": safe_text(row.get("model.inference_service")),
                        "temperature": safe_text(row.get("model.temperature")),
                    }
                )
    return occurrences


def summarize_occurrences(occurrences: list[dict[str, Any]], source_rows: int) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, Any]]] = {}
    for row in occurrences:
        grouped.setdefault(int(row["feature_index"]), []).append(row)

    rows: list[dict[str, Any]] = []
    for feature_index in sorted(grouped):
        group = grouped[feature_index]
        first = group[0]
        nudge_values = sorted({float(row["nudge_value"]) for row in group})
        modes = sorted({row["mode"] for row in group})
        labels = sorted({row["old_goodfire_label"] for row in group})
        models = sorted({row["source_model"] for row in group})
        controller_counts = Counter(row["controller_name"] for row in group)
        rows.append(
            {
                "feature_index": feature_index,
                "old_goodfire_label": labels[0],
                "nudge_value": nudge_values[0],
                "mode": modes[0],
                "max_activation_strength": float(first["max_activation_strength"]),
                "uuid": first["uuid"],
                "controller_name": controller_counts.most_common(1)[0][0],
                "source_model": models[0],
                "inference_service": first["inference_service"],
                "temperature": first["temperature"],
                "occurrence_count": len(group),
                "source_rows": source_rows,
                "source_file": first["source_file"],
            }
        )
        if len(nudge_values) != 1:
            raise ValueError(f"Feature {feature_index} has multiple nudge values: {nudge_values}")
        if len(modes) != 1:
            raise ValueError(f"Feature {feature_index} has multiple modes: {modes}")
        if len(labels) != 1:
            raise ValueError(f"Feature {feature_index} has multiple labels: {labels}")
        if len(models) != 1:
            raise ValueError(f"Feature {feature_index} has multiple source models: {models}")
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "feature_index",
        "old_goodfire_label",
        "nudge_value",
        "mode",
        "max_activation_strength",
        "uuid",
        "controller_name",
        "source_model",
        "inference_service",
        "temperature",
        "occurrence_count",
        "source_rows",
        "source_file",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def markdown_cell(value: Any) -> str:
    return safe_text(value).replace("|", "\\|").replace("\n", " ")


def write_report(path: Path, rows: list[dict[str, Any]], output: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    table = [
        "| Feature index | Old Goodfire label | Nudge | Occurrences |",
        "| ---: | --- | ---: | ---: |",
    ]
    for row in rows:
        table.append(
            "| "
            + " | ".join(
                [
                    markdown_cell(row["feature_index"]),
                    markdown_cell(row["old_goodfire_label"]),
                    markdown_cell(row["nudge_value"]),
                    markdown_cell(row["occurrence_count"]),
                ]
            )
            + " |"
        )

    text = f"""# Creativity Steering Provenance

Generated from `{rows[0]["source_file"] if rows else relative_path(DEFAULT_SOURCE)}` and
written to `{relative_path(output)}`.

The saved high-steering creativity condition used Goodfire hosted controller nudges.
This is provenance for the historical run, not an open-SAE regeneration run.

{chr(10).join(table)}

New steered responses can be generated with `scripts/run_open_sae_steering_generation.py`
by applying the same feature indices to `meta-llama/Llama-3.3-70B-Instruct` at
`model.layers.50` with `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`. That open runner is
not guaranteed to match the deprecated hosted Goodfire controller's private nudge
calibration exactly.
"""
    path.write_text(text, encoding="utf-8")


def extract(source: Path) -> list[dict[str, Any]]:
    frame = pd.read_csv(source)
    if "model.controller" not in frame.columns:
        raise ValueError(f"{relative_path(source)} is missing model.controller")
    occurrences = iter_controller_features(frame, source)
    if not occurrences:
        raise ValueError(f"No controller interventions found in {relative_path(source)}")
    return summarize_occurrences(occurrences, source_rows=len(frame))


def check_rows(rows: list[dict[str, Any]]) -> None:
    found = {int(row["feature_index"]) for row in rows}
    if found != EXPECTED_FEATURES:
        raise AssertionError(f"Expected steering features {sorted(EXPECTED_FEATURES)}, found {sorted(found)}")
    for row in rows:
        if not row["old_goodfire_label"]:
            raise AssertionError(f"Feature {row['feature_index']} is missing old Goodfire label")
        if float(row["nudge_value"]) <= 0:
            raise AssertionError(f"Feature {row['feature_index']} has nonpositive nudge value")
        if row["source_model"] != EXPECTED_MODEL:
            raise AssertionError(
                f"Feature {row['feature_index']} source model is {row['source_model']}, "
                f"expected {EXPECTED_MODEL}"
            )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = extract(args.source)
    write_csv(args.output, rows)
    write_report(args.report, rows, args.output)
    if args.check:
        check_rows(rows)
    print(
        json.dumps(
            {
                "steering_features": [row["feature_index"] for row in rows],
                "output": relative_path(args.output),
                "report": relative_path(args.report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
