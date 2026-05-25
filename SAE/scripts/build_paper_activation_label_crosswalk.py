#!/usr/bin/env python3
"""Build paper-facing Goodfire-to-Neuronpedia label crosswalks."""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
NEURONPEDIA_MODEL = "llama3.3-70b-it"
NEURONPEDIA_SOURCE = "50-resid-post-gf"
NEURONPEDIA_API_TEMPLATE = (
    "https://www.neuronpedia.org/api/feature/"
    f"{NEURONPEDIA_MODEL}/{NEURONPEDIA_SOURCE}/{{feature_index}}"
)
PAPER_REQUIRED_COLUMNS = {
    "source",
    "task",
    "condition",
    "offer_amount",
    "agent_index",
    "rank",
    "feature_label",
    "activation",
}
EXPECTED_EXACT_PAPER_ROWS = 3478
EXPECTED_OLD_ONLY_PAPER_ROWS = 58862
EXPECTED_TOTAL_PAPER_ROWS = 62340
EXPECTED_UNIQUE_OLD_LABELS = 106
EXPECTED_STEERING_FEATURES = {13142, 20117, 4992, 184, 4237, 31935}

# These are release-time Neuronpedia descriptions for controller features that
# are not always present in the processed top-feature caches.
KNOWN_RELEASE_NEURONPEDIA_LABELS = {
    184: "sacrifice for or at",
    4237: "before activities or anything",
    4992: "creative in thinking",
    11444: "trust and responsibility",
    13142: "creative acts and originality",
    17623: "trustworthy and reliable advice",
    20117: "creative and innovative thinking",
    31935: "sacrifice and empathy",
    38558: "us with",
    39359: "trust you have",
}


def release_path(path: Path | str) -> str:
    """Return a repo-relative path when possible."""

    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def neuronpedia_api_url(feature_index: int) -> str:
    """Return the Neuronpedia feature endpoint for this release's model/source."""

    return NEURONPEDIA_API_TEMPLATE.format(feature_index=int(feature_index))


def parse_condition_and_reward(path: Path) -> tuple[str, str]:
    """Infer the experimental condition and reward/offer from a raw result path."""

    stem = path.stem
    reward_match = re.search(r"(?:_|sent_)(\d+)$", stem)
    reward = reward_match.group(1) if reward_match else ""

    if stem in {"high_steering", "prompting", "baseline", "high_temperature"}:
        return stem, reward
    if stem.startswith("safe_risky_lite_steering_"):
        return "lite_steering", reward
    if stem.startswith("safe_risky_steering_"):
        return "steering", reward
    if stem.startswith("ultimatum_steering_"):
        return "steering", reward
    if stem.startswith("trust_game_intervention_sent_"):
        return "intervention", reward
    if stem.startswith("trust_game_baseline_sent_"):
        return "baseline", reward
    return "", reward


def dataset_kind_for_path(path: Path) -> str:
    """Infer the dataset family from a repo-relative path."""

    text = path.as_posix()
    if "/creativity/" in text or text.startswith("data/raw/creativity/"):
        return "creativity"
    if "/safe_risky/" in text or "safe_risky" in path.name:
        return "safe_risky"
    if "/ultimatum/" in text or "ultimatum" in path.name:
        return "ultimatum"
    if "/trust/" in text or "trust_game" in path.name:
        return "trust"
    return "unknown"


def read_controller_strings(path: Path) -> list[str]:
    """Read unique serialized Goodfire controller values from one CSV."""

    try:
        header = pd.read_csv(path, nrows=0).columns
    except Exception:
        return []
    if "model.controller" not in header:
        return []
    try:
        values = pd.read_csv(path, usecols=["model.controller"])["model.controller"]
    except Exception:
        return []
    return sorted(
        {
            str(value)
            for value in values.dropna()
            if "index_in_sae" in str(value)
        }
    )


def iter_controller_features() -> list[dict[str, Any]]:
    """Extract indexed historical Goodfire controller features from raw CSVs."""

    rows: list[dict[str, Any]] = []
    for path in sorted((REPO_ROOT / "data/raw").rglob("*.csv")):
        rel_path = Path(release_path(path))
        dataset_kind = dataset_kind_for_path(rel_path)
        condition, reward = parse_condition_and_reward(path)
        for raw_controller in read_controller_strings(path):
            try:
                controller = ast.literal_eval(raw_controller)
            except (SyntaxError, ValueError):
                continue
            for intervention in controller.get("interventions", []) or []:
                features = (intervention.get("features") or {}).get("features") or []
                for feature in features:
                    label = str(feature.get("label", "")).strip()
                    feature_index = feature.get("index_in_sae")
                    if not label or feature_index is None:
                        continue
                    rows.append(
                        {
                            "dataset_kind": dataset_kind,
                            "condition": condition,
                            "reward": reward,
                            "feature_index": int(feature_index),
                            "old_goodfire_label": label,
                            "nudge_value": intervention.get("value", ""),
                            "mode": intervention.get("mode", ""),
                            "max_activation_strength": feature.get("max_activation_strength", ""),
                            "controller_name": controller.get("name", ""),
                            "source_file": rel_path.as_posix(),
                        }
                    )
    return rows


def aggregate_controller_features(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse repeated reward files into one row per indexed controller feature."""

    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = (
            row["dataset_kind"],
            row["condition"],
            row["feature_index"],
            row["old_goodfire_label"],
            str(row["nudge_value"]),
            row["mode"],
        )
        grouped[key].append(row)

    output: list[dict[str, Any]] = []
    for key in sorted(grouped, key=lambda item: (str(item[0]), str(item[1]), int(item[2]), str(item[4]))):
        group = grouped[key]
        rewards = sorted({str(row["reward"]) for row in group if str(row["reward"])})
        source_files = sorted({row["source_file"] for row in group})
        first = group[0]
        output.append(
            {
                "dataset_kind": first["dataset_kind"],
                "condition": first["condition"],
                "feature_index": int(first["feature_index"]),
                "old_goodfire_label": first["old_goodfire_label"],
                "nudge_value": first["nudge_value"],
                "mode": first["mode"],
                "max_activation_strength": first["max_activation_strength"],
                "controller_name": first["controller_name"],
                "reward_values": ";".join(rewards),
                "source_file_count": len(source_files),
                "source_file": source_files[0] if source_files else "",
            }
        )
    return output


def load_cached_neuronpedia_labels() -> dict[int, dict[str, str]]:
    """Load cached Neuronpedia labels from existing processed release artifacts."""

    labels: dict[int, dict[str, str]] = {}

    def add(feature_index: Any, label: Any, source: str) -> None:
        if pd.isna(feature_index) or label is None or str(label).strip() == "":
            return
        try:
            index = int(feature_index)
        except (TypeError, ValueError):
            return
        text = str(label).strip()
        if text.startswith("feature_"):
            return
        labels.setdefault(index, {"label": text, "label_source": source})

    lookup = REPO_ROOT / "data/processed/feature_description_lookup.csv"
    if lookup.exists():
        frame = pd.read_csv(lookup)
        for row in frame.to_dict("records"):
            add(row.get("feature_index"), row.get("feature_label"), "cached_neuronpedia")

    for path in sorted(REPO_ROOT.rglob("feature_label_cache.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for feature_index, label in data.items():
            add(feature_index, label, "cached_neuronpedia")

    for path in sorted(REPO_ROOT.rglob("open_sae_steering_feature_metadata.csv")):
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        for row in frame.to_dict("records"):
            add(row.get("feature_index"), row.get("feature_label"), "cached_neuronpedia")

    for feature_index, label in KNOWN_RELEASE_NEURONPEDIA_LABELS.items():
        labels.setdefault(
            feature_index,
            {"label": label, "label_source": "release_known_neuronpedia"},
        )
    return labels


def fetch_neuronpedia_label(feature_index: int, timeout: float) -> str:
    """Fetch a Neuronpedia feature description."""

    with urllib.request.urlopen(neuronpedia_api_url(feature_index), timeout=timeout) as response:
        payload = json.load(response)
    explanations = payload.get("explanations") or []
    if explanations:
        description = explanations[0].get("description")
        if description:
            return str(description).strip()
    return ""


def resolve_neuronpedia_labels(
    feature_indices: set[int],
    *,
    refresh_neuronpedia: bool,
    timeout: float,
) -> dict[int, dict[str, str]]:
    """Return label metadata for a set of feature indices."""

    labels = load_cached_neuronpedia_labels()
    missing = sorted(feature_indices - set(labels))
    if refresh_neuronpedia:
        for feature_index in sorted(feature_indices):
            try:
                label = fetch_neuronpedia_label(feature_index, timeout=timeout)
            except Exception:
                continue
            if label:
                labels[feature_index] = {
                    "label": label,
                    "label_source": "live_neuronpedia",
                }
    else:
        for feature_index in missing:
            labels.setdefault(
                feature_index,
                {"label": "", "label_source": "missing_neuronpedia_label"},
            )
    return labels


def add_neuronpedia_fields(
    row: dict[str, Any],
    labels: dict[int, dict[str, str]],
) -> dict[str, Any]:
    """Attach Neuronpedia metadata to a row with a feature index."""

    feature_index = row.get("feature_index")
    if feature_index in {"", None} or pd.isna(feature_index):
        row.update(
            {
                "neuronpedia_label": "",
                "neuronpedia_model": "",
                "neuronpedia_source": "",
                "neuronpedia_api_url": "",
                "label_source": "",
            }
        )
        return row
    index = int(feature_index)
    label_record = labels.get(index, {"label": "", "label_source": "missing_neuronpedia_label"})
    row.update(
        {
            "neuronpedia_label": label_record.get("label", ""),
            "neuronpedia_model": NEURONPEDIA_MODEL,
            "neuronpedia_source": NEURONPEDIA_SOURCE,
            "neuronpedia_api_url": neuronpedia_api_url(index),
            "label_source": label_record.get("label_source", ""),
        }
    )
    return row


def build_steering_crosswalk(
    controller_rows: list[dict[str, Any]],
    labels: dict[int, dict[str, str]],
) -> list[dict[str, Any]]:
    """Build a broad crosswalk for all indexed controller features."""

    rows = aggregate_controller_features(controller_rows)
    for row in rows:
        add_neuronpedia_fields(row, labels)
    return rows


def build_old_label_index_map(
    steering_rows: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Create exact old-label mappings only where the feature index is unique."""

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in steering_rows:
        grouped[row["old_goodfire_label"]].append(row)

    label_map: dict[str, dict[str, Any]] = {}
    for label, rows in grouped.items():
        feature_indices = {int(row["feature_index"]) for row in rows}
        if len(feature_indices) != 1:
            continue
        dataset_kinds = sorted({row["dataset_kind"] for row in rows})
        source_file_count = sum(int(row.get("source_file_count", 1)) for row in rows)
        example_files = sorted({row["source_file"] for row in rows if row.get("source_file")})
        representative = rows[0]
        label_map[label] = {
            "feature_index": int(representative["feature_index"]),
            "metadata_dataset_kinds": ";".join(dataset_kinds),
            "metadata_source_file_count": source_file_count,
            "metadata_example_source_file": example_files[0] if example_files else "",
        }
    return label_map


def build_paper_crosswalk(
    paper_activations: Path,
    steering_rows: list[dict[str, Any]],
    labels: dict[int, dict[str, str]],
) -> list[dict[str, Any]]:
    """Build the full paper activation crosswalk."""

    frame = pd.read_csv(paper_activations)
    missing_columns = PAPER_REQUIRED_COLUMNS - set(frame.columns)
    if missing_columns:
        raise ValueError(
            f"Paper activation CSV is missing columns: {sorted(missing_columns)}"
        )

    label_map = build_old_label_index_map(steering_rows)
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict("records"):
        old_label = str(record["feature_label"])
        mapped = label_map.get(old_label)
        row: dict[str, Any] = {
            "source": record["source"],
            "task": record["task"],
            "condition": record["condition"],
            "offer_amount": "" if pd.isna(record["offer_amount"]) else record["offer_amount"],
            "agent_index": "" if pd.isna(record["agent_index"]) else record["agent_index"],
            "rank": int(record["rank"]),
            "old_goodfire_label": old_label,
            "old_goodfire_activation": record["activation"],
            "feature_index": int(mapped["feature_index"]) if mapped else "",
            "metadata_dataset_kinds": mapped["metadata_dataset_kinds"] if mapped else "",
            "metadata_source_file_count": mapped["metadata_source_file_count"] if mapped else "",
            "metadata_example_source_file": mapped["metadata_example_source_file"] if mapped else "",
            "mapping_status": "exact_feature_index_match" if mapped else "old_label_only_no_feature_index",
        }
        add_neuronpedia_fields(row, labels)
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write rows to CSV."""

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


def report_table(rows: list[dict[str, Any]], feature_indices: list[int]) -> list[str]:
    """Build a Markdown table for selected features."""

    by_index = {int(row["feature_index"]): row for row in rows}
    lines = [
        "| Feature index | Old Goodfire label | Neuronpedia label |",
        "| ---: | --- | --- |",
    ]
    for feature_index in feature_indices:
        row = by_index.get(feature_index)
        if row is None:
            continue
        lines.append(
            f"| {feature_index} | {row['old_goodfire_label']} | {row['neuronpedia_label']} |"
        )
    return lines


def write_report(
    path: Path,
    *,
    paper_rows: list[dict[str, Any]],
    steering_rows: list[dict[str, Any]],
    paper_output: Path,
    steering_output: Path,
) -> None:
    """Write a concise paper-facing Markdown report."""

    exact_rows = [row for row in paper_rows if row["mapping_status"] == "exact_feature_index_match"]
    old_only_rows = [row for row in paper_rows if row["mapping_status"] == "old_label_only_no_feature_index"]
    old_labels = {row["old_goodfire_label"] for row in paper_rows}
    exact_labels = sorted({row["old_goodfire_label"] for row in exact_rows})
    paper_exact_indices = sorted({int(row["feature_index"]) for row in exact_rows})
    steering_indices = sorted({int(row["feature_index"]) for row in steering_rows})

    steering_by_index = {int(row["feature_index"]): row for row in steering_rows}
    creativity_13142 = steering_by_index.get(13142)

    text = [
        "# Paper Activation Label Crosswalk",
        "",
        f"Generated from `{release_path(paper_output)}` and `{release_path(steering_output)}`.",
        "",
        "The stable identifier for an SAE feature is `feature_index`. Historical",
        "Goodfire activation logs in the paper-facing CSV often contain only the",
        "hosted Goodfire natural-language label, not the feature index. Those rows",
        "are preserved, but they are not treated as exact Neuronpedia mappings.",
        "",
        "## Coverage",
        "",
        f"- Paper activation rows: {len(paper_rows):,}",
        f"- Unique old Goodfire labels: {len(old_labels):,}",
        f"- Exact feature-index rows: {len(exact_rows):,}",
        f"- Old-label-only rows: {len(old_only_rows):,}",
        f"- Exact old labels in the paper CSV: {len(exact_labels):,}",
        f"- Exact feature indices in the paper CSV: {len(paper_exact_indices):,}",
        f"- Indexed steering/provenance features: {len(steering_indices):,}",
        "",
        "Rows with `mapping_status=exact_feature_index_match` have a recovered",
        "`feature_index` from saved Goodfire controller metadata. Rows with",
        "`mapping_status=old_label_only_no_feature_index` retain the old Goodfire",
        "label and activation but should not be described as exact feature identity",
        "matches to Neuronpedia.",
        "",
        "A companion source audit is available at",
        "`reports/PAPER_ACTIVATION_INDEX_SEARCH_AUDIT.md`. That audit searches",
        "the release repo plus companion EDSL/Goodfire development checkouts and",
        "keeps the same strict rule: no fuzzy label matching and no co-location",
        "matching across separate notebook cells or JSONL records.",
        "`reports/PAPER_ACTIVATION_GIT_HISTORY_AUDIT.md` extends the same",
        "strict search across reachable git history.",
        "",
        "## Exact Paper-CSV Matches",
        "",
        *report_table(steering_rows, [184, 4237, 31935, 20117, 4992]),
        "",
        "## Steering-Provenance Features",
        "",
        "The paper activation CSV does not contain every controller feature that was",
        "used for steering. The broader steering crosswalk keeps those indexed",
        "controller features as provenance.",
        "",
        *report_table(steering_rows, [13142, 20117, 4992, 184, 4237, 31935]),
        "",
    ]
    if creativity_13142:
        text.extend(
            [
                "`13142` is present in saved creativity steering provenance but absent",
                "from the supplied combined paper activation CSV. It is still included",
                "in the steering crosswalk because it is a saved controller feature.",
                "",
            ]
        )
    text.extend(
        [
            "## Source Pattern",
            "",
            "Neuronpedia feature descriptions are attached through:",
            "",
            "`https://www.neuronpedia.org/api/feature/llama3.3-70b-it/50-resid-post-gf/<feature_index>`",
            "",
            "Neuronpedia stores the released description under",
            "`explanations[0].description`; the top-level `label` field may be empty.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(text), encoding="utf-8")


def check_outputs(
    paper_rows: list[dict[str, Any]],
    steering_rows: list[dict[str, Any]],
) -> None:
    """Validate generated crosswalks."""

    if len(paper_rows) != EXPECTED_TOTAL_PAPER_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_TOTAL_PAPER_ROWS:,} paper rows, found {len(paper_rows):,}"
        )
    old_labels = {row["old_goodfire_label"] for row in paper_rows}
    if len(old_labels) != EXPECTED_UNIQUE_OLD_LABELS:
        raise AssertionError(
            f"Expected {EXPECTED_UNIQUE_OLD_LABELS} unique old labels, found {len(old_labels)}"
        )
    exact_rows = [row for row in paper_rows if row["mapping_status"] == "exact_feature_index_match"]
    old_only_rows = [row for row in paper_rows if row["mapping_status"] == "old_label_only_no_feature_index"]
    if len(exact_rows) != EXPECTED_EXACT_PAPER_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_EXACT_PAPER_ROWS:,} exact rows, found {len(exact_rows):,}"
        )
    if len(old_only_rows) != EXPECTED_OLD_ONLY_PAPER_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_OLD_ONLY_PAPER_ROWS:,} old-only rows, found {len(old_only_rows):,}"
        )
    for row in exact_rows:
        if row["feature_index"] in {"", None}:
            raise AssertionError("Exact row is missing feature_index")
        if not str(row["neuronpedia_api_url"]).startswith("https://www.neuronpedia.org/api/feature/"):
            raise AssertionError(f"Invalid Neuronpedia URL for feature {row['feature_index']}")
    for row in old_only_rows:
        if row["feature_index"] not in {"", None}:
            raise AssertionError("Old-label-only row unexpectedly has feature_index")

    steering_indices = {int(row["feature_index"]) for row in steering_rows}
    missing = EXPECTED_STEERING_FEATURES - steering_indices
    if missing:
        raise AssertionError(f"Steering crosswalk missing feature indices: {sorted(missing)}")
    for row in steering_rows:
        if not row["old_goodfire_label"]:
            raise AssertionError(f"Steering feature {row['feature_index']} has no Goodfire label")
        if not row["neuronpedia_label"]:
            raise AssertionError(f"Steering feature {row['feature_index']} has no Neuronpedia label")
        if not str(row["neuronpedia_api_url"]).startswith("https://www.neuronpedia.org/api/feature/"):
            raise AssertionError(f"Invalid Neuronpedia URL for steering feature {row['feature_index']}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--paper-activations", type=Path, required=True)
    parser.add_argument(
        "--paper-output",
        type=Path,
        default=REPO_ROOT / "data/processed/paper_activation_label_crosswalk.csv",
    )
    parser.add_argument(
        "--steering-output",
        type=Path,
        default=REPO_ROOT / "data/processed/steering_feature_label_crosswalk.csv",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=REPO_ROOT / "reports/PAPER_ACTIVATION_LABEL_CROSSWALK.md",
    )
    parser.add_argument("--refresh-neuronpedia", action="store_true")
    parser.add_argument("--neuronpedia-timeout", type=float, default=10.0)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Build the crosswalk outputs."""

    args = parse_args()
    if not args.paper_activations.exists():
        raise FileNotFoundError(args.paper_activations)

    controller_rows = iter_controller_features()
    controller_indices = {int(row["feature_index"]) for row in controller_rows}
    labels = resolve_neuronpedia_labels(
        controller_indices,
        refresh_neuronpedia=args.refresh_neuronpedia,
        timeout=args.neuronpedia_timeout,
    )
    steering_rows = build_steering_crosswalk(controller_rows, labels)
    paper_rows = build_paper_crosswalk(args.paper_activations, steering_rows, labels)

    write_csv(args.steering_output, steering_rows)
    write_csv(args.paper_output, paper_rows)
    write_report(
        args.report,
        paper_rows=paper_rows,
        steering_rows=steering_rows,
        paper_output=args.paper_output,
        steering_output=args.steering_output,
    )
    if args.check:
        check_outputs(paper_rows, steering_rows)
    print(
        json.dumps(
            {
                "paper_rows": len(paper_rows),
                "exact_feature_index_rows": sum(
                    row["mapping_status"] == "exact_feature_index_match" for row in paper_rows
                ),
                "old_label_only_rows": sum(
                    row["mapping_status"] == "old_label_only_no_feature_index" for row in paper_rows
                ),
                "steering_rows": len(steering_rows),
                "paper_output": release_path(args.paper_output),
                "steering_output": release_path(args.steering_output),
                "report": release_path(args.report),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
