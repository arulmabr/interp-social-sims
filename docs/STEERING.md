# Steering Provenance and Live Open-SAE Steering

## Current Saved Steering

The released creativity high-steering condition is a saved Goodfire hosted-controller
run. Its controller provenance is extracted
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

That historical file is why the repo can analyze 40-agent creativity steering
today: the steered responses already exist. The open-source runner below is for
generating new steered responses without the hosted Goodfire API.

## Smoke Planning

```bash
python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --conditions high_steering \
  --smoke-mode \
  --limit-units 4 \
  --output-dir data/processed/creativity/steering_provenance/open_sae_steering_smoke_plan
```

This validates the target feature indices, strengths, source prompts, model, SAE repo,
hook, and Neuronpedia metadata. It does not load the model.

The smoke-plan folder includes:

- `open_sae_steering_smoke_plan.json`
- `open_sae_steering_smoke_units.csv`
- `open_sae_steering_feature_metadata.csv`

## Live Open-SAE Generation

Live steering is implemented in:

`scripts/run_open_sae_steering_generation.py`

On a GPU pod with Hugging Face access to Llama 3.3 70B:

```bash
python scripts/run_open_sae_steering_generation.py \
  --dataset-kind creativity \
  --source-dir data/raw/creativity/product_innovation_20251102_202650 \
  --output-dir runs/creativity_open_sae_steering_smoke \
  --conditions high_steering \
  --feature-indices 13142,20117,4992 \
  --strengths 0.3,0.3,0.3 \
  --steering-mode clamp_min \
  --patch-scope last_token \
  --limit-units 4 \
  --max-new-tokens 256 \
  --load-in-4bit \
  --execute
```

The command writes a normalized EDSL-compatible run folder:

- `run_manifest.json`
- `response_units.csv`
- `response_units.jsonl`
- `source_prompt_units.csv`
- `open_sae_steering_metadata.json`
- `open_sae_steering_trace.jsonl`
- `open_sae_steering_feature_metadata.csv`

The generated `response_units.csv` can then be inspected by the standard Open-SAE
pipeline:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/creativity_open_sae_steering_smoke \
  --output-dir runs/creativity_open_sae_steering_smoke/open_sae \
  --activation-scope assistant_response \
  --feature-aggregation frequency \
  --activation-threshold 0.1 \
  --top-k 10 \
  --load-in-4bit
```

## How The Patch Works

For each generation forward pass, the runner hooks `model.layers.50`. It takes
the residual output, encodes it with `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`,
edits selected SAE activations, decodes back to residual space, and adds the
original SAE reconstruction error back:

```text
features = sae.encode(residual)
reconstruction = sae.decode(features)
error = residual - reconstruction
features[..., feature_index] = edit(features[..., feature_index])
steered_residual = sae.decode(features) + error
```

`--patch-scope last_token` is the default because it steers the current generation
position while leaving the full prompt encoding mostly intact. `--patch-scope
all_tokens` is available for stronger intervention tests.

## Steering Modes

- `clamp_min`: set each target feature to at least the supplied strength. This
  follows the Goodfire Hugging Face model-card intervention pattern.
- `add_delta`: add the supplied strength and clamp at zero. This is the closest
  transparent approximation to the old hosted `mode: nudge` language.
- `set`: set the target feature activation to the supplied strength.
- `nudge`: accepted as an alias for `add_delta` and recorded as such in metadata.

## Strength Calibration

The old hosted Goodfire `nudge=0.3` is not known to equal a raw SAE activation
target of `0.3`. The public runner therefore records both `input_strengths` and
`actual_strengths`.

Available calibration modes:

- `raw`: use strengths exactly as supplied.
- `fraction_of_neuronpedia_max`: multiply each supplied strength by the feature's
  Neuronpedia `maxActApprox`.
- `fraction_of_neuronpedia_default`: multiply by Neuronpedia
  `vectorDefaultSteerStrength`.

For the three creativity steering features, the smoke-plan metadata currently
records these Neuronpedia labels and approximate maxima:

| Feature index | Neuronpedia label | maxActApprox |
| ---: | --- | ---: |
| 13142 | creative acts and originality | 3.125 |
| 20117 | creative and innovative thinking | 6.9688 |
| 4992 | creative in thinking | 4.1875 |

## Claim Boundary

Correct claim:

> This repo includes historical Goodfire-hosted steering provenance and an
> executable open-source steering runner using Goodfire's released Llama 3.3 70B
> SAE.

Incorrect claim:

> This exactly reproduces the deprecated hosted Goodfire controller's private
> nudge calibration.

For paper or public release language, use the stable `feature_index`, the open
SAE repo ID, the steering mode, and the recorded `actual_strengths`.
The generated behavior is not guaranteed to match deprecated hosted Goodfire
controller calibration, because the old service did not expose its private nudge
normalization.
