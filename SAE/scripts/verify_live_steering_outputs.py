#!/usr/bin/env python3
"""Verify live Open-SAE steering generation outputs.

This check is intentionally narrow: it validates the fresh steering runs that
replace deprecated Goodfire controller generation for the paper games. It does
not inspect archived Goodfire provenance or unrelated post-hoc Open-SAE runs.
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ExpectedRun:
    path: str
    dataset_kind: str
    expected_units: int
    expected_topk_rows: int
    conditions: set[str]
    allowed_answers: set[str] | None


EXPECTED_SMOKE_RUNS = [
    ExpectedRun(
        "runs/safe_risky_open_sae_steering_lite_smoke",
        "safe_risky",
        8,
        80,
        {"lite_steering"},
        {"Safe Option", "Risky Option"},
    ),
    ExpectedRun(
        "runs/safe_risky_open_sae_steering_full_smoke",
        "safe_risky",
        8,
        80,
        {"steering"},
        {"Safe Option", "Risky Option"},
    ),
    ExpectedRun(
        "runs/ultimatum_open_sae_steering_smoke",
        "ultimatum",
        8,
        80,
        {"steering"},
        {"Accept", "Reject"},
    ),
    ExpectedRun(
        "runs/trust_open_sae_steering_smoke",
        "trust",
        8,
        80,
        {"baseline", "intervention"},
        None,
    ),
]

EXPECTED_FULL_RUNS = [
    ExpectedRun(
        "runs/safe_risky_open_sae_steering_lite_full",
        "safe_risky",
        1400,
        14000,
        {"lite_steering"},
        {"Safe Option", "Risky Option"},
    ),
    ExpectedRun(
        "runs/safe_risky_open_sae_steering_full",
        "safe_risky",
        1400,
        14000,
        {"steering"},
        {"Safe Option", "Risky Option"},
    ),
    ExpectedRun(
        "runs/ultimatum_open_sae_steering_full",
        "ultimatum",
        680,
        6800,
        {"steering"},
        {"Accept", "Reject"},
    ),
    ExpectedRun(
        "runs/trust_open_sae_steering_full",
        "trust",
        200,
        2000,
        {"baseline", "intervention"},
        None,
    ),
]


def require(path: Path) -> Path:
    if not path.exists():
        raise AssertionError(f"Missing required path: {path.relative_to(ROOT)}")
    if path.is_file() and path.stat().st_size <= 0:
        raise AssertionError(f"Required file is empty: {path.relative_to(ROOT)}")
    return path


def read_json(path: Path) -> dict:
    return json.loads(require(path).read_text(encoding="utf-8"))


def assert_numeric_series(series: pd.Series, *, name: str) -> None:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise AssertionError(f"{name} contains nonnumeric values")
    if not values.map(math.isfinite).all():
        raise AssertionError(f"{name} contains nonfinite values")


def check_answer_parsing(run: ExpectedRun, response_units: pd.DataFrame) -> None:
    if "generated_answer_parse_status" not in response_units.columns:
        raise AssertionError(f"{run.path} missing generated_answer_parse_status")
    if response_units["generated_answer_parse_status"].str.startswith("unparsed").any():
        bad = response_units[
            response_units["generated_answer_parse_status"].str.startswith("unparsed")
        ]
        raise AssertionError(f"{run.path} has {len(bad)} unparsed generated answers")

    if run.allowed_answers is not None:
        found = set(response_units["answer_text"].dropna().astype(str))
        if not found.issubset(run.allowed_answers):
            raise AssertionError(
                f"{run.path} has unexpected answers: {sorted(found - run.allowed_answers)}"
            )
    elif run.dataset_kind == "trust":
        assert_numeric_series(response_units["answer_text"], name=f"{run.path} answer_text")


def check_run(run: ExpectedRun) -> dict[str, object]:
    base = ROOT / run.path
    response_units = pd.read_csv(require(base / "response_units.csv"))
    steering_meta = read_json(base / "open_sae_steering_metadata.json")
    open_sae_dir = base / "open_sae"
    acts = pd.read_csv(require(open_sae_dir / "open_sae_feature_activations.csv"))
    condition_top = pd.read_csv(require(open_sae_dir / "open_sae_condition_top_features.csv"))
    open_sae_meta = read_json(open_sae_dir / "open_sae_metadata.json")

    if len(response_units) != run.expected_units:
        raise AssertionError(
            f"{run.path} expected {run.expected_units} response units, found {len(response_units)}"
        )
    if len(acts) != run.expected_topk_rows:
        raise AssertionError(
            f"{run.path} expected {run.expected_topk_rows} top-k rows, found {len(acts)}"
        )
    if steering_meta.get("generated_response_units") != run.expected_units:
        raise AssertionError(f"{run.path} steering metadata unit count mismatch")
    if open_sae_meta.get("processed_response_task_units") != run.expected_units:
        raise AssertionError(f"{run.path} Open-SAE metadata unit count mismatch")
    if set(response_units["condition"].astype(str)) != run.conditions:
        raise AssertionError(
            f"{run.path} condition mismatch: {sorted(set(response_units['condition'].astype(str)))}"
        )
    if steering_meta.get("dataset_kind") != run.dataset_kind:
        raise AssertionError(f"{run.path} steering metadata dataset mismatch")
    if open_sae_meta.get("dataset_kind") != run.dataset_kind:
        raise AssertionError(f"{run.path} Open-SAE metadata dataset mismatch")
    if condition_top.empty:
        raise AssertionError(f"{run.path} has empty condition top-feature table")
    if (pd.to_numeric(acts["activation"], errors="coerce") < 0).any():
        raise AssertionError(f"{run.path} contains negative SAE activations")
    assert_numeric_series(acts["activation"], name=f"{run.path} activation")
    check_answer_parsing(run, response_units)

    return {
        "run": run.path,
        "dataset_kind": run.dataset_kind,
        "response_units": len(response_units),
        "topk_rows": len(acts),
        "conditions": sorted(run.conditions),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=["smoke", "full", "all"],
        default="all",
        help="Which expected fresh steering outputs to verify.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    runs: list[ExpectedRun] = []
    if args.scope in {"smoke", "all"}:
        runs.extend(EXPECTED_SMOKE_RUNS)
    if args.scope in {"full", "all"}:
        runs.extend(EXPECTED_FULL_RUNS)

    results = [check_run(run) for run in runs]
    print(json.dumps({"status": "ok", "verified": results}, indent=2))


if __name__ == "__main__":
    main()
