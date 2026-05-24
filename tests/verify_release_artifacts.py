#!/usr/bin/env python3
"""Lightweight checks for the public release artifact set."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_STEERING_FEATURES = {13142, 20117, 4992}
FEATURE_FALLBACK_RE = re.compile(r"^feature_\d+$")
PLATFORM_FILES = [
    "social_sim_open_sae/__init__.py",
    "social_sim_open_sae/game_spec.py",
    "social_sim_open_sae/edsl_adapter.py",
    "scripts/run_edsl_social_simulation.py",
    "examples/games/creativity.py",
    "examples/games/safe_risky.py",
    "examples/games/ultimatum.py",
    "examples/games/trust.py",
    "docs/BUILD_A_GAME.md",
    "tests/verify_platform_smoke.py",
]


def require(path: str) -> Path:
    full = ROOT / path
    if not full.exists():
        raise AssertionError(f"Missing required artifact: {path}")
    return full


def require_nonempty(path: str) -> Path:
    full = require(path)
    if full.stat().st_size <= 0:
        raise AssertionError(f"Artifact is empty: {path}")
    return full


def check_open_sae_output(
    *,
    base: str,
    expected_rows: int,
    expected_units: int,
    expected_condition_cells: int,
    expected_reward_cells: int | None,
    condition_keys: list[str],
    reward_keys: list[str] | None = None,
    plots: list[str] | None = None,
) -> None:
    acts = pd.read_csv(require(f"{base}/open_sae_feature_activations.csv"))
    top = pd.read_csv(require(f"{base}/open_sae_condition_top_features.csv"))
    meta = json.loads(require(f"{base}/open_sae_metadata.json").read_text())
    if len(acts) != expected_rows:
        raise AssertionError(f"Expected {expected_rows:,} Open-SAE rows in {base}, found {len(acts):,}")
    if meta.get("processed_response_task_units") != expected_units:
        raise AssertionError(f"Open-SAE unit count mismatch in {base}")
    if meta.get("special_or_control_token_topk_hits") != 0:
        raise AssertionError(f"Open-SAE has special/control-token top-k hits in {base}")
    if top.groupby(condition_keys).ngroups != expected_condition_cells:
        raise AssertionError(f"Open-SAE condition-cell count mismatch in {base}")
    if expected_reward_cells is not None:
        reward_top = pd.read_csv(require(f"{base}/open_sae_condition_reward_top_features.csv"))
        if reward_keys is None:
            raise AssertionError("reward_keys must be provided when expected_reward_cells is set")
        if reward_top.groupby(reward_keys).ngroups != expected_reward_cells:
            raise AssertionError(f"Open-SAE reward-cell count mismatch in {base}")
    for plot in plots or []:
        require_nonempty(f"{base}/{plot}")


def check_creativity_torrance() -> None:
    evals = pd.read_csv(require("data/processed/creativity/torrance_gpt5_eval/torrance_gpt_evals.csv"))
    summary = pd.read_csv(require("data/processed/creativity/torrance_gpt5_eval/torrance_eval_summary.csv"))
    if len(evals) != 320:
        raise AssertionError(f"Expected 320 Torrance rows, found {len(evals)}")
    if len(summary) != 8:
        raise AssertionError(f"Expected 8 Torrance summary rows, found {len(summary)}")
    score_cols = ["fluency", "flexibility", "originality", "elaboration"]
    for col in score_cols:
        if not evals[col].between(1, 10).all():
            raise AssertionError(f"Score column out of range: {col}")
    expected = evals[score_cols].mean(axis=1)
    if not (abs(evals["final_score"] - expected) < 1e-12).all():
        raise AssertionError("final_score is not the mean of the four Torrance dimensions")


def check_creativity_open_sae() -> None:
    base = "data/processed/creativity/open_sae_response_only_frequency"
    check_open_sae_output(
        base=base,
        expected_rows=3200,
        expected_units=320,
        expected_condition_cells=8,
        expected_reward_cells=None,
        condition_keys=["task", "condition"],
        plots=[
            "open_sae_figure4_replacement_top_features.png",
            "open_sae_per_response_top_activation_diagnostics.png",
        ],
    )


def check_safe_risky() -> None:
    base = "data/processed/games/safe_risky/open_sae_calibration"
    check_open_sae_output(
        base=base,
        expected_rows=42000,
        expected_units=4200,
        expected_condition_cells=3,
        expected_reward_cells=105,
        condition_keys=["task", "condition"],
        reward_keys=["task", "condition", "reward"],
        plots=[
            "safe_risky_open_sae_top_feature_by_reward.png",
            "open_sae_per_response_top_activation_diagnostics.png",
            "open_sae_goodfire_label_overlap_diagnostics.png",
            "safe_risky_choice_rates_from_saved_outputs.png",
        ],
    )
    behavior = pd.read_csv(require(f"{base}/safe_risky_behavior_summary.csv"))
    if len(behavior) != 105:
        raise AssertionError(f"Expected 105 safe-risk behavior rows, found {len(behavior)}")
    if int(behavior["comment_nonempty_count"].sum()) != int(behavior["total_responses"].sum()):
        raise AssertionError("Safe-risk comments are not complete")


def check_remaining_game_source_audits() -> None:
    ultimatum = "data/processed/games/ultimatum/source_audit"
    ultimatum_units = pd.read_csv(require(f"{ultimatum}/open_sae_response_units.csv"))
    ultimatum_behavior = pd.read_csv(require(f"{ultimatum}/ultimatum_behavior_summary.csv"))
    ultimatum_goodfire = pd.read_csv(require(f"{ultimatum}/goodfire_api_feature_activations_parsed.csv"))
    ultimatum_meta = json.loads(require(f"{ultimatum}/open_sae_metadata.json").read_text())
    if len(ultimatum_units) != 2040:
        raise AssertionError(f"Expected 2,040 ultimatum response units, found {len(ultimatum_units)}")
    if len(ultimatum_behavior) != 51:
        raise AssertionError(f"Expected 51 ultimatum behavior rows, found {len(ultimatum_behavior)}")
    if len(ultimatum_goodfire) <= 0:
        raise AssertionError("Expected parsed old Goodfire ultimatum rows")
    if ultimatum_meta.get("processed_response_task_units") != 2040:
        raise AssertionError("Ultimatum source-audit unit count mismatch")
    require_nonempty(f"{ultimatum}/ultimatum_acceptance_rates_from_saved_outputs.png")

    trust = "data/processed/games/trust/source_audit"
    trust_units = pd.read_csv(require(f"{trust}/open_sae_response_units.csv"))
    trust_behavior = pd.read_csv(require(f"{trust}/trust_behavior_summary.csv"))
    trust_meta = json.loads(require(f"{trust}/open_sae_metadata.json").read_text())
    if len(trust_units) != 200:
        raise AssertionError(f"Expected 200 trust response units, found {len(trust_units)}")
    if len(trust_behavior) != 20:
        raise AssertionError(f"Expected 20 trust behavior rows, found {len(trust_behavior)}")
    if trust_meta.get("processed_response_task_units") != 200:
        raise AssertionError("Trust source-audit unit count mismatch")
    require_nonempty(f"{trust}/trust_mean_returns_from_saved_outputs.png")


def check_remaining_game_open_sae() -> None:
    ultimatum = "data/processed/games/ultimatum/open_sae_full"
    check_open_sae_output(
        base=ultimatum,
        expected_rows=20400,
        expected_units=2040,
        expected_condition_cells=3,
        expected_reward_cells=51,
        condition_keys=["task", "condition"],
        reward_keys=["task", "condition", "reward"],
        plots=[
            "ultimatum_open_sae_top_features_by_condition.png",
            "open_sae_per_response_top_activation_diagnostics.png",
            "open_sae_goodfire_label_overlap_diagnostics.png",
            "ultimatum_acceptance_rates_from_saved_outputs.png",
        ],
    )
    ultimatum_behavior = pd.read_csv(require(f"{ultimatum}/ultimatum_behavior_summary.csv"))
    ultimatum_goodfire = pd.read_csv(require(f"{ultimatum}/goodfire_api_feature_activations_parsed.csv"))
    if len(ultimatum_behavior) != 51:
        raise AssertionError(f"Expected 51 ultimatum behavior rows, found {len(ultimatum_behavior)}")
    if len(ultimatum_goodfire) <= 0:
        raise AssertionError("Expected parsed old Goodfire ultimatum rows")

    trust = "data/processed/games/trust/open_sae_full"
    check_open_sae_output(
        base=trust,
        expected_rows=2000,
        expected_units=200,
        expected_condition_cells=2,
        expected_reward_cells=20,
        condition_keys=["task", "condition"],
        reward_keys=["task", "condition", "reward"],
        plots=[
            "trust_open_sae_top_features_by_condition.png",
            "open_sae_per_response_top_activation_diagnostics.png",
            "trust_mean_returns_from_saved_outputs.png",
        ],
    )
    trust_behavior = pd.read_csv(require(f"{trust}/trust_behavior_summary.csv"))
    if len(trust_behavior) != 20:
        raise AssertionError(f"Expected 20 trust behavior rows, found {len(trust_behavior)}")


def check_feature_description_lookup() -> None:
    lookup = pd.read_csv(require("data/processed/feature_description_lookup.csv"))
    require_nonempty("reports/FEATURE_DESCRIPTION_SUMMARY.md")
    require_nonempty("docs/LABELS.md")
    if len(lookup) != 1920:
        raise AssertionError(f"Expected 1,920 feature-description rows, found {len(lookup)}")
    counts = lookup.groupby("dataset_kind").size().to_dict()
    expected_counts = {
        "creativity": 80,
        "safe_risky": 1080,
        "ultimatum": 540,
        "trust": 220,
    }
    if counts != expected_counts:
        raise AssertionError(f"Unexpected feature-description counts: {counts}")
    if lookup["feature_label"].fillna("").str.strip().eq("").any():
        raise AssertionError("Feature-description lookup contains empty labels")
    if lookup["feature_label"].fillna("").str.match(FEATURE_FALLBACK_RE).any():
        raise AssertionError("Feature-description lookup contains feature-index fallback labels")
    if not lookup["neuronpedia_api_url"].str.startswith(
        "https://www.neuronpedia.org/api/feature/"
    ).all():
        raise AssertionError("Feature-description lookup contains invalid Neuronpedia URLs")
    if set(lookup["label_source"]) != {"cached_neuronpedia"}:
        raise AssertionError("Feature-description lookup should use cached Neuronpedia labels")


def check_steering_provenance() -> None:
    base = "data/processed/creativity/steering_provenance"
    steering = pd.read_csv(require(f"{base}/steering_features.csv"))
    require_nonempty(f"{base}/STEERING_PROVENANCE.md")
    require_nonempty(f"{base}/open_sae_steering_smoke_plan/open_sae_steering_smoke_plan.json")
    require_nonempty(f"{base}/open_sae_steering_smoke_plan/open_sae_steering_smoke_units.csv")
    require_nonempty("docs/STEERING.md")
    require_nonempty("reports/slack_drafts/gaveal_label_steering_reply.md")
    found = set(steering["feature_index"].astype(int))
    if found != EXPECTED_STEERING_FEATURES:
        raise AssertionError(f"Unexpected steering features: {sorted(found)}")
    if steering["old_goodfire_label"].fillna("").str.strip().eq("").any():
        raise AssertionError("Steering provenance contains empty Goodfire labels")
    if not (steering["nudge_value"].astype(float) > 0).all():
        raise AssertionError("Steering provenance contains nonpositive nudge values")
    if set(steering["source_model"]) != {"meta-llama/Llama-3.3-70B-Instruct"}:
        raise AssertionError("Steering provenance source model mismatch")
    plan = json.loads(
        require(f"{base}/open_sae_steering_smoke_plan/open_sae_steering_smoke_plan.json").read_text()
    )
    if plan.get("status") != "smoke_plan_only":
        raise AssertionError("Steering smoke plan status mismatch")
    if set(plan.get("feature_indices", [])) != EXPECTED_STEERING_FEATURES:
        raise AssertionError("Steering smoke plan feature indices mismatch")


def check_platform_layer() -> None:
    for path in PLATFORM_FILES:
        require_nonempty(path)
    readme = require("README.md").read_text(encoding="utf-8")
    if "building EDSL social simulations" not in readme:
        raise AssertionError("README should foreground the EDSL platform workflow")
    build_doc = require("docs/BUILD_A_GAME.md").read_text(encoding="utf-8")
    if "scripts/run_edsl_social_simulation.py" not in build_doc:
        raise AssertionError("BUILD_A_GAME.md is missing the EDSL runner command")
    if "--run-dir" not in build_doc:
        raise AssertionError("BUILD_A_GAME.md is missing the Open-SAE run-dir path")


def main() -> None:
    check_platform_layer()
    check_creativity_torrance()
    check_creativity_open_sae()
    check_safe_risky()
    check_remaining_game_source_audits()
    check_remaining_game_open_sae()
    check_feature_description_lookup()
    check_steering_provenance()
    print("release artifact verification passed")


if __name__ == "__main__":
    main()
