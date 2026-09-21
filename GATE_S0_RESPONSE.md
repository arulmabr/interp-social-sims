# GATE_S0_RESPONSE.md

Response to `reports/PHASE0_SUMMARY.md`. Drafted by Claude in a chat session at the authors' request, from the S0 terminal summary only; the full reports were not seen. Where this file and a report disagree on a fact, the report wins and the disagreement gets flagged. Log this file in `logs/AI_USE_LOG.md` as AI feedback on methodology.

Revised 21 Sept: the authors decided to submit on Sept 25 and to produce results on the paper's own model, `meta-llama/Llama-3.3-70B-Instruct`. §1 now holds their answers; §2, P1 and P7 changed; P12–P13 were added after Gate S1; §7 is replaced by `FRIDAY_PLAN.md` until the deadline. P2–P5 and P10 are unchanged and already in force.

Everything else is in force only once an author has checked §1 and signs here.

CONFIRMED BY: _______shreyas_______  DATE: _____09/21/2026_____

---

## 1. Only the authors can answer

Answers below were given by an author in chat on 21 Sept and written in here for signing. Edit anything that is not what you meant before you sign.

| # | question | answer |
|---|---|---|
| 1.1 | Track: withdraw before Sept 25, or submit on Sept 25? | **Submit to ICLR on Sept 25.** Withdrawal is not an option. §6 is therefore in force, and `FRIDAY_PLAN.md` sets the order of work until the deadline. |
| 1.2 | SLURM partition, GPUs, budget, and a directory with space. | Storage: `/orcd/data/gabrieli/001/guna23` (found by Claude Code, write test passed). `HF_HOME` goes there. New results go in a new subdirectory; nothing existing on the share is touched. Partition and GPUs: delegated to Claude Code to discover and report (task V4), using only what this account is already entitled to. Pre-approved until the deadline: the ≈145 GB download of M4 and its SAE, and GPU tasks G2–G5 of `FRIDAY_PLAN.md` up to 40 GPU-hours in total. Ask before exceeding either. |
| 1.3 | Where did the 70B probe runs and the vLLM runs execute, with which weights? | Not known to the author who answered. Claude Code found only a 239 KB stub of `Llama-3.3-70B-Instruct` and a complete `Llama-3.1-70B-Instruct` on the lab share. Task V3 reports which checkpoint id the legacy code and run records name, before anything is downloaded. |
| 1.4 | Dense steering, and whether the anchors were already run. | "It hasn't been run yet." Recorded as: the LoRA and gradient anchors have not been run anywhere. If dense steering was never run either, there is nothing to archive or disclose. If any run of it exists anywhere, it still has to be logged in `reports/EXCLUDED_ARMS.md`. Not blocking. |
| 1.5 | Which dataset produced Fig. 5 of the PDF and 5.57 / 5.18 / 6.25 / 5.23? | The author expects everything to be in `Probes/`, `Revised Prompting/`, `SAE/` and `results/`. Delegated to Claude Code as task V1 (exhaustive search, including the raw files under `SAE/` and not only `cleaned/`). Whatever it finds, the rule for Friday is that the paper follows the repo. |
| 1.6 | Paper's LaTeX source in `paper_src/` (read-only), plus the abstract as registered on OpenReview in `paper_src/REGISTERED_ABSTRACT.txt`. | **TO DO by an author today.** Every text patch waits on it. |
| 1.7 | Are the judges named in Fig. 5's legend the models that produced the scores? | Delegated to Claude Code as task V2 (model ids and dates from the scoring logs). If the logs do not record them, this comes back to the authors. |

For Claude Code to answer from logs, not the authors: the exact model id of the "Qwen" arm. The paper says Qwen-2-7B-Instruct; the disk has `Qwen2.5-7B-Instruct` and no `Qwen2-7B-Instruct`.

---

## 2. Recommended decisions (edit before signing if you disagree)

**Amendments A1–A11:** confirm all. A10 stands as first written (build on the 8B model, then run on the 70B); see P7.

**Model path.** By author instruction the paper's results are produced on the paper's model. That model is `meta-llama/Llama-3.3-70B-Instruct`: the PDF names it 17 times and the authors' plan names it too, there is no mention of a 3.1 70B anywhere, and Goodfire released no SAE for one. It is not on this machine, so M4 is blocked until §1.2 or §1.3 supplies either the existing checkpoint's path or the space to download it. Nothing is downloaded without the approval rule 14 requires.

| id | model | status | role |
|---|---|---|---|
| M1 | `meta-llama/Llama-3.1-8B-Instruct` + `Goodfire/Llama-3.1-8B-Instruct-SAE-l19` (one 2.15 GB `.pth`; also in SAELens as release `goodfire-llama-3.1-8b-instruct`, id `layer_19`) | model on disk, SAE is a small download | development model and second SAE model: every task is built, tested and dry-run here before any 70B job, so that 70B hours are not spent on bugs |
| M2 | `Qwen/Qwen2.5-7B-Instruct` + `andyrdt/saes-qwen2.5-7b-instruct` (BatchTopK residual SAEs, no labels) | model on disk | replication, including an SAE arm with anchor-selected features only |
| M3 | `Qwen/Qwen2.5-72B-Instruct` | in the shared pool cache; confirm it is complete and that you may use it | optional scale check for probe, gradient and LoRA families; no SAE arm; decide after M1 |
| M4 | `meta-llama/Llama-3.3-70B-Instruct` + `Goodfire/Llama-3.3-70B-Instruct-SAE-l50` | not found on disk; ≈145 GB; gated repo, needs a Hugging Face token with access (never committed) | **primary for the paper's results.** bf16 forward passes need roughly 2×80 GB of GPU memory at the least; LoRA anchors need about 4×80 GB with checkpointing, or 4-bit base weights as B3.2 already allows |

Feature labels: Goodfire's hosted API, which supplied the labels and ran the paper's SAE steering, has been deprecated (note on goodfire.ai, Feb 2026). Before building F9 on M1, check what label sources exist offline (Neuronpedia lists Goodfire's 70B SAE with searchable explanations; arXiv 2602.10352 uses auto-interpretability label sets for both Goodfire SAEs) and archive what you use under `results/S/`. If no labels can be obtained for M1, F9 is reported only where labels exist and the gap is stated.

**Compute.** Approve S2.0–S2.4 on M1 now (small), and S2.0 on M4 the day its weights are reachable (under an hour of generation). Track B's budget is set after `reports/COMPUTE_BUDGET.md` (B0) measures throughput on M1 and scales it. A rough guess, to be replaced by that measurement: the full grid on a 70B is of the order of hundreds of GPU-hours, so B0 must propose a reduced grid for M4 (fewer templates and doses per family, a small prompt set for the random controls) before anything is submitted.

**B1 and B2 may start now.** They use no model, no GPU and no legacy data, and B2's recovery study is what decides whether the benchmark can work.

---

## 3. Amendments to `ICLR_PLAN.md` after S0

**P1. New task S2.0, the first GPU job: λ = 0 and the chat template.**
For each legacy probe-stack arm whose *logged* model id is on disk: run the legacy code path with the hook disabled (import it or copy it into `cv_bench/legacy_shim/`; do not edit it in place), legacy prompts verbatim (raw strings, no chat template), legacy sampling settings and N, both games. Then the same with the model's chat template applied and nothing else changed. Report switching point and threshold with bootstrap intervals, P(risky | n < 50) and P(reject | offer ≥ 50). If the logged model is not on disk, write "not available"; never run a different model under a legacy name. Run the same two conditions on M1 as the new-stack reference, labelled new. **On M4 this is the first job the day the weights are reachable**, because Figs. 4, 6 and 10 were made on that model. Before it runs, confirm from the legacy logs which checkpoint each legacy stack loaded; if any stack loaded a 70B other than `Llama-3.3-70B-Instruct`, report that as one more difference between stacks and stop for the authors.
Why: on the probe stack the calibrated λ is ≈0.3 at target 30 and grows with the target, so the unsteered model may itself switch below 50. Whether probe steering causes dominated choices or removes them depends on this run.

**P2. Guard on S1.1.**
On the legacy grid eight reward levels lie below 50, so P(risky | n < 50) follows from the achieved switching point: 30 gives about 4/8, 19.8 about 6/8, 60 gives 0. The S0 preview (probe 48%, persona 69%, SAE steering 0%) restates the switching points 30, 19.8 and ≈60, measured on three different stacks. It does not show that the families are separable. In `reports/S1_1.md`:
- give each rate beside its switching point and beside the same stack's unsteered rate; without that baseline do not write that an intervention induces dominated choices;
- make no comparison across stacks or across unequal doses;
- state what does hold within one stack: no monotone utility produces a switching point below 50 (for power utility n* = 50·2^(1/α), which approaches 50 from above), so a shift in risk preference has a floor at 50 in its dose-response, while an action bias or a payoff-scaling direction passes through it. The persona on the hosted stack goes from 127.6 to 19.8, through the floor. For the probe the matching statement waits for S2.0.

**P3. New task S1.8, cross-stack persona table.** Per stack: verbatim persona text, option labels, system prompt, chat template or not, temperature, precision, N, unsteered switching point, persona switching point (127.6 → 19.8 hosted; 102.9 → 97.3 vLLM). State whether persona wording and labels are identical across the two stacks. If they differ, note whether the persona that works shares a word with an option label. No interpretation beyond that.

**P4. The legacy choice probe is a function of n by construction** (45 prompts differing in one integer, 8 identical activation vectors each).
- S1.4 adds: the label rule; whether the train/test split was by row or by prompt (with identical vectors a row split puts the same vector on both sides); the best accuracy any function of n can reach given those labels, beside the paper's 82%.
- Track B lists two probes: **F6-legacy**, rebuilt from the legacy recipe on the new stack and called a reconstruction, and **F6**, a choice-labelled probe trained on the discovery split where s, p, x, template, order and labels all vary. Report cos(F6-legacy, C3) and cos(F6, C3).
- `PREREG.md` records, before any benchmark result exists, the prediction that F6-legacy behaves as payoff scaling: belief share dominant, recall and fact-probe decoding of x shifted, parallel translation on log x, high cosine with C3.

**P5. The legacy capability probe** was trained on two distinct prompts. State in `reports/S1_5.md` which two, what the labels were, and where activations were read. If they were read at the final prompt token there are two distinct vectors, and an accuracy figure means nothing. In B8 treat the legacy direction as a two-prompt contrast (an F8-type family).

**P6. Hook semantics.** Three descriptions exist. The prose of App. B.5.2 says the hook acts during decoding. The printed sketch (`max(1, seq_len // 5)`) would add 0.5 × the vector to every decoded token. The repo code adds nothing when `seq_len == 1`. `legacy` mode in `cv_bench/steer.py` reproduces the repo code (prefill only, last 20% of prompt positions, ramp 0.5 → 1.0) and a recording test proves it. For the creativity tasks this means legacy steering reached the output only through the prompt's keys and values; B8 compares `legacy`, `last`, `all_prompt` and `all`.

**P7. A10 stands: build on M1, run on M4.** M4 is the primary model for the paper's results. No M4 job is submitted until the same code has passed its tests and a complete dry run on M1. M1 results are kept and reported as the second SAE model, M2 as the replication. Probe-type families are reported at their selected layer and at the SAE layer (50 on M4, 19 on M1). On M4 do not write per-token residuals to disk: at 8,192 dimensions in bf16 a 150-token prompt is about 2.4 MB, and tens of thousands of prompts would need more space than the weights. Cache final-token vectors only, or recompute.

**P8. Save every artefact.** S0 found that no legacy probe survives. From now on every direction, probe (weights, bias, scaler, layer sweep, folds, seeds), adapter and calibration table is written to the run directory and hashed into `MANIFEST.csv`.

**P9. Calibration noise.** Legacy calibration used 12 samples per evaluation and |λ| is non-monotone at one lottery step. New calibration runs on logits. Any calibration that still samples reports an interval.

**P10. Two capability datasets exist** (§4.2). Until 1.5 is answered, S1.5 runs on the repo data and lists the PDF-read values in a separate column marked "PDF, source unknown". Do not reconcile them by choosing one. Report judge agreement within condition and within task beside the pooled 0.77.

**P11. Status of legacy results.** The hosted stack that produced Figs. 3 and 5's steering curves no longer exists, so those results cannot be re-run where they were made. In any text they are observations from a deprecated hosted system, with access dates. Numbers from different stacks never share an axis or a table column.

**P12. Tests and intervals for the sampled legacy data (after Gate S1).** The reward levels are a fixed design; the randomness is in the sampled responses. Forty draws at one level are independent evidence about that level's choice probability, though not forty different agents. For every headline contrast report, as primary, (a) a permutation test of the condition label stratified by reward level, and (b) a bootstrap interval for the shift with levels held fixed and responses resampled within level. Keep the level-resampling interval beside them as a sensitivity column: with a coarse grid and a steep curve only two or three levels carry information, so that interval mostly reflects which of them a draw happens to include. The rule in B6 (resample reward levels and templates, never trials) is for logit readouts, which have no trial noise. Reword finding 1 of `PHASE1_FINDINGS.md` by (a) and (b), and give shifts in grid steps as well as tokens: 3.4 tokens is under one 5-token step, against 25.1 for the persona.

**P13. Excess over the staircase (after Gate S1).** P2 applies to the ultimatum too. With nine offer levels at or above 50, a threshold calibrated to 60 means rejecting offers of 50 and 55, which is 2/9 ≈ 0.22; finding 4's 0.232 at target 60 is that arithmetic. For both games report each catch-trial rate beside the rate implied by the fitted switching point, and the difference with an interval. Zero excess means the curve moved as a clean translation, which is what S1.1 found for the lottery. Positive excess means responses the threshold does not explain, the signature of an added bias toward one action: Qwen's 0.400 at target 60, and layer 50's hyper-fair rejections at target 30 where the staircase gives none.

---

## 4. Corrections to `PAPER_AUDIT.md`

1. **§4.3.** The audit described the sketch printed in App. B.5.2, which applies a constant 0.5 during cached decoding. The repo code applies nothing during decoding. Both readings are right about their source; the finding is that the appendix prints code that did not run. Replace the listing with the real code and describe steering as prefill-only.
2. **§2.5 and §2.6.** Re-checked at 300 dpi on 20 Sept: in the PDF's Fig. 5A the high-temperature brick bars read GPT-5 ≈2.9, Claude ≈1.5, Gemini ≈2.15, Kimi ≈2.1, DeepSeek ≈1.85, mean ≈2.1. The repo says 4.91. The PDF figure and the inline means (5.57, 5.18) agree with each other, so the PDF was built from a dataset that is not the one in `cleaned/`. Candidates: scores under the older "be generous" rubric (App. A.3.4) versus the revised one (A.3.5); API judges versus proxy judges.
3. **§2.2** is settled as a contradiction with no arbiter: 127.6 (hosted), 102.9 (vLLM), ≈27 extrapolated (probe stack), and no λ = 0 row anywhere.
4. **§4.1 and §4.2** are settled by code: see P4 and P5. Fig. 2's synthetic-statement dataset does not exist.
5. **§4.10** is settled: the two presets are the two published conditions, and all eight feature UUIDs are in the logs.
6. **New.** Spearman 0.77 reproduces only when pooled over all conditions and both tasks; the paper does not say so.
7. **New.** Probe results at layer 50 already exist and agree with layer 48 to within 4% in calibrated λ. This answers part of `feedback.txt:111` at no cost.

---

## 5. Additions to `CLAUDE.md` (append as rules 13–15)

13. **SLURM.** Never run model code on a login node. Submit with `sbatch` to the partition named in §1.2. Low-priority jobs get preempted, so every job checkpoints, can be re-run safely, and is submitted with `--requeue`. Write the job id and node into the run directory. Do not hold idle allocations.
14. **Storage.** Check free space and quota before any download or cache write. `HF_HOME` points where §1.2 says. Never delete from a shared cache. While free space is under 100 GB, nothing above 5 GB is downloaded without approval; this replaces the 50 GB figure in rule 7.
15. **Pickled weights.** `.pt` and `.pth` files are pickles. Load them with `torch.load(..., weights_only=True)`; if that fails, stop and ask.

---

## 6. Minimum conditions for the Sept 25 submission (in force)

The authors are submitting, so these are requirements. Patches for all of them are delivered under `FRIDAY_PLAN.md`, and the authors check each one.

1. Main text at most 9 pages. First candidates to cut: Fig. 2 (it depicts a training set that does not exist) and Table 1 (a cross-stack comparison the stack audit invalidates).
2. §3.3, Fig. 2 and App. B.4 describe what `build_preference_probe` and `build_capability_probe` do. The accuracies 82%, ≈85% and ≈92% go unless regenerated; no artefact exists to check them.
3. App. B.5.2 shows the code that ran; the prose says prefill-only.
4. Fig. 5 and its inline numbers come from one identified dataset. l. 416 and App. A.3.5 say what that dataset shows judge by judge. The 0.77 is described as pooled.
5. Figs. 11 and 18 go unless a script in the repo reproduces them.
6. Every cross-stack comparison is removed or caveated with the three baselines and the missing λ = 0 run. The vLLM persona result (102.9 → 97.3) is reported beside the hosted one (127.6 → 19.8).
7. What the abstract says about the prompt ladder matches the ladder data (ρ sweep flat at 97–102, CoT at 140) or is removed.
8. The hosted API is described with access dates and its deprecation.
9. The Qwen model name matches the logs.
10. Everything in `PAPER_AUDIT.md` §1: AI-use statement covering this work, references, anonymised supplement, reviewer registration.

---

## 7. Order of work from here

Until the deadline `FRIDAY_PLAN.md` replaces this list. It applies again afterwards, for Track B.

1. Apply §3–§5 to `ICLR_PLAN.md`, `PAPER_AUDIT.md` and `CLAUDE.md` on the branch; commit.
2. Revise S1 under P12 and P13 (S1 itself is done).
3. Start B1 and B2 (CPU).
4. When §1.2 is filled in: S2.0, then S2.1–S2.4 on M1. S2.0 on M4 the day its weights are reachable, then S2.3–S2.5 on M4.
5. Stop at Gate S1 and at Gate B2 as the plan says.