# RunPod H100 Notes

Recommended pod for full Open-SAE reruns:

- GPU: 1x H100 80GB
- Template: PyTorch / CUDA
- Volume: 300-500GB
- Use `--load-in-4bit`

Install:

```bash
pip install -r requirements.txt
```

Check the pod before launching a paid run:

```bash
python scripts/check_environment.py --gpu
```

Set credentials without writing them to files:

```bash
export HF_TOKEN=...
export OPENAI_API_KEY=...
```

Run the remaining game Open-SAE smoke tests and full jobs:

```bash
bash ./runpod/run_remaining_games_open_sae.sh
```

Run the optional five-condition safe-risk Open-SAE refresh:

```bash
bash ./runpod/run_safe_risky_five_condition_open_sae.sh
RUN_FULL=1 bash ./runpod/run_safe_risky_five_condition_open_sae.sh
```

Run the live creativity steering smoke test:

```bash
bash ./runpod/run_creativity_open_sae_steering.sh
```

If the smoke output is sane, run the full 40-agent high-steering-prompt
regeneration and post-hoc Open-SAE inspection:

```bash
RUN_FULL=1 bash ./runpod/run_creativity_open_sae_steering.sh
```

Run the remaining live game steering smoke tests:

```bash
bash ./runpod/run_game_open_sae_steering.sh
```

If the smoke outputs verify, run the full safe-risk, ultimatum, and trust live
steering jobs:

```bash
RUN_FULL=1 bash ./runpod/run_game_open_sae_steering.sh
```

Stop the pod immediately after outputs are synced back. If the volume is retained, it
continues to accrue idle storage cost.
