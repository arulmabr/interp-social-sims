# Fresh Game Steering RunPod Checklist

This checklist runs the remaining live Open-SAE steering jobs for the paper games:

- safe-risk, lite steering: 1,400 generated units
- safe-risk, strong steering: 1,400 generated units
- ultimatum, steering: 680 generated units
- trust, baseline and intervention steering features: 200 generated units

The runner uses `meta-llama/Llama-3.3-70B-Instruct`,
`Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, and `model.layers.50`. It generates
new responses by patching SAE feature activations during decoding, then runs
post-hoc Open-SAE inspection over those generated responses.

## Local Upload

From the local machine, after the pod is running and the SSH command is known:

```bash
scp -i ~/.ssh/runpod_key -P RUNPOD_PORT \
  /tmp/social_sim_open_sae_fresh_steering_latest.tgz \
  root@RUNPOD_HOST:/workspace/
```

## Pod Setup

On the RunPod machine:

```bash
cd /workspace
rm -rf social-sim-open-sae-fresh
mkdir -p social-sim-open-sae-fresh
tar -xzf social_sim_open_sae_fresh_steering_latest.tgz -C social-sim-open-sae-fresh
cd social-sim-open-sae-fresh

python -m pip install -U pip
pip install -r requirements.txt
read -rsp "Hugging Face token: " TOKEN_VALUE
printf '\n'
export HF_TOKEN
HF_TOKEN=$TOKEN_VALUE

python scripts/check_environment.py --gpu
```

Do not write Hugging Face tokens into repository files.

## Smoke Run

```bash
bash ./runpod/run_game_open_sae_steering.sh
```

Expected smoke verification:

- 4 generated run folders
- 32 total generated response units
- 320 total post-hoc Open-SAE top-k rows
- no unparsed generated answers

## Full Run

```bash
RUN_FULL=1 bash ./runpod/run_game_open_sae_steering.sh
```

Expected full verification:

- `runs/safe_risky_open_sae_steering_lite_full`: 1,400 units, 14,000 top-k rows
- `runs/safe_risky_open_sae_steering_full`: 1,400 units, 14,000 top-k rows
- `runs/ultimatum_open_sae_steering_full`: 680 units, 6,800 top-k rows
- `runs/trust_open_sae_steering_full`: 200 units, 2,000 top-k rows

The script runs `python scripts/verify_live_steering_outputs.py --scope full`
automatically after the full run.

## Sync Back

From the local machine:

```bash
rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/safe_risky_open_sae_steering_lite_smoke \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/safe_risky_open_sae_steering_lite_full \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/safe_risky_open_sae_steering_full_smoke \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/safe_risky_open_sae_steering_full \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/ultimatum_open_sae_steering_smoke \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/ultimatum_open_sae_steering_full \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/trust_open_sae_steering_smoke \
  <LOCAL_REPO>/runs/

rsync -av -e "ssh -i ~/.ssh/runpod_key -p RUNPOD_PORT" \
  root@RUNPOD_HOST:/workspace/social-sim-open-sae-fresh/runs/trust_open_sae_steering_full \
  <LOCAL_REPO>/runs/
```

Stop the pod immediately after outputs are synced.

## Local Verification

```bash
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_live_steering_outputs.py --scope all
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_data_manifest.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/build_data_manifest.py --check
```
