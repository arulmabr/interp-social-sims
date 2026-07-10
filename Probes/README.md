# Probe Pipeline (Final)

The pipeline for the probe-based steering experiments (figures 7, 9-19).
Running it end-to-end produces the per-trial logs and the aggregated
`probe_results_final.json` that the probe figures are plotted from.

## What this implements

For each of two base models (`Llama-3.3-70B-Instruct`, `Qwen-2-7B-Instruct`):

1. **Data generation** — sweep task parameters, record baseline
   choices, capture layer-`l` hidden states as `(activation, binary_label)`
   pairs.
2. **Probe training** — fit `l2`-regularized logistic regression with
   cross-validated layer + regularization sweep. Pick best held-out layer.
3. **Lambda calibration** — coarse grid then bracketed binary search to find
   the steering strength that hits each target switching point / acceptance
   threshold / creativity score.
4. **Steered experiments** — replay each task with the probe-steering hook
   applied at the calibrated lambda. Log every per-agent trial.
5. **Creativity scoring** — GPT-5 judge via EDSL `QuestionLinearScale`
   produces per-dimension scores (fluency, flexibility, originality,
   elaboration); mean is the per-trial creativity score.
6. **Cross-object generalization** — train on subset of objects, evaluate
   on held-out object.
7. **Aggregation** — combine all per-trial JSONL logs into one JSON with the
   13 figure keys.

## Folder layout

```
Probes/
├── README.md              # this file
├── requirements.txt
├── config.py              # model/layer/grid/seed constants
├── models.py              # HF Transformers loader + activation hooks
├── probes.py              # probe training + scoring + steering hook
├── calibration.py         # coarse-grid + binary-search lambda solver
├── judge.py               # GPT-5 creativity scorer
├── tasks/
│   ├── __init__.py
│   ├── prompts.py         # exact prompt strings + parsing
│   ├── preference.py      # lottery + ultimatum decoding loop
│   └── capability.py      # brick / stapler / paperclip / bowl decoding loop
├── experiments/
│   ├── __init__.py
│   ├── psychometric_llama.py
│   ├── capability_llama.py             # run_brick + run_stapler_product_innovation
│   ├── four_objects_llama.py
│   ├── dose_response_llama.py
│   ├── probe_tracking_llama.py
│   ├── cross_object_llama.py
│   ├── psychometric_qwen.py
│   ├── dose_response_qwen.py
│   ├── probe_tracking_qwen.py
│   ├── brick_capability_qwen.py        # reuses capability_llama.run_brick
│   ├── four_objects_qwen.py            # reuses four_objects_llama
│   └── cross_object_qwen.py            # reuses cross_object_llama
├── aggregator.py          # consolidate JSONLs into the probe-results JSON
└── run_all.py             # orchestrator
```

## Output JSON structure

Top-level keys (one per probe figure):

```
figure_7_psychometric_curves_llama          (Llama, layer 48, lottery+ultimatum)
figure_9_capability_brick_target_vs_achieved
figure_9_capability_stapler_product_innovation_target_vs_achieved
figure_10_capability_four_objects_target_vs_achieved
figure_11_dose_response_lottery_ultimatum_llama
figure_12_probe_scores_track_target_lottery_ultimatum_llama
figure_13_cross_object_generalization_llama
figure_14_psychometric_curves_qwen          (Qwen, layer 17)
figure_15_dose_response_lottery_ultimatum_qwen
figure_16_probe_scores_track_target_qwen
figure_17_capability_brick_target_vs_achieved_qwen
figure_18_capability_four_objects_target_vs_achieved_qwen
figure_19_cross_object_generalization_qwen
```

Each figure entry has `figure_name`, `experiment_type`, `metadata`, `data`,
and (for psychometric figures) `per_agent_rows` + `row_count`.

## Hardware + cost

- Llama-3.3-70B-Instruct: 2x H100 (80 GB) or 4x A100 (40 GB), bf16
- Qwen-2-7B-Instruct: 1x A100 or any 24 GB GPU
- GPT-5 judge: ~10K-20K calls total for all capability figures, ~$50-100

Roughly:
- Llama full pipeline: ~12-18 GPU-hours
- Qwen full pipeline: ~3-5 GPU-hours
- Judge scoring: ~2 hours wallclock

## Quick run

```bash
pip install -r Probes/requirements.txt
export OPENAI_API_KEY=...                 # for the GPT-5 judge
export HF_TOKEN=...                       # for gated Llama weights
export ANTHROPIC_API_KEY=...              # optional multi-judge scorer
export GOOGLE_API_KEY=...                 # optional multi-judge scorer
export TOGETHER_API_KEY=...               # optional multi-judge scorer

python -m Probes.run_all \
  --model llama \
  --outdir runs/llama_final

python -m Probes.run_all \
  --model qwen \
  --outdir runs/qwen_final

# Aggregate both runs into the canonical JSON
python -m Probes.aggregator \
  --llama-run runs/llama_final \
  --qwen-run  runs/qwen_final \
  --out probe_results_final.json
```

## Multi-judge re-scoring (addresses the judge-circularity concern)

The judge layer supports five judge models across four providers:

| `judge_name`         | Provider   | Model ID                          | API key source |
|----------------------|-----------|------------------------------------|----------------|
| `gpt-5`              | OpenAI    | `gpt-5`                            | `OPENAI_API_KEY` |
| `claude-sonnet-4-6`  | Anthropic | `claude-sonnet-4-6`                | `ANTHROPIC_API_KEY` |
| `gemini-3.1-pro`     | Google    | `gemini-3.1-pro-preview`           | `GOOGLE_API_KEY` |
| `gemini-2.5-pro`     | Google    | `gemini-2.5-pro`                   | `GOOGLE_API_KEY` |
| `kimi-k2.6`          | Together  | `moonshotai/Kimi-K2.6`             | `TOGETHER_API_KEY` |
| `deepseek-v4-pro`    | Together  | `deepseek-ai/DeepSeek-V4-Pro`      | `TOGETHER_API_KEY` |

Re-score existing capability outputs (no need to regenerate responses):

```bash
python -m Probes.multi_judge_rescore \
    --in probe_results_final.json \
    --judges gpt-5 claude-sonnet-4-6 gemini-3.1-pro kimi-k2.6 deepseek-v4-pro \
    --out runs/multi_judge \
    --blind \
    --length-controlled
```

`--blind` pools and shuffles all responses before scoring. `--length-controlled`
adds a length-blind instruction to the rubric.

Outputs:
- `multi_judge_scores.jsonl`: one row per (response, judge) with the 4 Torrance sub-scores, mean creativity_score, response length, and blind-order index
- `inter_rater_agreement.json`: pairwise Spearman + mean pairwise rho across judges
- `length_regression.json`: per-judge OLS of creativity_score on log(response_length_chars) so length-confound can be inspected directly

The `--length-controlled` flag adds an explicit instruction to score on idea quality rather than length.

## Layer-matched steering control (probe layer 48 vs SAE layer 50)

The SAE interventions are applied at layer 50, but the probes are CV-selected to
layer 48, so a probe-vs-SAE steering comparison mixes a *method* difference with
a two-layer *depth* difference. `run_layer_comparison` isolates the layer: it
rebuilds the preference probes at a *fixed* layer (48 and 50 by default) with an
otherwise identical training / calibration / sweep procedure, and reports
steering efficacy (how well the achieved switching point tracks the calibration
target) for each. If the two layers steer equivalently, the head-to-head against
the layer-50 SAE reflects the method, not the depth.

```bash
# full run (mirrors the paper's psychometric settings, 40 agents/cell)
python -m Probes.run_layer_comparison --model llama --outdir runs/layer_cmp \
    --layers 48 50 --n-agents 40

# fast smoke run (few targets/agents; validates the pipeline end to end)
python -m Probes.run_layer_comparison --model llama --outdir runs/layer_cmp_fast \
    --layers 48 50 --n-agents 8 --n-agents-calib 6 \
    --lottery-targets 68 124 181 --ultimatum-targets 40 60
```

Outputs (under `runs/<outdir>/layer_comparison/`):
- `llama_layer{L}_{game}_per_agent.jsonl` / `_cells.jsonl` — per-trial + per-cell records at layer `L`
- `llama_layer{L}_calibration.json` — lambda per target, achieved switching point, probe CV accuracy
- `comparison.csv` — one row per (game, target, layer): target, calibrated lambda, achieved switching point, abs error
- `comparison_summary.json` — per-layer efficacy (RMSE / MAE / correlation) plus the cross-layer difference and an `equivalent`/`verdict` flag

The layer is pinned by rebuilding at a single fixed layer (no CV sweep), so
training, activation capture, steering, and row metadata all share that layer.

### Full layer-50 regeneration (all six affected figures)

`run_layer_comparison` covers the two preference figures needed for the
equivalence numbers. To regenerate **all six** Llama linear-probe figures at
layer 50 (for a matched-layer appendix), use `run_layer50_full`. It is purely
additive: it reuses the existing layer-48 production runners with the model
pinned to layer 50 and writes to a separate output tree; no existing module is
modified and a later layer-48 `run_all` is unaffected.

```bash
# all six (capability figures call the GPT-5 judge, as in the layer-48 run)
export OPENAI_API_KEY=...
python -m Probes.run_layer50_full --outdir runs/llama_layer50

# preference-only (Fig 4/8, 10/18, 11/19; no judge / API key needed)
python -m Probes.run_layer50_full --outdir runs/llama_layer50_pref --skip-capability
```

The six regenerated figures (May PDF / June PDF numbering) and their runner:

| Content | May | June | Runner |
|---|---|---|---|
| Preference psychometric | 4 | 8 | `psychometric_llama` |
| Probe lambda dose-response | 10 | 18 | `dose_response_llama` |
| Probe-score tracking | 11 | 19 | `probe_tracking_llama` |
| In-distribution capability control | 6 | 11 | `capability_llama` |
| Cross-object creativity | 9 | 20 | `four_objects_llama` |
| Cross-object generalization | 12 | 21 | `cross_object_llama` |

Layer 50 is pinned by locally swapping the model config to
`probe_layer=50, layer_sweep_range=(50, 50)` (the degenerate range makes the
capability runners' CV layer sweep select only layer 50); the swap is restored
in a `finally` block. Outputs use the same per-experiment subdirectories and
JSONL schema as the layer-48 run, with every row's `probe_layer = 50`, so the
existing aggregation / figure code plots the layer-50 counterparts directly.
Only the Llama probe figures are regenerated; SAE and Qwen figures are unchanged.

## Invariants (asserted by aggregator)

The aggregator enforces these on every run:

- All 13 figure keys present.
- Every per-agent row has the right fields.
- `creativity_score == mean(fluency, flexibility, originality, elaboration)`.
- `n_choosing_risky` / `n_accepting` per cell equals
  `sum(parsed_choice)` across the 40 agents at that (target, reward) pair.
- All capability rows carry both `response` and `prompt`.
- All trial seeds are deterministic and reproducible.

## Implementation notes

The probe methodology implemented here:
- Probe formulation: `score = w^T h + b`, steering with unit-normalized `w_hat`
- Position scaling: intervention applied to last 20% of tokens, scaled
  linearly from 0.5 to 1.0
- Layer selection: held-out CV sweep
- Median-split binary labels for probe training
- Coarse-grid + bracketed binary-search for lambda calibration
