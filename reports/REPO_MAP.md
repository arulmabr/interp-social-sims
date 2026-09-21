# REPO_MAP.md — S0.1

Repository: `interp-social-sims`, cloned from `github.com/arulmabr/interp-social-sims` on 2026-09-21.
Working branch: `iclr-extension`, cut from `main` at `0aeba62` ("added evals: layer-50 results merged
into raw-results files + layer-50 figures").

Nothing in this report was moved, renamed or edited. All four legacy directories are read-only.

---

## 1. Top level

| path | size | tracked | what it is |
|---|---:|---|---|
| `cleaned/` | 191 MB | yes | **The single source of truth for every paper figure.** Four combined CSVs + two scripts. |
| `Probes/` | 98 MB | yes | Probe-steering pipeline (code) and its aggregated results. |
| `Revised Prompting/` | 225 MB | yes | Prompting-ladder runs (CoT, few-shot, few-shot+CoT, ρ sweep) on a local vLLM stack. Name contains a space — quote it. |
| `SAE/` | 526 MB | yes | EDSL/Goodfire platform, the hosted-API raw game logs, and local open-SAE reruns. |
| `README.md` | 10 KB | yes | Repo overview; two pipelines, compute estimates, judge table. |
| `55998_Interpreting_and_Steerin.pdf` | 18 MB | **no** | The submitted draft (32 pp., built 2026-09-19). |
| `feedback.txt` | 72 KB | **no** | The automated review. |
| `mech_interp_paper_ICLR_extension_plan.docx` | 339 KB | **no** | The authors' plan (47 paragraphs, no tables). |
| `CLAUDE.md`, `ICLR_PLAN.md`, `PAPER_AUDIT.md` | — | **no** | Standing rules, work plan, draft audit. |

New, created by S0: `cv_bench/`, `reports/`, `logs/`, `results/S/`, `MANIFEST.csv`.

**Git.** 8 commits touch layer 50, all in July. Full history runs 2026-05-25 → **2026-07-10**. The PDF
was built 2026-09-19, so roughly ten weeks of paper work has no counterpart in this repository. Nothing
is uncommitted apart from the five untracked files above.

---

## 2. `cleaned/` — the figure renderer

Reads **only** its own four combined CSVs. This is what produced the PNGs the paper ships.

| file | rows | purpose |
|---|---:|---|
| `behavioral_games_combined.csv` (71 MB) | 27,760 | Lottery + ultimatum per-agent choices, two generations side by side (`treatment_condition` separates hosted-Goodfire rows from vLLM `*_rp` rows). Carries the verbatim system and user prompts and the raw generations. |
| `creativity_evals_combined.csv` (13 MB) | 3,720 | 320 single-judge GPT-5 rows + 3,400 five-judge rows (680 responses × 5 judges), with `response_text` and `raw_evaluator_json`. |
| `probe_results_combined.csv` (21 MB) | 33,598 | Every probe-steering result, keyed by `source_figure`. **Layer 48 only.** |
| `feature_activations_combined.csv` (6.9 MB) | 62,340 | Per-agent SAE feature ranks and activations (lottery, ultimatum) and per-task top-k (creativity). |
| `feature_activations_combined_neuronpedia_labels.csv` | 62,340 | Same table with Neuronpedia labels substituted. Not used by any figure. |
| `feature_activations_combined_neuronpedia_label_audit.csv` | 106 | Goodfire→Neuronpedia relabelling with cosine confidence buckets. |
| `source_csvs/` (47 MB) | — | The nine per-experiment CSVs the combined four were built from. No script reads them. |
| `regenerated_figures/` (28 MB) | 43 PNGs | Output, in the paper's `figures*/` layout. |

| script | lines | last commit | what it does |
|---|---:|---|---|
| `regenerate_all_figures.py` | 1,361 | 2026-06-02 | All 43 figures, five groups (G1 behavioural, G2 probe, G3 SAE features, G4 prompting ladder, G5 multi-judge). Enforces one condition→colour map. |
| `integrate_new_data.py` | 358 | 2026-06-02 | Idempotent ETL appending the vLLM behavioural rows and the multi-judge scores. Left `*.preintegration.bak` copies. |

---

## 3. `Probes/` — probe steering

| module | lines | purpose |
|---|---:|---|
| `config.py` | 207 | All grids, targets, seeds, decoding defaults, steering constants. Llama layer 48 (sweep 40–60), Qwen layer 17 (sweep 12–24). |
| `models.py` | 176 | HF loader, `capture_activations` (final prompt token, no chat template), `install_steering` (the hook). |
| `probes.py` | 157 | L2 logistic probe, CV over (layer, C), `direction_unit`, `score` (standardised projection). No steering code despite the docstring. |
| `calibration.py` | 183 | Coarse grid (includes λ=0) then bracketed binary search; switching point by linear interpolation. |
| `tasks/prompts.py` | 92 | The verbatim prompt strings and the regex parsers. |
| `tasks/preference.py` | 220 | Lottery/ultimatum sweeps; also `logistic_smooth`, which generates `plotted_fraction_*`. |
| `tasks/capability.py` | 81 | Creativity trials. |
| `experiments/_common.py` | 267 | `build_preference_probe`, `build_capability_probe`, the λ evaluators. The centre of gravity for S0.4. |
| `experiments/*.py` | 11 files | One runner per figure, Llama and Qwen. |
| `aggregator.py` | 605 | JSONL → `probe_results_final.json` (13 figure keys). |
| `aggregate_layer50_llama.py` | 349 | Merges layer-50 runs into the same schema (July work). |
| `judge.py`, `multi_judge_rescore.py` | 349 / 402 | GPT-5 scorer; five-judge blind, length-controlled rescoring. |
| `regenerate_all_figures.py` | 934 | A second, `Probes/`-local renderer. Distinct from `cleaned/`'s. |

| data | size | contents |
|---|---:|---|
| `raw_data/probe_results_final.json` | 43 MB | 20 figure keys (13 original + 7 `_layer50`). Per-agent rows for the psychometric keys only. |
| `raw_data/probe_results_combined.csv` | 37 MB | The same content flattened. **Layer 48 and layer 50 merged**, and it uses a *different* Qwen key naming than `cleaned/` (see §6). |
| `runs/mj_creativity_extra*/` | 5.7 MB | The five-judge run: `input.jsonl` (680), `multi_judge_scores.jsonl` (3,400), `inter_rater_agreement.json`, `length_regression.json`, `errors.jsonl` (47). |
| `figures/`, `raw_data/layer50_figures/` | 12 MB | Rendered PNGs. |

**Not present anywhere:** trained probe artefacts (no `.pkl`, `.pt`, `.npy`), cached activations, and the
`llama_layer{L}_calibration.json` files the Probes README describes. Consequences in `PROBE_PROVENANCE.md`.

---

## 4. `Revised Prompting/` — the prompting ladder

| path | contents |
|---|---|
| `games/*.py` | Four EDSL game specs with the strong-prompting conditions. |
| `scripts/run_local_vllm_generation.py` | The generation entry point (local vLLM). |
| `scripts/build_brick_exemplars.py`, `data/brick_exemplars.json`, `data/ocsai_brick_aut.jsonl` | Few-shot demonstrations, built from the OCSAI AUT dataset (licence and source files included). |
| `runs_fp16/runs/safe_risky_full/` | 9 conditions × 35 rewards × 40 agents. `behavior_units.csv`, `behavior_summary.csv`, `response_units.{csv,jsonl}`, `run_manifest.json`, 3 plots. |
| `runs_fp16/runs/ultimatum_full/` | 9 conditions × 17 offers × 40 agents, same layout. |
| `runs_fp16/runs/creativity_{brick,stapler}_full/` | Creativity runs with `multi_judge_plots/`. |
| `runs/srsp_*` | Mock and smoke runs. |

Conditions present in both game runs: `baseline`, `persona`, `cot`, `fewshot`,
`fewshot_cot_dose{000,025,050,075,100}`. Manifest: Llama-3.3-70B-Instruct, bfloat16,
tensor-parallel 2, temperature 0.7, top-p 1.0.

---

## 5. `SAE/` — hosted Goodfire logs and local open-SAE reruns

| path | contents |
|---|---|
| `data/raw/games/safe_risky/results_20251008_225522/` | **The source of Fig. 3A.** 175 per-cell CSVs (5 conditions × 35 rewards × 40 agents), plus `reward_experiment_summary.csv` and LDA topic files. Each CSV carries the full EDSL record including `model.controller`. |
| `data/raw/games/ultimatum/results_20251008_201139/` | **The source of Fig. 3B.** 51 CSVs (3 conditions × 17 offers). |
| `data/raw/games/trust/results/` | Trust game, 2 conditions × 10 amounts. Not in the paper. |
| `data/raw/creativity/product_innovation_20251102_202650/` | Brick + stapler, 4 conditions × 40 agents: `baseline.csv`, `prompting.csv`, `high_steering.csv`, `high_temperature.csv`. |
| `data/processed/` | Feature-description lookup (1,920 rows), steering provenance, four paper-activation audits. |
| `runs/` (237 MB) | Twelve local open-SAE runs: lottery steering (full + lite), ultimatum, trust, creativity (smoke + 40-agent), a dose sweep, and the five-condition inspection. Each has `response_units.csv`, `open_sae_steering_metadata.json`, `open_sae_steering_trace.jsonl`. |
| `scripts/` (18 files) | `run_open_sae_feature_inspection.py` (2,853 lines), `run_open_sae_steering_generation.py`, `run_open_sae_dose_sweep.py`, `extract_steering_provenance.py`, five audit builders, `build_release_zip.py`. |
| `docs/` | `STEERING.md` (the intervention semantics), `LABELS.md`, `DATA.md`, `REPRODUCTION.md`, `GPU_REGENERATION_ROADMAP.md`. |
| `tests/` | `verify_no_secrets.py`, `verify_release_anonymity.py`, `verify_release_artifacts.py`, `verify_platform_smoke.py`. |
| `reports/STATUS.md` | Dated 2026-05-23; lists what is complete and the label caveat. |

---

## 6. Two files named `probe_results_combined.csv`, and they disagree

| | `cleaned/` | `Probes/raw_data/` |
|---|---|---|
| records | 33,598 | 56,275 |
| layers | 48 only | 48 **and** 50, merged |
| `figure_15_*` | `capability_brick_target_vs_achieved_qwen` | `dose_response_lottery_ultimatum_qwen` |
| `figure_16_*` | `capability_four_objects_..._qwen` | `probe_scores_track_target_qwen` |
| `figure_17_*` | `dose_response_lottery_ultimatum_qwen` | `capability_brick_target_vs_achieved_qwen` |
| `figure_18_*` | `probe_scores_track_target_qwen` | `capability_four_objects_..._qwen` |

Eight keys collide (`MANIFEST.csv:S0.D.probe_csv.key_conflicts`). `cleaned/regenerate_all_figures.py`
reads its own copy, so the shipped figures are correct. Pointing it at the `Probes/` copy would silently
swap four Qwen figures and average layer 48 with layer 50 in every Llama probe figure. Any new renderer
must name the file by full path and assert its layer set.

---

## 7. Environment

Three separate `requirements.txt` (Probes, SAE, Revised Prompting), no lockfile, no pinned versions —
all constraints are `>=`. Python 3.10–3.13 per the README.

- **Probes:** torch≥2.2, transformers≥4.45, scikit-learn≥1.4, edsl≥0.1.30, openai, anthropic.
- **SAE / Revised Prompting:** edsl≥1.0.5, transformers≥4.51,<5, bitsandbytes, huggingface_hub<1.

The interpreter on this machine is Python 3.11.3 with numpy 1.24.3, scikit-learn 1.2.2, pandas 1.5.3,
torch 2.5.1+cu121 — **scikit-learn is below the `Probes` floor of 1.4**, so re-running the probe pipeline
here needs a fresh environment. `cv_bench/s0_recon.py` avoids pandas and sklearn for this reason.

Model and SAE weights: see `PHASE0_SUMMARY.md` Q10. None of the three weights the paper needs is on disk.

---

## 8. Where the paper's evidence actually lives

| paper claim family | authoritative file |
|---|---|
| Fig. 3A, five lottery conditions | `SAE/data/raw/games/safe_risky/results_20251008_225522/` |
| Fig. 3B, ultimatum | `SAE/data/raw/games/ultimatum/results_20251008_201139/` |
| Fig. 5, five-judge creativity | `cleaned/creativity_evals_combined.csv`, multi-judge slice |
| Figs. 4, 6, 9–18 (probe) | `Probes/raw_data/probe_results_final.json` and `cleaned/probe_results_combined.csv` |
| §4.1 top-feature readings | `cleaned/feature_activations_combined.csv` |
| Prompting ladder (promised, unpublished) | `Revised Prompting/runs_fp16/runs/` |
