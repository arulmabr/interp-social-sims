#!/usr/bin/env bash
set -euo pipefail
cd /workspace/sae-label-pilot
export HF_HOME=/workspace/hf
export TOKENIZERS_PARALLELISM=false
export HF_ENABLE_PARALLEL_LOADING=true
export HF_PARALLEL_LOADING_WORKERS=8
export PAPER_REPLICATION_PLAN_PATH=replication-plan
EDSL_SAE_PYTHON=/workspace/sae-label-pilot/edsl_local_sae/.venv/bin/python
if [ ! -x "$EDSL_SAE_PYTHON" ]; then
  python3 -m venv --system-site-packages /workspace/sae-label-pilot/edsl_local_sae/.venv
fi
"$EDSL_SAE_PYTHON" -m pip install -r label_pilot/requirements.txt -r edsl_local_sae/requirements.txt
"$EDSL_SAE_PYTHON" -m pip freeze > "$1"
shift
"$EDSL_SAE_PYTHON" -m label_pilot.cache
export HF_HUB_CACHE=/dev/shm/sae-hf/hub
exec "$EDSL_SAE_PYTHON" -u -m edsl_local_sae.session "$@"
