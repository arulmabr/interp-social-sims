#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root on a GPU machine with HF_TOKEN set.
# This script first regenerates the local smoke plan, then runs a tiny live
# steering generation job, inspects that generated run with Open-SAE, and
# optionally runs the full 40-agent/high-steering-prompt regeneration.

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN must be set for meta-llama/Llama-3.3-70B-Instruct access." >&2
  exit 1
fi

RUN_FULL="${RUN_FULL:-0}"
STEERING_FEATURES="${STEERING_FEATURES:-13142,20117,4992}"
STEERING_STRENGTHS="${STEERING_STRENGTHS:-0.3,0.3,0.3}"
STEERING_MODE="${STEERING_MODE:-clamp_min}"
PATCH_SCOPE="${PATCH_SCOPE:-last_token}"
SOURCE_DIR="${SOURCE_DIR:-data/raw/creativity/product_innovation_20251102_202650}"
SMOKE_DIR="${SMOKE_DIR:-runs/creativity_open_sae_steering_smoke}"
FULL_DIR="${FULL_DIR:-runs/creativity_open_sae_steering_40agent}"

COMMON_MODEL_ARGS=(
  --model-id meta-llama/Llama-3.3-70B-Instruct
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50
  --hook model.layers.50
  --load-in-4bit
)

COMMON_STEERING_ARGS=(
  --dataset-kind creativity
  --conditions high_steering
  --source-dir "$SOURCE_DIR"
  --feature-indices "$STEERING_FEATURES"
  --strengths "$STEERING_STRENGTHS"
  --steering-mode "$STEERING_MODE"
  --patch-scope "$PATCH_SCOPE"
  "${COMMON_MODEL_ARGS[@]}"
)

python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --conditions high_steering \
  --source-dir "$SOURCE_DIR" \
  --smoke-mode \
  --limit-units 4 \
  --expected-units 4 \
  --output-dir data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan \
  --feature-indices "$STEERING_FEATURES" \
  --strengths "$STEERING_STRENGTHS" \
  --steering-mode "$STEERING_MODE" \
  --patch-scope "$PATCH_SCOPE"

python scripts/run_open_sae_steering_generation.py \
  "${COMMON_STEERING_ARGS[@]}" \
  --output-dir "$SMOKE_DIR" \
  --limit-units 4 \
  --expected-units 4 \
  --max-new-tokens 256 \
  --progress \
  --execute

python scripts/run_open_sae_feature_inspection.py \
  --run-dir "$SMOKE_DIR" \
  --output-dir "$SMOKE_DIR/open_sae" \
  --activation-scope assistant_response \
  --feature-aggregation frequency \
  --activation-threshold 0.1 \
  --top-k 10 \
  --expected-units 4 \
  "${COMMON_MODEL_ARGS[@]}"

if [[ "$RUN_FULL" == "1" ]]; then
  python scripts/run_open_sae_steering_generation.py \
    "${COMMON_STEERING_ARGS[@]}" \
    --output-dir "$FULL_DIR" \
    --limit-units 80 \
    --expected-units 80 \
    --max-new-tokens 512 \
    --progress \
    --execute

  python scripts/run_open_sae_feature_inspection.py \
    --run-dir "$FULL_DIR" \
    --output-dir "$FULL_DIR/open_sae" \
    --activation-scope assistant_response \
    --feature-aggregation frequency \
    --activation-threshold 0.1 \
    --top-k 10 \
    --expected-units 80 \
    "${COMMON_MODEL_ARGS[@]}"
fi
