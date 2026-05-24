#!/usr/bin/env python3
"""Phase-2 entrypoint for open-SAE steering generation.

This v1 script implements smoke planning and validation only. It refuses to
produce generated responses until the full activation-patching generation path is
implemented, which prevents accidentally mistaking a plan for a regeneration run.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from run_open_sae_feature_inspection import (
    DEFAULT_HOOK,
    DEFAULT_MODEL_ID,
    DEFAULT_SAE_REPO,
    default_source_dir,
    load_creativity_units,
    load_safe_risky_units,
    load_trust_units,
    load_ultimatum_units,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_STEERING_FEATURES = [13142, 20117, 4992]
DEFAULT_STEERING_STRENGTHS = [0.3, 0.3, 0.3]


def parse_int_list(value: str) -> list[int]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("expected at least one integer")
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_float_list(value: str) -> list[float]:
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("expected at least one float")
    try:
        return [float(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_optional_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def parse_optional_int_set(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(part.strip()) for part in value.split(",") if part.strip()}


def relative_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def load_units(args: argparse.Namespace) -> list[Any]:
    source_dir = args.source_dir or default_source_dir(args.dataset_kind)
    conditions = parse_optional_set(args.conditions)
    rewards = parse_optional_int_set(args.rewards)

    if args.dataset_kind == "creativity":
        units, _ = load_creativity_units(
            source_dir,
            strict=True,
            conditions=conditions,
            limit_units=args.limit_units,
        )
    elif args.dataset_kind == "safe_risky":
        units, _ = load_safe_risky_units(
            source_dir,
            strict=True,
            conditions=conditions,
            rewards=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=args.limit_units,
        )
    elif args.dataset_kind == "ultimatum":
        units, _ = load_ultimatum_units(
            source_dir,
            strict=True,
            conditions=conditions,
            offers=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=args.limit_units,
        )
    elif args.dataset_kind == "trust":
        units, _ = load_trust_units(
            source_dir,
            strict=True,
            conditions=conditions,
            sent_amounts=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=args.limit_units,
        )
    else:
        raise ValueError(f"Unknown dataset kind: {args.dataset_kind}")

    if not units:
        raise ValueError("No source units selected for steering smoke plan")
    return units


def load_prompt_file(path: Path, limit: int | None) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            record = json.loads(text)
            if "user_prompt" not in record:
                raise ValueError(f"{relative_path(path)}:{line_number} missing user_prompt")
            records.append(
                {
                    "unit_id": record.get("unit_id", f"prompt_file:{line_number}"),
                    "condition": record.get("condition", ""),
                    "task": record.get("task", ""),
                    "reward": record.get("reward", ""),
                    "system_prompt": record.get("system_prompt", ""),
                    "user_prompt": record["user_prompt"],
                }
            )
            if limit is not None and len(records) >= limit:
                break
    if not records:
        raise ValueError(f"No prompt records found in {relative_path(path)}")
    return records


def selected_prompt_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    if args.prompt_file:
        return load_prompt_file(args.prompt_file, args.limit_units)

    records: list[dict[str, Any]] = []
    for unit in load_units(args):
        records.append(
            {
                "unit_id": unit.unit_id,
                "condition": unit.condition,
                "task": unit.task,
                "reward": "" if unit.reward is None else unit.reward,
                "system_prompt": unit.system_prompt,
                "user_prompt": unit.user_prompt,
            }
        )
    return records


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["unit_id", "condition", "task", "reward", "system_prompt", "user_prompt"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_smoke_plan(args: argparse.Namespace) -> dict[str, Any]:
    feature_indices = args.feature_indices
    strengths = args.strengths
    if len(feature_indices) != len(strengths):
        raise ValueError("--feature-indices and --strengths must have the same length")

    prompts = selected_prompt_records(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    units_path = args.output_dir / "open_sae_steering_smoke_units.csv"
    plan_path = args.output_dir / "open_sae_steering_smoke_plan.json"
    write_csv(units_path, prompts)

    plan = {
        "status": "smoke_plan_only",
        "dataset_kind": args.dataset_kind,
        "selected_prompt_units": len(prompts),
        "prompt_units_csv": relative_path(units_path),
        "model_id": args.model_id,
        "sae_repo": args.sae_repo,
        "hook": args.hook,
        "steering_mode": args.steering_mode,
        "feature_indices": feature_indices,
        "strengths": strengths,
        "source_dir": relative_path(args.source_dir or default_source_dir(args.dataset_kind)),
        "prompt_file": relative_path(args.prompt_file) if args.prompt_file else "",
        "implementation_status": (
            "The v1 public repo validates steering inputs and selected prompts. "
            "Full activation-patching generation is phase 2."
        ),
    }
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-kind",
        choices=["creativity", "safe_risky", "ultimatum", "trust"],
        required=True,
    )
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data/processed/steering_smoke_plan",
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--sae-repo", default=DEFAULT_SAE_REPO)
    parser.add_argument("--hook", default=DEFAULT_HOOK)
    parser.add_argument(
        "--feature-indices",
        type=parse_int_list,
        default=DEFAULT_STEERING_FEATURES,
        help="Comma-separated SAE feature indices.",
    )
    parser.add_argument(
        "--strengths",
        type=parse_float_list,
        default=DEFAULT_STEERING_STRENGTHS,
        help="Comma-separated steering strengths aligned to --feature-indices.",
    )
    parser.add_argument("--steering-mode", default="nudge")
    parser.add_argument("--limit-units", type=int, default=8)
    parser.add_argument("--max-agents-per-cell", type=int, default=None)
    parser.add_argument("--conditions", default=None)
    parser.add_argument("--rewards", default=None)
    parser.add_argument("--smoke-mode", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.execute:
        raise SystemExit(
            "Full open-SAE steering generation is intentionally not implemented in v1. "
            "Use --smoke-mode to validate feature indices and selected prompts."
        )
    if not args.smoke_mode:
        raise SystemExit("Pass --smoke-mode for the implemented v1 steering smoke plan.")
    plan = write_smoke_plan(args)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
