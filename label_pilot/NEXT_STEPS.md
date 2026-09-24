# Next steps for the revised lottery/ultimatum pilot

The local pipeline now runs the released SAE without Goodfire's inference or
interpretation API. Keep the existing SAE. Independently validate the selected
features instead of training a new SAE or relabeling all 65,536 features before
the deadline. Goodfire labels remain the starting annotations.

The active protocol is now **plan-v3: risk, altruism, fairness, creativity**.
Reciprocity and conformity were introduced by the assistant and have been
removed from the active design at the user's request. Earlier GPU engineering
checks remain preserved. The revised smoke and harvest are now complete: 176 evaluations, 32 exact zero-edit checks, and 352 harvested prompts.

## 1. Review the task definitions and candidate features

On September 23, the user reported that Goodfire supplied the CSV and believes it
matches `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`. Proceed with that working
correspondence and attribute the labels to Goodfire. This is supplier provenance
reported by the user, not independent verification against a release manifest.
The record is in `outputs/label-provenance.json`; no further credential setup is
needed.

Start with the readable `outputs/CANDIDATE_REVIEW.md`: it shows all 20 labels,
potential retrieval mismatches, and one task example per construct. The revised harvest covers 9/20 candidates. The original altruism anchor 31935 has no positive discovery coverage under the task-prompt calibration rule.

Read `outputs/plan-v3/candidates.json` and `outputs/plan-v3/discovery.json`.
The four constructs and BM25 retrieval are a pilot, not a validation of all social
science concepts. Record off-topic retrievals as failures. For risk, separate
dominated decisions from preference-sensitive lotteries. For ultimatum, keep
acceptance-by-offer curves for both altruism and fairness feature groups;
acceptance alone does not establish altruism, and blanket rejection does not
establish sensitivity to unequal offers. For
creativity, use independent ratings of relevance, feasibility, novelty and
diversity; answer length is not quality.

Resolve substantive changes before the behavioral run. If changing prompts,
candidates, or scoring, create a new immutable plan and recalibrate as needed.
Do not reuse the frozen scenarios for tuning.

## 2. Collect fresh activations, then obtain blinded descriptions

The new `outputs/blind-interpretation-v3` packet is ready: 20 aliases, nine with positive discovery evidence, and 332 held-out items spanning ten features. One feature activates only in selection, so an independent description for it may remain unavailable. The previous `blind-interpretation-v2` packet belongs to the superseded tasks. Use the new packet’s
`explanation_inputs.json` as the sole feature
evidence for a separate human or model annotator. It contains anonymous feature
aliases, activation values, and contexts. Do not give the annotator the CSV,
candidate labels, or private answer key. Save its descriptions and their hashes
before showing any held-out activation challenges.
The copy-and-paste annotator prompt and return format are in
`BLIND_ANNOTATOR_PROMPT.md`. Use a separate annotator/session that has not seen the
labels or this conversation; the current assistant context has seen the labels.

Then give a separate evaluator those locked descriptions and
`heldout_challenges.json`. Ask for a JSON list of
`{"id": "challenge ID", "predicted_active": true}` objects, one per challenge.
Repeat using Goodfire descriptions on the same challenge set with the evaluator
blinded to description source. Score both with `label_pilot.interpret score`.
Keep `private_answer_key.json` and the feature-alias mapping out of both contexts.
No-coverage features cannot be independently interpreted from these examples;
report them as unavailable. The packet samples task text, so it supports only a
limited interpretation claim, not general language-wide feature semantics.

## 3. Run behavioral screening, selection, and frozen confirmation

The completed `outputs/collected-plan-v3/results/plan-v3-harvest/run/calibration.json` supplies discovery calibration. Neither smoke
calibration nor `harvest-v2` calibration is valid for this plan. For each stage,
resume the stopped pod or use an equivalent two-GPU
host, obtain its current direct SSH endpoint, and attach a new session receipt
with a fresh absolute shutdown deadline. The old receipts and guards expire and
must not be reused for a new paid session.

Use `--plan label_pilot/outputs/plan-v3` and the downloaded calibration from the
new harvest. Launch `--stage screen` with a unique run ID,
then `selection`. Both compare feature doses against unmodified inference, zero
edits, persona prompts, strong prompts, and matched random directions. Collect
each run before stopping. A long stage can span bounded sessions using the same
run ID plus `--resume`, provided its exact source, plan, and calibration remain
unchanged. Keep the archived source named in its session receipt.

After complete selection, run `label_pilot.analyze lock`, then launch `confirm`
with that lock and the same calibration. Report all predeclared controls,
retrieval-only versus empirically selected interventions, and null results.
No behavioral selection or frozen confirmation has been completed yet.

## 4. Rate outputs and prepare the separate author-review report

The user explicitly requested no manuscript edits. Consolidate results in
`../output/SAE_RESULTS_FOR_REVIEW.md` (relative to the repository root), including
null/failed results and limitations. Include the raw evidence in the companion
`SAE_RESULTS_REVIEW_BUNDLE.zip`. The user chooses what is incorporated later.

Blind the creative outputs to condition and obtain ratings before claiming an
effect on creativity. Include a capability/validity check, answer-order and
wording sensitivity, intervention dose, prompt activation coverage, and the
frequency of zero realized suppression. The current random direction is one
fixed direction per feature; stronger claims would benefit from several random
directions and additional task families.

Present the contribution as a reproducible method for testing label-guided
interventions, with explicit failures and limits. Activation prediction and
behavioral changes answer different questions; neither establishes a stable
human-like trait. Do not describe the new explanations as independent if their
author saw Goodfire's labels.

## Resources and timing

The original working environment has locally configured credentials. A fresh
checkout must configure its own model and provider access; credentials and
generated outputs are not included in Git. See the package README for setup.

The replacement pair was quoted at $4.23/hour while running, with about 192 GB total VRAM, 377 GB allocated RAM and a 300 GB persistent volume. Compute is stopped. Both original and replacement volumes are retained at $0.083/hour each, about $4/day total. The current coverage-based forecast is 3.89 inference hours (about $16.44 at the observed quote), excluding startup, interpretation, human ratings, retries and analysis. See `outputs/workload-plan-v3-after-harvest.json`; `outputs/GPU_VALIDATION.md` is historical plan-v2 only. The two-hour session guard is not
a campaign-wide dollar cap. Track actual account spend between sessions.

The stated Friday September 25 EOD AoE deadline is Saturday September 26 at
12:00 UTC / 05:00 PDT. Aim to finish GPU experiments Thursday and use Friday for
ratings, analysis, and author review. Do not edit the paper without a later user
instruction to incorporate selected results.
