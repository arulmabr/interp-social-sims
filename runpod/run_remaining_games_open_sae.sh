#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root on a GPU machine with HF_TOKEN set.

COMMON_ARGS=(
  --model-id meta-llama/Llama-3.3-70B-Instruct
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50
  --hook model.layers.50
  --activation-scope all_content
  --top-k 10
  --load-in-4bit
)

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --dry-run \
  --expected-units 2040

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --dry-run \
  --expected-units 200

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --limit-units 8 \
  --expected-units 8 \
  --source-dir data/raw/games/ultimatum/results_20251008_201139 \
  --output-dir data/processed/games/ultimatum/open_sae_smoke \
  --goodfire-log data/raw/games/ultimatum/results_20251008_201139/feature_activations.txt \
  "${COMMON_ARGS[@]}"

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --limit-units 8 \
  --expected-units 8 \
  --source-dir data/raw/games/trust/results \
  --output-dir data/processed/games/trust/open_sae_smoke \
  "${COMMON_ARGS[@]}"

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --expected-units 2040 \
  --source-dir data/raw/games/ultimatum/results_20251008_201139 \
  --output-dir data/processed/games/ultimatum/open_sae_full \
  --goodfire-log data/raw/games/ultimatum/results_20251008_201139/feature_activations.txt \
  "${COMMON_ARGS[@]}"

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --expected-units 200 \
  --source-dir data/raw/games/trust/results \
  --output-dir data/processed/games/trust/open_sae_full \
  "${COMMON_ARGS[@]}"
