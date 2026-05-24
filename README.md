# EDSL Social Simulation Open-SAE Platform

This repository is a reusable platform for building EDSL social simulations,
collecting model-agent game data, and inspecting those transcripts with Goodfire
Open-SAE features.

The core workflow is:

1. Define a social-simulation game as an EDSL `GameSpec`.
2. Collect fresh model-agent responses with EDSL.
3. Run the open Hugging Face Goodfire SAE over the generated transcripts.
4. Compare behavior, top SAE features, cached Neuronpedia labels, and plots.

The archived creativity, safe-risk, ultimatum, and trust outputs are included as
worked examples and regression fixtures. They are no longer the whole point of the
repo.

## What Is Included

- A small `social_sim_open_sae` package for declaring EDSL game specs.
- Example EDSL game modules for creativity, safe-risk/lottery, ultimatum, and trust.
- `scripts/run_edsl_social_simulation.py` for collecting new normalized EDSL runs.
- `scripts/run_open_sae_feature_inspection.py --run-dir` for inspecting new runs.
- Archived creativity task responses, GPT-5 Torrance judge scores, and Open-SAE features.
- Archived safe-risk, ultimatum, and trust outputs with full Open-SAE reruns.
- Cached feature-description lookup and saved Goodfire steering provenance.

## Current Verified Outputs

| Experiment | Status | Evidence |
| --- | --- | --- |
| EDSL platform examples | Complete | 4 reusable game specs with deterministic smoke-run support |
| Generic Open-SAE run-dir loader | Complete | Normalized EDSL `response_units.csv` folders validate without GPU |
| Creativity GPT-5 Torrance eval | Complete | 320 judged response-task rows |
| Creativity Open-SAE response-only frequency | Complete | 320 units, 3,200 top-k rows, 0 special/control-token hits |
| Safe-risk Open-SAE calibration | Complete | 4,200 units, 42,000 top-k rows, behavior matches old summary exactly |
| Ultimatum Open-SAE replacement | Complete | 2,040 units, 20,400 top-k rows, 51 behavior cells, old `feature_activations.txt` parsed |
| Trust-game Open-SAE replacement | Complete | 200 units, 2,000 top-k rows, 20 behavior cells |
| Feature descriptions | Complete | 1,920 lookup rows, including safe-risk/lottery and ultimatum top features |
| Creativity steering provenance | Complete | Goodfire controller features `13142`, `20117`, `4992` extracted from saved run |

## Key Caveat: Feature Labels

The original hosted Goodfire Ember natural-language labels are not recoverable from the
open-source SAE weights alone. The old Goodfire API endpoint is currently unavailable.
This repo therefore uses feature indices and activations from:

- Base model: `meta-llama/Llama-3.3-70B-Instruct`
- SAE: `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`
- Hook: `model.layers.50`

Natural-language labels are Neuronpedia/Open-SAE replacement labels. Treat them as
interpretability aids, not exact historical Goodfire Ember label strings.

The offline lookup is `data/processed/feature_description_lookup.csv`. It stores the
stable `feature_index`, cached `feature_label`, and corresponding Neuronpedia API URL.

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

For local development beside the EDSL checkout, install EDSL directly:

```bash
pip install -e ../edsl
```

Create a new EDSL game run:

```bash
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/safe_risky.py \
  --output-dir runs/safe_risky_demo \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --agents 40
```

Inspect that run with the Open-SAE pipeline:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/safe_risky_demo \
  --output-dir runs/safe_risky_demo/open_sae \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --load-in-4bit
```

Local checks that do not require a GPU:

```bash
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/safe_risky.py \
  --output-dir /tmp/safe_risky_demo \
  --mock-model \
  --agents 2 \
  --conditions baseline \
  --limit-scenarios 1

python scripts/run_open_sae_feature_inspection.py \
  --run-dir /tmp/safe_risky_demo \
  --dry-run \
  --expected-units 2

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind creativity \
  --dry-run \
  --expected-units 320

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind safe_risky \
  --dry-run \
  --expected-units 4200

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind ultimatum \
  --dry-run \
  --expected-units 2040

python scripts/run_open_sae_feature_inspection.py \
  --dataset-kind trust \
  --dry-run \
  --expected-units 200

python scripts/build_feature_description_bundle.py --check
python scripts/extract_steering_provenance.py --check
python tests/verify_release_artifacts.py
```

Game-building instructions are in [docs/BUILD_A_GAME.md](docs/BUILD_A_GAME.md).
Archived-output rerun commands are in [docs/REPRODUCTION.md](docs/REPRODUCTION.md).

## Repository Layout

```text
data/raw/                         saved source experiment outputs
data/processed/                   derived GPT/Open-SAE outputs
docs/                             data, labels, and reproduction notes
examples/games/                   reusable EDSL game specs
figures/                          optional figure exports
reports/                          release reports and summaries
runpod/                           RunPod-oriented execution notes
scripts/                          reusable runners
social_sim_open_sae/              game-spec and EDSL adapter package
tests/                            lightweight artifact verification
```

## Public Release Safety

This repo is intentionally a clean export. It should not contain local `.env` files,
API keys, model caches, browser data, or full EDSL source internals.
