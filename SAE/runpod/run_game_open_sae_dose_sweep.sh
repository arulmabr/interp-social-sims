#!/usr/bin/env bash
set -euo pipefail

# Run from the repository root on a GPU machine with HF_TOKEN set.
# This fills in missing five-level dose-sensitive steering variants for the
# paper games, reusing completed exact-dose runs when available.

if [[ -z "${HF_TOKEN:-}" ]]; then
  echo "HF_TOKEN must be set for meta-llama/Llama-3.3-70B-Instruct access." >&2
  exit 1
fi

RUN_FULL="${RUN_FULL:-0}"
FORCE_RERUN="${FORCE_RERUN:-0}"
COMMON_ARGS=(
  --model-id meta-llama/Llama-3.3-70B-Instruct
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50
  --hook model.layers.50
  --steering-mode clamp_min
  --patch-scope last_token
  --max-new-tokens 256
  --load-in-4bit
  --progress
)

if [[ "$FORCE_RERUN" == "1" ]]; then
  COMMON_ARGS+=(--force-rerun)
fi

python scripts/run_open_sae_dose_sweep.py \
  --scope smoke \
  --dry-run

python scripts/run_open_sae_dose_sweep.py \
  --scope smoke \
  --execute-missing \
  "${COMMON_ARGS[@]}"

python scripts/verify_live_dose_sweep_outputs.py --scope smoke

if [[ "$RUN_FULL" == "1" ]]; then
  python scripts/run_open_sae_dose_sweep.py \
    --scope full \
    --dry-run

  python scripts/run_open_sae_dose_sweep.py \
    --scope full \
    --execute-missing \
    "${COMMON_ARGS[@]}"

  python scripts/run_open_sae_dose_sweep.py \
    --scope full \
    --summarize

  python scripts/verify_live_dose_sweep_outputs.py --scope full
fi
