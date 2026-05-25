# Interpretable Social Simulations

This repository contains the interpretability and control tooling for
EDSL-style LLM social simulations. It packages two complementary approaches
from the paper: **SAE-based interpretation/steering** (Sparse Autoencoder
feature inspection and editing) and **probe-based steering** (linear-probe
activation steering). Each lives in its own subdirectory with its own
dependencies and GPU requirements.

```
interp-social-sims/
├── SAE/       # EDSL social-simulation platform + Goodfire Open-SAE feature inspection & steering
└── Probes/    # Probe training, calibration, steered experiments, and figure generation
```

---

## SAE Pipeline (`SAE/`)

A reusable platform for building EDSL social simulations, collecting
model-agent game data, and inspecting those transcripts with Goodfire Open-SAE
features.

### Core workflow

1. Define a social-simulation game as an EDSL `GameSpec`.
2. Collect fresh model-agent responses with EDSL.
3. Run the open Hugging Face Goodfire SAE over the generated transcripts.
4. Compare behavior, top SAE features, cached Neuronpedia labels, and plots.

### What is included

- `social_sim_open_sae/` — package for declaring EDSL game specs.
- Example EDSL game modules for creativity, safe-risk/lottery, ultimatum, and trust.
- `scripts/run_edsl_social_simulation.py` — collect new normalized EDSL runs.
- `scripts/run_open_sae_feature_inspection.py --run-dir` — inspect new runs.
- Archived creativity task responses, GPT-5 Torrance judge scores, and Open-SAE features.
- Archived safe-risk, ultimatum, and trust outputs with full Open-SAE reruns.
- Paper five-condition safe-risk/lottery saved responses and source audit.
- Cached feature-description lookup and saved Goodfire steering provenance.
- Experimental live Open-SAE steering generation for new GPU-backed runs.
- Completed GPU evidence folders for release-critical smoke/full steering runs.
- Release completion audit separating completed artifacts from documented GPU extension paths.

### Verified outputs

| Experiment | Status | Evidence |
| --- | --- | --- |
| EDSL platform examples | Complete | 4 reusable game specs with deterministic smoke-run support |
| Generic Open-SAE run-dir loader | Complete | Normalized EDSL `response_units.csv` folders validate without GPU |
| Creativity GPT-5 Torrance eval | Complete | 320 judged response-task rows |
| Creativity Open-SAE response-only frequency | Complete | 320 units, 3,200 top-k rows, 0 special/control-token hits |
| Safe-risk Open-SAE calibration | Complete | 4,200 units, 42,000 top-k rows, behavior matches old summary exactly |
| Safe-risk five-condition paper fixture | Complete | 7,000 saved responses, 70,000 top-k rows, 175 reward-condition cells |
| Ultimatum Open-SAE replacement | Complete | 2,040 units, 20,400 top-k rows, 51 behavior cells |
| Trust-game Open-SAE replacement | Complete | 200 units, 2,000 top-k rows, 20 behavior cells |
| Feature descriptions | Complete | 1,920 lookup rows |
| Creativity steering provenance | Complete | Goodfire controller features `13142`, `20117`, `4992` |
| Live Open-SAE steering runner | Complete | 80 generated creativity high-steering units, 800 post-hoc Open-SAE rows |

### Key caveat — feature labels

The original hosted Goodfire Ember labels are not recoverable from the
open-source SAE weights alone. This repo uses Neuronpedia/Open-SAE replacement
labels from:

- Base model: `meta-llama/Llama-3.3-70B-Instruct`
- SAE: `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`
- Hook: `model.layers.50`

Offline lookup: `SAE/data/processed/feature_description_lookup.csv`.

### Quick start (SAE)

```bash
cd SAE
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Local checks (no GPU)
python scripts/check_environment.py
python tests/verify_release_artifacts.py

# New EDSL game run
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/safe_risky.py \
  --output-dir runs/safe_risky_demo \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --agents 40

# Open-SAE inspection
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/safe_risky_demo \
  --output-dir runs/safe_risky_demo/open_sae \
  --top-k 10 --load-in-4bit
```

### SAE compute & cost

- Recommended GPU: 1× H100 80 GB.
- 300–500 GB pod volume for model cache, SAE weights, source data, and outputs.
- Measured Open-SAE inference over all archived experiments: ~44 min on H100 (~$0.75–$1.09 raw compute).
- Practical first-time reproduction budget: $10–$25; iterative experiments: $100–$200.

### SAE repository layout

```
SAE/
├── data/raw/                     saved source experiment outputs
├── data/processed/               derived GPT/Open-SAE outputs
├── docs/                         data, labels, and reproduction notes
├── examples/games/               reusable EDSL game specs
├── reports/                      release reports and summaries
├── runpod/                       RunPod-oriented execution notes
├── runs/                         selected completed GPU run artifacts
├── scripts/                      reusable runners
├── social_sim_open_sae/          game-spec and EDSL adapter package
└── tests/                        lightweight artifact verification
```

Full SAE details: [`SAE/README.md`](SAE/README.md)

---

## Probe Pipeline (`Probes/`)

The pipeline for the probe-based steering experiments (figures 7, 9–19).
Running it end-to-end produces the per-trial logs and the aggregated
`probe_results_final.json` that the probe figures are plotted from.

### What this implements

For each of two base models (`Llama-3.3-70B-Instruct`, `Qwen-2-7B-Instruct`):

1. **Data generation** — sweep task parameters, record baseline choices, capture layer-`l` hidden states.
2. **Probe training** — `l2`-regularized logistic regression with cross-validated layer + regularization sweep.
3. **Lambda calibration** — coarse grid then bracketed binary search for target switching points.
4. **Steered experiments** — replay each task with the probe-steering hook at calibrated lambda.
5. **Creativity scoring** — GPT-5 judge via EDSL `QuestionLinearScale` (fluency, flexibility, originality, elaboration).
6. **Cross-object generalization** — train on subset of objects, evaluate on held-out object.
7. **Aggregation** — combine all per-trial JSONL logs into one JSON with 13 figure keys.

### Output JSON figure keys

```
figure_7_psychometric_curves_llama
figure_9_capability_brick_target_vs_achieved
figure_9_capability_stapler_product_innovation_target_vs_achieved
figure_10_capability_four_objects_target_vs_achieved
figure_11_dose_response_lottery_ultimatum_llama
figure_12_probe_scores_track_target_lottery_ultimatum_llama
figure_13_cross_object_generalization_llama
figure_14_psychometric_curves_qwen
figure_15_dose_response_lottery_ultimatum_qwen
figure_16_probe_scores_track_target_qwen
figure_17_capability_brick_target_vs_achieved_qwen
figure_18_capability_four_objects_target_vs_achieved_qwen
figure_19_cross_object_generalization_qwen
```

### Quick start (Probes)

```bash
pip install -r Probes/requirements.txt
export OPENAI_API_KEY=...    # for the GPT-5 judge
export HF_TOKEN=...          # for gated Llama weights

python -m Probes.run_all --model llama --outdir runs/llama_final
python -m Probes.run_all --model qwen  --outdir runs/qwen_final

# Aggregate into canonical JSON
python -m Probes.aggregator \
  --llama-run runs/llama_final \
  --qwen-run  runs/qwen_final \
  --out probe_results_final.json
```

### Multi-judge re-scoring

Five judge models across four providers:

| Judge | Provider | Model ID |
|---|---|---|
| `gpt-5` | OpenAI | `gpt-5` |
| `claude-sonnet-4-6` | Anthropic | `claude-sonnet-4-6` |
| `gemini-3.1-pro` | Google | `gemini-3.1-pro-preview` |
| `kimi-k2.6` | Together | `moonshotai/Kimi-K2.6` |
| `deepseek-v4-pro` | Together | `deepseek-ai/DeepSeek-V4-Pro` |

```bash
python -m Probes.multi_judge_rescore \
    --in probe_results_final.json \
    --judges gpt-5 claude-sonnet-4-6 gemini-3.1-pro kimi-k2.6 deepseek-v4-pro \
    --out runs/multi_judge \
    --blind --length-controlled
```

### Probe compute & cost

- Llama-3.3-70B-Instruct: 2× H100 (80 GB) or 4× A100 (40 GB), bf16 — ~12–18 GPU-hours
- Qwen-2-7B-Instruct: 1× A100 or any 24 GB GPU — ~3–5 GPU-hours
- GPT-5 judge: ~10K–20K calls, ~$50–100

### Probe methodology

- Probe formulation: `score = wᵀh + b`, steering with unit-normalized `ŵ`
- Position scaling: intervention on last 20% of tokens, linearly scaled 0.5→1.0
- Layer selection: held-out CV sweep
- Median-split binary labels for probe training
- Coarse-grid + bracketed binary-search for lambda calibration

### Probes folder layout

```
Probes/
├── config.py              model/layer/grid/seed constants
├── models.py              HF Transformers loader + activation hooks
├── probes.py              probe training + scoring + steering hook
├── calibration.py         coarse-grid + binary-search lambda solver
├── judge.py               GPT-5 creativity scorer
├── tasks/                 prompt strings, preference & capability decoding
├── experiments/           per-model experiment scripts
├── aggregator.py          consolidate JSONLs into probe-results JSON
├── run_all.py             orchestrator
└── figures/               generated figure exports
```

Full Probes details: [`Probes/README.md`](Probes/README.md)

---

## Shared Dependencies

Both pipelines target **Python 3.10–3.13** and share the following key
dependencies (installed separately in each subdirectory):

- `meta-llama/Llama-3.3-70B-Instruct` (gated — requires `HF_TOKEN`)
- `Goodfire/Llama-3.3-70B-Instruct-SAE-l50` (SAE only)
- EDSL framework
- PyTorch / Transformers

## Public Release Safety

Neither subdirectory should contain `.env` files, API keys, model caches, or
browser data. The SAE subdirectory includes its own
`tests/verify_no_secrets.py` check.
