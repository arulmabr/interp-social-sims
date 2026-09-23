#!/usr/bin/env bash
set -euo pipefail
# Run from the repository root in the official Runpod PyTorch 2.8.0 image.
# This script DOES NOT deploy, stop, or terminate a billed pod.
export HF_HOME="${HF_HOME:-/workspace/hf}"
export TOKENIZERS_PARALLELISM=false
# Ubuntu's system Python is externally managed. Reuse the template's CUDA torch
# through system-site-packages, while installing our dependencies in a venv.
PILOT_VENV="${PILOT_VENV:-/workspace/anchor_pilot/.venv}"
if [ ! -x "$PILOT_VENV/bin/python" ]; then
  python -m venv --system-site-packages "$PILOT_VENV"
fi
source "$PILOT_VENV/bin/activate"
python -m pip install -r anchor_pilot/requirements.txt
python -m anchor_pilot.preflight
python -m pytest anchor_pilot/test_core.py -q
OUTPUT="anchor_pilot/outputs/gpu-$(date -u +%Y%m%dT%H%M%SZ)"
# Bounds the model process only; GPU billing continues until the pod is stopped.
timeout --signal=TERM --kill-after=30s 45m python -u -m anchor_pilot.smoke --output "$OUTPUT"
