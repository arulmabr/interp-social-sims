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
- Paper five-condition safe-risk/lottery saved responses and source audit.
- Cached feature-description lookup and saved Goodfire steering provenance.
- Experimental live Open-SAE steering generation for new GPU-backed runs.
- Completed GPU evidence folders for release-critical smoke/full steering runs.
- A release completion audit that separates completed artifacts from documented
  GPU extension paths.

Scope boundary: this release covers the EDSL plus SAE path. It intentionally does
not package the paper's probe-training or probe-steering artifacts.

## Current Verified Outputs

| Experiment | Status | Evidence |
| --- | --- | --- |
| EDSL platform examples | Complete | 4 reusable game specs with deterministic smoke-run support |
| Generic Open-SAE run-dir loader | Complete | Normalized EDSL `response_units.csv` folders validate without GPU |
| Creativity GPT-5 Torrance eval | Complete | 320 judged response-task rows |
| Creativity Open-SAE response-only frequency | Complete | 320 units, 3,200 top-k rows, 0 special/control-token hits |
| Safe-risk Open-SAE calibration | Complete | 4,200 units, 42,000 top-k rows, behavior matches old summary exactly |
| Safe-risk five-condition paper fixture | Complete | 7,000 saved responses, 70,000 top-k rows, 175 reward-condition cells |
| Ultimatum Open-SAE replacement | Complete | 2,040 units, 20,400 top-k rows, 51 behavior cells, old `feature_activations.txt` parsed |
| Trust-game Open-SAE replacement | Complete | 200 units, 2,000 top-k rows, 20 behavior cells |
| Feature descriptions | Complete | 1,920 lookup rows, including safe-risk/lottery and ultimatum top features |
| Creativity steering provenance | Complete | Goodfire controller features `13142`, `20117`, `4992` extracted from saved run |
| Live Open-SAE steering runner | Complete | 80 generated creativity high-steering units, 800 post-hoc Open-SAE rows |

The machine-readable completion audit is:

- `reports/RELEASE_COMPLETION_AUDIT.json`
- `reports/RELEASE_COMPLETION_AUDIT.md`

The included audit currently reports every checked requirement as `complete`. If
you delete generated GPU outputs and rerun the audit, it can also report:

- `complete`: verified release artifact exists now.
- `implemented_gpu_pending`: code and local smoke-plan artifacts exist, but a live
  H100 execution is still required before claiming generated outputs.
- `source_audited_gpu_pending`: saved response data and behavior reconstruction are
  verified, but an optional full Open-SAE feature refresh still needs GPU time.

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

## Compute, Cost, and Scope

The local platform checks and EDSL smoke runs do not require a GPU. The expensive
step is Open-SAE inspection with Llama 3.3 70B.

Recommended GPU target:

- 1x H100 80GB.
- 300-500GB pod volume for model cache, SAE weights, source data, and outputs.
- Hugging Face token with access to `meta-llama/Llama-3.3-70B-Instruct`.

RunPod prices change. As of the May 2026 public pricing page, H100 pod examples
include H100 PCIe Community around `$1.99/hr`, H100 SXM Community around
`$2.69/hr`, and H100 PCIe Secure around `$2.89/hr`; check
[RunPod pricing](https://www.runpod.io/pricing) before launching. RunPod also lists
pod pricing as hourly but billed by the millisecond, and volume/container storage
can continue to cost money when pods are idle.

Measured Open-SAE inference time in this repo:

| Run | Units | GPU elapsed |
| --- | ---: | ---: |
| Creativity response-only Open-SAE | 320 | 1.8 min |
| Safe-risk/lottery Open-SAE | 4,200 | 12.4 min |
| Safe-risk five-condition Open-SAE | 7,000 | 21.7 min |
| Ultimatum Open-SAE | 2,040 | 7.4 min |
| Trust Open-SAE | 200 | 1.1 min |
| Total archived Open-SAE inspection | 13,760 | 44.3 min |

At `$1.99-$2.89/hr`, the measured inference time above is about `$0.75-$1.09` of
raw H100 compute. In practice, first-time reproduction costs more because the pod
must start, install dependencies, download/cache the 70B model and SAE, and may sit
idle during debugging. Practical credit guidance:

- Local docs/tests/smoke runs: `$0`, excluding any hosted EDSL model calls.
- One tiny GPU smoke test after the model is cached: usually under `$1`.
- Reproduce the archived Open-SAE feature runs once: budget `$10-$25`.
- Develop and inspect one new 40-agent EDSL game: budget `$25-$50`, depending on
  model-response generation cost and iteration.
- Iterative experiments or live steering sweeps: keep `$100-$200` available.

EDSL response collection cost is separate from Open-SAE inspection. If EDSL uses a
hosted model provider, token prices depend on that provider and model. If EDSL uses
your own GPU-backed model, that cost is GPU time instead.

Current steering status:

- Archived creativity high-steering responses are historical saved Goodfire
  hosted-controller outputs.
- New live steering is implemented as an experimental open-source GPU path in
  `scripts/run_open_sae_steering_generation.py`.
- The open runner hooks `model.layers.50`, encodes the residual with
  `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, edits selected feature activations,
  decodes back while preserving SAE reconstruction error, and writes a new
  normalized `response_units.csv`.
- This is not claimed to exactly match deprecated hosted Goodfire controller
  nudge calibration. Use `feature_index`, `steering_mode`, `actual_strengths`,
  and the saved `open_sae_steering_metadata.json` as the reproducible contract.

Minimal GPU steering smoke test:

```bash
bash ./runpod/run_creativity_open_sae_steering.sh
```

Optional five-condition safe-risk Open-SAE refresh:

```bash
bash ./runpod/run_safe_risky_five_condition_open_sae.sh
RUN_FULL=1 bash ./runpod/run_safe_risky_five_condition_open_sae.sh
```

Equivalent expanded command:

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

Inspect the generated steered responses with the normal Open-SAE runner:

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

## Quick Start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Use Python 3.10-3.13 for installed package workflows. Check the local setup without
installing or loading big models:

```bash
python scripts/check_environment.py
python scripts/check_environment.py --gpu
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
  --dataset-kind safe_risky \
  --source-dir data/raw/games/safe_risky/results_20251008_225522 \
  --dry-run \
  --expected-units 7000

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
python scripts/build_release_completion_audit.py --check
python scripts/build_data_manifest.py --check
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
runs/                             selected completed GPU run artifacts
scripts/                          reusable runners
social_sim_open_sae/              game-spec and EDSL adapter package
tests/                            lightweight artifact verification
```

## Build The Release Zip

After changing docs, scripts, or generated artifacts, rerun the release checks and
build a clean archive:

```bash
python scripts/build_release_completion_audit.py --check
python scripts/build_data_manifest.py --check
python tests/verify_release_artifacts.py
python tests/verify_platform_smoke.py
python tests/verify_no_secrets.py
python tests/verify_release_anonymity.py
python scripts/build_release_zip.py \
  --output ../social-sim-open-sae_release.zip
```

The zip builder includes selected completed `runs/` evidence folders, excludes
local caches and prior archives, and prints the final SHA-256 hash.

## Public Release Safety

This repo is intentionally a clean export. It should not contain local `.env` files,
API keys, model caches, browser data, or full EDSL source internals.
