# Reproduction Guide

## Local Non-GPU Checks

```bash
python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind creativity \
  --dry-run \
  --expected-units 320

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --dry-run \
  --expected-units 4200

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --dry-run \
  --expected-units 2040

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --dry-run \
  --expected-units 200

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
condition. It does not regenerate steered responses.

```bash
python scripts/extract_steering_provenance.py --check
```

The main output is `data/processed/creativity/steering_provenance/steering_features.csv`.

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
