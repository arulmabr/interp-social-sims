#!/usr/bin/env python3
"""Verify dose-sensitive live Open-SAE steering sweep outputs."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_open_sae_dose_sweep as sweep


def require(path: Path) -> Path:
    if not path.exists():
        raise AssertionError(f"Missing required path: {path.relative_to(ROOT)}")
    if path.is_file() and path.stat().st_size <= 0:
        raise AssertionError(f"Required file is empty: {path.relative_to(ROOT)}")
    return path


def assert_numeric(series: pd.Series, name: str) -> None:
    values = pd.to_numeric(series, errors="coerce")
    if values.isna().any():
        raise AssertionError(f"{name} contains nonnumeric values")
    if not values.map(math.isfinite).all():
        raise AssertionError(f"{name} contains nonfinite values")


def check_strengths(spec: sweep.DoseSpec, metadata: dict) -> None:
    found_features = tuple(int(value) for value in metadata.get("feature_indices", []))
    found_strengths = tuple(float(value) for value in metadata.get("input_strengths", []))
    if found_features != spec.feature_indices:
        raise AssertionError(f"{spec.dose_id} feature mismatch: {found_features}")
    if found_strengths != spec.strengths:
        raise AssertionError(f"{spec.dose_id} strength mismatch: {found_strengths}")


def check_answers(spec: sweep.DoseSpec, units: pd.DataFrame) -> None:
    if units["generated_answer_parse_status"].astype(str).str.startswith("unparsed").any():
        raise AssertionError(f"{spec.dose_id} has unparsed generated answers")
    if spec.dataset_kind == "safe_risky":
        allowed = {"Safe Option", "Risky Option"}
        found = set(units["answer_text"].dropna().astype(str))
        if not found.issubset(allowed):
            raise AssertionError(f"{spec.dose_id} has unexpected safe-risk answers: {found}")
    elif spec.dataset_kind == "ultimatum":
        allowed = {"Accept", "Reject"}
        found = set(units["answer_text"].dropna().astype(str))
        if not found.issubset(allowed):
            raise AssertionError(f"{spec.dose_id} has unexpected ultimatum answers: {found}")
    elif spec.dataset_kind == "trust":
        assert_numeric(units["answer_text"], f"{spec.dose_id} trust answer_text")


def check_one(spec: sweep.DoseSpec, scope: str) -> dict[str, object]:
    path = sweep.run_dir(spec, scope)
    expected_units = sweep.expected_units(spec, scope)
    expected_topk = sweep.expected_topk_rows(spec, scope)
    response_units = pd.read_csv(require(path / "response_units.csv"))
    steering_meta = json.loads(require(path / "open_sae_steering_metadata.json").read_text())
    open_sae_meta = json.loads(require(path / "open_sae/open_sae_metadata.json").read_text())
    activations = pd.read_csv(require(path / "open_sae/open_sae_feature_activations.csv"))
    condition_top = pd.read_csv(require(path / "open_sae/open_sae_condition_top_features.csv"))
    reward_top = pd.read_csv(require(path / "open_sae/open_sae_condition_reward_top_features.csv"))

    if len(response_units) != expected_units:
        raise AssertionError(f"{spec.dose_id} expected {expected_units} units, found {len(response_units)}")
    if len(activations) != expected_topk:
        raise AssertionError(f"{spec.dose_id} expected {expected_topk} top-k rows, found {len(activations)}")
    if steering_meta.get("generated_response_units") != expected_units:
        raise AssertionError(f"{spec.dose_id} steering metadata unit count mismatch")
    if open_sae_meta.get("processed_response_task_units") != expected_units:
        raise AssertionError(f"{spec.dose_id} Open-SAE metadata unit count mismatch")
    if open_sae_meta.get("special_or_control_token_topk_hits") != 0:
        raise AssertionError(f"{spec.dose_id} has special/control-token top-k hits")
    condition_cells = condition_top.groupby(["task", "condition"]).ngroups
    reward_cells = reward_top.groupby(["task", "condition", "reward"]).ngroups
    if scope == "full":
        if condition_cells != spec.condition_cells:
            raise AssertionError(f"{spec.dose_id} condition-cell count mismatch")
        if reward_cells != spec.reward_cells:
            raise AssertionError(f"{spec.dose_id} reward-cell count mismatch")
    elif condition_cells <= 0 or reward_cells <= 0:
        raise AssertionError(f"{spec.dose_id} smoke summary has no condition/reward cells")
    assert_numeric(activations["activation"], f"{spec.dose_id} activation")
    if (pd.to_numeric(activations["activation"], errors="coerce") < 0).any():
        raise AssertionError(f"{spec.dose_id} contains negative activations")
    check_strengths(spec, steering_meta)
    check_answers(spec, response_units)

    return {
        "dataset_kind": spec.dataset_kind,
        "dose_id": spec.dose_id,
        "run": sweep.rel(path),
        "response_units": len(response_units),
        "topk_rows": len(activations),
        "reused_existing_run": bool(scope == "full" and spec.reuse_full_run),
    }


def check_summary() -> dict[str, object]:
    summary_dir = sweep.SUMMARY_DIR
    index = pd.read_csv(require(summary_dir / "dose_sweep_run_index.csv"))
    behavior = pd.read_csv(require(summary_dir / "dose_sweep_behavior_summary.csv"))
    features = pd.read_csv(require(summary_dir / "dose_sweep_feature_summary.csv"))
    metadata = json.loads(require(summary_dir / "dose_sweep_metadata.json").read_text())
    if len(index) != len(sweep.DOSE_SPECS):
        raise AssertionError("Dose-sweep run index row count mismatch")
    if int(index["response_units"].sum()) != 11400:
        raise AssertionError("Dose-sweep response-unit total mismatch")
    if int(index["topk_rows"].sum()) != 114000:
        raise AssertionError("Dose-sweep top-k total mismatch")
    if metadata.get("response_units") != 11400 or metadata.get("topk_rows") != 114000:
        raise AssertionError("Dose-sweep metadata totals mismatch")
    if behavior.empty or features.empty:
        raise AssertionError("Dose-sweep summary tables must be nonempty")
    for dataset_kind in ["safe_risky", "ultimatum", "trust"]:
        require(summary_dir / f"{dataset_kind}_dose_response_behavior.png")
        require(summary_dir / f"{dataset_kind}_dose_feature_activation_diagnostics.png")
    return {
        "summary_dir": sweep.rel(summary_dir),
        "runs": len(index),
        "response_units": int(index["response_units"].sum()),
        "topk_rows": int(index["topk_rows"].sum()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["smoke", "full", "all"], default="all")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    results: list[dict[str, object]] = []
    scopes = ["smoke", "full"] if args.scope == "all" else [args.scope]
    for scope in scopes:
        for spec in sweep.DOSE_SPECS:
            results.append(check_one(spec, scope))
    payload: dict[str, object] = {"status": "ok", "verified": results}
    if args.scope in {"full", "all"}:
        payload["summary"] = check_summary()
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
