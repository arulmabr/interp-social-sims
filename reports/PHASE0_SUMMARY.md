# PHASE0_SUMMARY.md — Gate S0

Reconnaissance only. Read-only, CPU only, no GPU, no model weights, no API call. Nothing was moved,
renamed or edited in `cleaned/`, `Probes/`, `Revised Prompting/` or `SAE/`.

Every number below is recomputed by `cv_bench/s0_recon.py` (234 values) and registered in
`MANIFEST.csv` with its inputs and the git SHA `0aeba62`. Values not in the manifest are marked
"not available" and say why.

Companion reports: `REPO_MAP.md` (S0.1), `PROVENANCE.md` (S0.2), `STACK_AUDIT.md` (S0.3),
`PROBE_PROVENANCE.md` (S0.4), `EXCLUDED_ARMS.md` (S0.6).

---

## 0. What S0 changes about the plan

Three things, in order of how much they move the schedule.

**1. Both of Q1's candidate explanations are true at once, and there is no λ=0 run to arbitrate them.**
The unsteered model behaves very differently on each stack — 127.6, 102.9 and an extrapolated ~27 for
the same lottery — *and* λ is not zero-centred in the figures. There is no logged λ=0 row anywhere
(`S0.D.lambda.n_zero_rows` = 0). Until S2.3 runs, **no comparison between the probe figures and the
prompting/SAE figures is safe**, which is what `PAPER_AUDIT.md` §2.2 warned. This is the single
highest-value GPU hour in the whole plan.

**2. The probes cannot encode what the paper says they encode, and this is settled by reading the code,
not by running anything.** The preference probe is trained on 45 prompts that differ in one integer,
each repeated 8 times, with the activation read from the final prompt token — so it is a function of the
reward level and nothing else. The capability probe is trained on **two** distinct prompts. Details and
the exact argument: `PROBE_PROVENANCE.md`. Hypothesis 1 of the authors' plan is largely resolved before
any steering run.

**3. Nothing needed for the 70B work is on this machine.** No Llama-3.3-70B, no Qwen-2-7B, no Goodfire
SAE. Home has ~37 GB free and pool is at 100%. A bf16 70B checkout is ~140 GB. **Llama-3.1-8B-Instruct
— the development model amendment A10 asks for — is already on disk.** Storage, not compute, is the
binding constraint, and it needs an author decision before any download.

Against that, the news is better than the plan assumes in three places: the prompting ladder is
**complete** (Q6), the Goodfire feature UUIDs are **fully recovered** from the logs so the retired
hosted API is no longer a dependency (Q5), and a local open-SAE replication of the steering arm already
exists.

---

## 1. The ten blocking questions

### Q1. Lottery switching point and ultimatum threshold at λ = 0 on the local stack

**Not available as a measurement.** No row at λ = 0 exists in any probe artefact
(`S0.D.lambda.n_zero_rows` = 0), although `calibration.py`'s coarse grid starts at 0.0 and the cache
that would have held it was never written to disk.

What can be said, each with its status:

| quantity | value | status |
|---|---:|---|
| Stack C lottery switching point at λ=0, Llama L48 | **26.9** | **extrapolated**, OLS of target on λ, R² 0.981, λ observed only over −6.00…−0.32 |
| Stack C ultimatum threshold at λ=0, Llama L48 | **23.8** | extrapolated, R² 0.989 |
| Stack C lottery at λ=0, Qwen L17 | **26.1** | extrapolated, R² 0.984 |
| Stack C ultimatum at λ=0, Qwen L17 | **26.3** | extrapolated, R² 0.990 |
| Stack A lottery baseline (hosted) | **127.6** | **measured** |
| Stack A ultimatum baseline (hosted) | **38.1** | measured |
| Stack B lottery baseline (local vLLM) | **102.9** | measured |
| Stack B ultimatum baseline (local vLLM) | **never crosses 0.5** — accepts 78% at an offer of 10 | measured |

An extrapolation is not a measurement and does not go in the paper. But the picture it draws is
consistent across two models and two games: the probe stack's unsteered switching point sits near
**25**, not near 125. The authors' own plan anticipated this ("lambda is near zero at 30, so the
unsteered probe stack may already sit there").

So the answer to Q1 is *both* of the audit's disjuncts:

- the unsteered model really does differ enormously between stacks — Stack A 127.6 vs Stack B 102.9 for
  the *same model*, with no intervention at all, and the same persona moving Stack A from 127.6 to 19.8
  but Stack B only from 102.9 to 97.3; **and**
- λ is not zero-centred: it is negative throughout for preference probes and positive throughout for
  capability probes (Q2).

The Stack A ↔ Stack C gap is far larger than the Stack A ↔ Stack B gap, and Stack C is the one with no
chat template, no system prompt and a different answer vocabulary (`STACK_AUDIT.md` §3). That is the
prime suspect, and S2.5 is designed to test exactly it.

**Every dose-response figure needs its λ = 0 point, and S2.3 must measure it.** Cost: two grids,
one forward pass per trial, a few GPU-minutes on the 8B model and well under an hour on 70B.

### Q2. Positive class and sign convention

| probe | positive class | λ sign in code and data | figure |
|---|---|---|---|
| lottery | Risky = 1 | **negative** throughout, −5.999…−0.308 | Fig. 10a plots it rising with the target, so it plots −λ or \|λ\| |
| ultimatum | Accept = 1 | negative throughout | same |
| creativity | above-median judge score = 1 | **positive** throughout, 0.169…6.0 | plotted as positive |

`figure_11`'s own metadata records `lambda_range: [-6.0, 0.0]`. `build_preference_probe`'s docstring
states the labelling and the reasoning; `median_split`'s docstring explicitly forbids the alternative.

So ll. 397–398 are **correct about the signed λ** — a more positive λ pushes toward Risky and lowers the
switching point — and Fig. 10a uses the opposite convention without saying so. That is an editorial fix,
not a data problem. But note that the *sign flips between constructs*: the same symbol λ means "toward
risky" in one figure and "toward creative" in another. One sentence defining λ per probe, and one axis
label change, settles PAPER_AUDIT §2.1.

Separately, and not editorial: the probe scores in standardised space and steers in raw space
(`STACK_AUDIT.md` §3, point 3), so `h + λŵ` in §3.3 and Fig. 2 is not the direction the probe reads.

### Q3. Is the Fig. 11 probe score computed with the hook active, and on which tokens?

**Unverifiable from the repository — the shipped script and the shipped numbers are inconsistent.**

`probe_tracking_llama.py` computes the score with `capture_activations` **outside** the `steering_at`
context, on the final prompt token, on a prompt grid that is identical for every target. That is
deterministic, so the `all` subset must be a flat line across targets.

It is not: it falls monotonically from 0.721 at target 40 to 0.280 at target 240, spread 0.442
(`S0.D.tracking.all_subset.spread.llama_l48`; Qwen 0.257). The decline is well fitted by a line in λ
(R² 0.91) and in the target (R² 0.94), so the numbers look like they were produced with the hook
**active** — but the code in the repository cannot produce them.

Either the figure is right and the script is stale, or the script is right and the `all` series is not
what its label says. A single S2 forward pass decides it. Until then, no patch should state which
positions Fig. 11's score was read at, and the "probe scores track the target" claim should not be
strengthened.

### Q4. Creativity targets → λ, and the λ=0 score

| target | 3 | 5 | 7 | 9 |
|---|---:|---:|---:|---:|
| λ, brick (Llama L48) | 0.321 | 1.693 | 3.487 | 5.119 |
| achieved, brick | 4.013 | 5.669 | 6.931 | 8.156 |
| λ, stapler | 0.300 | 1.550 | 3.400 | 4.850 |
| achieved, stapler | 3.788 | 5.513 | 6.325 | 7.875 |

Achieved score extrapolated to λ = 0: **3.96** (brick), **3.77** (stapler), R² 0.985 / 0.961
(`S0.D.creativity.score_at_lambda0.extrapolated.*`). Again an extrapolation, not a measurement.

**It does not match the API-stack baseline.** Stack A's unsteered brick score is 5.194 single-judge and
5.003 five-judge (`S0.E.*.baseline`). The gap is ~1.2 points — the capability-side version of Q1, and
PAPER_AUDIT §2.9's observation that λ=1.2 yields a score below the unsteered 5.18 is the same fact seen
from the other end.

`PROBE_PROVENANCE.md` §2 explains why this is expected rather than puzzling: with two training prompts,
the probe direction is a baseline-vs-persona contrast, and its λ=0 intercept is a property of the fitted
line, not of the unsteered model. Fig. 6's range compression (slope ≈0.58) follows from the same fact.

### Q5. Which preset, value and features produced the SAE curve in Fig. 3A — **fully recovered**

From `model.controller` in the logged EDSL records. All eight features the paper names, with real
UUIDs, are saved to **`results/S/goodfire_labels.json`**.

| condition | idx | uuid | label | nudge |
|---|---:|---|---|---:|
| lottery `steering` | 184 | `7f0e30ffb55c412cacd711909b11e5d0` | Willing to take risks or make sacrifices for a goal | **0.7** |
| lottery `steering` | 4237 | `b53742bf6f5040e0a8aeba37766335ff` | Executing potentially risky operations that require caution | **0.5** |
| lottery `lite_steering` | 184 | (same) | (same) | **0.6** |
| lottery `lite_steering` | 4237 | (same) | (same) | **0.4** |
| ultimatum `steering` | 31935 | `a239616d4dcf470497b32ad3500f0145` | Altruistic and selfless behavior or intentions | 0.5 |
| creativity `high_steering` | 13142 | `2c83bf952a3a4213b45f098aa8c015e2` | Enabling or empowering creative expression and exploration | 0.3 |
| creativity `high_steering` | 20117 | `96f91d8ed8934998b52bf66a5951dafd` | Descriptions of creative unconventional thinking… | 0.3 |
| creativity `high_steering` | 4992 | `c148476f6cdc4cd9a2110c24045bfcbe` | Professional innovation and creative problem-solving | 0.3 |

This settles PAPER_AUDIT §4.10 outright. App. A.1.3's "two overlapping presets (0.5 to 0.7, 0.4 to 0.6)"
are not two candidate settings — they are the two published conditions, `steering` = (0.7, 0.5) and
`lite_steering` = (0.6, 0.4). The UUIDs in the appendix are described as placeholders; the real ones are
above, and they are now local, so the retired Goodfire service is no longer a dependency for
identifying features. The appendix can be corrected today.

One thing worth noticing while these are in view: **the creativity `prompting` condition's system prompt
is the three steered features' labels, verbatim** (`STACK_AUDIT.md` §1). Prompting and SAE steering are
not independent arms in the creativity task.

### Q6. Do results exist for `cot`, `fewshot`, `fewshot_cot` and the ρ sweep — **yes, complete**

`Revised Prompting/runs_fp16/runs/`, Stack B (local vLLM, Llama-3.3-70B, bf16, TP 2, temp 0.7, top-p 1.0).

| run | conditions | coverage |
|---|---|---|
| `safe_risky_full` | 9 | 35 rewards × 40 agents each |
| `ultimatum_full` | 9 | 17 offers × 40 agents each |
| `creativity_brick_full`, `creativity_stapler_full` | — | with five-judge scores |

Conditions: `baseline`, `persona`, `cot`, `fewshot`, `fewshot_cot_dose{000,025,050,075,100}` — the ρ
sweep is the dose suffix. Nothing is missing. The numbers are in `EXCLUDED_ARMS.md` §2; the headline is
that the ρ sweep is **flat** on the lottery (97–102 across the full dose range) and CoT moves the
switching point the wrong way (140.0 vs a baseline of 102.9).

S1.7 can be written entirely from these files. What it **cannot** do is overlay them on Figs. 3 and 5:
that is a Stack B vs Stack A comparison, and the persona alone moves 127.6→19.8 on one stack and
102.9→97.3 on the other. Overlaying them as they stand would be the confound the audit flags in §4.6.
The honest options are (a) report the ladder on its own axes with the stack stated, or (b) re-run the
ladder on the comparison stack at S2.5. (a) costs nothing.

### Q7. What is in `cleaned/`

The single source of truth for every paper figure: four combined CSVs and two scripts, documented in a
230-line README. `regenerate_all_figures.py` (1,361 lines) renders all 43 PNGs from those four CSVs and
nothing else; `integrate_new_data.py` is the idempotent ETL that appended the Stack B rows and the
five-judge scores. Inventory in `REPO_MAP.md` §2.

Two things to know. First, `cleaned/probe_results_combined.csv` is **layer 48 only** — the July layer-50
work never reached it, so the paper's figures are layer 48. Second, there is a second file with the same
basename under `Probes/raw_data/` which merges layers 48 and 50 **and uses a different meaning for four
Qwen figure keys** (`REPO_MAP.md` §6, `S0.D.probe_csv.key_conflicts`). Pointing the renderer at the
wrong one silently swaps four figures. Any new code must use full paths and assert the layer set.

### Q8. Are per-response judge scores stored, and what are Fig. 5's error bars

**Yes, all of them.** `cleaned/creativity_evals_combined.csv` holds 3,400 five-judge rows — 680 unique
responses × 5 judges — each with the four Torrance sub-scores, `final_score`, `response_text` and
`raw_evaluator_json`. Every judge has exactly 680 rows (`S0.E.multi_judge.rows_per_judge`). The 47
logged judge failures (all Claude, all `score_returned_none`) were retried; nothing was dropped.
S1.5 and S1.6 are fully feasible on CPU.

**Fig. 5's error bars are the SEM across the 40 responses within each judge × condition cell**
(`plot_mj_final_score`, line 1031: `np.std(vs, ddof=1)/sqrt(len(vs))`). They treat responses as
independent and carry no judge random effect — which is why S1.5(b)'s mixed-effects model is the right
replacement. Note also that `capability.png` uses **SD**, not SEM, for its bars; both conventions are in
the paper.

While the data was open, two things fell out that bear directly on PAPER_AUDIT §2.5:

- The published Spearman reproduces exactly: mean pairwise **0.7695**, range **0.675–0.849**
  (`S0.E.spearman.*`), against the paper's 0.77 and 0.68–0.85. But it is pooled over all 680 responses,
  **all four conditions and both tasks**, and that pooling is not stated.
- App. A.3.5's "the ordering of conditions was consistent across all five judges" is **false**. On
  brick, four of five judges rate `high_steering` *below* `baseline`: Claude 4.825→4.394, Gemini
  4.744→4.494, GPT-5 4.831→4.681, Kimi 5.094→4.756; only DeepSeek is flat at 5.519→5.531. The
  five-judge mean is 5.003→4.771, i.e. **steering lowers brick creativity**. On stapler every judge
  puts steering above baseline. The claim at l. 416 that "SAE steering attains the highest score in both
  tasks" does not survive its own data.

One discrepancy I could not resolve: PAPER_AUDIT §2.6 reads brick creativity falling from ≈5.2 to ≈2.1
under high temperature. Nothing in `cleaned/` scores anywhere near 2.1 — high-temperature brick is
**4.907** five-judge and **4.956** single-judge. Either the paper's panel uses a slice not in this
repository, or the read-off is of a different panel. **Authors to check against the PDF.** (The
supporting observation *is* confirmed: the top features under `high_temperature` are "Text that requires
cleanup or reformatting due to broken language patterns", "Non-Latin script characters and text
fragments", "Grammatical particles and connecting words in non-English languages".)

### Q9. Is Fig. 16 Qwen data scored under the five-judge protocol — **Qwen yes, five-judge no**

The achieved values in the repository's Qwen brick capability series are **3.944, 5.306, 6.538, 7.638**
at targets 3/5/7/9, which match the audit's read-off of Fig. 16 (≈3.95, 5.3, 6.55, 7.65) to the third
digit. The corresponding Llama series is 4.013, 5.669, 6.931, 8.156 — close, which is why they look
alike, but distinguishable. **So Fig. 16 is Qwen data.**

It is rendered by `plot_capability_brick` from the single stored `creativity_score` column — one judge,
with `errorbar(yerr=sem)` and a λ annotation per point, exactly the plot the audit describes seeing. The
caption's "one line per judge plus a bold mean" describes the *multi-judge* plots in
`figures_multijudge/`, which are a different figure. **The caption is attached to the wrong plot.** Fix
is editorial.

### Q10. Hardware, weights, API key

**This node has no GPU** (`nvidia-smi` absent). It is a login node behind Slurm.

| resource | state |
|---|---|
| Slurm | available; `ou_bcs_low` (1-day limit) has H100 ×4 and A100 ×8 nodes, `ou_bcs_high` 4 h, `ou_bcs_normal` 1 day |
| my slice here | memory high 8 G / max 10 G, 99 tasks — enough for the CPU analyses, not for anything else |
| other jobs | several of mine already running/pending on `mit_normal`; per standing instruction, ICLR work goes on `ou_bcs_low` only and nothing else of mine is touched |
| HOME quota | 162.8 / 200 GB used, **~37 GB free**; 530 K / 1 M files |
| POOL quota | 1018.3 / 1024 GB, **~5.7 GB free — effectively full** |
| SCRATCH | `~/orcd/scratch` exists and is **empty**; the filesystem has 249 TB free, my quota there is not reported in `~/orcd/.quota` |
| `HF_TOKEN` | set |
| `GOODFIRE_API_KEY` | **not set** |

Weights on disk (`S0.H.on_disk.*`):

| model | present |
|---|---|
| `meta-llama/Llama-3.3-70B-Instruct` | **no** |
| `Qwen/Qwen2-7B-Instruct` | **no** (`Qwen2.5-7B-Instruct` is present, a different model — do not substitute) |
| `Goodfire/Llama-3.3-70B-Instruct-SAE-l50` | **no** |
| `meta-llama/Llama-3.1-8B-Instruct` | **yes**, `~/orcd/pool/hf_cache`, 15 GB, 4 shards — **this is amendment A10's development model** |

**This is the binding constraint on everything after S1.** A bf16 70B checkout is ~140 GB; the SAE `.pt`
adds more. Neither HOME (37 GB) nor POOL (5.7 GB) can hold it. Scratch can, but it is unquota'd in the
report and is a purge-eligible filesystem. Under CLAUDE.md rule 7 a >50 GB download needs approval
anyway, so this is an author decision either way. See §3.

**Goodfire API key:** not set, and no call was made. Per `SAE/reports/STATUS.md` and
`SAE/docs/STEERING.md` the hosted Ember service is retired and its private nudge normalisation is gone —
so a key would not restore the published calibration even if one existed. The purpose of the Q10
request is nonetheless **met**: every feature label, UUID and index the paper names is now saved to
`results/S/goodfire_labels.json`, recovered from the logged runs rather than from the API. The external
dependency is closed.

---

## 2. S0.7 — paper claims that cannot be reproduced from this repository

| claim | why not |
|---|---|
| probe held-out accuracy **82%** | No probe artefact, no CV record, no layer-sweep table, no cached activations. A rerun would produce a *new* number, not a check of this one. |
| capability probe **≈85%**, **≈92%** | Same. And `PROBE_PROVENANCE.md` §2 shows a high number is expected from a two-prompt training set regardless of what the probe encodes. |
| **5.57 vs 5.18** and **6.25 vs 5.23** | No slice of any CSV yields these pairs. Closest: single-judge brick 5.281/5.194, five-judge stapler 6.284/5.834. **Flagged for the authors** — as printed these are not reproducible. |
| "ordering of conditions consistent across all five judges" (App. A.3.5) | Reproducible and **false** (Q8). |
| "SAE steering attains the highest score in both tasks" (l. 416) | Reproducible and **false for brick** under four of five judges (Q8). |
| probe scores "track the target" (Figs. 11, 18) | Provenance unverifiable: the shipped script cannot produce the shipped numbers (Q3). |
| the prompting-ladder conclusion in the abstract | The runs exist, on a different stack, and do not support it as stated (Q6, `EXCLUDED_ARMS.md` §2). |
| Fig. 2's probe training depiction | No synthetic altruism-statement dataset exists (`PROBE_PROVENANCE.md` §3). |
| Fig. 1's steering equation | The code adds the reconstruction error back; the figure replaces `h` with the reconstruction. |
| App. B.5.2's steering hook | The code steers **no** generated token; the hook is a no-op at `seq_len == 1`. Also a correction to PAPER_AUDIT §4.3, which reads it as a constant 0.5. |
| "40 agents" | Reproducible, and they are 40 `subject_id` strings on one prompt. |
| high-temperature brick ≈2.1 | Not found in the repository (Q8). Needs the PDF. |
| judge id `gemini-3.1-pro` (README) | Every data file says `gemini-2.5-pro`. |
| Table 1 | Not produced by any script; qualitative. |
| paper figure ↔ rendered PNG mapping | No LaTeX source, no figure manifest. `PROVENANCE.md` §1 infers it and marks the uncertain rows `?`. |

---

## 3. What I need from the authors at this gate

**A. Confirm or overrule the amendments in `ICLR_PLAN.md` §0.4 (A1–A11).** Two of them now have
evidence behind them: A10's development model is already on disk and is the only 70B-free path open,
and A9's iso-behavioural dosing is supported by `S0.C.lottery.dose_gap_risky_count` = 0, where two
different SAE doses produce literally the same 1,000 risky choices.

**B. Storage and the model plan — blocking for S2 onward.** Pick one:

| option | cost | consequence |
|---|---|---|
| 8B-only for now (A10) | 0 GB, weights present | S2 and B0–B3 can start immediately on `ou_bcs_low`. No 70B number until later. |
| 70B in scratch | ~140 GB + SAE weights, >50 GB so rule 7 applies | Needs an approved download and a scratch-purge policy. |
| 70B elsewhere | — | If there is a shared weights path I have not been told about, say where. |

I recommend the first, and starting S2 on 8B while the second is decided. Nothing in S2's design depends
on model size.

**C. GPU assignment.** Confirm `ou_bcs_low` and how many hours I may spend without asking again. My
current estimate for S2.1–S2.4 on the 8B model is well under the 8 GPU-hour threshold in rule 7.

**D. Track selection, and whether to submit on 2026-09-25 at all.** S0 does not change the audit's
arithmetic: the main text is ~1.4 pages over, and three statements in it are contradicted by the repo's
own data (Q3, Q8 ×2). Track S as scoped is the honest path to a submission; Track B is not completable
by Friday and the plan already says so.

**E. Five small confirmations, each cheap and each blocking a patch.**
1. The paper-figure ↔ PNG mapping in `PROVENANCE.md` §1 — confirm the rows marked `?`.
2. Where "5.57 vs 5.18" and "6.25 vs 5.23" came from.
3. Whether brick creativity under high temperature really reads ≈2.1 in the PDF.
4. Where the dense-steering arm lives, if anywhere — see `EXCLUDED_ARMS.md` §1; **S0.6's two flags
   cannot be raised without it.**
5. Whether `figure9.png`/`figure10.png` (proxy-judge renders) or their `_GPT5` variants are in the PDF.

**F. Two unreported arms to decide on** (`EXCLUDED_ARMS.md` §3–§5): the twelve local open-SAE reruns,
and the July layer-50 replication. Both are already computed, both answer things reviewers asked for,
and both need one sentence and a figure at most.

---

## 4. What I am doing while waiting

Per the gate's own instruction, S1 needs no GPU and no decisions, so I continue there and start nothing
else. In order: S1.1 dominated and negative-premium choices, S1.2 catch trials, S1.3 switching points
with bootstrap intervals, S1.4(a)(b) what the choice probe encodes — S1.4(c) is **not feasible**, since
no activations are cached anywhere — S1.5 the per-judge and mixed-effects capability picture, S1.6 the
judge-independent text measures, S1.7 the prompting ladder.

A preview of S1.1, already computed and in the manifest. P(risky | n < 50), where the gamble's best
outcome is worse than the sure 50:

| calibrated target | 30 | 49 | 68 | 87 | ≥106 |
|---|---:|---:|---:|---:|---:|
| Llama L48 probe steering | **0.483** | 0.079 | 0.025 | 0.000 | 0.000 |
| Qwen L17 (targets 30/40/50/60/≥70) | **0.575** | 0.304 | 0.108 | 0.042 | ≤0.013 |

(240 trials per cell; Wilson intervals at S1.3.) On the hosted stack the `slightly_prompting` persona
takes the dominated gamble **69%** of the time and SAE steering **0%**
(`S0.A.lottery.pRisky_dominated.hosted.*`).

> **Corrected 2026-09-21 under GATE_S0_RESPONSE §3 P2** (`logs/DEVIATIONS.md` D-2026-09-21-01). This
> passage previously concluded that the three families "are not interchangeable on this diagnostic" and
> that this favoured the benchmark separating them. That does not follow. Eight legacy reward levels lie
> below 50, so P(risky | n < 50) is an arithmetic restatement of the achieved switching point: a switch
> at 30 puts about 4 of 8 levels above it, 19.8 about 6 of 8, ≈59 none. The three rates are the three
> switching points (30 probe, 19.8 persona, 59.1 SAE), measured on **two different stacks at unequal
> doses**, and no unsteered rate exists on the probe stack to compare against. S1.1 reports each rate
> beside its own switching point and its own stack's baseline, and makes no cross-stack claim.

What does hold, within one stack and without a baseline, is a floor argument: no monotone utility
produces a switching point below 50, since for power utility n* = 50·2^(1/α) approaches 50 from above.
A risk-preference shift therefore has a floor at 50 in its dose-response; an action bias or a
payoff-scaling direction passes through it. The hosted persona goes from 127.6 to 19.8, through the
floor. The matching statement for the probe stack waits on S2.0.

Two more for S1.2 while they are in view. On the hosted stack no condition ever rejects an offer
≥ 50 (`S0.A.ultimatum.pReject_hyperfair.hosted.*` = 0 everywhere). And the `barely_prompting` persona
takes the risky option **0%** of the time at every reward up to 180, where the gamble's expected value
is 90 against a sure 50 — the mirror image of the dominated-choice anomaly, and not currently in the
audit.

> **Corrected 2026-09-21** (`logs/DEVIATIONS.md` D-2026-09-21-04). This passage previously added that
> the offer grid stopping at 90 meant "the paper has no hyper-fair catch trials at all", and that
> PAPER_AUDIT §3.3 was about calibration targets rather than realised rejections. Both are wrong.
> Offers of 50 to 90 are on the grid throughout — 360 such trials per hosted condition and 440 per
> probe condition — so the trials exist; what the hosted stack has is no hyper-fair *rejections*. And
> the probe stack does produce them: S1.2 measures P(reject | offer ≥ 50) rising with the calibrated
> target to 0.232 on Llama layer 48, 0.268 on layer 50 and 0.400 on Qwen. See `reports/S1_2.md`.

---

## 5. Housekeeping done

- Branch `iclr-extension` cut from `0aeba62`. Nothing committed yet.
- `cv_bench/s0_recon.py` recomputes all 234 values; `MANIFEST.csv` and `results/S/s0_numbers.json`
  regenerate from scratch with one command.
- `results/S/goodfire_labels.json` written (Q10's standing instruction).
- `logs/DECISIONS.md` and `logs/AI_USE_LOG.md` started.
- No GPU used, no API called, no paid batch, nothing downloaded, nothing outside this repository
  written to.

**Stopping here, as GATE S0 requires.**
