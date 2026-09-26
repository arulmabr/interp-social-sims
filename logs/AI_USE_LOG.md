# AI_USE_LOG.md

A running record of what an AI assistant (Claude, via Claude Code) did in this repository, for the
AI-use statement ICLR 2027 requires. Written as it happens, per CLAUDE.md rule 11.

The ICLR policy requires disclosure of, among other things: designing or giving feedback on methodology
or experiments; proposing or refining hypotheses; implementing methods; generating synthetic datasets;
and interpreting results. Entries below are tagged with the policy category they fall under.

---

## Session 1 — 2026-09-21 — S0 reconnaissance

**Model:** Claude Opus 5, run through Claude Code in an interactive terminal on the group's HPC login
node. No GPU, no external API, no network access beyond cloning the repository.

**Instructed by the authors to:** clone the repository, read `CLAUDE.md`, `ICLR_PLAN.md` and
`PAPER_AUDIT.md`, carry out task S0, and stop at Gate S0.

### What the assistant did

| policy category | work |
|---|---|
| *Analysing or interpreting existing data* | Read the repository's logged run records, combined CSVs and aggregated JSON, and computed 234 summary quantities from them: switching points and acceptance thresholds on three inference stacks, dominated-choice and catch-trial rates, calibrated-λ ranges and their λ=0 extrapolations, per-judge condition means, inter-rater Spearman, length-regression R², SAE top-feature frequencies, and a layer-48 vs layer-50 comparison. All are in `MANIFEST.csv` with their inputs and the source git SHA. |
| *Implementing methods / writing code* | Wrote `cv_bench/s0_recon.py` (≈500 lines), the script that produces every one of those numbers, plus `results/S/goodfire_labels.json`. No existing code was modified. |
| *Analysing or interpreting existing data* | Read the pipeline source (`Probes/`, `SAE/scripts/`, `cleaned/regenerate_all_figures.py`) and determined, from the code rather than from the paper, what the probes were trained on, what the steering hook does at each token position, which Goodfire controller produced each published curve, and which of the paper's three descriptions of probe training is accurate. |
| *Analysing or interpreting existing data* | Identified inconsistencies between the draft and the repository's own data and recorded them in `reports/`. Where the repository was consistent with more than one explanation, the assistant recorded the alternatives rather than choosing. |
| *Writing — internal documents only* | Drafted `reports/{REPO_MAP,PROVENANCE,STACK_AUDIT,PROBE_PROVENANCE,EXCLUDED_ARMS,PHASE0_SUMMARY}.md`, `logs/DECISIONS.md` and this file. **No text was drafted for the paper in this session**; `paper_patches/` does not yet exist. |

### What the assistant did not do

- No model was run, fine-tuned or queried. No synthetic dataset was generated.
- No hypothesis was proposed or refined; the hypotheses under test are the authors' (`ICLR_PLAN.md`
  §0.2, the plan `.docx`).
- No experiment was designed or run. Nothing was rerun, and no result was changed.
- No file in `cleaned/`, `Probes/`, `Revised Prompting/` or `SAE/` was modified, moved or deleted.
- No paid API call, no download, nothing written outside this repository.

### Note for the authors

Two separate AI-use facts belong in the statement alongside this log and are **not** the assistant's to
assert:

1. whether the probe-training description in Fig. 2 or any other paper text was LLM-generated;
2. that `feedback.txt` is an automated review, if it is.

A third is already established in the repository and does need disclosing: the creativity and
preference responses were **judged by five LLMs** (`gpt-5`, `claude-sonnet-4-6`, `gemini-2.5-pro`,
`moonshotai/Kimi-K2.6`, `deepseek-ai/DeepSeek-V4-Pro`), and `Probes/judge.py` uses GPT-5 as the
single judge for the capability probe's training labels — so an LLM produced the labels the capability
probe was trained on, not only the scores it is evaluated with.

If the extension plan is adopted, the assistant's continued work on it is disclosable under
"implementing methods" and "analysing or interpreting results". This log is the record.

---

## Session 2 — 2026-09-21 — S1, under GATE_S0_RESPONSE §3 P2–P5 and P10

**Model:** Claude Opus 5, Claude Code, same HPC login node. No GPU, no external API, no paid service.
One small local encoder was run on CPU (see below).

**Instructed by the authors to:** read `GATE_S0_RESPONSE.md` §3 P2–P5 and P10, apply them to S1, revise
any existing S1 report to comply and log the change in `logs/DEVIATIONS.md`. The rest of that file is
not in force.

### AI feedback on methodology — disclosable, and not the assistant's own work

`GATE_S0_RESPONSE.md` states in its own header that it was **drafted by Claude in a separate chat
session at the authors' request**, from the Gate S0 terminal summary only. It contains methodological
directions: how to report a rate (P2), a new task (P3), what to add to two analyses (P4, P5), and how to
handle two conflicting datasets (P10). Under the ICLR policy that is *designing or giving feedback on
methodology or experiments* and *proposing or refining hypotheses*, and it is **required disclosure**.
The authors should record that a second AI session produced it, that this session then acted on five of
its items, and which items those were. Nothing in it has been signed: §1 is blank and the CONFIRMED BY
line is empty.

### What the assistant did

| policy category | work |
|---|---|
| *Analysing or interpreting existing data* | Ran S1.1–S1.8 over the logged choices and judge scores: dominated and negative-premium rates with Wilson intervals; hyper-fair catch-trial rates; 68 logistic switching points with two kinds of bootstrap interval and 121 within-stack contrasts; the ceiling of any predictor of the logged choices that sees only the reward level; per-judge condition orderings, a crossed mixed-effects model, length residualisation and inter-judge agreement sliced by condition and task; four judge-independent text measures; the prompting ladder; the cross-stack persona table. |
| *Implementing methods / writing code* | Wrote `cv_bench/s1_data.py`, `s1_behaviour.py`, `s1_probe.py`, `s1_capability.py`, `s1_text.py`, `s1_ladder.py`, `s1_figures.py`, `cv_bench/__init__.py`, and eight `figures/make_s1_*.py`. No existing code was modified. |
| *Implementing methods* | Ran `sentence-transformers/all-MiniLM-L6-v2` (22M parameters, CPU, already in the local cache) to embed 680 existing creativity responses for the S1.6 text measures. This is an encoder used as a measuring instrument over text the authors already had; it generated no data and judged nothing. The Divergent Semantic Integration figure is an **approximation** of Johnson et al.'s operationalisation with a different encoder, and is labelled as such everywhere it appears. |
| *Writing — internal documents only* | Drafted `reports/S1_1.md` … `S1_8.md` and `reports/PHASE1_FINDINGS.md`; extended `logs/DECISIONS.md` and `logs/DEVIATIONS.md`. |
| *Writing — one draft destined for the paper* | `paper_patches/appendix_prompts.md`: the verbatim prompting-ladder prompts, extracted from the logs, not composed. The paper promises these conditions and contains no appendix for them. |
| *Correcting its own earlier output* | Withdrew two claims made in the Gate S0 summary — the separability reading of the dominated-choice rates (D-2026-09-21-01) and the statement that the paper had no hyper-fair catch trials (D-2026-09-21-04). Both are recorded with before and after. |

### What the assistant did not do

- No model was fine-tuned, steered or asked to produce data. No synthetic dataset was generated. No
  response was scored by an LLM judge in this session.
- No experiment was rerun, and no logged result was altered. The four legacy directories are untouched.
- No hypothesis was proposed; the hypotheses are the authors'.
- No paid API call, no download, nothing written outside this repository.

### Still outstanding for the statement

Unchanged from session 1: whether any paper text was LLM-generated, and whether `feedback.txt` is an
automated review. Now added: the provenance of `GATE_S0_RESPONSE.md` above.

- **23 Sept 2026.** Wrote `cv_bench/g4u.py`, `cv_bench/g4u_figure.py`, `cv_bench/g4u.sbatch` and
  `cv_bench/tests/test_g4u.py` (141 tests pass). Adopted `cv_bench/instr.py` and `cv_bench/resume.py`
  unchanged from `iclr-extension` so the ultimatum prompt matches the one G4 used. Ran job 23607904.
  Produced `figures/g4u_summary.{png,pdf}` and the two CSVs under the run root. Drafted BD53, including
  the argument that the panel's three high bars reflect shared fitting rather than signal.

## 2026-09-26, B10.6 to B10.8, creativity anchors

- Corrected the creativity LoRA anchor's `w0` construction rule (agent spread matched to the
  model's readout spread rather than a ratio of means) and reran; logged in `logs/B_DEVIATIONS.md`.
- Wrote `cv_bench/anchors/creativity_disp.py`, which extracts each creativity adapter's
  residual-stream displacement so the LoRA anchor has a direction to be placed against.
- Wrote `cv_bench/anchors/creativity_place.py`, which places the 3 SAE features and the probe
  against all 4 LoRA poles with a 2,000-draw random-feature null.
- Wrote `cv_bench/anchors/creativity_probe_check.py`, which recomputes the probe's judge
  agreement holding out responses as well as judges and separately within each task.
- Drafted `reports/B10_CREATIVITY_ANCHORS.md`. Every number in it was verified against its
  source file by script before commit; no value was typed from memory.
- Drafted `reports/B10_CREATIVITY_SPEAKER_NOTES.md` and rendered it as
  `reports/B10_Creativity_Speaker_Notes.docx` with a navigable contents list. Every number in it
  was verified against its source file by script before commit.
- Ran the probe recheck (job 23986960, 45m15s) and updated both creativity documents and the docx
  with its result. The probe's judge agreement falls from 0.846 pooled to 0.437 within brick and
  0.541 within stapler. Registered as 24 rows under `B10.8.*`. Recorded as BD60.
