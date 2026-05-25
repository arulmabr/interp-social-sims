#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root on a GPU machine with HF_TOKEN set.
# This regenerates the paper game steering conditions with the open-source
# Goodfire SAE instead of Goodfire's deprecated hosted controller API, then runs
# post-hoc Open-SAE inspection over the generated responses.

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN must be set for meta-llama/Llama-3.3-70B-Instruct access." >&2
  exit 1
fi

RUN_FULL="${RUN_FULL:-0}"
STEERING_MODE="${STEERING_MODE:-clamp_min}"
PATCH_SCOPE="${PATCH_SCOPE:-last_token}"
MAX_NEW_TOKENS="${MAX_NEW_TOKENS:-256}"

SAFE_RISKY_SOURCE_DIR="${SAFE_RISKY_SOURCE_DIR:-data/raw/games/safe_risky/results_20251008_225522}"
ULTIMATUM_SOURCE_DIR="${ULTIMATUM_SOURCE_DIR:-data/raw/games/ultimatum/results_20251008_201139}"
TRUST_SOURCE_DIR="${TRUST_SOURCE_DIR:-data/raw/games/trust/results}"

COMMON_MODEL_ARGS=(
  --model-id meta-llama/Llama-3.3-70B-Instruct
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50
  --hook model.layers.50
  --load-in-4bit
)

run_steering_job() {
  local dataset_kind="$1"
  local source_dir="$2"
  local conditions="$3"
  local rewards="$4"
  local features="$5"
  local strengths="$6"
  local smoke_units="$7"
  local full_units="$8"
  local smoke_dir="$9"
  local full_dir="${10}"

  python scripts/run_open_sae_steering_generation.py \
    --dataset-kind "$dataset_kind" \
    --source-dir "$source_dir" \
    --conditions "$conditions" \
    --rewards "$rewards" \
    --feature-indices "$features" \
    --strengths "$strengths" \
    --steering-mode "$STEERING_MODE" \
    --patch-scope "$PATCH_SCOPE" \
    --smoke-mode \
    --limit-units "$smoke_units" \
    --expected-units "$smoke_units" \
    --output-dir "$smoke_dir/smoke_plan"

  python scripts/run_open_sae_steering_generation.py \
    --dataset-kind "$dataset_kind" \
    --source-dir "$source_dir" \
    --conditions "$conditions" \
    --rewards "$rewards" \
    --feature-indices "$features" \
    --strengths "$strengths" \
    --steering-mode "$STEERING_MODE" \
    --patch-scope "$PATCH_SCOPE" \
    --output-dir "$smoke_dir" \
    --limit-units "$smoke_units" \
    --expected-units "$smoke_units" \
    --max-new-tokens "$MAX_NEW_TOKENS" \
    --progress \
    --execute \
    "${COMMON_MODEL_ARGS[@]}"

  python scripts/run_open_sae_feature_inspection.py \
    --run-dir "$smoke_dir" \
    --output-dir "$smoke_dir/open_sae" \
    --activation-scope all_content \
    --feature-aggregation max \
    --activation-threshold 0.1 \
    --top-k 10 \
    --expected-units "$smoke_units" \
    "${COMMON_MODEL_ARGS[@]}"

  if [[ "$RUN_FULL" == "1" ]]; then
    python scripts/run_open_sae_steering_generation.py \
      --dataset-kind "$dataset_kind" \
      --source-dir "$source_dir" \
      --conditions "$conditions" \
      --rewards "$rewards" \
      --feature-indices "$features" \
      --strengths "$strengths" \
      --steering-mode "$STEERING_MODE" \
      --patch-scope "$PATCH_SCOPE" \
      --output-dir "$full_dir" \
      --limit-units "$full_units" \
      --expected-units "$full_units" \
      --max-new-tokens "$MAX_NEW_TOKENS" \
      --progress \
      --execute \
      "${COMMON_MODEL_ARGS[@]}"

    python scripts/run_open_sae_feature_inspection.py \
      --run-dir "$full_dir" \
      --output-dir "$full_dir/open_sae" \
      --activation-scope all_content \
      --feature-aggregation max \
      --activation-threshold 0.1 \
      --top-k 10 \
      --expected-units "$full_units" \
      "${COMMON_MODEL_ARGS[@]}"
  fi
}

run_steering_job \
  safe_risky \
  "$SAFE_RISKY_SOURCE_DIR" \
  lite_steering \
  "" \
  184,4237 \
  0.6,0.4 \
  8 \
  1400 \
  runs/safe_risky_open_sae_steering_lite_smoke \
  runs/safe_risky_open_sae_steering_lite_full

run_steering_job \
  safe_risky \
  "$SAFE_RISKY_SOURCE_DIR" \
  steering \
  "" \
  184,4237 \
  0.7,0.5 \
  8 \
  1400 \
  runs/safe_risky_open_sae_steering_full_smoke \
  runs/safe_risky_open_sae_steering_full

run_steering_job \
  ultimatum \
  "$ULTIMATUM_SOURCE_DIR" \
  steering \
  "" \
  31935 \
  0.5 \
  8 \
  680 \
  runs/ultimatum_open_sae_steering_smoke \
  runs/ultimatum_open_sae_steering_full

run_steering_job \
  trust \
  "$TRUST_SOURCE_DIR" \
  baseline,intervention \
  "" \
  38558,11444,17623,39359 \
  0.4,0.4,0.3,0.3 \
  8 \
  200 \
  runs/trust_open_sae_steering_smoke \
  runs/trust_open_sae_steering_full

python scripts/verify_live_steering_outputs.py --scope smoke

if [[ "$RUN_FULL" == "1" ]]; then
  python scripts/verify_live_steering_outputs.py --scope full
fi
