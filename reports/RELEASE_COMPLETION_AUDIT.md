# Release Completion Audit

Scope: Reusable EDSL social-simulation platform plus Goodfire Open-SAE inspection, labels, archived fixtures, and steering provenance.

Overall status: `release_ready`

Status counts:
- `complete`: 11

## Requirements

### platform_new_games

- Status: `complete`
- Requirement: Users can define EDSL games, collect normalized response units, and run Open-SAE inspection through the platform interface.
- Evidence:
  - `social_sim_open_sae/game_spec.py`
  - `social_sim_open_sae/edsl_adapter.py`
  - `scripts/run_edsl_social_simulation.py`
  - `scripts/check_environment.py`
  - `scripts/run_open_sae_feature_inspection.py`
  - `docs/BUILD_A_GAME.md`
  - `examples/games/creativity.py`
  - `examples/games/safe_risky.py`
  - `examples/games/trust.py`
  - `examples/games/ultimatum.py`
- Verification:
```json
{
  "build_doc_has_edsl_command": true,
  "build_doc_has_open_sae_run_dir": true,
  "environment_doctor_present": true,
  "example_game_ids": [
    "creativity",
    "safe_risky",
    "trust",
    "ultimatum"
  ]
}
```

### creativity_torrance_gpt5

- Status: `complete`
- Requirement: Creativity GPT judge evals use the Torrance-style four-score rubric.
- Evidence:
  - `data/processed/creativity/torrance_gpt5_eval/torrance_gpt_evals.csv`
  - `data/processed/creativity/torrance_gpt5_eval/torrance_eval_summary.csv`
- Verification:
```json
{
  "final_score_is_dimension_mean": true,
  "judged_rows": 320,
  "score_columns_integer_1_to_10": true,
  "summary_rows": 8
}
```

### creativity_open_sae

- Status: `complete`
- Requirement: Creativity saved responses have response-only Open-SAE features.
- Evidence:
  - `data/processed/creativity/open_sae_response_only_frequency/open_sae_feature_activations.csv`
  - `data/processed/creativity/open_sae_response_only_frequency/open_sae_condition_top_features.csv`
  - `data/processed/creativity/open_sae_response_only_frequency/open_sae_metadata.json`
- Verification:
```json
{
  "activation_rows": 3200,
  "condition_cells": 8,
  "expected": {
    "activation_rows": 3200,
    "condition_cells": 8,
    "processed_response_task_units": 320
  },
  "processed_response_task_units": 320,
  "special_or_control_token_topk_hits": 0,
  "top_k": 10
}
```

### safe_risky_open_sae_calibration

- Status: `complete`
- Requirement: Safe-risk calibration saved responses have Open-SAE features and behavior checks.
- Evidence:
  - `data/processed/games/safe_risky/open_sae_calibration/open_sae_feature_activations.csv`
  - `data/processed/games/safe_risky/open_sae_calibration/open_sae_condition_top_features.csv`
  - `data/processed/games/safe_risky/open_sae_calibration/open_sae_metadata.json`
- Verification:
```json
{
  "activation_rows": 42000,
  "condition_cells": 3,
  "expected": {
    "activation_rows": 42000,
    "condition_cells": 3,
    "processed_response_task_units": 4200,
    "reward_cells": 105
  },
  "processed_response_task_units": 4200,
  "reward_cells": 105,
  "special_or_control_token_topk_hits": 0,
  "top_k": 10
}
```

### ultimatum_open_sae

- Status: `complete`
- Requirement: Ultimatum saved responses have full Open-SAE replacement outputs.
- Evidence:
  - `data/processed/games/ultimatum/open_sae_full/open_sae_feature_activations.csv`
  - `data/processed/games/ultimatum/open_sae_full/open_sae_condition_top_features.csv`
  - `data/processed/games/ultimatum/open_sae_full/open_sae_metadata.json`
- Verification:
```json
{
  "activation_rows": 20400,
  "condition_cells": 3,
  "expected": {
    "activation_rows": 20400,
    "condition_cells": 3,
    "processed_response_task_units": 2040,
    "reward_cells": 51
  },
  "processed_response_task_units": 2040,
  "reward_cells": 51,
  "special_or_control_token_topk_hits": 0,
  "top_k": 10
}
```

### trust_open_sae

- Status: `complete`
- Requirement: Trust-game saved responses have full Open-SAE replacement outputs.
- Evidence:
  - `data/processed/games/trust/open_sae_full/open_sae_feature_activations.csv`
  - `data/processed/games/trust/open_sae_full/open_sae_condition_top_features.csv`
  - `data/processed/games/trust/open_sae_full/open_sae_metadata.json`
- Verification:
```json
{
  "activation_rows": 2000,
  "condition_cells": 2,
  "expected": {
    "activation_rows": 2000,
    "condition_cells": 2,
    "processed_response_task_units": 200,
    "reward_cells": 20
  },
  "processed_response_task_units": 200,
  "reward_cells": 20,
  "special_or_control_token_topk_hits": 0,
  "top_k": 10
}
```

### safe_risky_five_condition_fixture

- Status: `complete`
- Requirement: The paper five-condition safe-risk fixture is reconstructable; full Open-SAE feature refresh is available when GPU outputs are present.
- Evidence:
  - `data/processed/games/safe_risky/source_audit_five_condition/open_sae_response_units.csv`
  - `data/processed/games/safe_risky/source_audit_five_condition/safe_risky_behavior_summary.csv`
  - `data/processed/games/safe_risky/open_sae_five_condition_full/open_sae_feature_activations.csv`
  - `data/processed/games/safe_risky/open_sae_five_condition_full/open_sae_metadata.json`
  - `data/processed/games/safe_risky/open_sae_five_condition_full/open_sae_condition_reward_top_features.csv`
  - `runpod/run_safe_risky_five_condition_open_sae.sh`
- Verification:
```json
{
  "behavior_cells": 175,
  "expected_open_sae_topk_rows_after_gpu_refresh": 70000,
  "open_sae_activation_rows": 70000,
  "open_sae_actual_top_feature_rows": 70000,
  "open_sae_expected_top_feature_rows": 70000,
  "open_sae_plots": [
    "open_sae_per_response_top_activation_diagnostics.png",
    "safe_risky_choice_rates_from_saved_outputs.png",
    "safe_risky_open_sae_top_feature_by_reward.png"
  ],
  "open_sae_processed_response_task_units": 7000,
  "open_sae_reward_cells": 175,
  "open_sae_special_or_control_token_topk_hits": 0,
  "source_units": 7000
}
```

### ultimatum_trust_source_audits

- Status: `complete`
- Requirement: Ultimatum and trust archived source responses are reconstructable.
- Evidence:
  - `data/processed/games/ultimatum/source_audit/open_sae_response_units.csv`
  - `data/processed/games/trust/source_audit/open_sae_response_units.csv`
- Verification:
```json
{
  "trust_source_units": 200,
  "ultimatum_source_units": 2040
}
```

### feature_description_bundle

- Status: `complete`
- Requirement: Top features for creativity, safe-risk/lottery, ultimatum, and trust have cached Neuronpedia descriptions keyed by stable feature_index.
- Evidence:
  - `data/processed/feature_description_lookup.csv`
  - `reports/FEATURE_DESCRIPTION_SUMMARY.md`
  - `docs/LABELS.md`
- Verification:
```json
{
  "neuronpedia_urls_valid": true,
  "no_blank_labels": true,
  "rows": 1920,
  "rows_by_dataset_kind": {
    "creativity": 80,
    "safe_risky": 1080,
    "trust": 220,
    "ultimatum": 540
  }
}
```

### creativity_steering

- Status: `complete`
- Requirement: Saved creativity steering provenance is extracted, and a transparent Open-SAE activation-patching generator exists for new GPU runs.
- Evidence:
  - `data/processed/creativity/steering_provenance/steering_features.csv`
  - `data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan/open_sae_steering_smoke_plan.json`
  - `data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan/open_sae_steering_feature_metadata.csv`
  - `runs/creativity_open_sae_steering_40agent/response_units.csv`
  - `runs/creativity_open_sae_steering_40agent/open_sae/open_sae_feature_activations.csv`
  - `runs/creativity_open_sae_steering_40agent/open_sae/open_sae_metadata.json`
  - `scripts/run_open_sae_steering_generation.py`
  - `runpod/run_creativity_open_sae_steering.sh`
- Verification:
```json
{
  "live_generated_response_units": 80,
  "live_open_sae_activation_rows": 800,
  "live_open_sae_actual_top_feature_rows": 800,
  "live_open_sae_expected_top_feature_rows": 800,
  "live_open_sae_plots": [
    "open_sae_figure4_replacement_top_features.png",
    "open_sae_per_response_top_activation_diagnostics.png"
  ],
  "live_open_sae_processed_response_task_units": 80,
  "live_open_sae_special_or_control_token_topk_hits": 0,
  "runner_has_forward_hook": true,
  "runner_preserves_reconstruction_error": true,
  "saved_goodfire_feature_indices": [
    4992,
    13142,
    20117
  ],
  "selected_prompt_units": 4,
  "smoke_plan_status": "smoke_plan_only"
}
```

### release_safety

- Status: `complete`
- Requirement: The repo has release hygiene checks, a manifest, a clean zip builder, and no checked-in secrets file.
- Evidence:
  - `tests/verify_no_secrets.py`
  - `tests/verify_release_anonymity.py`
  - `.env.example`
  - `DATA_MANIFEST.tsv`
  - `scripts/build_release_zip.py`
  - `README.md`
- Verification:
```json
{
  "data_manifest_present": true,
  "env_example_present": true,
  "release_anonymity_scanner_present": true,
  "release_zip_builder_present": true,
  "secret_scanner_present": true
}
```
