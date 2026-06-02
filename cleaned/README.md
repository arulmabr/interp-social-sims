# `cleaned/` — single source of truth for every paper figure

This folder holds **all the data** and **two scripts** needed to reproduce
every data-driven figure in the paper.

```
cleaned/
├── README.md                                   <-- you are here
│
├── behavioral_games_combined.csv               <-- lottery + ultimatum choices
├── creativity_evals_combined.csv               <-- creativity Torrance scores
├── feature_activations_combined.csv            <-- SAE feature ranks / activations
├── feature_activations_combined_neuronpedia_labels.csv
├── feature_activations_combined_neuronpedia_label_audit.csv
├── probe_results_combined.csv                  <-- probe-steering results
│
├── integrate_new_data.py                       <-- one-shot, idempotent ETL
├── regenerate_all_figures.py                   <-- the unified figure renderer
│
├── source_csvs/                                <-- raw per-experiment CSVs
│                                                  (only kept for provenance,
│                                                  the four combined CSVs above
│                                                  are derived from these)
├── regenerated_figures/                        <-- output of regenerate_all_figures.py
│
└── *.preintegration.bak                        <-- safety backups (see §4)
```

The two scripts and four combined CSVs replace what used to be **nine**
per-experiment CSVs scattered across `SAE/`, `Probes/`, `Revised Prompting/`
and `all_data_and_results/`. Everything a re-runner needs lives here.

---

## 1. Quick start

```bash
# (Optional, one-shot, idempotent — only needed if you pulled fresh data from
#  Revised Prompting/ and Probes/runs/mj_creativity_extra/ and want it merged.)
python3 cleaned/integrate_new_data.py

# Render every paper figure into cleaned/regenerated_figures/ (43 PNGs).
python3 cleaned/regenerate_all_figures.py
```

The output mirrors the `mech_interp/` layout, so each regenerated PNG drops
into the paper's `figures*/` subfolder at the same relative path:

```
cleaned/regenerated_figures/
├── *.png                            (9 top-level figures)
├── figures/*.png                    (10 Qwen appendix figures)
├── figures_llama/*.png              (11 Llama probe figures)
├── figures_multijudge/*.png         (5 5-judge creativity figures)
└── figures_revised_prompting/*.png  (8 few-shot/CoT figures)
```

To push the freshly-rendered PNGs into the paper itself, copy them on top of
`mech_interp/figures*/*.png` — the matching files are pixel-identical to what
the paper currently ships.

---

## 2. Data files

The four "combined" CSVs are the only inputs the figure script reads.

### 2.1 `behavioral_games_combined.csv`  (≈73 MB, 27,760 rows × 60 cols)

Lottery (safe-vs-risky) and Ultimatum game per-agent choices. Two generations
of rows live here side-by-side, distinguished by the value in
`treatment_condition`:

| `treatment_condition` | Provenance | Used by figure(s) |
|---|---|---|
| `baseline` | original Goodfire SAE-steering pipeline | preference, 5_conditions, capability, probe_*, … |
| `slightly_prompting`, `barely_prompting` | original Goodfire prompting variants | preference, 5_conditions |
| `steering`, `lite_steering` | original Goodfire SAE steering | preference, 5_conditions, capability |
| `baseline_rp` | local vLLM @ fp16 (Revised-Prompting run) — kept separate so it does NOT silently average with the Goodfire baseline | revised-prompting plots (Group 4) |
| `persona`, `cot`, `fewshot` | vLLM Revised-Prompting run | revised-prompting plots (Group 4) |
| `fewshot_cot_dose000` … `_dose100` | vLLM dose sweep, 5 levels | revised-prompting plots (Group 4) |

Key columns:

| column | meaning |
|---|---|
| `game` | `lottery` or `ultimatum` |
| `treatment_condition` | see table above |
| `offer_amount` | the reward / offer presented to the agent, in tokens (5–180 step 5 for lottery; 5–90 step 5 for ultimatum) |
| `source_file` | filename of the raw per-condition CSV that the row came from (e.g. `safe_risky_baseline_10.csv` or `safe_risky_strong_prompting`) |
| `answer.safe_risky_choice` | `Safe Option` / `Risky Option` (lottery only) |
| `answer.ultimatum_response` | `Accept` / `Reject` (ultimatum only) |
| `agent.agent_index`, `agent.subject_id`, `agent.agent_name` | 40 unique agents per cell |
| `model.model`, `model.temperature`, `model.inference_service` | inference provenance |
| `prompt.*_system_prompt`, `prompt.*_user_prompt` | exact prompts shown to the model |
| `generated_tokens.*` | raw model output |
| `comment.*` | the model's free-form comment portion (the line after the choice) |
| `validated.*` | parse OK? |

### 2.2 `creativity_evals_combined.csv`  (≈13 MB, 3,720 rows × 22 cols)

Per-response creativity Torrance scores (4 dimensions + final). Two
generations of rows live here side-by-side, distinguished by
`eval_prompt_version`:

| `eval_prompt_version` | What this slice contains |
|---|---|
| `torrance_four_dimension_v1` | **Original 320 rows.** Single-judge GPT-5 eval of the SAE-steering creativity responses (brick + stapler × 4 conditions × 40 agents). Used by `capability.png`. |
| `torrance_four_dimension_length_controlled_v1` | **3,400 multi-judge rows.** 680 unique responses scored by 5 judges (GPT-5, Claude Sonnet 4.6, Gemini 2.5 Pro, Kimi K2.6, DeepSeek V4 Pro), with a length-controlled rubric. Spans three datasets — see `source_file` below. Used by all `figures_multijudge/*` and the two `creativity_*_multijudge_final_score_delta_vs_baseline` figures. |

`source_file` values for the multi-judge slice tell you which generation
pipeline produced the responses being scored:

| `source_file` | Response provenance | `condition` values |
|---|---|---|
| `open_sae_creativity` | original SAE-steering creativity run (same 320 responses as the single-judge slice, just re-scored by 5 judges) | `baseline`, `prompting`, `high_temperature`, `high_steering` |
| `revised_prompting_brick` | vLLM Revised-Prompting brick run | `baseline_rp`, `persona`, `cot`, `fewshot`, `fewshot_cot` |
| `revised_prompting_stapler` | vLLM Revised-Prompting stapler run | `baseline_rp`, `persona`, `cot`, `persona_cot` |

(As with the behavioural data, the revised-prompting baseline is tagged
`baseline_rp` so it never silently averages with the open-SAE baseline.)

Key columns:

| column | meaning |
|---|---|
| `task` | `detailed_ways_to_use_a_brick` (divergent creativity) or `improve_the_stapler_with_many_specific_enhancements` (product innovation) |
| `condition` | see tables above |
| `condition_label` | human-readable form (`Baseline`, `Few-shot + CoT`, …) |
| `source_file` | which dataset this row came from (see table above) |
| `agent_index`, `subject_id`, `agent_name` | 40 agents per cell |
| `response_text` | the actual model-generated response that was judged |
| `fluency`, `flexibility`, `originality`, `elaboration` | the four Torrance dimensions, 1–10 |
| `final_score` | mean of the four dimensions |
| `evaluator_model` | which judge produced this row (`gpt-5`, `claude-sonnet-4-6`, …) |
| `eval_prompt_version` | rubric version (see table above) |
| `raw_evaluator_json` | the judge's raw structured output |

### 2.3 `probe_results_combined.csv`  (≈22 MB, 33,598 rows × 46 cols)

Every probe-steering result — psychometric curves, dose-response calibration,
activation tracking, capability target-vs-achieved, cross-object
generalisation — for both Llama-3.3-70B and Qwen-2-7B. Figures are keyed by
the `source_figure` column, e.g.:

| `source_figure` | Figure |
|---|---|
| `figure_7_psychometric_curves_llama` | `figures_llama/figure7.png` |
| `figure_9_capability_brick_target_vs_achieved` | `figures_llama/figure9_Gpt5.png` |
| `figure_10_capability_four_objects_target_vs_achieved` | `figures_llama/figure10_GPT5.png` |
| `figure_11_dose_response_lottery_ultimatum_llama` | `figures_llama/figure11.png` |
| `figure_12_probe_scores_track_target_lottery_ultimatum_llama` | `figures_llama/figure12.png` |
| `figure_13_cross_object_generalization_llama` | `figures_llama/figure13a*.png`, `figure13b*.png` |
| `figure_14_psychometric_curves_qwen` | `figures/figure5.png` |
| `figure_15_capability_brick_target_vs_achieved_qwen` | `figures/figd_brick.png` |
| `figure_16_capability_four_objects_target_vs_achieved_qwen` | `figures/figd.png`, `figures/figd_appendix.png` |
| `figure_17_dose_response_lottery_ultimatum_qwen` | `figures/dose_response_lambda.png` |
| `figure_18_probe_scores_track_target_qwen` | `figures/figc.png` |
| `figure_19_cross_object_generalization_qwen` | `figures/crossgen_*.png` |

Top-level routing column:

| column | meaning |
|---|---|
| `probe_group` | `lottery` / `ultimatum` / `creativity` — the high-level experiment family |
| `source_figure` | exact figure key (see table above) |
| `data_section` | within-row role: typically `data` for the smoothed/aggregate series used in the figure |
| `model` | `Llama-3.3-70B-Instruct` or `Qwen-2-7B-Instruct` |
| `experiment_type` | `probe_steering_psychometric`, `_dose_response_calibration`, `_capability_target_vs_achieved`, `_activation_tracking`, `_cross_object_generalization` |

Common per-experiment columns:

| column | used by | meaning |
|---|---|---|
| `target_switching_point_tokens` | psychometric, dose-response, activation | target reward (in tokens) the probe steers the agent toward |
| `lambda_calibrated` / `lambda_required` | dose-response, capability | calibrated steering strength to hit the target |
| `risky_reward_tokens` / `offer_amount_tokens` | psychometric | x-axis of the psychometric curve |
| `raw_fraction_*` / `plotted_fraction_*` | psychometric | aggregate fraction of agents picking risky / accepting |
| `mean_probe_activation` | activation tracking | mean probe score over the chosen agent subset |
| `choice_subset` | activation tracking | `all` / `risky` / `safe` / `accept` / `reject` |
| `target_creativity_score`, `creativity_score`, `scores_*` | capability | requested vs achieved creativity, per-dim and final |
| `object`, `train_object`, `test_object`, `split_type` | cross-object | per-object accuracy + in-distribution vs cross-object split |
| `mean_score`, `std_score`, `n_runs` | cross-object | aggregate probe accuracy stats |

### 2.4 `feature_activations_combined.csv`  (≈7 MB, 62,340 rows × 8 cols)

Per-agent SAE feature activations (lottery + ultimatum) and per-task top-k
activation strengths (brick + stapler creativity).

| column | meaning |
|---|---|
| `source` | `lottery`, `ultimatum`, or `product_innovation_folder` (the latter holds BOTH brick and stapler creativity rows; the `task` column further splits them) |
| `task` | for behavioural rows: `safe_risky_choice` / `ultimatum_response`; for creativity rows: `detailed_ways_to_use_a_brick` / `improve_the_stapler_with_many_specific_enhancements` |
| `condition` | the experimental condition (`baseline`, `prompting`, `slightly_prompting`, `steering`, `high_temperature`, `high_steering`, …) |
| `offer_amount` | only for behavioural rows; the offer/reward value |
| `agent_index` | 0..39 |
| `rank` | for behavioural rows: 1..K rank of this feature among all activated features for that agent×offer |
| `feature_label` | human-readable label of the SAE feature (mostly Goodfire's original explanations) |
| `activation` | activation strength of the feature |

Used by `preference_activations.png` / `combined_lottery_ultimatum_grid.png`
(rank grids, top-10 per condition × game) and the three creativity feature
panels (`activation_grid_top5.png` / `top5_task_condition.png` /
`capability_activations.png`).

### 2.5 `feature_activations_combined_neuronpedia_labels.csv` (≈5 MB, 62,340 rows × 8 cols)

Drop-in replacement for `feature_activations_combined.csv` where the
`feature_label` column has been rewritten to use the Neuronpedia
auto-explanations for the same feature indices, rather than Goodfire's
original labels. **Not used by the paper figures.** Provided so re-runners
can A/B the two label sets.

### 2.6 `feature_activations_combined_neuronpedia_label_audit.csv` (106 rows × 9 cols)

The 1-to-1 mapping table behind the relabelling, with cosine-similarity
confidence buckets. Useful for sanity-checking individual relabels.

| column | meaning |
|---|---|
| `old_goodfire_label` | original Goodfire feature label as it appears in `feature_activations_combined.csv` |
| `replacement_feature_label` | Neuronpedia auto-explanation |
| `replacement_status` | `approximate_neuronpedia_explanation_search_top1` if the relabel came from a top-1 nearest-neighbour search |
| `feature_index` | SAE feature index (Llama-3.3-70B SAE @ resid-post layer 50, Goodfire variant) |
| `neuronpedia_api_url` | clickable URL for the feature's Neuronpedia page |
| `approx_cosine_similarity` | similarity of Goodfire's label to Neuronpedia's |
| `approx_confidence_bucket` | `high_semantic_similarity` / `medium_semantic_similarity` / `low_semantic_similarity` |
| `paper_row_count` | how many rows in the combined feature CSV this relabel touches |

### 2.7 `source_csvs/`

The original nine per-experiment CSVs that the four combined CSVs were
derived from, kept here only for provenance / spot-checking:

| file | now folded into |
|---|---|
| `safe_risky_combined.csv`, `ultimatum_combined.csv` | `behavioral_games_combined.csv` |
| `divergent_creativity_combined_results.csv`, `divergent_creativity_full.csv`, `product_innovation_combined_results.csv` | `creativity_evals_combined.csv` (original-eval slice) |
| `lottery_probe_results.csv`, `ultimatum_probe_results.csv`, `divergent_creativity_probe_results.csv`, `product_innovation_probe_results.csv` | `probe_results_combined.csv` |

None of the scripts in this folder read from `source_csvs/`. They are kept
only so you can verify how the four combined CSVs were built.

---

## 3. Scripts

### 3.1 `regenerate_all_figures.py` — the renderer

Reads ONLY the four combined CSVs (and the two NeuronPedia auxiliaries are
optional). Writes 43 PNGs into `cleaned/regenerated_figures/` arranged in the
same subfolder layout as `mech_interp/`. The script is internally organised
into five "Groups":

| Group | What it plots | Slice it reads |
|---|---|---|
| **G1** Behavioural psychometric curves & capability bars | `preference.png`, `5_conditions.png`, `safe-vs-risky.png`, `ultimatum_game.png`, `capability.png` | original Goodfire rows of `behavioral_games_combined.csv` + single-judge GPT-5 slice of `creativity_evals_combined.csv` |
| **G2** Probe-steering plots | `figures_llama/figure7.png`, `figure9*`, `figure10*`, `figure11`, `figure12`, `figure13*`, plus Qwen counterparts in `figures/` | `probe_results_combined.csv` |
| **G3** SAE feature-activation plots | `preference_activations.png`, `combined_lottery_ultimatum_grid.png`, `activation_grid_top5.png`, `top5_task_condition.png`, `capability_activations.png` | `feature_activations_combined.csv` |
| **G4** Revised-Prompting behavioural plots (few-shot / CoT / persona) | `figures_revised_prompting/{lottery,ultimatum}_*.png` (3 each: psychometric, dose-response, Δ-vs-baseline) | revised-prompting rows of `behavioral_games_combined.csv` (`baseline_rp` + cot/fewshot/persona + `fewshot_cot_dose000..100`) |
| **G5** Multi-judge creativity plots | `figures_multijudge/{brick,stapler}_*_multijudge.png`, `sae_creativity_agreement_heatmap.png`, and the two `creativity_{brick,stapler}_multijudge_final_score_delta_vs_baseline.png` files in `figures_revised_prompting/` | multi-judge slice of `creativity_evals_combined.csv` |

**Cross-plot colour alignment.** The script enforces ONE canonical
condition→colour map across every figure:

| Condition / family | Colour | Hex |
|---|---|---|
| `baseline` / `baseline_rp` (control) | navy | `#27286B` |
| `prompting` / `persona` (basic prompt engineering) | orange | `#E8804B` |
| `cot` (prompting-family, warm variant) | burnt sienna | `#C0442D` |
| `fewshot` (prompting-family, warm variant) | goldenrod | `#D4A017` |
| `fewshot_cot_dose100` (strongest prompting intervention) | deep red | `#970026` |
| `fewshot_cot_dose 0%→100%` sweep | warm sequential | `YlOrRd(0.30→0.95)` |
| `sae_steering` / `steering` / `lite_steering` / `high_steering` | teal | `#1FA8A8` |
| `probe_steering` | purple | `#7B3FA0` |
| `high_temperature` | coral red | `#D6453D` |

Prompting-family conditions always live in the warm half of the palette;
SAE-steering family always teal; probe-steering always purple. So a reader
can tell at a glance from the colour alone what kind of intervention each
line / bar represents, across every figure in the paper.

### 3.2 `integrate_new_data.py` — the one-shot ETL

Appends two new generations of data into the combined CSVs **without
deleting anything**:

1. **Revised-Prompting behavioural data** (`Revised Prompting/runs_fp16/runs/{safe_risky_full,ultimatum_full}/behavior_units.csv`)
   → +18,720 rows appended to `behavioral_games_combined.csv`.
2. **Multi-judge creativity scores** (`Probes/runs/mj_creativity_extra/multi_judge_scores.jsonl` + the matching responses in `input.jsonl`)
   → +3,400 rows appended to `creativity_evals_combined.csv`.

The script is **idempotent**: every appended row carries a stable dedup key,
so re-running it adds 0 rows. You only need to re-run it if you've pulled
fresh upstream data from `Revised Prompting/` or `Probes/runs/mj_creativity_extra/`.

---

## 4. Safety backups

The first time `integrate_new_data.py` was run, it left these two backup
copies of the pre-integration CSVs:

```
cleaned/behavioral_games_combined.csv.preintegration.bak    (~22 MB, 9,040 rows)
cleaned/creativity_evals_combined.csv.preintegration.bak    (~512 KB, 320 rows)
```

If you ever want to roll back to the pre-integration state:

```bash
cp cleaned/behavioral_games_combined.csv.preintegration.bak \
   cleaned/behavioral_games_combined.csv
cp cleaned/creativity_evals_combined.csv.preintegration.bak \
   cleaned/creativity_evals_combined.csv
```

You can safely delete these backups once you're confident the integrated
data is correct; everything in them is bit-identically reproducible by
re-running `integrate_new_data.py`.

---

## 5. Common slice recipes

### Original (pre-Revised-Prompting) behavioural rows only

```python
import pandas as pd
df = pd.read_csv("cleaned/behavioral_games_combined.csv", low_memory=False)
ORIGINAL_LOTTERY = {"baseline", "barely_prompting", "slightly_prompting",
                    "lite_steering", "steering"}
ORIGINAL_ULT     = {"baseline", "prompting", "steering"}
df = df[((df.game == "lottery")   & df.treatment_condition.isin(ORIGINAL_LOTTERY)) |
        ((df.game == "ultimatum") & df.treatment_condition.isin(ORIGINAL_ULT))]
```

### Revised-Prompting rows only

```python
REVISED = {"baseline_rp", "cot", "fewshot", "persona",
           "fewshot_cot_dose000", "fewshot_cot_dose025",
           "fewshot_cot_dose050", "fewshot_cot_dose075",
           "fewshot_cot_dose100"}
df = df[df.treatment_condition.isin(REVISED)]
```

### Original single-judge GPT-5 creativity evals only

```python
df = pd.read_csv("cleaned/creativity_evals_combined.csv", low_memory=False)
df = df[df.eval_prompt_version == "torrance_four_dimension_v1"]
# 320 rows: 2 tasks × 4 conditions × 40 agents
```

### Multi-judge creativity evals only

```python
df = df[df.eval_prompt_version == "torrance_four_dimension_length_controlled_v1"]
# 3,400 rows. Filter by source_file for the dataset:
#   "open_sae_creativity"        -> same responses as the single-judge slice
#   "revised_prompting_brick"    -> new vLLM brick responses
#   "revised_prompting_stapler"  -> new vLLM stapler responses
```

### Probe results for a specific figure

```python
df = pd.read_csv("cleaned/probe_results_combined.csv", low_memory=False)
fig7 = df[(df.source_figure == "figure_7_psychometric_curves_llama") &
          (df.data_section == "data")]
```
