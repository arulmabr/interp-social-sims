#!/usr/bin/env bash
set -euo pipefail
cd /workspace
export HF_HOME=/workspace/hf
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=8
python -m venv --system-site-packages /workspace/anchor_pilot/.venv
source /workspace/anchor_pilot/.venv/bin/activate
python -m pip install -r anchor_pilot/requirements.txt
python -m pytest anchor_pilot/test_core.py anchor_pilot/test_cpt.py anchor_pilot/test_modeling.py -q
python -m anchor_pilot.preflight
run_dir="anchor_pilot/outputs/pilot-$(date -u +%Y%m%dT%H%M%SZ)"
# A separate stop_guard.py MUST already be armed; timeout caps this process,
# not provider billing. Analysis runs on CPU after copying artifacts home.
timeout --signal=TERM --kill-after=30s 105m python -u -m anchor_pilot.pilot \
  --design anchor_pilot/outputs/design-v1 --output "$run_dir" \
  --steps 200 --train-batch 8 --batch-size 8 --max-seconds 6000 --reserve-seconds 2400
