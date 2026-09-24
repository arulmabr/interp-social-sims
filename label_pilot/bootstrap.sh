#!/usr/bin/env bash
set -euo pipefail
cd /workspace/sae-label-pilot
export HF_HOME="${HF_HOME:-/workspace/hf}"
export TOKENIZERS_PARALLELISM=false
export HF_ENABLE_PARALLEL_LOADING=true
export HF_PARALLEL_LOADING_WORKERS=8
PILOT_VENV=/workspace/sae-label-pilot/label_pilot/.venv
if [ ! -x "$PILOT_VENV/bin/python" ]; then
  python3 -m venv --system-site-packages "$PILOT_VENV"
fi
"$PILOT_VENV/bin/python" -m pip install -r label_pilot/requirements.txt
"$PILOT_VENV/bin/python" -m label_pilot.access check --model-only
"$PILOT_VENV/bin/python" -m pytest label_pilot/tests -q
"$PILOT_VENV/bin/python" -m label_pilot.cache
export HF_HUB_CACHE=/dev/shm/sae-hf/hub
exec "$PILOT_VENV/bin/python" -u -m label_pilot.run "$@"
