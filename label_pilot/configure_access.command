#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")/.."
printf '%s\n' 'Enter credentials here, never in chat. Input is hidden.' 'Runpod API key is optional when using the signed-in console.' 'HF_TOKEN must have read access to the approved Llama-3.3-70B-Instruct model.'
label_pilot/.venv/bin/python -m label_pilot.access configure
label_pilot/.venv/bin/python -m label_pilot.access check --model-only
read -r -p 'Press Enter to close.'
