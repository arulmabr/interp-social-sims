#!/usr/bin/env bash
# Run the strong-prompting sweeps on a RunPod pod at FULL PRECISION (bf16 = the
# native, non-Turbo Llama-3.3 weights).
#
# Pod requirements:
#   * 2x H100 80GB (or 2x A100 80GB) -- bf16 70B needs ~140GB of weights + KV cache
#   * ~250GB+ container/volume disk for the model cache and outputs
#   * HF token with gated access to meta-llama/Llama-3.3-70B-Instruct
#
# Setup on the pod (run from the repo root):
#   export HF_TOKEN=hf_xxx          # gated access to the model
#   bash runpod/run_fp16_strong_prompting.sh
#
# Pull the CSVs back to your Mac afterwards (see the message that shipped this).

set -euo pipefail

MODEL="meta-llama/Llama-3.3-70B-Instruct"
TP=2                 # number of GPUs (tensor parallel)
TEMP=0.7             # >0 so the 40 agents differ; set to match your paper's decoding
PREF_MAX_TOKENS=512  # preference tasks: CoT reasoning + "Final answer"
CREA_MAX_TOKENS=1536 # creativity tasks: up to 10 elaborated paragraphs

# Cache the ~140GB model on the PERSISTENT VOLUME (/workspace), not the small
# ephemeral container disk. Override HF_HOME if your volume is mounted elsewhere.
export HF_HOME="${HF_HOME:-/workspace/hf}"
echo ">> HF cache dir: $HF_HOME"

echo ">> installing vllm + jinja2"
pip install -q vllm jinja2

echo ">> checking HF access / pre-caching the model"
python -c "import os; assert os.environ.get('HF_TOKEN'), 'set HF_TOKEN (gated access) first'"
huggingface-cli download "$MODEL" >/dev/null

run_game () {  # $1 = game stem, $2 = max_tokens
  echo ">> running $1 (max_tokens=$2)"
  python scripts/run_local_vllm_generation.py \
    --game-module "games/$1_strong_prompting.py" \
    --output-dir "runs/$1_full" \
    --model "$MODEL" --dtype bfloat16 --tensor-parallel-size "$TP" \
    --temperature "$TEMP" --max-tokens "$2"
}

# Preference games -> behavior_summary.csv gives the dose-response directly
run_game safe_risky "$PREF_MAX_TOKENS"
run_game ultimatum  "$PREF_MAX_TOKENS"

# Creativity games -> response_units.csv feed the GPT Torrance eval afterwards
run_game creativity_brick   "$CREA_MAX_TOKENS"
run_game creativity_stapler "$CREA_MAX_TOKENS"

echo ">> ALL RUNS COMPLETE"
echo "   results: runs/*/response_units.csv  and  runs/*/behavior_summary.csv"
