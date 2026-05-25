#!/usr/bin/env python3
"""Build a machine-readable release completion audit."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from social_sim_open_sae.edsl_adapter import load_game_spec

AUDIT_JSON = ROOT / "reports" / "RELEASE_COMPLETION_AUDIT.json"
AUDIT_MD = ROOT / "reports" / "RELEASE_COMPLETION_AUDIT.md"
EXPECTED_STEERING_FEATURES = {13142, 20117, 4992}


@dataclass
class AuditItem:
    """One checked release requirement."""

    id: str
    requirement: str
    status: str
    evidence: list[str]
    verification: dict[str, Any]
    next_step: str = ""


def rel(path: Path | str) -> str:
    """Return a repo-relative path when possible."""

    path = Path(path)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def exists(path: str) -> bool:
    """Return true when a repo-relative path exists and is non-empty."""

    full = ROOT / path
    return full.exists() and full.stat().st_size > 0


def status_from_bool(done: bool) -> str:
    """Normalize boolean checks to audit statuses."""

    return "complete" if done else "incomplete"


def open_sae_counts(base: str) -> dict[str, Any]:
    """Read common Open-SAE output counts."""

    base_path = ROOT / base
    activations = pd.read_csv(base_path / "open_sae_feature_activations.csv")
    top = pd.read_csv(base_path / "open_sae_condition_top_features.csv")
    metadata = json.loads((base_path / "open_sae_metadata.json").read_text(encoding="utf-8"))
    verification: dict[str, Any] = {
        "activation_rows": int(len(activations)),
        "processed_response_task_units": int(metadata.get("processed_response_task_units", -1)),
        "condition_cells": int(top.groupby(["task", "condition"]).ngroups),
        "special_or_control_token_topk_hits": int(
            metadata.get("special_or_control_token_topk_hits", -1)
        ),
        "top_k": int(metadata.get("top_k", -1)),
    }
    reward_path = base_path / "open_sae_condition_reward_top_features.csv"
    if reward_path.exists():
        reward = pd.read_csv(reward_path)
        verification["reward_cells"] = int(reward.groupby(["task", "condition", "reward"]).ngroups)
    return verification


def build_platform_item() -> AuditItem:
    """Audit reusable platform files and example game specs."""

    examples = sorted((ROOT / "examples/games").glob("*.py"))
    examples = [path for path in examples if path.name != "__init__.py"]
    specs = [load_game_spec(path) for path in examples]
    expected_files = [
        "social_sim_open_sae/game_spec.py",
        "social_sim_open_sae/edsl_adapter.py",
        "scripts/run_edsl_social_simulation.py",
        "scripts/check_environment.py",
        "scripts/run_open_sae_feature_inspection.py",
        "docs/BUILD_A_GAME.md",
    ]
    docs_text = (ROOT / "docs/BUILD_A_GAME.md").read_text(encoding="utf-8")
    done = (
        all(exists(path) for path in expected_files)
        and {spec.game_id for spec in specs} == {"creativity", "safe_risky", "ultimatum", "trust"}
        and "scripts/run_edsl_social_simulation.py" in docs_text
        and "--run-dir" in docs_text
    )
    return AuditItem(
        id="platform_new_games",
        requirement=(
            "Users can define EDSL games, collect normalized response units, and run "
            "Open-SAE inspection through the platform interface."
        ),
        status=status_from_bool(done),
        evidence=[*expected_files, *[rel(path) for path in examples]],
        verification={
            "example_game_ids": [spec.game_id for spec in specs],
            "build_doc_has_edsl_command": "scripts/run_edsl_social_simulation.py" in docs_text,
            "build_doc_has_open_sae_run_dir": "--run-dir" in docs_text,
            "environment_doctor_present": exists("scripts/check_environment.py"),
        },
    )


def build_torrance_item() -> AuditItem:
    """Audit GPT-5 Torrance creativity eval outputs."""

    base = ROOT / "data/processed/creativity/torrance_gpt5_eval"
    evals = pd.read_csv(base / "torrance_gpt_evals.csv")
    summary = pd.read_csv(base / "torrance_eval_summary.csv")
    score_cols = ["fluency", "flexibility", "originality", "elaboration"]
    score_ok = all(evals[col].between(1, 10).all() for col in score_cols)
    mean_ok = (abs(evals["final_score"] - evals[score_cols].mean(axis=1)) < 1e-12).all()
    done = len(evals) == 320 and len(summary) == 8 and score_ok and mean_ok
    return AuditItem(
        id="creativity_torrance_gpt5",
        requirement="Creativity GPT judge evals use the Torrance-style four-score rubric.",
        status=status_from_bool(done),
        evidence=[
            "data/processed/creativity/torrance_gpt5_eval/torrance_gpt_evals.csv",
            "data/processed/creativity/torrance_gpt5_eval/torrance_eval_summary.csv",
        ],
        verification={
            "judged_rows": int(len(evals)),
            "summary_rows": int(len(summary)),
            "score_columns_integer_1_to_10": bool(score_ok),
            "final_score_is_dimension_mean": bool(mean_ok),
        },
    )


def build_open_sae_items() -> list[AuditItem]:
    """Audit completed post-hoc Open-SAE outputs."""

    specs = [
        (
            "creativity_open_sae",
            "Creativity saved responses have response-only Open-SAE features.",
            "data/processed/creativity/open_sae_response_only_frequency",
            {"activation_rows": 3200, "processed_response_task_units": 320, "condition_cells": 8},
        ),
        (
            "safe_risky_open_sae_calibration",
            "Safe-risk calibration saved responses have Open-SAE features and behavior checks.",
            "data/processed/games/safe_risky/open_sae_calibration",
            {
                "activation_rows": 42000,
                "processed_response_task_units": 4200,
                "condition_cells": 3,
                "reward_cells": 105,
            },
        ),
        (
            "ultimatum_open_sae",
            "Ultimatum saved responses have full Open-SAE replacement outputs.",
            "data/processed/games/ultimatum/open_sae_full",
            {
                "activation_rows": 20400,
                "processed_response_task_units": 2040,
                "condition_cells": 3,
                "reward_cells": 51,
            },
        ),
        (
            "trust_open_sae",
            "Trust-game saved responses have full Open-SAE replacement outputs.",
            "data/processed/games/trust/open_sae_full",
            {
                "activation_rows": 2000,
                "processed_response_task_units": 200,
                "condition_cells": 2,
                "reward_cells": 20,
            },
        ),
    ]
    items: list[AuditItem] = []
    for item_id, requirement, base, expected in specs:
        counts = open_sae_counts(base)
        done = (
            all(counts.get(key) == value for key, value in expected.items())
            and counts["special_or_control_token_topk_hits"] == 0
        )
        items.append(
            AuditItem(
                id=item_id,
                requirement=requirement,
                status=status_from_bool(done),
                evidence=[
                    f"{base}/open_sae_feature_activations.csv",
                    f"{base}/open_sae_condition_top_features.csv",
                    f"{base}/open_sae_metadata.json",
                ],
                verification={**counts, "expected": expected},
            )
        )
    return items


def build_source_audit_items() -> list[AuditItem]:
    """Audit saved-response source reconstruction fixtures."""

    safe_units = pd.read_csv(
        ROOT / "data/processed/games/safe_risky/source_audit_five_condition/open_sae_response_units.csv"
    )
    safe_behavior = pd.read_csv(
        ROOT / "data/processed/games/safe_risky/source_audit_five_condition/safe_risky_behavior_summary.csv"
    )
    safe_done = (
        len(safe_units) == 7000
        and safe_behavior.groupby(["condition", "reward"]).ngroups == 175
        and exists("runpod/run_safe_risky_five_condition_open_sae.sh")
    )
    safe_refresh_base = ROOT / "data/processed/games/safe_risky/open_sae_five_condition_full"
    safe_refresh_verification: dict[str, Any] = {}
    safe_refresh_done = False
    if safe_refresh_base.exists():
        safe_acts = pd.read_csv(safe_refresh_base / "open_sae_feature_activations.csv")
        safe_meta = json.loads(
            (safe_refresh_base / "open_sae_metadata.json").read_text(encoding="utf-8")
        )
        safe_reward_top = pd.read_csv(
            safe_refresh_base / "open_sae_condition_reward_top_features.csv"
        )
        safe_plots = sorted(path.name for path in safe_refresh_base.glob("*.png"))
        safe_refresh_verification = {
            "open_sae_processed_response_task_units": int(
                safe_meta.get("processed_response_task_units", -1)
            ),
            "open_sae_activation_rows": int(len(safe_acts)),
            "open_sae_expected_top_feature_rows": int(
                safe_meta.get("expected_top_feature_rows", -1)
            ),
            "open_sae_actual_top_feature_rows": int(safe_meta.get("actual_top_feature_rows", -1)),
            "open_sae_reward_cells": int(
                safe_reward_top.groupby(["task", "condition", "reward"]).ngroups
            ),
            "open_sae_special_or_control_token_topk_hits": int(
                safe_meta.get("special_or_control_token_topk_hits", -1)
            ),
            "open_sae_plots": safe_plots,
        }
        safe_refresh_done = (
            safe_refresh_verification["open_sae_processed_response_task_units"] == 7000
            and safe_refresh_verification["open_sae_activation_rows"] == 70000
            and safe_refresh_verification["open_sae_actual_top_feature_rows"] == 70000
            and safe_refresh_verification["open_sae_reward_cells"] == 175
            and safe_refresh_verification["open_sae_special_or_control_token_topk_hits"] == 0
            and all((safe_refresh_base / plot).stat().st_size > 0 for plot in safe_plots)
        )
    safe_item = AuditItem(
        id="safe_risky_five_condition_fixture",
        requirement=(
            "The paper five-condition safe-risk fixture is reconstructable; full "
            "Open-SAE feature refresh is available when GPU outputs are present."
        ),
        status=(
            "complete"
            if safe_done and safe_refresh_done
            else "source_audited_gpu_pending"
            if safe_done
            else "incomplete"
        ),
        evidence=[
            "data/processed/games/safe_risky/source_audit_five_condition/open_sae_response_units.csv",
            "data/processed/games/safe_risky/source_audit_five_condition/safe_risky_behavior_summary.csv",
            "data/processed/games/safe_risky/open_sae_five_condition_full/open_sae_feature_activations.csv",
            "data/processed/games/safe_risky/open_sae_five_condition_full/open_sae_metadata.json",
            "data/processed/games/safe_risky/open_sae_five_condition_full/open_sae_condition_reward_top_features.csv",
            "runpod/run_safe_risky_five_condition_open_sae.sh",
        ],
        verification={
            "source_units": int(len(safe_units)),
            "behavior_cells": int(safe_behavior.groupby(["condition", "reward"]).ngroups),
            "expected_open_sae_topk_rows_after_gpu_refresh": 70000,
            **safe_refresh_verification,
        },
        next_step=(
            "Run `bash ./runpod/run_safe_risky_five_condition_open_sae.sh` on an H100 "
            "to produce the optional 70,000-row five-condition Open-SAE feature refresh."
            if not safe_refresh_done
            else ""
        ),
    )

    ultimatum_units = pd.read_csv(
        ROOT / "data/processed/games/ultimatum/source_audit/open_sae_response_units.csv"
    )
    trust_units = pd.read_csv(ROOT / "data/processed/games/trust/source_audit/open_sae_response_units.csv")
    remaining_done = len(ultimatum_units) == 2040 and len(trust_units) == 200
    remaining_item = AuditItem(
        id="ultimatum_trust_source_audits",
        requirement="Ultimatum and trust archived source responses are reconstructable.",
        status=status_from_bool(remaining_done),
        evidence=[
            "data/processed/games/ultimatum/source_audit/open_sae_response_units.csv",
            "data/processed/games/trust/source_audit/open_sae_response_units.csv",
        ],
        verification={
            "ultimatum_source_units": int(len(ultimatum_units)),
            "trust_source_units": int(len(trust_units)),
        },
    )
    return [safe_item, remaining_item]


def build_label_item() -> AuditItem:
    """Audit cached Neuronpedia label bundle."""

    lookup = pd.read_csv(ROOT / "data/processed/feature_description_lookup.csv")
    counts = lookup.groupby("dataset_kind").size().to_dict()
    no_blank = not lookup["feature_label"].fillna("").str.strip().eq("").any()
    urls_ok = lookup["neuronpedia_api_url"].str.startswith(
        "https://www.neuronpedia.org/api/feature/"
    ).all()
    done = len(lookup) == 1920 and no_blank and urls_ok
    return AuditItem(
        id="feature_description_bundle",
        requirement=(
            "Top features for creativity, safe-risk/lottery, ultimatum, and trust "
            "have cached Neuronpedia descriptions keyed by stable feature_index."
        ),
        status=status_from_bool(done),
        evidence=[
            "data/processed/feature_description_lookup.csv",
            "reports/FEATURE_DESCRIPTION_SUMMARY.md",
            "docs/LABELS.md",
        ],
        verification={
            "rows": int(len(lookup)),
            "rows_by_dataset_kind": {key: int(value) for key, value in counts.items()},
            "no_blank_labels": bool(no_blank),
            "neuronpedia_urls_valid": bool(urls_ok),
        },
    )


def build_steering_item() -> AuditItem:
    """Audit saved Goodfire steering provenance and open steering implementation."""

    base = ROOT / "data/processed/creativity/steering_provenance"
    steering = pd.read_csv(base / "steering_features.csv")
    plan = json.loads(
        (base / "open_sae_steering_smoke_plan/open_sae_steering_smoke_plan.json").read_text(
            encoding="utf-8"
        )
    )
    metadata = pd.read_csv(base / "open_sae_steering_smoke_plan/open_sae_steering_feature_metadata.csv")
    runner = (ROOT / "scripts/run_open_sae_steering_generation.py").read_text(encoding="utf-8")
    done = (
        set(steering["feature_index"].astype(int)) == EXPECTED_STEERING_FEATURES
        and set(metadata["feature_index"].astype(int)) == EXPECTED_STEERING_FEATURES
        and plan.get("status") == "smoke_plan_only"
        and "register_forward_hook" in runner
        and "apply_sae_feature_edits" in runner
    )
    steering_output_base = ROOT / "runs/creativity_open_sae_steering_40agent"
    steering_output_verification: dict[str, Any] = {}
    steering_output_done = False
    if steering_output_base.exists():
        response_units = pd.read_csv(steering_output_base / "response_units.csv")
        steering_acts = pd.read_csv(
            steering_output_base / "open_sae/open_sae_feature_activations.csv"
        )
        steering_meta = json.loads(
            (steering_output_base / "open_sae/open_sae_metadata.json").read_text(
                encoding="utf-8"
            )
        )
        steering_plots = sorted(path.name for path in (steering_output_base / "open_sae").glob("*.png"))
        steering_output_verification = {
            "live_generated_response_units": int(len(response_units)),
            "live_open_sae_processed_response_task_units": int(
                steering_meta.get("processed_response_task_units", -1)
            ),
            "live_open_sae_activation_rows": int(len(steering_acts)),
            "live_open_sae_expected_top_feature_rows": int(
                steering_meta.get("expected_top_feature_rows", -1)
            ),
            "live_open_sae_actual_top_feature_rows": int(
                steering_meta.get("actual_top_feature_rows", -1)
            ),
            "live_open_sae_special_or_control_token_topk_hits": int(
                steering_meta.get("special_or_control_token_topk_hits", -1)
            ),
            "live_open_sae_plots": steering_plots,
        }
        steering_output_done = (
            steering_output_verification["live_generated_response_units"] == 80
            and steering_output_verification["live_open_sae_processed_response_task_units"] == 80
            and steering_output_verification["live_open_sae_activation_rows"] == 800
            and steering_output_verification["live_open_sae_actual_top_feature_rows"] == 800
            and steering_output_verification["live_open_sae_special_or_control_token_topk_hits"] == 0
            and all(
                (steering_output_base / "open_sae" / plot).stat().st_size > 0
                for plot in steering_plots
            )
        )
    return AuditItem(
        id="creativity_steering",
        requirement=(
            "Saved creativity steering provenance is extracted, and a transparent "
            "Open-SAE activation-patching generator exists for new GPU runs."
        ),
        status=(
            "complete"
            if done and steering_output_done
            else "implemented_gpu_pending"
            if done
            else "incomplete"
        ),
        evidence=[
            "data/processed/creativity/steering_provenance/steering_features.csv",
            "data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan/open_sae_steering_smoke_plan.json",
            "data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan/open_sae_steering_feature_metadata.csv",
            "runs/creativity_open_sae_steering_40agent/response_units.csv",
            "runs/creativity_open_sae_steering_40agent/open_sae/open_sae_feature_activations.csv",
            "runs/creativity_open_sae_steering_40agent/open_sae/open_sae_metadata.json",
            "scripts/run_open_sae_steering_generation.py",
            "runpod/run_creativity_open_sae_steering.sh",
        ],
        verification={
            "saved_goodfire_feature_indices": sorted(steering["feature_index"].astype(int).tolist()),
            "smoke_plan_status": plan.get("status"),
            "selected_prompt_units": int(plan.get("selected_prompt_units", -1)),
            "runner_has_forward_hook": "register_forward_hook" in runner,
            "runner_preserves_reconstruction_error": "reconstruction_error" in runner,
            **steering_output_verification,
        },
        next_step=(
            "Run `bash ./runpod/run_creativity_open_sae_steering.sh` on an H100 "
            "to validate live generation, then `RUN_FULL=1` for the full 80-unit "
            "high-steering prompt regeneration."
            if not steering_output_done
            else ""
        ),
    )


def build_live_game_steering_item() -> AuditItem:
    """Audit live Open-SAE steering generation for non-creativity games."""

    specs = [
        (
            "safe_risky_lite",
            "runs/safe_risky_open_sae_steering_lite_full",
            {"response_units": 1400, "activation_rows": 14000, "condition_cells": 1, "reward_cells": 35},
        ),
        (
            "safe_risky_strong",
            "runs/safe_risky_open_sae_steering_full",
            {"response_units": 1400, "activation_rows": 14000, "condition_cells": 1, "reward_cells": 35},
        ),
        (
            "ultimatum",
            "runs/ultimatum_open_sae_steering_full",
            {"response_units": 680, "activation_rows": 6800, "condition_cells": 1, "reward_cells": 17},
        ),
        (
            "trust",
            "runs/trust_open_sae_steering_full",
            {"response_units": 200, "activation_rows": 2000, "condition_cells": 2, "reward_cells": 20},
        ),
    ]
    verification: dict[str, Any] = {}
    done = True
    evidence = [
        "scripts/run_open_sae_steering_generation.py",
        "runpod/run_game_open_sae_steering.sh",
        "scripts/verify_live_steering_outputs.py",
    ]
    for name, run_dir, expected in specs:
        base = ROOT / run_dir
        response_units = pd.read_csv(base / "response_units.csv")
        activations = pd.read_csv(base / "open_sae/open_sae_feature_activations.csv")
        top = pd.read_csv(base / "open_sae/open_sae_condition_top_features.csv")
        reward_top = pd.read_csv(base / "open_sae/open_sae_condition_reward_top_features.csv")
        metadata = json.loads((base / "open_sae/open_sae_metadata.json").read_text(encoding="utf-8"))
        plots = sorted(path.name for path in (base / "open_sae").glob("*.png"))
        actual = {
            "response_units": int(len(response_units)),
            "processed_response_task_units": int(metadata.get("processed_response_task_units", -1)),
            "activation_rows": int(len(activations)),
            "expected_top_feature_rows": int(metadata.get("expected_top_feature_rows", -1)),
            "actual_top_feature_rows": int(metadata.get("actual_top_feature_rows", -1)),
            "condition_cells": int(top.groupby(["task", "condition"]).ngroups),
            "reward_cells": int(reward_top.groupby(["task", "condition", "reward"]).ngroups),
            "special_or_control_token_topk_hits": int(
                metadata.get("special_or_control_token_topk_hits", -1)
            ),
            "conditions": sorted(response_units["condition"].dropna().unique().tolist()),
            "plots": plots,
            "expected": expected,
        }
        verification[name] = actual
        done = done and (
            actual["response_units"] == expected["response_units"]
            and actual["processed_response_task_units"] == expected["response_units"]
            and actual["activation_rows"] == expected["activation_rows"]
            and actual["actual_top_feature_rows"] == expected["activation_rows"]
            and actual["condition_cells"] == expected["condition_cells"]
            and actual["reward_cells"] == expected["reward_cells"]
            and actual["special_or_control_token_topk_hits"] == 0
            and all((base / "open_sae" / plot).stat().st_size > 0 for plot in plots)
        )
        evidence.extend(
            [
                f"{run_dir}/response_units.csv",
                f"{run_dir}/open_sae/open_sae_feature_activations.csv",
                f"{run_dir}/open_sae/open_sae_metadata.json",
            ]
        )
    return AuditItem(
        id="live_game_steering",
        requirement=(
            "Safe-risk, ultimatum, and trust games have fresh live Open-SAE "
            "steered generations plus post-hoc Open-SAE inspections."
        ),
        status=status_from_bool(done),
        evidence=evidence,
        verification=verification,
    )


def build_dose_sweep_item() -> AuditItem:
    """Audit five-level dose-sensitive live Open-SAE steering sweeps."""

    base = ROOT / "runs/open_sae_dose_sweeps/summary"
    verification: dict[str, Any] = {}
    done = False
    if base.exists():
        index = pd.read_csv(base / "dose_sweep_run_index.csv")
        behavior = pd.read_csv(base / "dose_sweep_behavior_summary.csv")
        features = pd.read_csv(base / "dose_sweep_feature_summary.csv")
        metadata = json.loads((base / "dose_sweep_metadata.json").read_text(encoding="utf-8"))
        plots = sorted(path.name for path in base.glob("*.png"))
        by_dataset = {
            key: int(value) for key, value in index.groupby("dataset_kind")["response_units"].sum().items()
        }
        verification = {
            "dose_count": int(len(index)),
            "response_units": int(index["response_units"].sum()),
            "topk_rows": int(index["topk_rows"].sum()),
            "response_units_by_dataset": by_dataset,
            "behavior_rows": int(len(behavior)),
            "feature_summary_rows": int(len(features)),
            "plots": plots,
            "metadata_status": metadata.get("status"),
        }
        done = (
            verification["dose_count"] == 15
            and verification["response_units"] == 11400
            and verification["topk_rows"] == 114000
            and by_dataset == {"safe_risky": 7000, "trust": 1000, "ultimatum": 3400}
            and verification["metadata_status"] == "complete"
            and len(plots) >= 6
            and all((base / plot).stat().st_size > 0 for plot in plots)
        )
    return AuditItem(
        id="dose_sensitive_steering_sweeps",
        requirement=(
            "Safe-risk, ultimatum, and trust have five-level live Open-SAE "
            "dose-response steering sweeps with combined summaries and plots."
        ),
        status=status_from_bool(done),
        evidence=[
            "scripts/run_open_sae_dose_sweep.py",
            "scripts/verify_live_dose_sweep_outputs.py",
            "runpod/run_game_open_sae_dose_sweep.sh",
            "runs/open_sae_dose_sweeps/summary/dose_sweep_run_index.csv",
            "runs/open_sae_dose_sweeps/summary/dose_sweep_behavior_summary.csv",
            "runs/open_sae_dose_sweeps/summary/dose_sweep_feature_summary.csv",
        ],
        verification=verification,
        next_step=(
            "Run `RUN_FULL=1 bash ./runpod/run_game_open_sae_dose_sweep.sh` on an H100."
            if not done
            else ""
        ),
    )


def build_release_safety_item() -> AuditItem:
    """Audit public-release safety scaffolding."""

    done = (
        exists("tests/verify_no_secrets.py")
        and exists("tests/verify_release_anonymity.py")
        and exists(".env.example")
        and exists("DATA_MANIFEST.tsv")
        and exists("scripts/build_release_zip.py")
        and exists("README.md")
    )
    return AuditItem(
        id="release_safety",
        requirement=(
            "The repo has release hygiene checks, a manifest, a clean zip builder, "
            "and no checked-in secrets file."
        ),
        status=status_from_bool(done),
        evidence=[
            "tests/verify_no_secrets.py",
            "tests/verify_release_anonymity.py",
            ".env.example",
            "DATA_MANIFEST.tsv",
            "scripts/build_release_zip.py",
            "README.md",
        ],
        verification={
            "secret_scanner_present": exists("tests/verify_no_secrets.py"),
            "release_anonymity_scanner_present": exists("tests/verify_release_anonymity.py"),
            "env_example_present": exists(".env.example"),
            "data_manifest_present": exists("DATA_MANIFEST.tsv"),
            "release_zip_builder_present": exists("scripts/build_release_zip.py"),
        },
    )


def build_audit() -> dict[str, Any]:
    """Build the full audit payload."""

    items = [
        build_platform_item(),
        build_torrance_item(),
        *build_open_sae_items(),
        *build_source_audit_items(),
        build_label_item(),
        build_steering_item(),
        build_live_game_steering_item(),
        build_dose_sweep_item(),
        build_release_safety_item(),
    ]
    counts: dict[str, int] = {}
    for item in items:
        counts[item.status] = counts.get(item.status, 0) + 1
    return {
        "schema_version": 1,
        "repo": "social-sim-open-sae",
        "scope": (
            "Reusable EDSL social-simulation platform plus Goodfire Open-SAE "
            "inspection, labels, archived fixtures, and steering provenance."
        ),
        "status_counts": counts,
        "completion_status": (
            "release_ready"
            if set(counts) == {"complete"}
            else "release_ready_with_documented_gpu_extensions"
            if counts.get("incomplete", 0) == 0
            else "incomplete"
        ),
        "items": [asdict(item) for item in items],
    }


def write_markdown(audit: dict[str, Any], output: Path) -> None:
    """Write a human-readable audit report."""

    lines = [
        "# Release Completion Audit",
        "",
        f"Scope: {audit['scope']}",
        "",
        f"Overall status: `{audit['completion_status']}`",
        "",
        "Status counts:",
    ]
    for status, count in sorted(audit["status_counts"].items()):
        lines.append(f"- `{status}`: {count}")
    lines.extend(["", "## Requirements", ""])
    for item in audit["items"]:
        lines.append(f"### {item['id']}")
        lines.append("")
        lines.append(f"- Status: `{item['status']}`")
        lines.append(f"- Requirement: {item['requirement']}")
        if item.get("next_step"):
            lines.append(f"- Next step: {item['next_step']}")
        lines.append("- Evidence:")
        for evidence in item["evidence"]:
            lines.append(f"  - `{evidence}`")
        lines.append("- Verification:")
        lines.append("```json")
        lines.append(json.dumps(item["verification"], indent=2, sort_keys=True))
        lines.append("```")
        lines.append("")
    output.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-output", type=Path, default=AUDIT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=AUDIT_MD)
    parser.add_argument("--check", action="store_true")
    return parser.parse_args()


def main() -> None:
    """Build or check the release completion audit."""

    args = parse_args()
    audit = build_audit()
    if audit["status_counts"].get("incomplete", 0):
        raise AssertionError("Release audit has incomplete items")
    if args.check:
        expected_json = json.dumps(audit, indent=2, sort_keys=True) + "\n"
        expected_md_path = args.markdown_output
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            tmp_md = Path(tmp) / "audit.md"
            write_markdown(audit, tmp_md)
            expected_md = tmp_md.read_text(encoding="utf-8")
        actual_json = args.json_output.read_text(encoding="utf-8") if args.json_output.exists() else ""
        actual_md = expected_md_path.read_text(encoding="utf-8") if expected_md_path.exists() else ""
        if actual_json != expected_json:
            raise AssertionError(f"{rel(args.json_output)} is not current")
        if actual_md != expected_md:
            raise AssertionError(f"{rel(expected_md_path)} is not current")
        print("release completion audit check passed")
        return
    args.json_output.parent.mkdir(parents=True, exist_ok=True)
    args.json_output.write_text(json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    write_markdown(audit, args.markdown_output)
    print(f"wrote {rel(args.json_output)} and {rel(args.markdown_output)}")


if __name__ == "__main__":
    main()
