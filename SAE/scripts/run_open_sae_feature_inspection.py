#!/usr/bin/env python3
"""Inspect EDSL social-simulation responses with Goodfire's open Hugging Face SAE.

The primary interface is now ``--run-dir`` over a normalized EDSL run folder
created by ``scripts/run_edsl_social_simulation.py``. Legacy saved-output loaders
remain for the archived creativity, safe-risk, ultimatum, and trust examples.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]

CREATIVITY_SOURCE_DIR = (
    REPO_ROOT / "data" / "raw" / "creativity" / "product_innovation_20251102_202650"
)
SAFE_RISKY_SOURCE_DIR = (
    REPO_ROOT / "data" / "raw" / "games" / "safe_risky" / "results_20251018_205613"
)
ULTIMATUM_SOURCE_DIR = (
    REPO_ROOT / "data" / "raw" / "games" / "ultimatum" / "results_20251008_201139"
)
TRUST_SOURCE_DIR = REPO_ROOT / "data" / "raw" / "games" / "trust" / "results"

DEFAULT_MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
DEFAULT_SAE_REPO = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"
DEFAULT_HOOK = "model.layers.50"
DEFAULT_NEURONPEDIA_MODEL = "llama3.3-70b-it"
DEFAULT_NEURONPEDIA_SOURCE = "50-resid-post-gf"

CREATIVITY_CONDITION_FILES = {
    "baseline": "baseline.csv",
    "prompting": "prompting.csv",
    "high_temperature": "high_temperature.csv",
    "high_steering": "high_steering.csv",
}
CREATIVITY_TASKS = [
    "detailed_ways_to_use_a_brick",
    "improve_the_stapler_with_many_specific_enhancements",
]
CREATIVITY_CONDITION_TITLES = {
    "baseline": "Baseline",
    "prompting": "Prompting",
    "high_temperature": "High Temperature",
    "high_steering": "High Steering",
}
CREATIVITY_TASK_TITLES = {
    "detailed_ways_to_use_a_brick": "Divergent Creativity Tasks",
    "improve_the_stapler_with_many_specific_enhancements": "Product Innovation Tasks",
}

SAFE_RISKY_TASK = "safe_risky_choice"
SAFE_RISKY_TASK_TITLES = {SAFE_RISKY_TASK: "Safe vs. Risky Choice"}
SAFE_RISKY_CONDITION_TITLES = {
    "baseline": "Baseline",
    "barely_prompting": "Prompting: Barely Risky",
    "slightly_prompting": "Prompting: Slightly Risky",
    "lite_steering": "Steering: 0.6, 0.4",
    "steering": "Steering: 0.7, 0.5",
}
SAFE_RISKY_CONDITION_ORDER = [
    "baseline",
    "barely_prompting",
    "slightly_prompting",
    "lite_steering",
    "steering",
]

ULTIMATUM_TASK = "ultimatum_response"
ULTIMATUM_TASK_TITLES = {ULTIMATUM_TASK: "Ultimatum Game"}
ULTIMATUM_CONDITION_TITLES = {
    "baseline": "Baseline",
    "prompting": "Prompting",
    "steering": "Steering",
}
ULTIMATUM_CONDITION_ORDER = ["baseline", "prompting", "steering"]

TRUST_TASK = "trust_return"
TRUST_TASK_TITLES = {TRUST_TASK: "Trust Game"}
TRUST_CONDITION_TITLES = {
    "baseline": "Baseline",
    "intervention": "Intervention",
}
TRUST_CONDITION_ORDER = ["baseline", "intervention"]

DATASET_SOURCE_DIRS = {
    "creativity": CREATIVITY_SOURCE_DIR,
    "safe_risky": SAFE_RISKY_SOURCE_DIR,
    "ultimatum": ULTIMATUM_SOURCE_DIR,
    "trust": TRUST_SOURCE_DIR,
}
DATASET_TASKS = {
    "creativity": CREATIVITY_TASKS,
    "safe_risky": [SAFE_RISKY_TASK],
    "ultimatum": [ULTIMATUM_TASK],
    "trust": [TRUST_TASK],
}
DATASET_TASK_TITLES = {
    "creativity": CREATIVITY_TASK_TITLES,
    "safe_risky": SAFE_RISKY_TASK_TITLES,
    "ultimatum": ULTIMATUM_TASK_TITLES,
    "trust": TRUST_TASK_TITLES,
}
DATASET_CONDITION_TITLES = {
    "creativity": CREATIVITY_CONDITION_TITLES,
    "safe_risky": SAFE_RISKY_CONDITION_TITLES,
    "ultimatum": ULTIMATUM_CONDITION_TITLES,
    "trust": TRUST_CONDITION_TITLES,
}
DATASET_CONDITION_ORDERS = {
    "creativity": list(CREATIVITY_CONDITION_FILES),
    "safe_risky": SAFE_RISKY_CONDITION_ORDER,
    "ultimatum": ULTIMATUM_CONDITION_ORDER,
    "trust": TRUST_CONDITION_ORDER,
}


def release_path(path: Path | str | None) -> str | None:
    """Return a reproducible metadata path without local user directories."""

    if path is None:
        return None
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        if path.is_absolute():
            return f"<external>/{path.name}"
        return path.as_posix()


@dataclass(frozen=True)
class WorkUnit:
    """One saved response transcript to inspect."""

    unit_id: str
    dataset_kind: str
    condition: str
    task: str
    source_file: str
    source_row_index: int
    response_index: int
    agent_index: str
    agent_subject_id: str
    reward: int | None
    answer_text: str
    comment_text: str
    system_prompt: str
    user_prompt: str
    response_text: str


@dataclass(frozen=True)
class TokenizedUnit:
    """Model input ids plus the token positions allowed for SAE pooling."""

    input_ids: Any
    included_positions: list[int]
    content_positions_by_role: dict[str, list[int]]
    special_or_control_positions: list[int]
    tokenization_notes: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Open-SAE feature inspection over EDSL social-simulation outputs."
    )
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=None,
        help=(
            "Normalized EDSL run folder containing run_manifest.json and "
            "response_units.csv. This is the preferred platform interface."
        ),
    )
    parser.add_argument(
        "--dataset-kind",
        choices=["creativity", "safe_risky", "ultimatum", "trust"],
        default=None,
        help="Legacy saved dataset schema to load when --run-dir is not supplied.",
    )
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--sae-repo", default=DEFAULT_SAE_REPO)
    parser.add_argument("--sae-filename", default=None)
    parser.add_argument("--hook", default=DEFAULT_HOOK)
    parser.add_argument(
        "--activation-scope",
        choices=["all_content", "assistant_response", "user_prompt"],
        default="all_content",
        help=(
            "Content-token span used for feature aggregation. The full chat "
            "context is still fed to the model."
        ),
    )
    parser.add_argument(
        "--include-system-message",
        action="store_true",
        help=(
            "Include saved system prompts in the model transcript. The old "
            "Goodfire inspect code used only user and assistant messages, so "
            "the default is to omit system prompts."
        ),
    )
    parser.add_argument(
        "--include-system-in-all-content",
        action="store_true",
        help="When system messages are included, also allow their content tokens in all_content pooling.",
    )
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--condition-top-k", type=int, default=10)
    parser.add_argument("--summary-top-n-per-cell", type=int, default=200)
    parser.add_argument(
        "--feature-aggregation",
        choices=["max", "frequency", "sum", "mean"],
        default="max",
        help=(
            "Per-response feature score used for top-k ranking and condition "
            "aggregation. Goodfire's public SDK default was frequency: count "
            "tokens where activation_strength exceeds --activation-threshold."
        ),
    )
    parser.add_argument(
        "--activation-threshold",
        type=float,
        default=0.1,
        help="Threshold for frequency/sum/mean feature aggregation.",
    )
    parser.add_argument("--activation-chunk-size", type=int, default=64)
    parser.add_argument("--max-seq-len", type=int, default=None)
    parser.add_argument("--limit-units", type=int, default=None)
    parser.add_argument("--max-agents-per-cell", type=int, default=None)
    parser.add_argument(
        "--conditions",
        default=None,
        help="Comma-separated condition names to keep.",
    )
    parser.add_argument(
        "--rewards",
        default=None,
        help=(
            "Comma-separated numeric game values to keep: safe-risk risky reward, "
            "ultimatum offer, or trust sent amount."
        ),
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--audit-only",
        action="store_true",
        help="Write source response-unit and behavior audit outputs without loading model/SAE.",
    )
    parser.add_argument("--strict", action="store_true", default=True)
    parser.add_argument("--no-strict", dest="strict", action="store_false")
    parser.add_argument("--torch-dtype", default="bfloat16")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--sae-device", default="auto")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--load-in-8bit", action="store_true")
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--hf-token", default=os.getenv("HF_TOKEN"))
    parser.add_argument("--skip-labels", action="store_true")
    parser.add_argument("--label-workers", type=int, default=16)
    parser.add_argument("--label-timeout", type=float, default=15.0)
    parser.add_argument("--neuronpedia-model", default=DEFAULT_NEURONPEDIA_MODEL)
    parser.add_argument("--neuronpedia-source", default=DEFAULT_NEURONPEDIA_SOURCE)
    parser.add_argument(
        "--goodfire-log",
        type=Path,
        default=None,
        help="Optional old Goodfire feature_activations.txt log to parse and compare.",
    )
    parser.add_argument("--write-full-summary", action="store_true")
    parser.add_argument(
        "--expected-units",
        type=int,
        default=None,
        help="Optional hard assertion for processed response units after filtering.",
    )
    return parser.parse_args()


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except TypeError:
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def normalized_agent_index(value: Any, fallback: int) -> str:
    text = safe_text(value)
    if not text:
        return str(fallback)
    try:
        as_float = float(text)
        if as_float.is_integer():
            return str(int(as_float))
    except ValueError:
        pass
    return text


def parse_csv_list(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def parse_int_list(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(part.strip()) for part in value.split(",") if part.strip()}


def import_pandas():
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas is required to read source CSVs") from exc
    return pd


def import_numpy():
    try:
        import numpy as np
    except ImportError as exc:
        raise SystemExit("numpy is required for aggregate outputs") from exc
    return np


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def default_source_dir(dataset_kind: str) -> Path:
    return DATASET_SOURCE_DIRS[dataset_kind]


def infer_run_dataset_kind(run_dir: Path) -> str:
    """Infer a dataset/game id from a normalized EDSL run folder."""

    manifest_path = run_dir / "run_manifest.json"
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        game_id = safe_text(manifest.get("game_id"))
        if game_id:
            return game_id
    response_units_path = run_dir / "response_units.csv"
    if response_units_path.exists():
        pd = import_pandas()
        frame = pd.read_csv(response_units_path, nrows=1)
        if "game_id" in frame.columns and len(frame):
            game_id = safe_text(frame.iloc[0].get("game_id"))
            if game_id:
                return game_id
    return run_dir.name


def parse_int_or_none(value: Any) -> int | None:
    text = safe_text(value)
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if math.isnan(parsed):
        return None
    return int(parsed)


def default_output_dir(dataset_kind: str, source_dir: Path, activation_scope: str) -> Path:
    if dataset_kind == "creativity":
        suffix = f"goodfire_open_sae_40agent_features_{activation_scope}"
        return source_dir.parent / f"{source_dir.name}_{suffix}"
    suffix = f"goodfire_open_sae_{dataset_kind}_{activation_scope}"
    return source_dir.parent / f"{source_dir.name}_{suffix}"


def load_creativity_units(
    source_dir: Path,
    *,
    strict: bool,
    conditions: set[str] | None,
    limit_units: int | None,
) -> tuple[list[WorkUnit], dict[str, Any]]:
    pd = import_pandas()
    units: list[WorkUnit] = []
    validation: dict[str, Any] = {
        "dataset_kind": "creativity",
        "source_dir": release_path(source_dir),
        "condition_files": {},
        "tasks": CREATIVITY_TASKS,
        "expected_rows_per_condition": 40,
        "expected_response_task_units_unfiltered": 320,
    }

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    condition_files = {
        condition: filename
        for condition, filename in CREATIVITY_CONDITION_FILES.items()
        if conditions is None or condition in conditions
    }
    missing_conditions = sorted((conditions or set()) - set(CREATIVITY_CONDITION_FILES))
    if missing_conditions:
        raise ValueError(f"Unknown creativity conditions: {missing_conditions}")

    for condition, filename in condition_files.items():
        csv_path = source_dir / filename
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing condition CSV: {csv_path}")
        frame = pd.read_csv(csv_path)
        validation["condition_files"][condition] = {
            "path": release_path(csv_path),
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "sha256": file_sha256(csv_path),
        }
        if strict and len(frame) != 40:
            raise ValueError(f"{csv_path} has {len(frame)} rows, expected 40")

        for task in CREATIVITY_TASKS:
            required = [
                f"answer.{task}",
                f"prompt.{task}_user_prompt",
                f"generated_tokens.{task}_generated_tokens",
            ]
            missing = [column for column in required if column not in frame.columns]
            if missing:
                raise ValueError(f"{csv_path} is missing required columns: {missing}")

        for row_index, row in frame.iterrows():
            agent_index = normalized_agent_index(row.get("agent.agent_index"), row_index)
            agent_subject_id = safe_text(row.get("agent.subject_id"))
            for task in CREATIVITY_TASKS:
                unit_id = f"creativity:{condition}:{row_index}:{task}"
                units.append(
                    WorkUnit(
                        unit_id=unit_id,
                        dataset_kind="creativity",
                        condition=condition,
                        task=task,
                        source_file=filename,
                        source_row_index=int(row_index),
                        response_index=int(row_index) + 1,
                        agent_index=agent_index,
                        agent_subject_id=agent_subject_id,
                        reward=None,
                        answer_text=safe_text(row.get(f"answer.{task}")),
                        comment_text=safe_text(row.get(f"comment.{task}_comment")),
                        system_prompt=safe_text(row.get(f"prompt.{task}_system_prompt")),
                        user_prompt=safe_text(row.get(f"prompt.{task}_user_prompt")),
                        response_text=safe_text(
                            row.get(f"generated_tokens.{task}_generated_tokens")
                        ),
                    )
                )

    validation["actual_response_task_units_unfiltered"] = len(units)
    if strict and conditions is None and len(units) != 320:
        raise ValueError(f"Found {len(units)} creativity units, expected 320")

    if limit_units is not None:
        units = units[:limit_units]
        validation["limited_response_task_units"] = len(units)

    return units, validation


def load_run_dir_units(args: argparse.Namespace) -> tuple[list[WorkUnit], dict[str, Any]]:
    """Load normalized response units produced by the EDSL platform runner."""

    pd = import_pandas()
    run_dir = args.run_dir
    response_units_path = run_dir / "response_units.csv"
    manifest_path = run_dir / "run_manifest.json"
    if not response_units_path.exists():
        raise FileNotFoundError(f"Missing normalized response units: {response_units_path}")

    frame = pd.read_csv(response_units_path)
    manifest: dict[str, Any] = {}
    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    required = ["condition", "task", "user_prompt", "response_text"]
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise ValueError(f"{response_units_path} is missing required columns: {missing}")

    conditions = parse_csv_list(args.conditions)
    rewards = parse_int_list(args.rewards)
    units: list[WorkUnit] = []
    seen_conditions: set[str] = set()
    seen_rewards: set[int] = set()
    per_cell_counts: dict[tuple[str, str, int | None], int] = defaultdict(int)
    for row_index, row in frame.iterrows():
        condition = safe_text(row.get("condition"))
        task = safe_text(row.get("task"))
        reward = parse_int_or_none(row.get("reward"))
        seen_conditions.add(condition)
        if reward is not None:
            seen_rewards.add(reward)
        if conditions is not None and condition not in conditions:
            continue
        if rewards is not None and reward not in rewards:
            continue
        cell_key = (condition, task, reward)
        if (
            args.max_agents_per_cell is not None
            and per_cell_counts[cell_key] >= args.max_agents_per_cell
        ):
            continue
        per_cell_counts[cell_key] += 1

        units.append(
            WorkUnit(
                unit_id=safe_text(row.get("unit_id")) or f"{args.dataset_kind}:{row_index}",
                dataset_kind=args.dataset_kind,
                condition=condition,
                task=task,
                source_file=safe_text(row.get("source_file")) or "response_units.csv",
                source_row_index=int(row.get("source_row_index", row_index) or row_index),
                response_index=int(row.get("response_index", row_index + 1) or row_index + 1),
                agent_index=normalized_agent_index(row.get("agent_index"), row_index),
                agent_subject_id=safe_text(row.get("agent_subject_id")),
                reward=reward,
                answer_text=safe_text(row.get("answer_text")),
                comment_text=safe_text(row.get("comment_text")),
                system_prompt=safe_text(row.get("system_prompt")),
                user_prompt=safe_text(row.get("user_prompt")),
                response_text=safe_text(row.get("response_text")),
            )
        )

    if conditions is not None:
        missing_conditions = sorted(conditions - seen_conditions)
        if missing_conditions:
            raise ValueError(f"Unknown run-dir conditions: {missing_conditions}")
    if rewards is not None:
        missing_rewards = sorted(rewards - seen_rewards)
        if missing_rewards:
            raise ValueError(f"Unknown run-dir rewards: {missing_rewards}")

    validation = {
        "dataset_kind": args.dataset_kind,
        "source_dir": release_path(run_dir),
        "run_dir": release_path(run_dir),
        "response_units_csv": release_path(response_units_path),
        "run_manifest": release_path(manifest_path) if manifest_path.exists() else None,
        "manifest": manifest,
        "csv_rows": int(len(frame)),
        "csv_columns": list(frame.columns),
        "sha256": file_sha256(response_units_path),
        "available_conditions": sorted(seen_conditions),
        "available_rewards": sorted(seen_rewards),
        "selected_conditions": sorted(conditions) if conditions else None,
        "selected_rewards": sorted(rewards) if rewards else None,
        "actual_response_task_units_unfiltered": int(len(frame)),
        "selected_csv_file_count": 1,
    }
    if args.limit_units is not None:
        units = units[: args.limit_units]
        validation["limited_response_task_units"] = len(units)
    validation["actual_response_task_units"] = len(units)
    if args.expected_units is not None and len(units) != args.expected_units:
        raise ValueError(f"Found {len(units)} response units, expected {args.expected_units}")
    return units, validation


SAFE_RISKY_FILE_RE = re.compile(r"^safe_risky_(?P<condition>.+)_(?P<reward>\d+)\.csv$")


def safe_risky_sort_key(path: Path) -> tuple[int, str, int]:
    match = SAFE_RISKY_FILE_RE.match(path.name)
    if not match:
        return (999, path.name, 0)
    condition = match.group("condition")
    reward = int(match.group("reward"))
    try:
        order = SAFE_RISKY_CONDITION_ORDER.index(condition)
    except ValueError:
        order = 500
    return (order, condition, reward)


def load_safe_risky_units(
    source_dir: Path,
    *,
    strict: bool,
    conditions: set[str] | None,
    rewards: set[int] | None,
    max_agents_per_cell: int | None,
    limit_units: int | None,
) -> tuple[list[WorkUnit], dict[str, Any]]:
    pd = import_pandas()
    units: list[WorkUnit] = []
    validation: dict[str, Any] = {
        "dataset_kind": "safe_risky",
        "source_dir": release_path(source_dir),
        "csv_files": {},
        "task": SAFE_RISKY_TASK,
        "expected_rows_per_condition_reward": 40,
    }

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    csv_paths = sorted(source_dir.glob("safe_risky_*.csv"), key=safe_risky_sort_key)
    csv_paths = [path for path in csv_paths if SAFE_RISKY_FILE_RE.match(path.name)]
    if not csv_paths:
        raise FileNotFoundError(f"No safe_risky_<condition>_<reward>.csv files in {source_dir}")

    seen_conditions: set[str] = set()
    seen_rewards: set[int] = set()
    for csv_path in csv_paths:
        match = SAFE_RISKY_FILE_RE.match(csv_path.name)
        if match is None:
            continue
        condition = match.group("condition")
        reward = int(match.group("reward"))
        seen_conditions.add(condition)
        seen_rewards.add(reward)
        if conditions is not None and condition not in conditions:
            continue
        if rewards is not None and reward not in rewards:
            continue

        frame = pd.read_csv(csv_path)
        validation["csv_files"][csv_path.name] = {
            "path": release_path(csv_path),
            "condition": condition,
            "reward": reward,
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "sha256": file_sha256(csv_path),
        }
        if strict and len(frame) != 40:
            raise ValueError(f"{csv_path} has {len(frame)} rows, expected 40")
        required = [
            "answer.safe_risky_choice",
            "prompt.safe_risky_choice_user_prompt",
            "generated_tokens.safe_risky_choice_generated_tokens",
        ]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"{csv_path} is missing required columns: {missing}")

        if max_agents_per_cell is not None:
            frame = frame.head(max_agents_per_cell)

        for row_index, row in frame.iterrows():
            agent_index = normalized_agent_index(row.get("agent.agent_index"), row_index)
            unit_id = f"safe_risky:{condition}:{reward}:{row_index}"
            units.append(
                WorkUnit(
                    unit_id=unit_id,
                    dataset_kind="safe_risky",
                    condition=condition,
                    task=SAFE_RISKY_TASK,
                    source_file=csv_path.name,
                    source_row_index=int(row_index),
                    response_index=int(row_index) + 1,
                    agent_index=agent_index,
                    agent_subject_id=safe_text(row.get("agent.subject_id")),
                    reward=reward,
                    answer_text=safe_text(row.get("answer.safe_risky_choice")),
                    comment_text=safe_text(row.get("comment.safe_risky_choice_comment")),
                    system_prompt=safe_text(row.get("prompt.safe_risky_choice_system_prompt")),
                    user_prompt=safe_text(row.get("prompt.safe_risky_choice_user_prompt")),
                    response_text=safe_text(
                        row.get("generated_tokens.safe_risky_choice_generated_tokens")
                    ),
                )
            )

    validation["available_conditions"] = sorted(seen_conditions)
    validation["available_rewards"] = sorted(seen_rewards)
    validation["selected_conditions"] = sorted(conditions) if conditions else None
    validation["selected_rewards"] = sorted(rewards) if rewards else None
    validation["actual_response_task_units_unfiltered"] = len(units)
    validation["selected_csv_file_count"] = len(validation["csv_files"])

    if conditions is not None:
        missing_conditions = sorted(conditions - seen_conditions)
        if missing_conditions:
            raise ValueError(f"Unknown safe-risk conditions: {missing_conditions}")
    if rewards is not None:
        missing_rewards = sorted(rewards - seen_rewards)
        if missing_rewards:
            raise ValueError(f"Unknown safe-risk rewards: {missing_rewards}")

    if limit_units is not None:
        units = units[:limit_units]
        validation["limited_response_task_units"] = len(units)

    return units, validation


ULTIMATUM_FILE_RE = re.compile(r"^ultimatum_(?P<condition>.+)_(?P<offer>\d+)\.csv$")
TRUST_FILE_RE = re.compile(r"^trust_game_(?P<condition>.+)_sent_(?P<sent>\d+)\.csv$")


def condition_value_sort_key(
    path: Path,
    *,
    pattern: re.Pattern[str],
    condition_order_values: list[str],
    value_group: str,
) -> tuple[int, str, int]:
    match = pattern.match(path.name)
    if not match:
        return (999, path.name, 0)
    condition = match.group("condition")
    value = int(match.group(value_group))
    try:
        order = condition_order_values.index(condition)
    except ValueError:
        order = 500
    return (order, condition, value)


def load_ultimatum_units(
    source_dir: Path,
    *,
    strict: bool,
    conditions: set[str] | None,
    offers: set[int] | None,
    max_agents_per_cell: int | None,
    limit_units: int | None,
) -> tuple[list[WorkUnit], dict[str, Any]]:
    pd = import_pandas()
    units: list[WorkUnit] = []
    validation: dict[str, Any] = {
        "dataset_kind": "ultimatum",
        "source_dir": release_path(source_dir),
        "csv_files": {},
        "task": ULTIMATUM_TASK,
        "expected_rows_per_condition_offer": 40,
    }

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    csv_paths = sorted(
        source_dir.glob("ultimatum_*.csv"),
        key=lambda path: condition_value_sort_key(
            path,
            pattern=ULTIMATUM_FILE_RE,
            condition_order_values=ULTIMATUM_CONDITION_ORDER,
            value_group="offer",
        ),
    )
    csv_paths = [path for path in csv_paths if ULTIMATUM_FILE_RE.match(path.name)]
    if not csv_paths:
        raise FileNotFoundError(f"No ultimatum_<condition>_<offer>.csv files in {source_dir}")

    seen_conditions: set[str] = set()
    seen_offers: set[int] = set()
    for csv_path in csv_paths:
        match = ULTIMATUM_FILE_RE.match(csv_path.name)
        if match is None:
            continue
        condition = match.group("condition")
        offer = int(match.group("offer"))
        seen_conditions.add(condition)
        seen_offers.add(offer)
        if conditions is not None and condition not in conditions:
            continue
        if offers is not None and offer not in offers:
            continue

        frame = pd.read_csv(csv_path)
        validation["csv_files"][csv_path.name] = {
            "path": release_path(csv_path),
            "condition": condition,
            "offer": offer,
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "sha256": file_sha256(csv_path),
        }
        if strict and len(frame) != 40:
            raise ValueError(f"{csv_path} has {len(frame)} rows, expected 40")
        required = [
            "answer.ultimatum_response",
            "prompt.ultimatum_response_user_prompt",
            "generated_tokens.ultimatum_response_generated_tokens",
        ]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"{csv_path} is missing required columns: {missing}")

        if max_agents_per_cell is not None:
            frame = frame.head(max_agents_per_cell)

        for row_index, row in frame.iterrows():
            agent_index = normalized_agent_index(row.get("agent.agent_index"), row_index)
            unit_id = f"ultimatum:{condition}:{offer}:{row_index}"
            units.append(
                WorkUnit(
                    unit_id=unit_id,
                    dataset_kind="ultimatum",
                    condition=condition,
                    task=ULTIMATUM_TASK,
                    source_file=csv_path.name,
                    source_row_index=int(row_index),
                    response_index=int(row_index) + 1,
                    agent_index=agent_index,
                    agent_subject_id=safe_text(row.get("agent.subject_id")),
                    reward=offer,
                    answer_text=safe_text(row.get("answer.ultimatum_response")),
                    comment_text=safe_text(row.get("comment.ultimatum_response_comment")),
                    system_prompt=safe_text(row.get("prompt.ultimatum_response_system_prompt")),
                    user_prompt=safe_text(row.get("prompt.ultimatum_response_user_prompt")),
                    response_text=safe_text(
                        row.get("generated_tokens.ultimatum_response_generated_tokens")
                    ),
                )
            )

    validation["available_conditions"] = sorted(seen_conditions)
    validation["available_offers"] = sorted(seen_offers)
    validation["selected_conditions"] = sorted(conditions) if conditions else None
    validation["selected_offers"] = sorted(offers) if offers else None
    validation["actual_response_task_units_unfiltered"] = len(units)
    validation["selected_csv_file_count"] = len(validation["csv_files"])

    if conditions is not None:
        missing_conditions = sorted(conditions - seen_conditions)
        if missing_conditions:
            raise ValueError(f"Unknown ultimatum conditions: {missing_conditions}")
    if offers is not None:
        missing_offers = sorted(offers - seen_offers)
        if missing_offers:
            raise ValueError(f"Unknown ultimatum offers: {missing_offers}")

    if limit_units is not None:
        units = units[:limit_units]
        validation["limited_response_task_units"] = len(units)

    return units, validation


def load_trust_units(
    source_dir: Path,
    *,
    strict: bool,
    conditions: set[str] | None,
    sent_amounts: set[int] | None,
    max_agents_per_cell: int | None,
    limit_units: int | None,
) -> tuple[list[WorkUnit], dict[str, Any]]:
    pd = import_pandas()
    units: list[WorkUnit] = []
    validation: dict[str, Any] = {
        "dataset_kind": "trust",
        "source_dir": release_path(source_dir),
        "csv_files": {},
        "task": TRUST_TASK,
        "expected_rows_per_condition_sent_amount": 10,
    }

    if not source_dir.exists():
        raise FileNotFoundError(f"Source directory does not exist: {source_dir}")

    csv_paths = sorted(
        source_dir.glob("trust_game_*_sent_*.csv"),
        key=lambda path: condition_value_sort_key(
            path,
            pattern=TRUST_FILE_RE,
            condition_order_values=TRUST_CONDITION_ORDER,
            value_group="sent",
        ),
    )
    csv_paths = [path for path in csv_paths if TRUST_FILE_RE.match(path.name)]
    if not csv_paths:
        raise FileNotFoundError(f"No trust_game_<condition>_sent_<amount>.csv files in {source_dir}")

    seen_conditions: set[str] = set()
    seen_sent_amounts: set[int] = set()
    for csv_path in csv_paths:
        match = TRUST_FILE_RE.match(csv_path.name)
        if match is None:
            continue
        condition = match.group("condition")
        sent_amount = int(match.group("sent"))
        seen_conditions.add(condition)
        seen_sent_amounts.add(sent_amount)
        if conditions is not None and condition not in conditions:
            continue
        if sent_amounts is not None and sent_amount not in sent_amounts:
            continue

        frame = pd.read_csv(csv_path)
        validation["csv_files"][csv_path.name] = {
            "path": release_path(csv_path),
            "condition": condition,
            "sent_amount": sent_amount,
            "rows": int(len(frame)),
            "columns": list(frame.columns),
            "sha256": file_sha256(csv_path),
        }
        if strict and len(frame) != 10:
            raise ValueError(f"{csv_path} has {len(frame)} rows, expected 10")
        required = [
            "answer.trust_return",
            "prompt.trust_return_user_prompt",
            "generated_tokens.trust_return_generated_tokens",
        ]
        missing = [column for column in required if column not in frame.columns]
        if missing:
            raise ValueError(f"{csv_path} is missing required columns: {missing}")

        if max_agents_per_cell is not None:
            frame = frame.head(max_agents_per_cell)

        for row_index, row in frame.iterrows():
            agent_index = normalized_agent_index(row.get("agent.agent_index"), row_index)
            unit_id = f"trust:{condition}:{sent_amount}:{row_index}"
            units.append(
                WorkUnit(
                    unit_id=unit_id,
                    dataset_kind="trust",
                    condition=condition,
                    task=TRUST_TASK,
                    source_file=csv_path.name,
                    source_row_index=int(row_index),
                    response_index=int(row_index) + 1,
                    agent_index=agent_index,
                    agent_subject_id=safe_text(row.get("agent.subject_id")),
                    reward=sent_amount,
                    answer_text=safe_text(row.get("answer.trust_return")),
                    comment_text=safe_text(row.get("comment.trust_return_comment")),
                    system_prompt=safe_text(row.get("prompt.trust_return_system_prompt")),
                    user_prompt=safe_text(row.get("prompt.trust_return_user_prompt")),
                    response_text=safe_text(row.get("generated_tokens.trust_return_generated_tokens")),
                )
            )

    validation["available_conditions"] = sorted(seen_conditions)
    validation["available_sent_amounts"] = sorted(seen_sent_amounts)
    validation["selected_conditions"] = sorted(conditions) if conditions else None
    validation["selected_sent_amounts"] = sorted(sent_amounts) if sent_amounts else None
    validation["actual_response_task_units_unfiltered"] = len(units)
    validation["selected_csv_file_count"] = len(validation["csv_files"])

    if conditions is not None:
        missing_conditions = sorted(conditions - seen_conditions)
        if missing_conditions:
            raise ValueError(f"Unknown trust conditions: {missing_conditions}")
    if sent_amounts is not None:
        missing_amounts = sorted(sent_amounts - seen_sent_amounts)
        if missing_amounts:
            raise ValueError(f"Unknown trust sent amounts: {missing_amounts}")

    if limit_units is not None:
        units = units[:limit_units]
        validation["limited_response_task_units"] = len(units)

    return units, validation


def load_work_units(args: argparse.Namespace) -> tuple[list[WorkUnit], dict[str, Any]]:
    if args.run_dir is not None:
        return load_run_dir_units(args)

    conditions = parse_csv_list(args.conditions)
    rewards = parse_int_list(args.rewards)
    if args.dataset_kind == "creativity":
        if rewards:
            raise ValueError("--rewards applies only to game datasets, not creativity")
        units, validation = load_creativity_units(
            args.source_dir,
            strict=args.strict,
            conditions=conditions,
            limit_units=args.limit_units,
        )
    elif args.dataset_kind == "safe_risky":
        units, validation = load_safe_risky_units(
            args.source_dir,
            strict=args.strict,
            conditions=conditions,
            rewards=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=args.limit_units,
        )
    elif args.dataset_kind == "ultimatum":
        units, validation = load_ultimatum_units(
            args.source_dir,
            strict=args.strict,
            conditions=conditions,
            offers=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=args.limit_units,
        )
    elif args.dataset_kind == "trust":
        units, validation = load_trust_units(
            args.source_dir,
            strict=args.strict,
            conditions=conditions,
            sent_amounts=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=args.limit_units,
        )
    else:
        raise ValueError(f"Unsupported dataset kind: {args.dataset_kind}")

    validation["actual_response_task_units"] = len(units)
    if args.expected_units is not None and len(units) != args.expected_units:
        raise ValueError(
            f"Found {len(units)} response units, expected {args.expected_units}"
        )
    return units, validation


def condition_order(dataset_kind: str, conditions: Iterable[str]) -> list[str]:
    seen = list(dict.fromkeys(conditions))
    base = DATASET_CONDITION_ORDERS.get(dataset_kind, [])
    ordered = [condition for condition in base if condition in seen]
    ordered.extend(sorted(condition for condition in seen if condition not in ordered))
    return ordered


def task_order(dataset_kind: str, tasks: Iterable[str]) -> list[str]:
    seen = list(dict.fromkeys(tasks))
    base = DATASET_TASKS.get(dataset_kind, [])
    ordered = [task for task in base if task in seen]
    ordered.extend(sorted(task for task in seen if task not in ordered))
    return ordered


def print_dry_run(units: list[WorkUnit], validation: dict[str, Any]) -> None:
    condition_counts: dict[str, int] = defaultdict(int)
    task_counts: dict[str, int] = defaultdict(int)
    reward_counts: dict[str, int] = defaultdict(int)
    for unit in units:
        condition_counts[unit.condition] += 1
        task_counts[unit.task] += 1
        if unit.reward is not None:
            reward_counts[str(unit.reward)] += 1

    payload = {
        "status": "ok",
        "dataset_kind": validation["dataset_kind"],
        "source_dir": validation["source_dir"],
        "unit_count": len(units),
        "condition_counts": dict(sorted(condition_counts.items())),
        "task_counts": dict(sorted(task_counts.items())),
        "reward_counts": dict(sorted(reward_counts.items(), key=lambda kv: int(kv[0]))),
        "selected_csv_file_count": validation.get("selected_csv_file_count"),
        "first_unit": asdict(units[0]) if units else None,
    }
    print(json.dumps(payload, indent=2))


def resolve_sae_filename(sae_repo: str, explicit_filename: str | None) -> str:
    if explicit_filename:
        return explicit_filename
    if sae_repo.endswith("Llama-3.3-70B-Instruct-SAE-l50"):
        return "Llama-3.3-70B-Instruct-SAE-l50.pt"
    if sae_repo.endswith("Llama-3.1-8B-Instruct-SAE-l19"):
        return "Llama-3.1-8B-Instruct-SAE-l19.pth"
    raise ValueError(
        "Could not infer SAE filename. Pass --sae-filename explicitly for "
        f"{sae_repo}."
    )


def parse_torch_dtype(torch_module: Any, dtype_name: str) -> Any:
    if not hasattr(torch_module, dtype_name):
        raise ValueError(f"Unknown torch dtype: {dtype_name}")
    return getattr(torch_module, dtype_name)


def get_nested_module(root: Any, dotted_path: str) -> Any:
    current = root
    for part in dotted_path.split("."):
        current = current[int(part)] if part.isdigit() else getattr(current, part)
    return current


def module_device(module: Any) -> Any:
    for param in module.parameters(recurse=True):
        return param.device
    raise ValueError("Could not infer device for hook module")


def first_model_device(model: Any) -> Any:
    for param in model.parameters():
        return param.device
    raise ValueError("Could not infer model input device")


def load_model_and_sae(args: argparse.Namespace):
    try:
        import torch
        from huggingface_hub import hf_hub_download
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise SystemExit(
            "Full inference requires torch, transformers, and huggingface_hub. "
            "Use the RunPod PyTorch image or install these packages there."
        ) from exc

    dtype = parse_torch_dtype(torch, args.torch_dtype)
    tokenizer = AutoTokenizer.from_pretrained(
        args.model_id,
        token=args.hf_token,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token_id is None and tokenizer.eos_token is not None:
        tokenizer.pad_token = tokenizer.eos_token

    model_kwargs: dict[str, Any] = {
        "torch_dtype": dtype,
        "device_map": args.device_map,
        "token": args.hf_token,
        "trust_remote_code": args.trust_remote_code,
    }
    if args.load_in_4bit or args.load_in_8bit:
        try:
            from transformers import BitsAndBytesConfig
        except ImportError as exc:
            raise SystemExit("bitsandbytes/transformers quantization is required") from exc
        if args.load_in_4bit and args.load_in_8bit:
            raise ValueError("Use only one of --load-in-4bit or --load-in-8bit")
        model_kwargs["quantization_config"] = BitsAndBytesConfig(
            load_in_4bit=args.load_in_4bit,
            load_in_8bit=args.load_in_8bit,
            bnb_4bit_compute_dtype=dtype,
            bnb_4bit_quant_type="nf4",
        )

    model = AutoModelForCausalLM.from_pretrained(args.model_id, **model_kwargs)
    model.eval()

    hook_module = get_nested_module(model, args.hook)
    inferred_sae_device = module_device(hook_module)
    sae_device = inferred_sae_device if args.sae_device == "auto" else torch.device(args.sae_device)

    sae_filename = resolve_sae_filename(args.sae_repo, args.sae_filename)
    sae_path = hf_hub_download(
        repo_id=args.sae_repo,
        filename=sae_filename,
        token=args.hf_token,
    )

    class SparseAutoEncoder(torch.nn.Module):
        def __init__(
            self,
            d_in: int,
            d_hidden: int,
            device: Any,
            dtype: Any = torch.bfloat16,
        ) -> None:
            super().__init__()
            self.d_in = d_in
            self.d_hidden = d_hidden
            self.encoder_linear = torch.nn.Linear(d_in, d_hidden)
            self.decoder_linear = torch.nn.Linear(d_hidden, d_in)
            self.dtype = dtype
            self.to(device, dtype)

        def encode(self, x: Any) -> Any:
            return torch.nn.functional.relu(self.encoder_linear(x))

        def decode(self, x: Any) -> Any:
            return self.decoder_linear(x)

        def forward(self, x: Any) -> tuple[Any, Any]:
            features = self.encode(x)
            return self.decode(features), features

    try:
        state_dict = torch.load(sae_path, weights_only=True, map_location=sae_device)
    except TypeError:
        state_dict = torch.load(sae_path, map_location=sae_device)
    encoder_weight = state_dict.get("encoder_linear.weight")
    if encoder_weight is None:
        raise RuntimeError(
            "Could not infer SAE dimensions because encoder_linear.weight is missing "
            f"from {sae_path}."
        )
    d_hidden, d_in = map(int, encoder_weight.shape)
    d_model = int(model.config.hidden_size)
    if d_in != d_model:
        raise RuntimeError(f"SAE input width {d_in} does not match model hidden size {d_model}.")

    sae = SparseAutoEncoder(d_in=d_in, d_hidden=d_hidden, device=sae_device, dtype=dtype)
    sae.load_state_dict(state_dict)
    sae.eval()

    return torch, tokenizer, model, hook_module, sae, str(sae_path), str(sae_device)


def transcript_messages(unit: WorkUnit, *, include_system_message: bool) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if include_system_message and unit.system_prompt:
        messages.append({"role": "system", "content": unit.system_prompt})
    messages.append({"role": "user", "content": unit.user_prompt})
    messages.append({"role": "assistant", "content": unit.response_text})
    return messages


def token_ids_for_text(tokenizer: Any, text: str) -> list[int]:
    if not text:
        return []
    encoded = tokenizer(text, add_special_tokens=False)
    return [int(token_id) for token_id in encoded["input_ids"]]


def find_subsequence(haystack: list[int], needle: list[int], start: int = 0) -> int | None:
    if not needle:
        return None
    max_start = len(haystack) - len(needle)
    for index in range(start, max_start + 1):
        if haystack[index : index + len(needle)] == needle:
            return index
    return None


def find_content_positions(
    *,
    tokenizer: Any,
    input_ids_list: list[int],
    messages: list[dict[str, str]],
) -> tuple[dict[str, list[int]], list[str]]:
    positions_by_role: dict[str, list[int]] = defaultdict(list)
    notes: list[str] = []
    cursor = 0
    for message in messages:
        role = message["role"]
        content = message["content"]
        content_ids = token_ids_for_text(tokenizer, content)
        if not content_ids:
            continue
        start = find_subsequence(input_ids_list, content_ids, cursor)
        if start is None:
            # Some chat templates merge leading whitespace with the first
            # content token. Retry from the beginning before falling back.
            start = find_subsequence(input_ids_list, content_ids, 0)
        if start is None:
            notes.append(f"could_not_find_{role}_content_subsequence")
            continue
        positions = list(range(start, start + len(content_ids)))
        positions_by_role[role].extend(positions)
        cursor = start + len(content_ids)
    return dict(positions_by_role), notes


def special_or_control_positions(tokenizer: Any, input_ids_list: list[int]) -> list[int]:
    special_ids = set(int(token_id) for token_id in (tokenizer.all_special_ids or []))
    positions: list[int] = []
    for index, token_id in enumerate(input_ids_list):
        token_text = tokenizer.decode([token_id])
        if token_id in special_ids or "<|" in token_text or token_text in {"system", "user", "assistant"}:
            positions.append(index)
    return positions


def make_tokenized_unit(
    tokenizer: Any,
    unit: WorkUnit,
    torch_module: Any,
    *,
    max_seq_len: int | None,
    activation_scope: str,
    include_system_message: bool,
    include_system_in_all_content: bool,
) -> TokenizedUnit:
    messages = transcript_messages(unit, include_system_message=include_system_message)
    tokenization_notes: list[str] = []
    try:
        input_ids_raw = tokenizer.apply_chat_template(
            messages,
            return_tensors=None,
            add_generation_prompt=False,
        )
    except Exception as exc:
        tokenization_notes.append(f"chat_template_failed:{type(exc).__name__}")
        transcript = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}" for message in messages
        )
        input_ids_raw = tokenizer(transcript, add_special_tokens=True)["input_ids"]

    input_ids_list = [int(token_id) for token_id in input_ids_raw]
    if max_seq_len is not None and len(input_ids_list) > max_seq_len:
        trim = len(input_ids_list) - max_seq_len
        input_ids_list = input_ids_list[-max_seq_len:]
        tokenization_notes.append(f"left_truncated_{trim}_tokens")

    positions_by_role, notes = find_content_positions(
        tokenizer=tokenizer,
        input_ids_list=input_ids_list,
        messages=messages,
    )
    tokenization_notes.extend(notes)
    control_positions = special_or_control_positions(tokenizer, input_ids_list)
    control_set = set(control_positions)

    if activation_scope == "assistant_response":
        included_positions = positions_by_role.get("assistant", [])
    elif activation_scope == "user_prompt":
        included_positions = positions_by_role.get("user", [])
    else:
        roles = ["user", "assistant"]
        if include_system_message and include_system_in_all_content:
            roles.insert(0, "system")
        included_positions = []
        for role in roles:
            included_positions.extend(positions_by_role.get(role, []))

    included_positions = sorted(
        position
        for position in set(included_positions)
        if 0 <= position < len(input_ids_list) and position not in control_set
    )
    if not included_positions:
        fallback = [
            index
            for index in range(len(input_ids_list))
            if index not in control_set
        ]
        included_positions = fallback
        tokenization_notes.append("used_non_control_token_fallback")
    if not included_positions:
        raise ValueError(f"No analyzable token positions for {unit.unit_id}")

    input_ids = torch_module.tensor([input_ids_list], dtype=torch_module.long)
    return TokenizedUnit(
        input_ids=input_ids,
        included_positions=included_positions,
        content_positions_by_role={role: positions for role, positions in positions_by_role.items()},
        special_or_control_positions=control_positions,
        tokenization_notes=tokenization_notes,
    )


def capture_hidden_states(
    *,
    torch_module: Any,
    model: Any,
    hook_module: Any,
    input_ids: Any,
) -> Any:
    captured: dict[str, Any] = {}

    def hook(_module: Any, _inputs: Any, output: Any) -> None:
        hidden = output[0] if isinstance(output, tuple) else output
        captured["hidden"] = hidden.detach()

    handle = hook_module.register_forward_hook(hook)
    try:
        with torch_module.inference_mode():
            _ = model(input_ids=input_ids.to(first_model_device(model)), use_cache=False)
    finally:
        handle.remove()

    if "hidden" not in captured:
        raise RuntimeError("Hook did not capture any hidden states")
    return captured["hidden"]


def compute_feature_scores(
    *,
    torch_module: Any,
    sae: Any,
    hidden: Any,
    included_positions: list[int],
    chunk_size: int,
    feature_aggregation: str,
    activation_threshold: float,
) -> tuple[Any, Any, Any]:
    if hidden.ndim != 3 or hidden.shape[0] != 1:
        raise ValueError(f"Expected hidden shape [1, seq, d_model], got {tuple(hidden.shape)}")

    hidden = hidden[0].to(device=next(sae.parameters()).device, dtype=sae.dtype)
    included = torch_module.tensor(
        included_positions,
        device=hidden.device,
        dtype=torch_module.long,
    )
    hidden = hidden.index_select(0, included)
    d_hidden = int(sae.d_hidden)
    feature_max = torch_module.full(
        (d_hidden,),
        -math.inf,
        device=hidden.device,
        dtype=torch_module.float32,
    )
    feature_pos = torch_module.zeros(
        (d_hidden,),
        device=hidden.device,
        dtype=torch_module.long,
    )
    feature_score = torch_module.zeros(
        (d_hidden,),
        device=hidden.device,
        dtype=torch_module.float32,
    )
    active_count = torch_module.zeros(
        (d_hidden,),
        device=hidden.device,
        dtype=torch_module.float32,
    )

    with torch_module.inference_mode():
        for start in range(0, int(hidden.shape[0]), chunk_size):
            end = min(start + chunk_size, int(hidden.shape[0]))
            features = sae.encode(hidden[start:end]).float()
            values, local_positions = features.max(dim=0)
            absolute_positions = included[local_positions + start]
            update_mask = values > feature_max
            feature_max[update_mask] = values[update_mask]
            feature_pos[update_mask] = absolute_positions[update_mask]

            if feature_aggregation == "frequency":
                feature_score += (features > activation_threshold).sum(dim=0).float()
            elif feature_aggregation in {"sum", "mean"}:
                active = features > activation_threshold
                feature_score += features.masked_fill(~active, 0).sum(dim=0)
                if feature_aggregation == "mean":
                    active_count += active.sum(dim=0).float()
            del features

    feature_max[feature_max == -math.inf] = 0
    if feature_aggregation == "max":
        feature_score = feature_max
    elif feature_aggregation == "mean":
        feature_score = torch_module.where(
            active_count > 0,
            feature_score / active_count.clamp_min(1),
            torch_module.zeros_like(feature_score),
        )
    return feature_score, feature_max, feature_pos


def topk_records_from_scores(
    *,
    feature_score: Any,
    feature_max: Any,
    feature_pos: Any,
    input_ids: Any,
    tokenizer: Any,
    top_k: int,
    control_positions: set[int],
    feature_aggregation: str,
) -> list[dict[str, Any]]:
    values, indices = feature_score.topk(k=top_k)
    records: list[dict[str, Any]] = []
    input_ids_cpu = input_ids.detach().cpu()[0]
    special_token_topk_hits = 0

    for rank, (value, feature_index) in enumerate(zip(values.tolist(), indices.tolist()), start=1):
        token_index = int(feature_pos[feature_index].item())
        token_id = int(input_ids_cpu[token_index].item()) if token_index < len(input_ids_cpu) else None
        token_text = tokenizer.decode([token_id]) if token_id is not None else ""
        is_control = token_index in control_positions
        special_token_topk_hits += int(is_control)
        records.append(
            {
                "feature_rank": rank,
                "feature_index": int(feature_index),
                "activation": float(value),
                "feature_aggregation": feature_aggregation,
                "max_activation": float(feature_max[feature_index].item()),
                "max_token_index": token_index,
                "max_token_id": token_id,
                "max_token_text": token_text,
                "max_token_is_special_or_control": bool(is_control),
            }
        )
    if special_token_topk_hits:
        records[0]["special_token_topk_hits_in_unit"] = special_token_topk_hits
    return records


def initialize_aggregates(
    units: list[WorkUnit],
    d_hidden: int,
) -> tuple[dict[tuple[Any, ...], dict[str, Any]], dict[tuple[Any, ...], dict[str, Any]]]:
    np = import_numpy()

    def empty_aggregate() -> dict[str, Any]:
        return {
            "sum": np.zeros(d_hidden, dtype="float64"),
            "sumsq": np.zeros(d_hidden, dtype="float64"),
            "nonzero": np.zeros(d_hidden, dtype="int32"),
            "n": 0,
        }

    condition_aggs: dict[tuple[Any, ...], dict[str, Any]] = {}
    reward_aggs: dict[tuple[Any, ...], dict[str, Any]] = {}
    for unit in units:
        condition_key = (unit.task, unit.condition)
        condition_aggs.setdefault(condition_key, empty_aggregate())
        if unit.reward is not None:
            reward_key = (unit.task, unit.condition, unit.reward)
            reward_aggs.setdefault(reward_key, empty_aggregate())
    return condition_aggs, reward_aggs


def update_aggregate(aggregate: dict[str, Any], feature_max: Any) -> None:
    values = feature_max.detach().cpu().numpy().astype("float64", copy=False)
    aggregate["sum"] += values
    aggregate["sumsq"] += values * values
    aggregate["nonzero"] += values > 0
    aggregate["n"] += 1


def aggregate_records(
    aggregates: dict[tuple[Any, ...], dict[str, Any]],
    *,
    key_names: list[str],
    condition_top_k: int,
    summary_top_n_per_cell: int,
    write_full_summary: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    np = import_numpy()
    top_rows: list[dict[str, Any]] = []
    summary_rows: list[dict[str, Any]] = []

    for key, aggregate in sorted(aggregates.items(), key=lambda item: item[0]):
        n = int(aggregate["n"])
        if n == 0:
            continue
        key_payload = dict(zip(key_names, key, strict=True))
        mean = aggregate["sum"] / n
        variance = np.maximum((aggregate["sumsq"] / n) - (mean * mean), 0)
        std = np.sqrt(variance)
        nonzero = aggregate["nonzero"]

        top_indices = np.argsort(mean)[::-1][:condition_top_k]
        for rank, feature_index in enumerate(top_indices.tolist(), start=1):
            top_rows.append(
                {
                    **key_payload,
                    "rank": rank,
                    "feature_index": int(feature_index),
                    "mean_activation": float(mean[feature_index]),
                    "std_activation": float(std[feature_index]),
                    "nonzero_count": int(nonzero[feature_index]),
                    "n_response_units": n,
                }
            )

        if write_full_summary:
            summary_indices = range(len(mean))
        else:
            summary_indices = np.argsort(mean)[::-1][:summary_top_n_per_cell].tolist()
        for feature_index in summary_indices:
            summary_rows.append(
                {
                    **key_payload,
                    "feature_index": int(feature_index),
                    "mean_activation": float(mean[feature_index]),
                    "std_activation": float(std[feature_index]),
                    "nonzero_count": int(nonzero[feature_index]),
                    "n_response_units": n,
                }
            )

    return top_rows, summary_rows


def load_label_cache(cache_path: Path) -> dict[str, str]:
    if not cache_path.exists():
        return {}
    with cache_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_label_cache(cache_path: Path, cache: dict[str, str]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2, sort_keys=True)


def fetch_one_label(
    feature_index: int,
    *,
    neuronpedia_model: str,
    neuronpedia_source: str,
    timeout: float,
) -> tuple[str, str]:
    url = (
        "https://www.neuronpedia.org/api/feature/"
        f"{neuronpedia_model}/{neuronpedia_source}/{feature_index}"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return str(feature_index), f"feature_{feature_index}"

    label = ""
    explanations = payload.get("explanations") or []
    if explanations and isinstance(explanations[0], dict):
        label = safe_text(explanations[0].get("description"))
    if not label:
        label = safe_text(payload.get("vectorLabel"))
    if not label:
        label = f"feature_{feature_index}"
    return str(feature_index), label


def fetch_feature_labels(
    feature_indices: set[int],
    *,
    cache_path: Path,
    skip_labels: bool,
    workers: int,
    timeout: float,
    neuronpedia_model: str,
    neuronpedia_source: str,
) -> dict[str, str]:
    cache = load_label_cache(cache_path)
    if skip_labels:
        for feature_index in feature_indices:
            cache.setdefault(str(feature_index), f"feature_{feature_index}")
        save_label_cache(cache_path, cache)
        return cache

    missing = sorted(index for index in feature_indices if str(index) not in cache)
    if missing:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
            futures = [
                executor.submit(
                    fetch_one_label,
                    feature_index,
                    neuronpedia_model=neuronpedia_model,
                    neuronpedia_source=neuronpedia_source,
                    timeout=timeout,
                )
                for feature_index in missing
            ]
            for future in as_completed(futures):
                key, label = future.result()
                cache[key] = label
        save_label_cache(cache_path, cache)
    return cache


def add_labels(rows: list[dict[str, Any]], labels: dict[str, str]) -> None:
    for row in rows:
        index = str(row["feature_index"])
        row["feature_label"] = labels.get(index, f"feature_{index}")


def response_preview(text: str, max_chars: int = 240) -> str:
    text = " ".join(text.split())
    return text if len(text) <= max_chars else text[: max_chars - 3] + "..."


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
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


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def safe_risky_behavior_summary(units: list[WorkUnit]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for unit in units:
        if unit.reward is None:
            continue
        key = (unit.condition, unit.reward)
        row = grouped.setdefault(
            key,
            {
                "condition": unit.condition,
                "reward": unit.reward,
                "safe_count": 0,
                "risky_count": 0,
                "other_count": 0,
                "comment_nonempty_count": 0,
                "total_responses": 0,
            },
        )
        row["total_responses"] += 1
        answer = unit.answer_text.lower()
        if "risky" in answer:
            row["risky_count"] += 1
        elif "safe" in answer:
            row["safe_count"] += 1
        else:
            row["other_count"] += 1
        row["comment_nonempty_count"] += int(bool(unit.comment_text.strip()))

    rows: list[dict[str, Any]] = []
    for condition, reward in sorted(
        grouped,
        key=lambda key: (SAFE_RISKY_CONDITION_ORDER.index(key[0]) if key[0] in SAFE_RISKY_CONDITION_ORDER else 999, key[0], key[1]),
    ):
        row = grouped[(condition, reward)]
        total = row["total_responses"]
        row["safe_percentage"] = 100 * row["safe_count"] / total if total else 0
        row["risky_percentage"] = 100 * row["risky_count"] / total if total else 0
        row["other_percentage"] = 100 * row["other_count"] / total if total else 0
        row["comment_nonempty_percentage"] = (
            100 * row["comment_nonempty_count"] / total if total else 0
        )
        rows.append(row)
    return rows


def ultimatum_behavior_summary(units: list[WorkUnit]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for unit in units:
        if unit.reward is None:
            continue
        key = (unit.condition, unit.reward)
        row = grouped.setdefault(
            key,
            {
                "condition": unit.condition,
                "offer": unit.reward,
                "accept_count": 0,
                "reject_count": 0,
                "other_count": 0,
                "comment_nonempty_count": 0,
                "total_responses": 0,
            },
        )
        row["total_responses"] += 1
        answer = unit.answer_text.lower()
        if "accept" in answer:
            row["accept_count"] += 1
        elif "reject" in answer:
            row["reject_count"] += 1
        else:
            row["other_count"] += 1
        row["comment_nonempty_count"] += int(bool(unit.comment_text.strip()))

    rows: list[dict[str, Any]] = []
    for condition, offer in sorted(
        grouped,
        key=lambda key: (
            ULTIMATUM_CONDITION_ORDER.index(key[0])
            if key[0] in ULTIMATUM_CONDITION_ORDER
            else 999,
            key[0],
            key[1],
        ),
    ):
        row = grouped[(condition, offer)]
        total = row["total_responses"]
        row["accept_percentage"] = 100 * row["accept_count"] / total if total else 0
        row["reject_percentage"] = 100 * row["reject_count"] / total if total else 0
        row["other_percentage"] = 100 * row["other_count"] / total if total else 0
        row["comment_nonempty_percentage"] = (
            100 * row["comment_nonempty_count"] / total if total else 0
        )
        rows.append(row)
    return rows


def parse_float_or_none(value: str) -> float | None:
    text = safe_text(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def trust_behavior_summary(units: list[WorkUnit]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, Any]] = {}
    for unit in units:
        if unit.reward is None:
            continue
        key = (unit.condition, unit.reward)
        row = grouped.setdefault(
            key,
            {
                "condition": unit.condition,
                "sent_amount": unit.reward,
                "tripled_amount": unit.reward * 3,
                "return_sum": 0.0,
                "valid_numeric_count": 0,
                "invalid_numeric_count": 0,
                "comment_nonempty_count": 0,
                "total_responses": 0,
            },
        )
        row["total_responses"] += 1
        value = parse_float_or_none(unit.answer_text)
        if value is None:
            row["invalid_numeric_count"] += 1
        else:
            row["valid_numeric_count"] += 1
            row["return_sum"] += value
        row["comment_nonempty_count"] += int(bool(unit.comment_text.strip()))

    rows: list[dict[str, Any]] = []
    for condition, sent_amount in sorted(
        grouped,
        key=lambda key: (
            TRUST_CONDITION_ORDER.index(key[0]) if key[0] in TRUST_CONDITION_ORDER else 999,
            key[0],
            key[1],
        ),
    ):
        row = grouped[(condition, sent_amount)]
        valid = row["valid_numeric_count"]
        total = row["total_responses"]
        row["mean_return"] = row["return_sum"] / valid if valid else 0
        row["mean_return_share_of_tripled"] = (
            row["mean_return"] / row["tripled_amount"] if row["tripled_amount"] else 0
        )
        row["comment_nonempty_percentage"] = (
            100 * row["comment_nonempty_count"] / total if total else 0
        )
        rows.append(row)
    return rows


def build_safe_risky_behavior_plot(output_dir: Path, summary_rows: list[dict[str, Any]]) -> list[str]:
    if not summary_rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    plot_paths: list[str] = []
    conditions = condition_order("safe_risky", [row["condition"] for row in summary_rows])
    rewards = sorted({int(row["reward"]) for row in summary_rows})
    by_key = {(row["condition"], int(row["reward"])): row for row in summary_rows}

    fig, ax = plt.subplots(figsize=(10.5, 6))
    colors = {
        "baseline": "blue",
        "barely_prompting": "purple",
        "slightly_prompting": "orange",
        "lite_steering": "green",
        "steering": "red",
    }
    markers = {
        "baseline": "o",
        "barely_prompting": "s",
        "slightly_prompting": "D",
        "lite_steering": "^",
        "steering": "v",
    }
    for condition in conditions:
        xs: list[int] = []
        ys: list[float] = []
        for reward in rewards:
            row = by_key.get((condition, reward))
            if row:
                xs.append(reward)
                ys.append(row["risky_percentage"])
        if xs:
            ax.plot(
                xs,
                ys,
                marker=markers.get(condition, "o"),
                label=SAFE_RISKY_CONDITION_TITLES.get(condition, condition),
                color=colors.get(condition),
            )
    ax.set_title("Lottery Game Results: Safe vs. Risky\n(saved response audit)")
    ax.set_xlabel("Risky Reward Value (tokens)")
    ax.set_ylabel("Percentage Choosing Risky Option")
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    behavior_path = output_dir / "safe_risky_choice_rates_from_saved_outputs.png"
    fig.savefig(behavior_path, dpi=220)
    plt.close(fig)
    plot_paths.append(str(behavior_path))
    return plot_paths


def build_ultimatum_behavior_plot(output_dir: Path, summary_rows: list[dict[str, Any]]) -> list[str]:
    if not summary_rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    plot_paths: list[str] = []
    conditions = condition_order("ultimatum", [row["condition"] for row in summary_rows])
    offers = sorted({int(row["offer"]) for row in summary_rows})
    by_key = {(row["condition"], int(row["offer"])): row for row in summary_rows}

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    for condition in conditions:
        xs: list[int] = []
        ys: list[float] = []
        for offer in offers:
            row = by_key.get((condition, offer))
            if row:
                xs.append(offer)
                ys.append(row["accept_percentage"])
        if xs:
            ax.plot(
                xs,
                ys,
                marker="o",
                label=ULTIMATUM_CONDITION_TITLES.get(condition, condition),
            )
    ax.set_title("Ultimatum Game Acceptance Rates\n(saved response audit)")
    ax.set_xlabel("Offer to responder")
    ax.set_ylabel("Percentage Accepting")
    ax.set_ylim(0, 105)
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "ultimatum_acceptance_rates_from_saved_outputs.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    plot_paths.append(str(path))
    return plot_paths


def build_trust_behavior_plot(output_dir: Path, summary_rows: list[dict[str, Any]]) -> list[str]:
    if not summary_rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    plot_paths: list[str] = []
    conditions = condition_order("trust", [row["condition"] for row in summary_rows])
    sent_amounts = sorted({int(row["sent_amount"]) for row in summary_rows})
    by_key = {(row["condition"], int(row["sent_amount"])): row for row in summary_rows}

    fig, ax = plt.subplots(figsize=(9.5, 5.5))
    for condition in conditions:
        xs: list[int] = []
        ys: list[float] = []
        for sent_amount in sent_amounts:
            row = by_key.get((condition, sent_amount))
            if row:
                xs.append(sent_amount)
                ys.append(row["mean_return"])
        if xs:
            ax.plot(
                xs,
                ys,
                marker="o",
                label=TRUST_CONDITION_TITLES.get(condition, condition),
            )
    ax.set_title("Trust Game Return Amounts\n(saved response audit)")
    ax.set_xlabel("Amount Sent")
    ax.set_ylabel("Mean Amount Returned")
    ax.grid(True, alpha=0.25)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "trust_mean_returns_from_saved_outputs.png"
    fig.savefig(path, dpi=220)
    plt.close(fig)
    plot_paths.append(str(path))
    return plot_paths


def behavior_summary_for_dataset(dataset_kind: str, units: list[WorkUnit]) -> list[dict[str, Any]]:
    if dataset_kind == "safe_risky":
        return safe_risky_behavior_summary(units)
    if dataset_kind == "ultimatum":
        return ultimatum_behavior_summary(units)
    if dataset_kind == "trust":
        return trust_behavior_summary(units)
    return []


def write_behavior_summary(
    output_dir: Path,
    dataset_kind: str,
    behavior_rows: list[dict[str, Any]],
) -> Path | None:
    if not behavior_rows:
        return None
    path = output_dir / f"{dataset_kind}_behavior_summary.csv"
    write_csv(path, behavior_rows)
    return path


def build_behavior_plot(
    output_dir: Path,
    dataset_kind: str,
    behavior_rows: list[dict[str, Any]],
) -> list[str]:
    if dataset_kind == "safe_risky":
        return build_safe_risky_behavior_plot(output_dir, behavior_rows)
    if dataset_kind == "ultimatum":
        return build_ultimatum_behavior_plot(output_dir, behavior_rows)
    if dataset_kind == "trust":
        return build_trust_behavior_plot(output_dir, behavior_rows)
    return []


def normalized_condition_label(label: str) -> str:
    text = label.lower()
    if "barely" in text:
        return "barely_prompting"
    if "slightly" in text:
        return "slightly_prompting"
    if "0.6" in text or "lite" in text:
        return "lite_steering"
    if "steering" in text:
        return "steering"
    if "prompt" in text:
        return "prompting"
    if "baseline" in text or "base" in text:
        return "baseline"
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def parse_goodfire_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    current_scenario = ""
    current_condition = ""
    current_reward: int | None = None
    current_response: int | None = None
    in_features = False
    rank_counter = 0
    scenario_re = re.compile(r"SCENARIO:\s*(?P<label>.+?)(?:\s+\(Reward:\s*(?P<reward>\d+)\))?\s*$", re.I)
    response_re = re.compile(r"Response\s+(?P<response>\d+):", re.I)

    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        scenario_match = scenario_re.search(stripped)
        if scenario_match:
            current_scenario = scenario_match.group("label").strip()
            current_condition = normalized_condition_label(current_scenario)
            current_reward = (
                int(scenario_match.group("reward"))
                if scenario_match.group("reward")
                else None
            )
            in_features = False
            continue

        if stripped.startswith("===") and "Feature Activation Analysis" in stripped:
            label = stripped.strip("= ").replace("Feature Activation Analysis", "").strip()
            current_scenario = label
            current_condition = normalized_condition_label(label)
            current_reward = None
            in_features = False
            continue

        response_match = response_re.search(stripped)
        if response_match:
            current_response = int(response_match.group("response"))
            in_features = False
            rank_counter = 0
            continue

        if stripped.lower() in {"top feature activations:", "top activated features:"}:
            in_features = True
            rank_counter = 0
            continue

        if in_features:
            if (
                not stripped
                or stripped.startswith("-")
                or stripped.lower().startswith("response ")
                or stripped.lower().startswith("user prompt")
                or stripped.lower().startswith("model response")
            ):
                if stripped.lower().startswith("response "):
                    response_match = response_re.search(stripped)
                    if response_match:
                        current_response = int(response_match.group("response"))
                in_features = False
                continue
            if ":" not in stripped:
                continue
            label_part, activation_part = stripped.rsplit(":", 1)
            activation_part = activation_part.strip()
            try:
                activation = float(activation_part)
            except ValueError:
                continue
            numbered = re.match(r"^(?P<rank>\d+)\.\s*(?P<label>.+)$", label_part.strip())
            if numbered:
                rank = int(numbered.group("rank"))
                feature_label = numbered.group("label").strip()
            else:
                rank_counter += 1
                rank = rank_counter
                feature_label = label_part.strip()
            rows.append(
                {
                    "scenario": current_scenario,
                    "condition": current_condition,
                    "reward": current_reward,
                    "response_index": current_response,
                    "rank": rank,
                    "feature_label": feature_label,
                    "activation": activation,
                    "source_log": str(path),
                }
            )
    return rows


def build_goodfire_overlap(
    *,
    produced_rows: list[dict[str, Any]],
    goodfire_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    old_by_key: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    old_activation_by_key: dict[tuple[Any, ...], dict[str, float]] = defaultdict(dict)
    for row in goodfire_rows:
        if row["rank"] > 10:
            continue
        key = (row["condition"], row.get("reward"), row.get("response_index"))
        label = row["feature_label"]
        old_by_key[key].add(label)
        old_activation_by_key[key][label] = row["activation"]

    new_by_key: dict[tuple[Any, ...], set[str]] = defaultdict(set)
    for row in produced_rows:
        if row["feature_rank"] > 10:
            continue
        key = (row["condition"], row.get("reward"), row.get("response_index"))
        new_by_key[key].add(row["feature_label"])

    rows: list[dict[str, Any]] = []
    all_keys = sorted(set(old_by_key) | set(new_by_key), key=lambda key: (str(key[0]), key[1] or -1, key[2] or -1))
    for condition, reward, response_index in all_keys:
        old_labels = old_by_key.get((condition, reward, response_index), set())
        new_labels = new_by_key.get((condition, reward, response_index), set())
        overlap = old_labels & new_labels
        rows.append(
            {
                "condition": condition,
                "reward": reward,
                "response_index": response_index,
                "old_top10_count": len(old_labels),
                "new_top10_count": len(new_labels),
                "label_overlap_count": len(overlap),
                "label_overlap_fraction_of_old": (
                    len(overlap) / len(old_labels) if old_labels else None
                ),
                "label_overlap": "; ".join(sorted(overlap)),
            }
        )
    return rows


def build_plots(
    *,
    output_dir: Path,
    dataset_kind: str,
    units: list[WorkUnit],
    condition_top_rows: list[dict[str, Any]],
    condition_reward_top_rows: list[dict[str, Any]],
    top_feature_rows: list[dict[str, Any]],
    goodfire_overlap_rows: list[dict[str, Any]],
) -> list[str]:
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []

    plot_paths: list[str] = []
    if dataset_kind != "safe_risky":
        condition_titles = DATASET_CONDITION_TITLES.get(dataset_kind, {})
        task_titles = DATASET_TASK_TITLES.get(dataset_kind, {})
        conditions = condition_order(dataset_kind, [unit.condition for unit in units])
        tasks = task_order(dataset_kind, [unit.task for unit in units])
        feature_aggregation = next(
            (
                row.get("feature_aggregation")
                for row in top_feature_rows
                if row.get("feature_aggregation")
            ),
            "max",
        )
        xlabel_by_aggregation = {
            "frequency": "Mean active-token count",
            "max": "Mean max SAE activation",
            "sum": "Mean summed SAE activation",
            "mean": "Mean active-token SAE activation",
        }
        x_label = xlabel_by_aggregation.get(feature_aggregation, "Mean response-level feature score")
        fig, axes = plt.subplots(len(tasks), len(conditions), figsize=(4.6 * len(conditions), 4.8 * len(tasks)))
        if len(tasks) == 1 and len(conditions) == 1:
            axes_grid = [[axes]]
        elif len(tasks) == 1:
            axes_grid = [list(axes)]
        elif len(conditions) == 1:
            axes_grid = [[ax] for ax in axes]
        else:
            axes_grid = axes
        for row_idx, task in enumerate(tasks):
            for col_idx, condition in enumerate(conditions):
                ax = axes_grid[row_idx][col_idx]
                panel_rows = [
                    row
                    for row in condition_top_rows
                    if row["task"] == task and row["condition"] == condition and row["rank"] <= 5
                ]
                panel_rows = sorted(panel_rows, key=lambda row: row["rank"], reverse=True)
                labels = [
                    row["feature_label"] if len(row["feature_label"]) <= 50 else row["feature_label"][:47] + "..."
                    for row in panel_rows
                ]
                values = [row["mean_activation"] for row in panel_rows]
                ax.barh(labels, values, color="#4C78A8" if row_idx == 0 else "#B75D8A")
                ax.set_title(f"{task_titles.get(task, task)}\n{condition_titles.get(condition, condition)}", fontsize=9)
                ax.set_xlabel(x_label)
                ax.tick_params(axis="y", labelsize=7)
        fig.suptitle(
            "Top 5 Activated Goodfire Open-SAE Features by Task and Condition",
            fontsize=14,
            y=0.995,
        )
        fig.tight_layout(rect=(0, 0, 1, 0.965))
        figure_name = (
            "open_sae_figure4_replacement_top_features.png"
            if dataset_kind == "creativity"
            else f"{dataset_kind}_open_sae_top_features_by_condition.png"
        )
        figure_path = output_dir / figure_name
        fig.savefig(figure_path, dpi=220, bbox_inches="tight", pad_inches=0.2)
        plt.close(fig)
        plot_paths.append(str(figure_path))

    if dataset_kind == "safe_risky":
        condition_titles = SAFE_RISKY_CONDITION_TITLES
        conditions = condition_order(dataset_kind, [unit.condition for unit in units])
        rewards = sorted({unit.reward for unit in units if unit.reward is not None})
        if rewards:
            counts: dict[tuple[str, int], list[int]] = defaultdict(lambda: [0, 0])
            for unit in units:
                if unit.reward is None:
                    continue
                counts[(unit.condition, unit.reward)][1] += 1
                if "risky" in unit.answer_text.lower():
                    counts[(unit.condition, unit.reward)][0] += 1
            fig, ax = plt.subplots(figsize=(10.5, 6))
            colors = {
                "baseline": "blue",
                "barely_prompting": "purple",
                "slightly_prompting": "orange",
                "lite_steering": "green",
                "steering": "red",
            }
            markers = {
                "baseline": "o",
                "barely_prompting": "s",
                "slightly_prompting": "D",
                "lite_steering": "^",
                "steering": "v",
            }
            for condition in conditions:
                xs: list[int] = []
                ys: list[float] = []
                for reward in rewards:
                    risky_count, total = counts[(condition, reward)]
                    if total:
                        xs.append(reward)
                        ys.append(100 * risky_count / total)
                if xs:
                    ax.plot(
                        xs,
                        ys,
                        marker=markers.get(condition, "o"),
                        label=condition_titles.get(condition, condition),
                        color=colors.get(condition),
                    )
            ax.set_title("Lottery Game Results: Safe vs. Risky\n(saved response audit)")
            ax.set_xlabel("Risky Reward Value (tokens)")
            ax.set_ylabel("Percentage Choosing Risky Option")
            ax.set_ylim(0, 105)
            ax.grid(True, alpha=0.25)
            ax.legend()
            fig.tight_layout()
            behavior_path = output_dir / "safe_risky_choice_rates_from_saved_outputs.png"
            fig.savefig(behavior_path, dpi=220)
            plt.close(fig)
            plot_paths.append(str(behavior_path))

        if condition_reward_top_rows:
            selected_rewards = [reward for reward in [10, 50, 100, 150, 180] if reward in rewards]
            if not selected_rewards:
                selected_rewards = rewards[: min(5, len(rewards))]
            fig, axes = plt.subplots(len(selected_rewards), 1, figsize=(11, 3.4 * len(selected_rewards)))
            if len(selected_rewards) == 1:
                axes = [axes]
            for ax, reward in zip(axes, selected_rewards):
                panel_rows = [
                    row
                    for row in condition_reward_top_rows
                    if row.get("reward") == reward and row["rank"] == 1
                ]
                xs = [condition_titles.get(row["condition"], row["condition"]) for row in panel_rows]
                ys = [row["mean_activation"] for row in panel_rows]
                labels = [
                    row["feature_label"][:60] + ("..." if len(row["feature_label"]) > 60 else "")
                    for row in panel_rows
                ]
                ax.bar(xs, ys, color="#6C8EBF")
                ax.set_ylabel("Mean top feature activation")
                ax.set_title(f"Top feature by condition at risky reward {reward}")
                ax.tick_params(axis="x", rotation=15)
                for index, label in enumerate(labels):
                    ax.text(index, ys[index], label, ha="center", va="bottom", fontsize=7, rotation=18)
            fig.tight_layout()
            feature_path = output_dir / "safe_risky_open_sae_top_feature_by_reward.png"
            fig.savefig(feature_path, dpi=220)
            plt.close(fig)
            plot_paths.append(str(feature_path))

    tasks = task_order(dataset_kind, [unit.task for unit in units])
    conditions = condition_order(dataset_kind, [unit.condition for unit in units])
    condition_titles = DATASET_CONDITION_TITLES.get(dataset_kind, {})
    task_titles = DATASET_TASK_TITLES.get(dataset_kind, {})
    fig, axes = plt.subplots(1, len(tasks), figsize=(5.5 * len(tasks), 5), sharey=True)
    if len(tasks) == 1:
        axes = [axes]
    for ax, task in zip(axes, tasks):
        distributions = []
        labels = []
        for condition in conditions:
            values = [
                row["activation"]
                for row in top_feature_rows
                if row["task"] == task and row["condition"] == condition and row["feature_rank"] == 1
            ]
            if values:
                distributions.append(values)
                labels.append(condition_titles.get(condition, condition))
        if distributions:
            ax.boxplot(distributions, tick_labels=labels, showfliers=False)
        ax.set_title(task_titles.get(task, task))
        ax.tick_params(axis="x", rotation=20)
        ax.set_ylabel("Top-1 max SAE activation")
    fig.tight_layout()
    diagnostics_path = output_dir / "open_sae_per_response_top_activation_diagnostics.png"
    fig.savefig(diagnostics_path, dpi=220)
    plt.close(fig)
    plot_paths.append(str(diagnostics_path))

    if goodfire_overlap_rows:
        values = [
            row["label_overlap_fraction_of_old"]
            for row in goodfire_overlap_rows
            if row["label_overlap_fraction_of_old"] is not None
        ]
        if values:
            fig, ax = plt.subplots(figsize=(7, 4.5))
            ax.hist(values, bins=[index / 10 for index in range(0, 12)], color="#7E6BC4", edgecolor="white")
            ax.set_title("Old Goodfire API vs Open-SAE Top-10 Label Overlap")
            ax.set_xlabel("Overlap fraction of old top-10 labels")
            ax.set_ylabel("Response units")
            fig.tight_layout()
            overlap_path = output_dir / "open_sae_goodfire_label_overlap_diagnostics.png"
            fig.savefig(overlap_path, dpi=220)
            plt.close(fig)
            plot_paths.append(str(overlap_path))

    return plot_paths


def dependency_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for module_name in [
        "torch",
        "transformers",
        "huggingface_hub",
        "numpy",
        "pandas",
        "matplotlib",
    ]:
        try:
            module = __import__(module_name)
            versions[module_name] = safe_text(getattr(module, "__version__", "unknown"))
        except Exception:
            versions[module_name] = "not_importable"
    return versions


def gpu_metadata(torch_module: Any | None) -> dict[str, Any]:
    if torch_module is None:
        return {}
    if not torch_module.cuda.is_available():
        return {"cuda_available": False}
    return {
        "cuda_available": True,
        "device_count": torch_module.cuda.device_count(),
        "devices": [
            {
                "index": index,
                "name": torch_module.cuda.get_device_name(index),
                "capability": torch_module.cuda.get_device_capability(index),
                "total_memory_gb": round(
                    torch_module.cuda.get_device_properties(index).total_memory / (1024**3),
                    2,
                ),
            }
            for index in range(torch_module.cuda.device_count())
        ],
    }


def run_inference(
    args: argparse.Namespace,
    units: list[WorkUnit],
    validation: dict[str, Any],
    loaded_model_bundle: tuple[Any, Any, Any, Any, Any, str, str] | None = None,
) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)

    if loaded_model_bundle is None:
        torch_module, tokenizer, model, hook_module, sae, sae_path, sae_device = load_model_and_sae(
            args
        )
    else:
        torch_module, tokenizer, model, hook_module, sae, sae_path, sae_device = loaded_model_bundle
    d_in = int(sae.d_in)
    d_hidden = int(sae.d_hidden)
    condition_aggs, reward_aggs = initialize_aggregates(units, d_hidden)
    top_feature_rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []

    started = time.time()
    for index, unit in enumerate(units, start=1):
        unit_started = time.time()
        status = "ok"
        error = ""
        top_records: list[dict[str, Any]] = []
        tokenized: TokenizedUnit | None = None
        try:
            tokenized = make_tokenized_unit(
                tokenizer,
                unit,
                torch_module,
                max_seq_len=args.max_seq_len,
                activation_scope=args.activation_scope,
                include_system_message=args.include_system_message,
                include_system_in_all_content=args.include_system_in_all_content,
            )
            hidden = capture_hidden_states(
                torch_module=torch_module,
                model=model,
                hook_module=hook_module,
                input_ids=tokenized.input_ids,
            )
            feature_score, feature_max, feature_pos = compute_feature_scores(
                torch_module=torch_module,
                sae=sae,
                hidden=hidden,
                included_positions=tokenized.included_positions,
                chunk_size=args.activation_chunk_size,
                feature_aggregation=args.feature_aggregation,
                activation_threshold=args.activation_threshold,
            )
            update_aggregate(condition_aggs[(unit.task, unit.condition)], feature_score)
            if unit.reward is not None:
                update_aggregate(reward_aggs[(unit.task, unit.condition, unit.reward)], feature_score)
            top_records = topk_records_from_scores(
                feature_score=feature_score,
                feature_max=feature_max,
                feature_pos=feature_pos,
                input_ids=tokenized.input_ids,
                tokenizer=tokenizer,
                top_k=args.top_k,
                control_positions=set(tokenized.special_or_control_positions),
                feature_aggregation=args.feature_aggregation,
            )
            del hidden, feature_score, feature_max, feature_pos
            if torch_module.cuda.is_available():
                torch_module.cuda.empty_cache()
        except Exception as exc:
            status = "error"
            error = repr(exc)

        elapsed = round(time.time() - unit_started, 3)
        included_count = len(tokenized.included_positions) if tokenized else 0
        control_count = len(tokenized.special_or_control_positions) if tokenized else 0
        sequence_length = int(tokenized.input_ids.shape[-1]) if tokenized is not None else None
        note_text = ";".join(tokenized.tokenization_notes) if tokenized else ""
        for top_record in top_records:
            top_feature_rows.append(
                {
                    "dataset_kind": unit.dataset_kind,
                    "condition": unit.condition,
                    "task": unit.task,
                    "reward": unit.reward,
                    "agent_index": unit.agent_index,
                    "agent_subject_id": unit.agent_subject_id,
                    "source_file": unit.source_file,
                    "source_row_index": unit.source_row_index,
                    "response_index": unit.response_index,
                    "unit_id": unit.unit_id,
                    **top_record,
                    "activation_scope": args.activation_scope,
                    "included_token_count": included_count,
                    "special_or_control_token_count": control_count,
                    "sequence_length": sequence_length,
                    "model_id": args.model_id,
                    "sae_repo": args.sae_repo,
                    "hook": args.hook,
                    "status": status,
                    "error": error,
                    "tokenization_notes": note_text,
                    "answer_text": unit.answer_text,
                    "comment_text": unit.comment_text,
                    "response_preview": response_preview(unit.response_text),
                }
            )

        audit_rows.append(
            {
                **asdict(unit),
                "status": status,
                "error": error,
                "elapsed_seconds": elapsed,
                "sequence_length": sequence_length,
                "activation_scope": args.activation_scope,
                "included_token_count": included_count,
                "special_or_control_token_count": control_count,
                "content_token_counts_by_role": {
                    role: len(positions)
                    for role, positions in (tokenized.content_positions_by_role.items() if tokenized else [])
                },
                "tokenization_notes": tokenized.tokenization_notes if tokenized else [],
                "top_features": top_records,
            }
        )

        print(
            f"[{index:04d}/{len(units):04d}] {unit.dataset_kind} {unit.condition} "
            f"reward={unit.reward} task={unit.task} response={unit.response_index} "
            f"tokens={included_count}/{sequence_length} status={status} elapsed={elapsed}s",
            flush=True,
        )

    condition_top_rows, condition_summary_rows = aggregate_records(
        condition_aggs,
        key_names=["task", "condition"],
        condition_top_k=args.condition_top_k,
        summary_top_n_per_cell=args.summary_top_n_per_cell,
        write_full_summary=args.write_full_summary,
    )
    condition_reward_top_rows, condition_reward_summary_rows = aggregate_records(
        reward_aggs,
        key_names=["task", "condition", "reward"],
        condition_top_k=args.condition_top_k,
        summary_top_n_per_cell=args.summary_top_n_per_cell,
        write_full_summary=args.write_full_summary,
    )
    summary_rows = condition_summary_rows + condition_reward_summary_rows

    feature_indices = {
        int(row["feature_index"])
        for row in [
            *top_feature_rows,
            *condition_top_rows,
            *condition_reward_top_rows,
            *summary_rows,
        ]
    }
    labels = fetch_feature_labels(
        feature_indices,
        cache_path=args.output_dir / "feature_label_cache.json",
        skip_labels=args.skip_labels,
        workers=args.label_workers,
        timeout=args.label_timeout,
        neuronpedia_model=args.neuronpedia_model,
        neuronpedia_source=args.neuronpedia_source,
    )
    for rows in [top_feature_rows, condition_top_rows, condition_reward_top_rows, summary_rows]:
        add_labels(rows, labels)
    for audit in audit_rows:
        for top_feature in audit["top_features"]:
            index = str(top_feature["feature_index"])
            top_feature["feature_label"] = labels.get(index, f"feature_{index}")

    goodfire_rows: list[dict[str, Any]] = []
    overlap_rows: list[dict[str, Any]] = []
    if args.goodfire_log:
        goodfire_rows = parse_goodfire_log(args.goodfire_log)
        overlap_rows = build_goodfire_overlap(
            produced_rows=top_feature_rows,
            goodfire_rows=goodfire_rows,
        )

    behavior_rows = behavior_summary_for_dataset(args.dataset_kind, units)

    plot_paths = build_plots(
        output_dir=args.output_dir,
        dataset_kind=args.dataset_kind,
        units=units,
        condition_top_rows=condition_top_rows,
        condition_reward_top_rows=condition_reward_top_rows,
        top_feature_rows=top_feature_rows,
        goodfire_overlap_rows=overlap_rows,
    )
    if args.dataset_kind in {"ultimatum", "trust"}:
        plot_paths.extend(build_behavior_plot(args.output_dir, args.dataset_kind, behavior_rows))

    response_unit_rows = [asdict(unit) for unit in units]
    write_csv(args.output_dir / "open_sae_response_units.csv", response_unit_rows)
    write_csv(args.output_dir / "open_sae_feature_activations.csv", top_feature_rows)
    write_jsonl(args.output_dir / "open_sae_feature_activations.jsonl", audit_rows)
    write_csv(args.output_dir / "open_sae_condition_top_features.csv", condition_top_rows)
    if condition_reward_top_rows:
        write_csv(args.output_dir / "open_sae_condition_reward_top_features.csv", condition_reward_top_rows)
    write_csv(args.output_dir / "open_sae_feature_summary.csv", summary_rows)
    write_behavior_summary(args.output_dir, args.dataset_kind, behavior_rows)
    if goodfire_rows:
        write_csv(args.output_dir / "goodfire_api_feature_activations_parsed.csv", goodfire_rows)
    if overlap_rows:
        write_csv(args.output_dir / "open_sae_goodfire_overlap.csv", overlap_rows)

    unit_status_counts: dict[str, int] = defaultdict(int)
    special_topk_hits = 0
    for audit in audit_rows:
        unit_status_counts[audit["status"]] += 1
        for top_feature in audit["top_features"]:
            special_topk_hits += int(top_feature.get("max_token_is_special_or_control", False))

    metadata = {
        "dataset_kind": args.dataset_kind,
        "source_dir": release_path(args.source_dir),
        "output_dir": release_path(args.output_dir),
        "script_path": release_path(Path(__file__)),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model_id": args.model_id,
        "sae_repo": args.sae_repo,
        "sae_path": sae_path,
        "hook": args.hook,
        "sae_device": sae_device,
        "sae_input_size": d_in,
        "sae_hidden_size": d_hidden,
        "activation_scope": args.activation_scope,
        "feature_aggregation": args.feature_aggregation,
        "activation_threshold": args.activation_threshold,
        "include_system_message": args.include_system_message,
        "include_system_in_all_content": args.include_system_in_all_content,
        "top_k": args.top_k,
        "condition_top_k": args.condition_top_k,
        "summary_top_n_per_cell": args.summary_top_n_per_cell,
        "write_full_summary": args.write_full_summary,
        "aggregation_rule": (
            "For each response unit, compute a feature score over only the selected "
            "content-token scope, after excluding chat-template special/control "
            "tokens. feature_aggregation=max uses the max SAE activation per "
            "feature; frequency counts tokens with activation greater than "
            "activation_threshold; sum and mean use thresholded active tokens. "
            "Aggregate rows rank features by the mean of those per-response scores."
        ),
        "expected_top_feature_rows": len(units) * args.top_k,
        "actual_top_feature_rows": len(top_feature_rows),
        "processed_response_task_units": len(audit_rows),
        "unit_status_counts": dict(unit_status_counts),
        "special_or_control_token_topk_hits": special_topk_hits,
        "condition_summary_cells": len(
            {(row["task"], row["condition"]) for row in condition_top_rows}
        ),
        "condition_reward_summary_cells": len(
            {(row["task"], row["condition"], row.get("reward")) for row in condition_reward_top_rows}
        ),
        "plots": [release_path(path) for path in plot_paths],
        "goodfire_log": release_path(args.goodfire_log),
        "goodfire_parsed_rows": len(goodfire_rows),
        "goodfire_overlap_rows": len(overlap_rows),
        "behavior_summary_rows": len(behavior_rows),
        "validation": validation,
        "dependencies": dependency_versions(),
        "gpu": gpu_metadata(torch_module),
        "platform": {
            "hostname": "<redacted>",
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version,
        },
        "elapsed_seconds": round(time.time() - started, 3),
    }
    with (args.output_dir / "open_sae_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)

    print(
        json.dumps(
            {
                "status": "complete",
                "output_dir": str(args.output_dir),
                "processed_response_task_units": len(audit_rows),
                "top_feature_rows": len(top_feature_rows),
                "special_or_control_token_topk_hits": special_topk_hits,
                "plots": plot_paths,
                "elapsed_seconds": metadata["elapsed_seconds"],
            },
            indent=2,
        )
    )


def run_dataset_audit(args: argparse.Namespace, units: list[WorkUnit], validation: dict[str, Any]) -> None:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    response_unit_rows = [asdict(unit) for unit in units]
    write_csv(args.output_dir / "open_sae_response_units.csv", response_unit_rows)

    behavior_rows: list[dict[str, Any]] = []
    plot_paths: list[str] = []
    behavior_rows = behavior_summary_for_dataset(args.dataset_kind, units)
    write_behavior_summary(args.output_dir, args.dataset_kind, behavior_rows)
    plot_paths.extend(build_behavior_plot(args.output_dir, args.dataset_kind, behavior_rows))

    goodfire_rows: list[dict[str, Any]] = []
    if args.goodfire_log:
        goodfire_rows = parse_goodfire_log(args.goodfire_log)
        write_csv(args.output_dir / "goodfire_api_feature_activations_parsed.csv", goodfire_rows)

    metadata = {
        "mode": "audit_only",
        "dataset_kind": args.dataset_kind,
        "source_dir": release_path(args.source_dir),
        "output_dir": release_path(args.output_dir),
        "script_path": release_path(Path(__file__)),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "processed_response_task_units": len(units),
        "behavior_summary_rows": len(behavior_rows),
        "goodfire_log": release_path(args.goodfire_log),
        "goodfire_parsed_rows": len(goodfire_rows),
        "plots": [release_path(path) for path in plot_paths],
        "validation": validation,
        "dependencies": dependency_versions(),
        "platform": {
            "hostname": "<redacted>",
            "system": platform.system(),
            "release": platform.release(),
            "python": sys.version,
        },
    }
    with (args.output_dir / "open_sae_metadata.json").open("w", encoding="utf-8") as handle:
        json.dump(metadata, handle, indent=2, sort_keys=True)
    print(
        json.dumps(
            {
                "status": "audit_complete",
                "output_dir": str(args.output_dir),
                "processed_response_task_units": len(units),
                "behavior_summary_rows": len(behavior_rows),
                "goodfire_parsed_rows": len(goodfire_rows),
                "plots": plot_paths,
            },
            indent=2,
        )
    )


def main() -> None:
    args = parse_args()
    if args.run_dir is not None:
        if args.dataset_kind is None:
            args.dataset_kind = infer_run_dataset_kind(args.run_dir)
        args.source_dir = args.run_dir
        if args.output_dir is None:
            args.output_dir = args.run_dir / "open_sae"
    else:
        if args.dataset_kind is None:
            raise SystemExit("--dataset-kind is required when --run-dir is not supplied")
        if args.source_dir is None:
            args.source_dir = default_source_dir(args.dataset_kind)
        if args.output_dir is None:
            args.output_dir = default_output_dir(
                args.dataset_kind,
                args.source_dir,
                args.activation_scope,
            )

    units, validation = load_work_units(args)
    if args.dry_run:
        print_dry_run(units, validation)
        if args.goodfire_log:
            rows = parse_goodfire_log(args.goodfire_log)
            print(
                json.dumps(
                    {
                        "goodfire_log": str(args.goodfire_log),
                        "parsed_goodfire_rows": len(rows),
                        "first_goodfire_row": rows[0] if rows else None,
                    },
                    indent=2,
                )
            )
        return

    if args.audit_only:
        run_dataset_audit(args, units, validation)
        return

    run_inference(args, units, validation)


if __name__ == "__main__":
    main()
