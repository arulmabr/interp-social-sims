#!/usr/bin/env bash
set -euo pipefail
cd /workspace
: "${ANCHOR_SESSION_DEADLINE:?Absolute provider stop deadline required}"
export HF_HOME=/workspace/hf
export TOKENIZERS_PARALLELISM=false
export OMP_NUM_THREADS=8
python -m venv --system-site-packages /workspace/anchor_pilot/.venv
source /workspace/anchor_pilot/.venv/bin/activate
python -m pip install --disable-pip-version-check -r anchor_pilot/requirements.txt
python -m pytest -q anchor_pilot/test_core.py anchor_pilot/test_cpt.py anchor_pilot/test_modeling.py anchor_pilot/test_repair.py anchor_pilot/test_replay.py anchor_pilot/test_decision.py
python -m anchor_pilot.preflight
remaining=$(python -c 'import datetime,os,time; print(int(datetime.datetime.fromisoformat(os.environ["ANCHOR_SESSION_DEADLINE"].replace("Z","+00:00")).timestamp()-time.time()-720))')
if (( remaining <= 1800 )); then
  echo 'Insufficient time before backup cutoff.'
  exit 2
fi
run_dir="anchor_pilot/outputs/decision-$(date -u +%Y%m%dT%H%M%SZ)"
timeout --signal=TERM --kill-after=30s "${remaining}s" python -u -m anchor_pilot.decision --output "$run_dir"
