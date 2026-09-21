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
