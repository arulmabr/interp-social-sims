# PROVENANCE.md — S0.2

One row per rendered figure, per Table 1, and per inline number named in the plan.

**How to read the "paper figure" column.** The repository contains no LaTeX source and no
figure-number manifest, so the mapping from rendered PNG to the paper's Figure *k* is **inferred** from
`PAPER_AUDIT.md`'s descriptions plus the `cleaned/README.md` routing table. Rows where the inference is
not forced are marked `?`. Confirming this mapping is an **AUTHOR DECISION** and the cheapest single
thing the authors can hand back at Gate S0; every S4 patch depends on it.

"Regenerable today" means: on this machine, CPU only, from files in this repository, with no model
weights and no API call.

---

## 1. Figures

| paper fig (inferred) | rendered file | generating script | input data | stack | regenerable today | notes |
|---|---|---|---|---|---|---|
| 1 | `figures/sae_schematic.png` | — hand-drawn | — | — | **no** | Not produced by any script. Its equation replaces `h` with the SAE reconstruction; the code adds the error back (`STACK_AUDIT.md` §4). PAPER_AUDIT §4.4. |
| 2 | `figures/probe_schematic.png` | — hand-drawn | — | — | **no** | Depicts a probe trained on synthetic altruism statements. No such training set exists (`PROBE_PROVENANCE.md` §3). |
| 3A | `5_conditions.png` | `cleaned/regenerate_all_figures.py::plot_5_conditions` | `behavioral_games_combined.csv`, 5 hosted conditions | A | **yes** | Source of truth is `SAE/data/raw/games/safe_risky/results_20251008_225522/`. |
| 3B ? | `figures/ultimatum_game.png`, `preference.png` | `plot_ultimatum_game`, `plot_preference` | same CSV, 3 hosted conditions | A | **yes** | |
| 3 (lottery panel, alt) ? | `figures/safe-vs-risky.png` | `plot_safe_vs_risky` | same | A | **yes** | Three-condition variant of 3A. |
| 4 | `figures_llama/figure7.png` | `plot_probe_psychometric` | `probe_results_combined.csv`, `figure_7_psychometric_curves_llama` | C | **yes** | Plots `plotted_fraction_*`, a fitted logistic, not the measured fractions — see §3. |
| 5 | `figures_multijudge/{brick,stapler}_final_score_multijudge.png` | `plot_mj_final_score` | multi-judge slice of `creativity_evals_combined.csv` | A (responses), 5 judges | **yes** | Error bars = SEM over the 40 responses within judge×condition. |
| 5 (dimensions) | `figures_multijudge/{brick,stapler}_dimensions_multijudge.png` | `plot_mj_dimensions` | same | same | **yes** | |
| 5 (agreement) | `figures_multijudge/sae_creativity_agreement_heatmap.png` | `plot_mj_agreement` | same | same | **yes** | |
| 6 | `probe_capability_target_vs_achieved_combined.png` | `plot_probe_capability_combined` | `figure_9_capability_{brick,stapler}…` | C | **yes** | Achieved values in `MANIFEST.csv:S0.D.creativity.achieved.*`. |
| 6A ? | `figures_llama/figure9_Gpt5.png`, `figure9.png` | `plot_capability_brick` | `figure_9_capability_brick…` | C | **yes** | `figure9.png` is a *proxy*: the original judge's scores are missing, so the GPT-5 scores are plotted under the plain name. Flagged in the script's own header. |
| 7 ? | `figures_llama/figure10_GPT5.png`, `figure10.png` | `plot_capability_four_objects` | `figure_10_capability_four_objects…` | C | **yes** | Same proxy caveat. |
| 9 ? | `figures_llama/figure13a*.png`, `figure13b*.png` | `plot_crossgen_bar`, `plot_crossgen_profile` | `figure_13_cross_object_generalization_llama` | C | **yes** | Only 8 aggregate rows survive; the per-seed fits do not. PAPER_AUDIT §6 (App. B.8 vs Fig. 9 protocols). |
| 10a, 10b | `figures_llama/figure11.png` | `plot_dose_response` | `figure_11_dose_response_lottery_ultimatum_llama` | C | **yes** | λ is negative in the data and rising in the figure: the figure plots −λ or \|λ\|. |
| 11 | `figures_llama/figure12.png` | `plot_activation_tracking` | `figure_12_probe_scores_track_target…` | C | **yes, but see §4** | The shipped values are not reproducible by the shipped script. |
| 14 ? | `figures/figure5.png` | `plot_probe_psychometric` | `figure_14_psychometric_curves_qwen` | C (Qwen) | **yes** | |
| 15 ? | `figures/dose_response_lambda.png` | `plot_dose_response` | `figure_17_dose_response…_qwen` (cleaned key) | C (Qwen) | **yes** | Caption cross-reference error, PAPER_AUDIT §2.10. |
| 16 | `figures/figd_brick.png` | `plot_capability_brick` | `figure_15_capability_brick_target_vs_achieved_qwen` (cleaned key) | C (Qwen) | **yes** | **Q9 settled**: it is Qwen data, single-judge. See §5. |
| 17 ? | `figures/figd.png`, `figures/figd_appendix.png` | `plot_capability_four_objects` | `figure_16_capability_four_objects…_qwen` | C (Qwen) | **yes** | Two files, identical content, appendix copy. |
| 18 ? | `figures/figc.png` | `plot_activation_tracking` | `figure_18_probe_scores_track_target_qwen` | C (Qwen) | **yes, but see §4** | |
| 18 ? | `figures/crossgen_bar.png`, `crossgen_profile.png` | crossgen plotters | `figure_19_cross_object_generalization_qwen` | C (Qwen) | **yes** | |
| §4.1 feature panels | `preference_activations.png`, `combined_lottery_ultimatum_grid.png` | `plot_feature_rank_grid` | `feature_activations_combined.csv` | A | **yes** | |
| §4.1 feature panels | `activation_grid_top5.png`, `top5_task_condition.png`, `capability_activations.png` | `plot_feature_top5_bars` | same | A | **yes** | |
| capability bars | `capability.png` | `plot_capability_bar` | single-judge slice | A | **yes** | Error bars here are **SD**, while Fig. 5's are **SEM**. Both appear in the paper. |
| not in paper | `figures_revised_prompting/*.png` (8 files) | `plot_rp_*`, `plot_mj_final_score_delta` | vLLM rows | B | **yes** | The prompting-ladder results the abstract refers to. Q6. |

---

## 2. Table 1

Not produced by any script in the repository. It is a qualitative comparison table (cost, data needs,
recommendation). Nothing to regenerate; the audit's two objections (§4.9: SAE training cost listed as a
limitation although nothing was trained; §6: the recommendation contradicts the Limitations section) are
editorial. **Regenerable: n/a.**

---

## 3. `plotted_fraction_*` is a fitted curve, not the data

`Probes/tasks/preference.py::logistic_smooth` returns
`1/(1+exp(-slope·(x − switching_point)))` with the slope taken from `config` or from
`fit_logistic_slope`, and the centre **pinned at the calibrated target**. The psychometric figures plot
this column, and `raw_fraction_*` — the measured proportion — sits beside it unplotted.

This matters for three reasons and should be stated in the paper:

1. The smoothness of Figs. 4/14 is assumed, not observed. A curve that is not logistic cannot show it.
2. The curve is centred on the *target*, so a calibration miss is invisible in the figure.
3. Both columns are in the CSVs, so S1.3 can plot the measured fractions with intervals at no cost.

---

## 4. Fig. 11 / Fig. 18: the numbers and the script disagree (Q3)

`Probes/experiments/probe_tracking_llama.py` computes the tracked score as
`probe.score(model.capture_activations(r["prompt"], probe.layer))`, **outside** the
`steering_at` context. The prompt grid is the same for every target. A deterministic score over an
identical prompt set must therefore be identical across targets, so the `all` subset should be a flat
line.

It is not. The shipped `all` values fall monotonically from 0.721 at target 40 to 0.280 at target 240,
a spread of 0.442 (`S0.D.tracking.all_subset.spread.llama_l48`; Qwen 0.257).

Two readings, and the repository cannot choose between them:

- the logged numbers were produced by an earlier version that scored **with the hook active** (the
  decline is well fitted by a line in λ, R² 0.91), in which case the figure is fine and the shipped
  script is stale; or
- the shipped script is what ran, in which case the `all` series cannot be what its label says.

Either way the provenance of Fig. 11 and Fig. 18 is **unverifiable from this repository**, and the
"probe scores track the target" claim rests on it. S2 resolves this with one forward pass. Until then no
patch should assert which token positions the score was read at.

---

## 5. Inline numbers

| number as printed | what the repo gives | MANIFEST id | regenerable | note |
|---|---|---|---|---|
| probe held-out accuracy **82%** | — | — | **no** | No probe artefact, no CV record (`PROBE_PROVENANCE.md` §4). Only a GPU rerun can produce a number, and it would be a *new* number. |
| capability probe **≈85%**, **≈92%** | — | — | **no** | Same. §2 of `PROBE_PROVENANCE.md` explains why a high number is expected regardless. |
| switching point **125** (unsteered) | **127.6** | `S0.A.lottery.switch.hosted.baseline` | **yes** | Stack A. Rounding, fine. |
| ultimatum threshold **≈38** | **38.1** | `S0.A.ultimatum.threshold.hosted.baseline` | **yes** | |
| switching point **20** (persona) | **19.8** | `S0.A.lottery.switch.hosted.slightly_prompting` | **yes** | |
| switching point **50** ? | **59.1** (`steering`), **64.8** (`lite_steering`) | `S0.A.lottery.switch.hosted.{steering,lite_steering}` | **yes** | Neither is 50. If "50" refers to the pivot's onset rather than the 50% crossing, say so. |
| switching point **30**, **10** ? | probe targets 30 and the ultimatum persona 13.3 | `S0.A.ultimatum.threshold.hosted.prompting` | **partly** | The mapping of these two to conditions is not determined by the repo; authors to confirm. |
| **5.57 vs 5.18** | single-judge brick: steering **5.281** vs baseline **5.194**; five-judge brick: **4.771** vs **5.003** | `S0.E.single_judge.mean.*`, `S0.E.multi_judge.mean5.*` | **no, as printed** | No slice of any CSV yields 5.57/5.18. The baseline is close to 5.19; the steering figure is not close to 5.57 in either scoring. **Flagged for the authors.** |
| **6.25 vs 5.23** | single-judge stapler: **5.919** vs **5.438**; five-judge stapler: **6.284** vs **5.834** | same | **no, as printed** | 6.25 is near the five-judge steering mean 6.284 and near Claude's 6.250; 5.23 matches no baseline. Probably a mixed-provenance pair. **Flagged.** |
| Spearman **0.77**, range **0.68–0.85** | **0.7695**, range **0.675–0.849** | `S0.E.spearman.*` | **yes** | Exact. But it is pooled over all 680 responses, **all four conditions and both tasks**, which is what inflates it (PAPER_AUDIT §2.5). Pooling is not stated in App. A.3.5. |
| judge ordering "consistent across all five judges" (App. A.3.5) | **false** | `S0.E.multi_judge.mean.*` | **yes** | Brick: Claude 4.825→4.394, GPT-5 4.831→4.681, Kimi 5.094→4.756, Gemini 4.744→4.494 all rate steering **below** baseline; DeepSeek 5.519→5.531 is flat. On brick, four of five judges order steering below baseline. PAPER_AUDIT §2.5 confirmed and strengthened. |
| high-temperature creativity "≈5.2 → ≈2.1" (PAPER_AUDIT §2.6) | brick high-temp **4.907** (five-judge), **4.956** (single) | `S0.E.*high_temperature*` | **discrepancy** | Nothing in the repository scores near 2.1. Either the paper's figure uses a slice not in `cleaned/`, or the audit's read-off is of a different panel. **Needs the authors or the PDF.** |
| length explains "up to 43%" of a judge's variance | Gemini R² **0.4318** | `S0.E.length_r2.gemini-2.5-pro` | **yes** | Range across judges 0.121 (Claude) to 0.432 (Gemini). |
| "40 agents" | 40 `subject_id`s, no other trait | — | **yes** | `agent.agent_instruction` is empty in every logged row; the persona conditions add one `personality` string shared by all 40. PAPER_AUDIT §4.5 confirmed. |

---

## 6. Judge identity

| where | judge id |
|---|---|
| top-level `README.md` | `gemini-3.1-pro` (provider id `gemini-3.1-pro-preview`) |
| every data file, every run artefact | `gemini-2.5-pro` |

The data is authoritative: 680 rows per judge under `gemini-2.5-pro`. The README is wrong, and the
paper must give the id that actually scored, plus an access date, for all five
(PAPER_AUDIT §1.3). Model ids in the data: `gpt-5`, `claude-sonnet-4-6`, `gemini-2.5-pro`,
`moonshotai/Kimi-K2.6`, `deepseek-ai/DeepSeek-V4-Pro`.

## 7. Judge failures

47 logged failures, all `score_returned_none`, all Claude
(`S0.E.judge_errors`). All were retried: every judge ends with exactly 680 rows
(`S0.E.multi_judge.rows_per_judge`), and no `final_score` is blank. Nothing was silently dropped. This
should be one sentence in the appendix rather than an unexplained `errors.jsonl` in the supplement.
