# PHASE1_FINDINGS.md — Gate S1

Analyses of existing results. CPU only, no GPU, no model run except a 22M-parameter sentence encoder for
the S1.6 text measures. Nothing in `cleaned/`, `Probes/`, `Revised Prompting/` or `SAE/` was touched.

**Constraints in force**, at the authors' instruction: `GATE_S0_RESPONSE.md` §3 **P2, P3, P4, P5, P10**.
Everything else in that file — including P1, P6–P9, P11 and §2, §4, §5, §6, §7 — is **not in force** and
has not been applied; that file is unsigned. `logs/DEVIATIONS.md` D-2026-09-21-00 records the scope.

Per-task reports: `S1_1.md` … `S1_8.md`. Data: `results/S/s1/` (17 CSVs). Figures: `figures/s1_*.pdf`
with `figures/make_s1_*.py` beside them. All 283 S1 values are in `MANIFEST.csv` under `S1.*`, each with
its inputs and the git SHA.

---

## 1. The six results that change what the paper can say

**1. The SAE altruism feature's effect on the ultimatum threshold is not distinguishable from zero.**
Within the hosted stack, against its own baseline, `baseline − steering` = **3.4 tokens, 95% CI
[0.0, 7.6]** with reward levels resampled. The persona's effect on the same stack against the same
baseline is 25.1 [20.4, 29.4]. §4 of the draft describes both as moving the threshold.
(`S1_3.md` §3; `MANIFEST.csv:S1.3.hosted.ultimatum.*`)

**2. Four of five judges rate SAE steering *below* baseline on the brick task.** Claude 4.83→4.39,
Gemini 4.74→4.49, GPT-5 4.83→4.68, Kimi 5.09→4.76; DeepSeek is flat. The five-judge mean is 5.00→4.77.
In the mixed model the gap is 0.23 raw (p = 0.061) and **0.26 with length partialled out, 95% CI
[0.03, 0.50], p = 0.030**. On stapler every judge goes the other way. App. A.3.5's "consistent across all
five judges" and l. 416's "highest score in both tasks" are both contradicted by the repository's own
scores. (`S1_5.md` §1–2)

**3. The published inter-judge Spearman of 0.77 is a between-task statistic.** It reproduces exactly
when pooled over all 680 responses, all conditions and both tasks (0.7695). Condition on the comparison
the paper makes — same task, same condition — and it falls to **0.02** (stapler, prompting) to **0.65**
(brick, steering); within task alone it is 0.458 and 0.353. Dropping the high-temperature condition
moves the pooled value *up* (0.634 → 0.650), so `PAPER_AUDIT.md` §2.5's guess that high temperature
carries the 0.77 is wrong; **pooling across tasks and datasets carries it**. (`S1_5.md` §4)

**4. Probe steering produces hyper-fair rejections, at rates that rise with the calibrated target.**
P(reject | offer ≥ 50) reaches **0.232** [0.195, 0.274] on Llama layer 48, **0.268** [0.229, 0.312] on
layer 50 and **0.400** [0.335, 0.469] on Qwen, at target 60. No standard fairness preference produces
this. The hosted stack produces none in 1,080 such trials. And layer 50 produces them at target 30
where layer 48 does not — 0.061 [0.043, 0.088] against 0.000 [0.000, 0.009] — at matched λ and matched
threshold. That last dissociation is exactly what the benchmark is for, and it is already computed.
(`S1_2.md` §3)

**5. A predictor that knows only the reward level reaches 0.95–0.99 on every logged lottery dataset,
and a one-parameter threshold on n does exactly as well.** The gap between "best function of n" and
"best threshold on n" is **0.000** for 67 of 68 curves. The paper's 82% probe accuracy is not above that
bar; it is below it. Combined with the design facts — 45 prompts differing in one integer, eight
identical activation vectors each, a row-wise CV split that puts every vector on both sides of every
fold — the 82% is consistent with a probe that has learned a noisier version of "compare n with a
number". (`S1_4.md` §1–2)

**6. The prompting ladder's ρ sweep is flat, and chain of thought moves risk-taking the wrong way.**
From ρ = 0.25 to 1.00 the lottery switching point moves between 96.0 and 101.6, inside intervals about
8 tokens wide; the ρ = 0 arm has no switching point at all. `cot` raises the switching point to 175.7
against a baseline of 106.8, a difference of −69.0 [−86.9, −52.0]. The abstract's conclusion about the
ladder must match this or be removed. (`S1_7.md` §1)

## 2. Six more that are worth a sentence each

- **Fluency is a constant.** Every response in every condition produces exactly ten ideas, because the
  prompt caps the list at ten. A quarter of the composite creativity score is noise around a constant.
  (`S1_6.md` §2)
- **Length explains up to 59% of a judge's variance within the dataset the capability figures use**, and
  the slope is *negative* there — longer scores lower, for all five judges. The repository's own pooled
  `length_regression.json` reports positive slopes and up to 43%; the relationship reverses between the
  two response datasets it pools. (`S1_5.md` §3)
- **The ρ labels are wrong at two of five points.** Six demonstrations can only realise sixths:
  `dose025` is ρ = 0.333 and `dose075` is ρ = 0.667. (`S1_7.md` §3)
- **The plain few-shot prompt demonstrates a dominated choice** (answer "risky" at n = 33 against a sure
  50) and the ρ = 0 ultimatum prompt demonstrates three catch trials (reject 72, 86 and 58 out of 100) —
  after which that condition rejects hyper-fair offers at 13.1% against a 2.8% baseline. (`S1_7.md` §4)
- **`barely_prompting` refuses a gamble worth 90 against a sure 50, 1,400 times out of 1,400.** The
  strongest single persona effect in the repository, and it is not in the paper. (`S1_1.md` §4)
- **Five curves in the repository have no switching point**, including the vLLM ultimatum baseline,
  which is not a threshold responder at all. Any figure that assigns them one is plotting an
  extrapolation. (`S1_3.md` §2)

## 3. What P2 removed, and what replaced it

P2 was right and my Gate S0 summary was wrong. Eight legacy reward levels lie below 50, so
P(risky | n < 50) is an arithmetic restatement of the switching point: the measured points lie on the
staircase in `figures/s1_1_dominated.pdf`, which is drawn from the switching points alone. The three
rates I compared at S0 (probe 0.483, persona 0.690, SAE 0.000) are the three switching points (33, 20,
59) restated, on two stacks at unequal doses, with no unsteered rate on the probe stack. Withdrawn in
`logs/DEVIATIONS.md` D-2026-09-21-01.

What replaced it is a floor argument that survives within one stack: **no monotone utility puts the
lottery switching point below 50** — for power utility n\* = 50·2^(1/α) approaches 50 from above — so a
risk-preference shift has a floor at 50 and an action bias or a payoff rescaling passes through it. The
hosted persona goes 127.6 → 19.8, through the floor. The probe reaches 33 at its lowest target but has
no zero-dose endpoint, so nothing can yet be attributed to it.

A second S0 claim is also withdrawn: I wrote that the paper had "no hyper-fair catch trials at all".
The trials are on every grid (360 per hosted condition, 440 per probe condition); what the hosted stack
lacks is hyper-fair *rejections*, and the probe stack produces them in quantity
(D-2026-09-21-04, finding 4 above).

## 4. What S1 could not do, and why

| plan item | status |
|---|---|
| S1.4(a) correlation of the logged baseline probe score with n | **not available** — no baseline probe score is logged anywhere; no λ = 0 row exists. Substituted with the score's dependence on λ and on the target, both readings of its provenance stated. D-2026-09-21-03 |
| S1.4(c) ridge probe for log n, cosine with the choice probe | **not available** — presumes cached activations and a saved probe; neither exists. D-2026-09-21-02 |
| S1.6 Ocsai scorer | **unavailable offline** — the repository ships the OCSAI *dataset*, not the scoring model, which is a hosted service |
| S1.7 overlay on the Fig. 3 and Fig. 5 panels | **done differently** — those panels are Stack A and the ladder is Stack B; Stack A's baseline is drawn as a labelled reference line and nothing is differenced across the two. D16 |
| exact ceiling for the probe's own training labels | **not available** — those labels were never saved. Bounded by the design argument and estimated on the nearest datasets. P8 stops this recurring |

## 5. Still blocked on S2.0 / Q1

Three of the six headline results are one-sided because the probe stack has **no unsteered condition
anywhere in the repository** (`S0.D.lambda.n_zero_rows` = 0):

- whether probe steering *induces* dominated choices or merely fails to remove them (S1.1);
- whether it *induces* hyper-fair rejections (S1.2);
- what its clean, monotone dose-response — every adjacent target separated, 13 to 24 tokens per step —
  amounts to as an effect size (S1.3 §3).

One forward pass per trial on two grids settles all three. It remains the highest-value GPU hour in the
plan.

## 6. Still needed from the authors

Unchanged from Gate S0 §3, and now with two items sharpened by S1:

1. **Which dataset produced Fig. 5 and the numbers 5.57 / 5.18 / 6.25 / 5.23** (`GATE_S0_RESPONSE` §1.5).
   The gap is 2.8–3.6 points, in the same direction for **every** judge, so the built paper used a
   scoring pass this repository does not contain. Both sets are carried side by side in
   `results/S/s1/s1_5_pdf_vs_repo.csv` and neither is preferred. (`S1_5.md` §5)
2. **The paper's LaTeX source**, which settles the figure-to-file mapping and lets patches target real
   lines.
3. The model path and GPU assignment, so S2.0 can run.
4. Where the dense-steering arm lives, if anywhere (`EXCLUDED_ARMS.md` §1).

## 7. Delivered

| | |
|---|---|
| reports | `S1_1.md` … `S1_8.md`, this file |
| data | 17 CSVs in `results/S/s1/` |
| figures | 9 PDFs + PNGs in `figures/`, each with its `make_*.py` |
| paper patch | `paper_patches/appendix_prompts.md` — the ladder's verbatim prompts, which the paper promises and does not contain |
| code | `cv_bench/s1_data.py`, `s1_behaviour.py`, `s1_probe.py`, `s1_capability.py`, `s1_text.py`, `s1_ladder.py`, `s1_figures.py` |
| manifest | 517 values, 283 of them from S1 |
| logs | `DECISIONS.md` D11–D16, `DEVIATIONS.md` D-2026-09-21-00 … -04, `AI_USE_LOG.md` session 2 |

**Stopping here, as GATE S1 requires.**
