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

Set credentials without writing them to files:

```bash
export HF_TOKEN=...
export OPENAI_API_KEY=...
```

Run the remaining game Open-SAE smoke tests and full jobs:

```bash
./runpod/run_remaining_games_open_sae.sh
```

Stop the pod immediately after outputs are synced back. If the volume is retained, it
continues to accrue idle storage cost.
