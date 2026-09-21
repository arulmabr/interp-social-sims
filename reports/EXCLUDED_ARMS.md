# EXCLUDED_ARMS.md — S0.6 and the standing record

Every arm that was run and is not in the paper. Nothing is deleted; nothing has been moved. Where the
plan asks for an `archive/` location, one is *proposed* only.

---

## 1. "Dense steering" — not found

`ICLR_PLAN.md` §0.3 records an author decision to drop dense steering, and S0.6 asks for what it was and
what it produced. **There is nothing in this repository under that name or any of the alternatives the
plan lists.** Searched, all case-insensitive, over every tracked `.py`, `.md`, `.sh`, `.txt` and
`.json`:

- `dense` — 2 hits, neither an arm: `Probes/experiments/dose_response_llama.py:4` ("a dense version of
  the psychometric calibration record", describing grid spacing) and `feedback.txt:111`, where the
  reviewer contrasts "sparse dictionary latents vs. dense discriminative directions" as a description of
  probe steering.
- `learned_vector`, `dense_vector`, `optimis/zed vector`, `steering_vector`, `mean_diff`,
  `difference of means`, `contrastive`, `actadd` / `act_add`, `CAA` — no hits outside `PAPER_AUDIT.md`
  and `ICLR_PLAN.md`.
- `git log --all --name-only` over the full history (2026-05-25 → 2026-07-10): no file, at any commit,
  has `dense` in its path. No deleted file matches either.
- `mech_interp_paper_ICLR_extension_plan.docx` (47 paragraphs, read with `python-docx`): the word
  does not appear.

**The two things S0.6 asks to be flagged at the gate therefore cannot be checked here.** Specifically,
whether the dropped arm was a difference-of-means / contrastive-activation direction — which the
reviewers explicitly ask for as a baseline (S3.1) — and whether it was an optimised dense vector trained
to reproduce a target agent's choices, which would be an activation-space counterpart of the LoRA
anchor. Both bear on how S3.1 and Track B are scoped.

**Asked of the authors:** where does the dense-steering work live (a different repository, a branch, a
notebook, a machine), and what was it? If it no longer exists, say so and the paper says nothing about
it. If it was a difference-of-means direction, S3.1 is partly already done and the reviewers' request is
cheaper than budgeted.

Proposed archive location once it is found: `archive/dense_steering/`, contents unmodified, with a
`README.md` giving the original path and the commit it came from.

---

## 2. The prompting ladder — run in full, published nowhere

`Revised Prompting/runs_fp16/runs/{safe_risky_full,ultimatum_full}`, Stack B.

| | |
|---|---|
| conditions | `baseline`, `persona`, `cot`, `fewshot`, `fewshot_cot_dose{000,025,050,075,100}` |
| coverage | lottery 35 rewards × 40 agents; ultimatum 17 offers × 40 agents; both complete |
| plus | `creativity_brick_full`, `creativity_stapler_full`, each with five-judge scores |

The abstract states a conclusion about this ladder ("this advantage narrows"); no figure, table or
appendix contains it (PAPER_AUDIT §4.7). The results exist. Read on their own stack
(`MANIFEST.csv:S0.B.*`):

| condition | lottery switching point | ultimatum threshold |
|---|---:|---:|
| baseline | 102.9 | never crosses 0.5 (accepts 78% at offer 10) |
| persona | 97.3 | never crosses (accepts everything) |
| cot | **140.0** | never crosses |
| fewshot | 100.8 | 12.2 |
| fewshot_cot ρ=0.00 | never crosses (10% risky at n=180) | 40.0 |
| ρ=0.25 | 101.2 | 37.5 |
| ρ=0.50 | 97.3 | 37.7 |
| ρ=0.75 | 99.7 | 37.6 |
| ρ=1.00 | 101.5 | 10.7 |

Two things a reviewer would notice immediately. The ρ sweep is **flat** on the lottery — 97 to 102
across the whole dose range — so there is no dose-response to report. And CoT moves the lottery the
*wrong* way, to 140. These are results, not failures, and under CLAUDE.md rule 4 they are reported as
prominently as anything else.

The reason they are not comparable to Fig. 3 is Stack B ≠ Stack A: the same persona that moves Stack A's
switching point from 127.6 to 19.8 moves Stack B's from 102.9 to 97.3. **Not an excluded arm — an
unreported one.** S1.7 writes it up; S2.5 is what would make it comparable.

---

## 3. Local open-SAE reruns — twelve runs, published nowhere

`SAE/runs/`, Stack D. Greedy decoding, 4-bit base, `clamp_min` at `last_token`, layer 50, the same
feature indices as the hosted runs.

| run | units | result |
|---|---:|---|
| `safe_risky_open_sae_steering_full` (0.7/0.5) | 1,400 | switching point **57.5** |
| `safe_risky_open_sae_steering_lite_full` (0.6/0.4) | 1,400 | switching point **57.5** |
| `ultimatum_open_sae_steering_full` (0.5) | 680 | threshold **17.5** |
| `trust_open_sae_steering_full` | 200 | trust game; never in the paper |
| `creativity_open_sae_steering_40agent` | 80 | + 800 post-hoc top-k rows |
| `open_sae_dose_sweeps/{smoke,full,summary}` | — | dose sweep artefacts |
| 6 smoke runs | — | validation only |

Three findings worth the authors' attention:

1. **The lottery steering result replicates off the hosted service** — 57.5 against 59.1 — despite a
   different intervention (`clamp_min` vs `nudge`), greedy decoding and 4-bit weights. That is a
   stronger robustness statement than the paper currently makes.
2. **The ultimatum result does not** — 17.5 against 32.9. The same feature, the same layer, a different
   patch, and the threshold moves four times as far.
3. **The two lottery doses are behaviourally identical.** 0.6/0.4 and 0.7/0.5 give the same switching
   point and the same 1,000 risky choices out of 1,400; the risky-count difference is **0**
   (`S0.C.lottery.dose_gap_risky_count`). The response *texts* differ, so these are genuinely two runs,
   not a duplicated file. Under `clamp_min` both doses clamp above the natural activation, so the dose
   does nothing — which is dose-insensitivity of exactly the kind Ma (arXiv 2504.11671) reports, in the
   paper's own data.

**Not an excluded arm — an unreported one.** It costs nothing to report; it is already computed.

---

## 4. Trust game — run, never mentioned

`SAE/data/raw/games/trust/results/` (hosted, 2 conditions × 10 amounts × 10 agents) and
`SAE/runs/trust_open_sae_steering_{full,smoke}` (local). The intervention takes the return ratio from
0.5 to 1.0 at almost every sent amount. Whether to include it is an **AUTHOR DECISION**; it is a third
social task and a fourth behavioural instrument, and at nine pages it may simply not fit.

---

## 5. Layer-50 probe replication — run, not in the figures

The last eight commits (July) re-ran every Llama probe figure at layer 50 to match the SAE's layer, and
merged the results into `Probes/raw_data/probe_results_{final.json,combined.csv}` under `_layer50` keys.
`cleaned/` — which is what renders the paper's figures — was never updated, so **the paper shows layer
48 only**.

This is directly responsive to the reviewer's request quoted in `feedback.txt:111` ("an ablation of
probe steering ... evaluated at layer 50 would help isolate these factors"), and the work is done. It
overlaps S3.2. Calibrated λ at layer 50 differs from layer 48 by at most **3.8%** across the ten
lottery targets and **3.3%** across the four ultimatum targets
(`S0.J.{lottery,ultimatum}.lambda_l48_vs_l50.max_rel_diff`), so the two layers behave alike — again, a
result, and one that partly answers the reviewer at zero cost.

One blemish worth recording while the data is open: |λ| is not monotone in the lottery target at layer
48 — target 162 needs a *smaller* |λ| (3.065) than target 143 (3.285)
(`S0.J.lottery.lambda_monotonicity_inversions.l48` = 1 of 9 steps). With 12 agents per calibration
evaluation that is within sampling noise, which is itself the point: the calibration has no interval on
it anywhere.

**Asked of the authors:** should the layer-50 arm go in, and if so should `cleaned/` be refreshed or the
comparison presented separately? Refreshing `cleaned/` would change shipped figures and is not mine to
decide.

---

## 6. Figures rendered under a proxy judge

`cleaned/regenerate_all_figures.py` renders `figures_llama/figure9.png` and `figure10.png` from the
**GPT-5** scores, because the original judge's scores are missing, and says so in its own header
comment. If either file is in the paper under a caption naming a different judge, that caption is wrong.
Listed here so it is not lost. **Authors to confirm** which of the two variants
(`figure9.png` / `figure9_Gpt5.png`) is the one in the PDF.
