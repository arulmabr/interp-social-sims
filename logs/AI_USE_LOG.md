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
