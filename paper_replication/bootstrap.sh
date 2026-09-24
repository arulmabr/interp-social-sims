#!/usr/bin/env bash
set -euo pipefail
cd /workspace/sae-label-pilot
export HF_HOME=/workspace/hf
export TOKENIZERS_PARALLELISM=false
export HF_ENABLE_PARALLEL_LOADING=true
export HF_PARALLEL_LOADING_WORKERS=8
export PAPER_REPLICATION_PLAN_PATH=replication-plan
REPLICATION_PYTHON=/workspace/sae-label-pilot/label_pilot/.venv/bin/python
if [ ! -x "$REPLICATION_PYTHON" ]; then
  python3 -m venv --system-site-packages /workspace/sae-label-pilot/label_pilot/.venv
fi
"$REPLICATION_PYTHON" -m pip install -r label_pilot/requirements.txt
"$REPLICATION_PYTHON" -m label_pilot.access check --model-only
"$REPLICATION_PYTHON" -m pytest paper_replication/tests label_pilot/tests -q
"$REPLICATION_PYTHON" -m label_pilot.cache
export HF_HUB_CACHE=/dev/shm/sae-hf/hub
exec "$REPLICATION_PYTHON" -u -m paper_replication.run "$@"
