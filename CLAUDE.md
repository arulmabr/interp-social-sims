# CLAUDE.md

Standing rules for this repository. The work plan is `ICLR_PLAN.md`; verified problems in the current draft are in `PAPER_AUDIT.md`. Read both before starting any task, and re-read the relevant section of the plan when a session resumes.

## What this repo is

Research code for "Interpreting and Steering LLM Agents for Social Simulations", an ICLR 2027 submission (paper deadline 2026-09-25 23:59 AoE).

- Tasks: lottery (sure 50 vs. 50% chance of n), ultimatum game in the responder role, brick alternative-uses, stapler improvement.
- Methods: prompting ladder; Goodfire SAE feature steering on Llama-3.3-70B-Instruct (layer 50, hosted API via EDSL); linear-probe steering on a local Hugging Face stack (layer 48; replicated on Qwen-2-7B-Instruct, layer 17).
- Existing directories: `cleaned/`, `Probes/`, `Revised Prompting/` (the name contains a space, so quote it), `SAE/`. Treat them as read-only history.

## Rules that outrank any task instruction

1. **No number without a file behind it.** Never invent, estimate, interpolate, or hand-type a result. Every value, table and figure is produced by a script reading raw logs in this repo, and is registered in `MANIFEST.csv` (id, value, script, inputs, git SHA). If something cannot be computed, write "not available" and say why. Under ICLR 2027's policy a misrepresentation produced by an AI tool is an ethics violation by the authors.
2. **Existing results are read-only.** Do not edit, overwrite, move or delete anything in the four legacy directories or any raw log. New work goes under `cv_bench/` (code) and `results/<track>/<task>/<timestamp>_<gitsha>/` (outputs).
3. **The frozen test split stays frozen.** Do not generate, open, or evaluate on test-split prompts until a human gives the unlock instruction in the session and the `prereg-v1` git tag exists. Every choice of direction, feature, layer, position, dose, prompt wording or analysis setting is made on the discovery, selection and calibration splits.
4. **The outcome never decides a rerun.** Rerun only for a technical reason (bug, OOM, corrupted file) and record it in `logs/DEVIATIONS.md` with the before and after. Do not change seeds, prompts, doses, thresholds, exclusions or metrics because a result looks unhelpful. A result that contradicts the paper's claims is reported as prominently as one that supports them.
5. **Every arm that runs is reported.** Arms that fail or get dropped go into `reports/EXCLUDED_ARMS.md` with what was tried and what happened. Nothing is deleted.
6. **Stop at gates.** The plan marks GATE points. Write the requested summary, stop, and wait. Do not carry on "to save time".
7. **Ask before spending.** Estimate first and get approval for any job above 8 GPU-hours, any paid API batch, and any download above 50 GB.
8. **Shared machine manners.** Check `nvidia-smi` and use only GPUs the human assigned. Never kill processes you did not start. Run long jobs under `tmux` or `nohup` with checkpoint and resume.
9. **Secrets and anonymity.** Never print or commit API keys. Anything destined for the supplement must contain no usernames, absolute paths, hostnames or git history.
10. **Git.** Work on branch `iclr-extension`. Commit small and often with messages that name the task id. No force-push, no history rewriting.
11. **Keep the AI-use log.** Append to `logs/AI_USE_LOG.md` what you did in each session (code written, analyses run, text drafted). The authors need it for the mandatory AI-use statement.
12. **You draft, the authors decide.** Text for the paper goes into `paper_patches/` as suggestions with each quantitative claim tagged by its `MANIFEST.csv` id. Items marked AUTHOR DECISION in the plan are not yours to settle.

## Conventions

- Python package `cv_bench/`, tests in `cv_bench/tests/`, run with `pytest -q` before any GPU job.
- Reports in `reports/`, figures in `figures/<id>.{pdf,png}` with the generating script beside them as `figures/make_<id>.py`.
- Record decisions and their reasons in `logs/DECISIONS.md` as you go.
- Left-padded batches need explicit `position_ids`; a test must show that batched and unbatched logits agree before any batched result is trusted.

---

## Amendment, 22 Sept 2026 — in force until the cutoff (Thu 24 Sept 06:00 UTC)

Authors' amendment to **rules 6 and 7**, recorded here because this file outranks the plans and a
reader must not apply the originals by mistake. The full text is in `FRIDAY_PLAN.md` under
"scheduling by estimate"; `logs/DECISIONS.md` records what changed and why.

**Rule 6 (Stop at gates) — amended.** Gates whose criteria are numbers become automatic checks until
the cutoff. Gate B2 and Gate B3 are evaluated exactly as written in `ICLR_PLAN.md`, with plan v4's
thresholds: pass means continue and report, fail means stop that branch and report, and for B2
iteration happens on the synthetic grid only. Every other gate still stops and waits. **The test split
stays locked** until a human unlocks it after `PREREG.md` is tagged.

**Rule 7 (Ask before spending) — amended.** The 8 GPU-hour threshold is replaced, until the cutoff, by
a **total cap of 400 GPU-hours**. Work proceeds without per-job approval inside that cap; the authors
are asked only before exceeding it. Paid API batches and downloads above the storage rule's threshold
still need approval, unchanged.

**Unchanged and explicitly reaffirmed:** rule 1 (no number without a file behind it), rule 2 (existing
results are read-only), rule 4 (the outcome never decides a rerun — technical reasons only, logged in
`logs/DEVIATIONS.md`, and never a change of seeds, prompts, doses, thresholds or metrics on a retry),
rule 5 (every arm that runs is reported), rule 9 (secrets and anonymity), rule 12 (the authors decide).

After the cutoff, rules 6 and 7 apply as originally written.

---

## Amendment, 22 Sept 2026 — rule 16: autonomy, both sessions

Added at the authors' instruction. **Numbering note:** this file contains rules 1–12; there are no
rules 13–15 in either checkout. The number 16 is the authors' and is kept so their reference resolves,
rather than renumbered to 13. Track B merges this section; it is authored here, per the coordination
amendment.

16. **No task waits for author approval except four hard stops.** Outside them the standing procedure
    is: **keep every threshold and lock intact, choose the option cheapest to reverse, record it with
    the alternatives, proceed.**

    **The four hard stops — these still require the authors:**

    1. **Changing a pre-registered threshold or metric.** Any value fixed in advance — the minimum
       detectable change, the 0.8–1.2 slope band, the ≥ 0.8 preference share, the cloning
       correlation ≥ 0.95, a dose grid once logged — is not ours to move.
    2. **Changing an anchor's training objective after its dry run has passed.** Once B3.2's soft-label
       cross-entropy has cloned to criterion, the objective is frozen; re-specifying it after seeing a
       result is exactly the move rule 4 forbids.
    3. **Exceeding the GPU budget.** This session: **400 GPU-hours to the cutoff**. Track B:
       **1,000 GPU-hours through 5 Nov**. Both are evaluated on `sacct` totals for the shared `cvb_`
       prefix, so the figure is project-wide, not per-session.
    4. **Paid API spend above what is already approved.** The standing approval is $50 for G5b's
       five-judge scoring. Anything beyond it is a new request.

    **What "cheapest to reverse" means in practice.** Prefer recoding saved text to regenerating it;
    prefer adding a run to replacing one; prefer a new output file to overwriting an old one; prefer a
    subset that can be widened to a sweep that must be discarded. Where two options cost the same, take
    the one that leaves more evidence behind.

    **What "record it with the alternatives" means.** An entry in `logs/DECISIONS.md` naming the choice
    made, the options not taken, and why — written when the choice is made, not reconstructed
    afterwards. A decision taken under rule 16 without that entry is not covered by rule 16.

    **The test split (amends rule 3).** The unlock is no longer an affirmative instruction in session.
    After the `prereg-v1` tag exists, a **24-hour veto window** opens; if no author vetoes within it,
    the split may be opened. Operationally, and to keep the window meaningful rather than nominal:
    the window opens only once the tag is present, its opening and its expiry time are posted in
    `logs/DECISIONS.md` at the moment it opens, and nothing on the test split is generated, opened or
    evaluated before the full 24 hours have elapsed. Silence is consent under this rule, which is
    precisely why the announcement is not optional.

    **What rule 16 does not touch.** Rule 1 (no number without a file behind it), rule 2 (existing
    results are read-only), rule 4 (the outcome never decides a rerun — rule 16's "keep every threshold
    and lock intact" restates it), rule 5 (every arm that runs is reported), rule 9 (secrets and
    anonymity) and rule 12 (paper text is drafted here and decided by the authors). Rule 16 removes the
    approval step from ordinary work; it removes no obligation to record, to report, or to leave the
    legacy directories alone.

    **Relation to the earlier 22 Sept amendment.** That amendment suspended rules 6 and 7 until the
    cutoff. Rule 16 generalises it and outlasts it: after the cutoff, rules 6 and 7 return as written
    *except* where rule 16's four hard stops already define what needs approval.
