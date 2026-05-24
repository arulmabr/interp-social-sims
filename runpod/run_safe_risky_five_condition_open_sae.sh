#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root on a GPU machine with HF_TOKEN set.
# This is the optional full Open-SAE refresh for the paper Figure 6-style
# five-condition safe-risk fixture.

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN must be set for meta-llama/Llama-3.3-70B-Instruct access." >&2
  exit 1
fi

SOURCE_DIR="${SOURCE_DIR:-data/raw/games/safe_risky/results_20251008_225522}"
SMOKE_DIR="${SMOKE_DIR:-runs/safe_risky_five_condition_open_sae_smoke}"
FULL_DIR="${FULL_DIR:-data/processed/games/safe_risky/open_sae_five_condition_full}"
RUN_FULL="${RUN_FULL:-0}"

COMMON_ARGS=(
  --dataset-kind safe_risky
  --source-dir "$SOURCE_DIR"
  --model-id meta-llama/Llama-3.3-70B-Instruct
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50
  --hook model.layers.50
  --activation-scope all_content
  --feature-aggregation max
  --top-k 10
  --load-in-4bit
)

python scripts/run_open_sae_feature_inspection.py \
  "${COMMON_ARGS[@]}" \
  --dry-run \
  --expected-units 7000

python scripts/run_open_sae_feature_inspection.py \
  "${COMMON_ARGS[@]}" \
  --limit-units 8 \
  --expected-units 8 \
  --output-dir "$SMOKE_DIR"

if [[ "$RUN_FULL" == "1" ]]; then
  python scripts/run_open_sae_feature_inspection.py \
    "${COMMON_ARGS[@]}" \
    --expected-units 7000 \
    --output-dir "$FULL_DIR"
fi
