# Steering Provenance and Phase-2 Plan

## Current Saved Steering

The released creativity high-steering condition is a saved Goodfire hosted-controller
run, not a new open-SAE steering regeneration. Its controller provenance is extracted
from:

`data/raw/creativity/product_innovation_20251102_202650/high_steering.csv`

The extracted file is:

`data/processed/creativity/steering_provenance/steering_features.csv`

It contains the three Goodfire controller features used in the saved run:

| Feature index | Historical Goodfire label | Nudge |
| ---: | --- | ---: |
| 13142 | Enabling or empowering creative expression and exploration | 0.3 |
| 20117 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | 0.3 |
| 4992 | Professional innovation and creative problem-solving | 0.3 |

Regenerate the provenance artifact locally with:

```bash
python scripts/extract_steering_provenance.py --check
```

## Open-SAE Steering Status

The public repo includes a phase-2 entrypoint for open-SAE steering smoke planning:

```bash
python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --smoke-mode \
  --limit-units 4 \
  --output-dir data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan
```

This validates the target feature indices, strengths, source prompts, model, SAE repo,
and hook. It does not generate new responses.

Full open-SAE steering regeneration should be implemented as a GPU phase:

- Load `meta-llama/Llama-3.3-70B-Instruct`.
- Load `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`.
- Hook `model.layers.50`.
- During generation, encode the layer-50 residual with the SAE, nudge the target
  feature activations, decode back to residual space, and preserve reconstruction
  error as in the Goodfire open model-card pattern.
- Save regenerated responses, behavior summaries, steering metadata, and Open-SAE
  post-hoc inspection outputs in a new derived folder.

Until that phase is run, steering claims in this repo should be phrased as provenance
for saved Goodfire controller outputs, not as a completed open-SAE steering regeneration.
