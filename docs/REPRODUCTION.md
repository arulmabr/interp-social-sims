# Reproduction Guide

## Platform Workflow For New EDSL Games

The preferred public workflow is to collect a new EDSL social-simulation run and
then inspect that run with Open-SAE:

```bash
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/safe_risky.py \
  --output-dir runs/safe_risky_demo \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --agents 40

python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/safe_risky_demo \
  --output-dir runs/safe_risky_demo/open_sae \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --load-in-4bit
```

The archived-output commands below remain as paper-replication fixtures.

## Local Non-GPU Checks

Check local prerequisites without installing packages or loading the model:

```bash
python scripts/check_environment.py
```

```bash
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/safe_risky.py \
  --output-dir /tmp/safe_risky_demo \
  --mock-model \
  --agents 2 \
  --conditions baseline \
  --limit-scenarios 1

python scripts/run_open_sae_feature_inspection.py \
  --run-dir /tmp/safe_risky_demo \
  --dry-run \
  --expected-units 2

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind creativity \
  --dry-run \
  --expected-units 320

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --dry-run \
  --expected-units 4200

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --source-dir data/raw/games/safe_risky/results_20251008_225522 \
  --dry-run \
  --expected-units 7000

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --dry-run \
  --expected-units 2040

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --dry-run \
  --expected-units 200

python scripts/build_feature_description_bundle.py --check
python scripts/extract_steering_provenance.py --check
python scripts/build_release_completion_audit.py --check
python scripts/build_data_manifest.py --check
python tests/verify_release_artifacts.py
```

## Cached Feature Description Bundle

This rebuilds the offline lookup that maps top Open-SAE feature indices to cached
Neuronpedia descriptions.

```bash
python scripts/build_feature_description_bundle.py --check
```

The main output is `data/processed/feature_description_lookup.csv`.

## Creativity Steering Provenance

This extracts the saved Goodfire controller features from the high-steering creativity
condition.

```bash
python scripts/extract_steering_provenance.py --check
```

The main output is `data/processed/creativity/steering_provenance/steering_features.csv`.

## Release Completion Audit

The release audit records which requirements are fully verified and which ones are
implemented but still need GPU execution.

```bash
python scripts/build_release_completion_audit.py --check
python scripts/build_data_manifest.py --check
```

Regenerate these artifacts after changing release files:

```bash
python scripts/build_release_completion_audit.py
python scripts/build_data_manifest.py
```

## Live Open-SAE Steering Generation

The historical creativity steering responses were already saved in
`high_steering.csv`. To generate new steered responses without the hosted Goodfire
API, use the live Open-SAE runner on a GPU pod.

Local smoke plan, no GPU:

```bash
python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --conditions high_steering \
  --smoke-mode \
  --limit-units 4 \
  --output-dir data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan
```

GPU generation smoke test:

```bash
python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --source-dir data/raw/creativity/product_innovation_20251102_202650 \
  --output-dir runs/creativity_open_sae_steering_smoke \
  --conditions high_steering \
  --feature-indices 13142,20117,4992 \
  --strengths 0.3,0.3,0.3 \
  --steering-mode clamp_min \
  --patch-scope last_token \
  --limit-units 4 \
  --max-new-tokens 256 \
  --load-in-4bit \
  --execute
```

Full archived creativity prompt regeneration:

```bash
python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --source-dir data/raw/creativity/product_innovation_20251102_202650 \
  --output-dir runs/creativity_open_sae_steering_40agent \
  --conditions high_steering \
  --feature-indices 13142,20117,4992 \
  --strengths 0.3,0.3,0.3 \
  --steering-mode clamp_min \
  --patch-scope last_token \
  --limit-units 80 \
  --expected-units 80 \
  --max-new-tokens 512 \
  --load-in-4bit \
  --execute
```

Then inspect the generated run:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/creativity_open_sae_steering_40agent \
  --output-dir runs/creativity_open_sae_steering_40agent/open_sae \
  --activation-scope assistant_response \
  --feature-aggregation frequency \
  --activation-threshold 0.1 \
  --top-k 10 \
  --load-in-4bit
```

This is a new open-source steering run. It should not be described as an exact
recreation of the deprecated hosted Goodfire controller calibration.

## GPT-5 Torrance Judge Rerun

Requires `OPENAI_API_KEY`.

```bash
python scripts/rerun_creativity_torrance_eval.py \
  --source-dir data/raw/creativity/product_innovation_20251102_202650 \
  --output-dir data/processed/creativity/torrance_gpt5_eval_rerun \
  --requested-model gpt-5 \
  --overwrite
```

## Creativity Open-SAE Rerun

Requires a GPU with enough memory for Llama 3.3 70B in 4-bit mode and a Hugging Face
token with access to Meta Llama 3.3 70B.

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind creativity \
  --activation-scope assistant_response \
  --feature-aggregation frequency \
  --activation-threshold 0.1 \
  --source-dir data/raw/creativity/product_innovation_20251102_202650 \
  --output-dir data/processed/creativity/open_sae_response_only_frequency_rerun \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --expected-units 320 \
  --load-in-4bit
```

## Safe-Risk Open-SAE Rerun

The verified Open-SAE calibration fixture uses the three-condition saved run:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --activation-scope all_content \
  --source-dir data/raw/games/safe_risky/results_20251018_205613 \
  --output-dir data/processed/games/safe_risky/open_sae_calibration_rerun \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --expected-units 4200 \
  --goodfire-log data/raw/games/safe_risky/results_20251018_205613/feature_activations.txt \
  --load-in-4bit
```

The paper Figure 6-style five-condition saved run is included as a source fixture.
This local audit reconstructs the 7,000 response units and saved behavior curve
without loading the model or SAE:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --audit-only \
  --source-dir data/raw/games/safe_risky/results_20251008_225522 \
  --output-dir data/processed/games/safe_risky/source_audit_five_condition_rerun \
  --expected-units 7000
```

To refresh Open-SAE features for all five conditions, run the same GPU path:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --activation-scope all_content \
  --source-dir data/raw/games/safe_risky/results_20251008_225522 \
  --output-dir data/processed/games/safe_risky/open_sae_five_condition_rerun \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --expected-units 7000 \
  --load-in-4bit
```

The RunPod helper wraps the same dry-run, 8-unit smoke, and optional full run:

```bash
bash ./runpod/run_safe_risky_five_condition_open_sae.sh
RUN_FULL=1 bash ./runpod/run_safe_risky_five_condition_open_sae.sh
```

## Ultimatum Source Audit

This does not load the model or SAE. It reconstructs the saved response units, parses
the old Goodfire log, and writes behavior summaries.

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --audit-only \
  --expected-units 2040 \
  --source-dir data/raw/games/ultimatum/results_20251008_201139 \
  --output-dir data/processed/games/ultimatum/source_audit_rerun \
  --goodfire-log data/raw/games/ultimatum/results_20251008_201139/feature_activations.txt
```

## Trust Source Audit

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --audit-only \
  --expected-units 200 \
  --source-dir data/raw/games/trust/results \
  --output-dir data/processed/games/trust/source_audit_rerun
```

## Ultimatum Open-SAE Rerun

On RunPod, the combined smoke/full script is:

```bash
bash ./runpod/run_remaining_games_open_sae.sh
```

The individual command is:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --activation-scope all_content \
  --source-dir data/raw/games/ultimatum/results_20251008_201139 \
  --output-dir data/processed/games/ultimatum/open_sae_rerun \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --expected-units 2040 \
  --goodfire-log data/raw/games/ultimatum/results_20251008_201139/feature_activations.txt \
  --load-in-4bit
```

## Trust Open-SAE Rerun

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --activation-scope all_content \
  --source-dir data/raw/games/trust/results \
  --output-dir data/processed/games/trust/open_sae_rerun \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --expected-units 200 \
  --load-in-4bit
```
