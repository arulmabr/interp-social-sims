# Anchor recovery and answer-format repair

**GPU execution is complete and the pod is stopped.** See
[REPAIR_RESULTS.md](REPAIR_RESULTS.md) for the results, remaining limitations
and verified $9.00 session estimate under the approved $20/two-hour cap. The first pilot's
results and archived execution source remain in [PILOT_RESULTS.md](PILOT_RESULTS.md).
This experiment addresses the two failures that currently block a larger SAE sweep:
inaccurate recovery of the planted CPT agent and unreliable A/B answer mass under
some interventions. It may stop with a documented failure; convergence is not guaranteed.

## Evidence motivating the change

The previous refined adapter's teacher-choice RMSE was 0.0867 even on its 540
training prompts. Its fresh-test RMSE was 0.1142, and the planted curvature,
weighting and loss aversion lay outside the scenario bootstrap intervals.
These observations support testing greater adapter capacity and better training
coverage. They do not establish that capacity is the only cause.

## Fixed design

- Same pinned Llama-3.3-70B-Instruct, bf16 weights, two-H200 stack and released
  layer-50 Goodfire SAE. No quantization or model-family change.
- 3,240 prompts: **2,160 training, 540 validation, 540 frozen test**, spanning
  gains, losses, mixed gambles, five probabilities, three stakes and paired A/B
  orderings. Reward ratios are disjoint across splits. The new frozen prompts
  are disjoint from both earlier evaluation grids. These remain tests within
  the same prompt template, not external-task generalization.
- CPT target: curvature 0.8, weighting 0.72, loss aversion 2.0, inverse
  temperature 3.0, A-label bias 0.0. Exact synthetic probabilities recover all
  five parameters on each split; the corresponding Jacobians have full rank.
- Rank-16 LoRA in all seven attention/MLP linear projections in blocks 0–50.
  The prior adapter used rank 8 in q/v projections in blocks 40–50. Keeping the
  new adapted blocks at or before layer 50 allows the footprint there to
  capture all adapter-induced changes entering the remaining frozen suffix.
- Soft full-vocabulary answer-token cross entropy, paired A/B mini-batches,
  effective batch 16, peak learning rate 0.0001, 50-update warmup, cosine decay
  to 0.00001. At most 2,400 updates; the wall-clock budget can stop it earlier.
  Checkpoints are assessed every 100 updates, plus the first and final update.
  Only training responses enter optimizer updates. Prefer validation-passing
  checkpoints, then the lowest full-vocabulary validation cross entropy.
  Two consecutive passing validations after at least 400 updates stop training.

## Calibration and frozen-test gates

1. Compare the original response format, a strict A/B system instruction,
   and assistant prefills `Answer:` and `I choose option`. The prefills are
   rendered with Transformers' documented
   [assistant-continuation mechanism](https://huggingface.co/docs/transformers/chat_templating).
   Real-tokenizer checks must confirm one continuation token per option and
   no retokenization of the existing prefix. All conditions then share one
   selected format, token pair, and edited position.
2. Use 240 **training** prompts for initial calibration. Require baseline A/B
   mass ≥ 0.99 and both signs of both raw gradients to have A/B mass ≥ 0.95 and
   realized norm error ≤ 2%. Try common norms 1, 0.5, 0.25, 0.1 in that order
   for formats ranked by baseline minimum answer mass. Stop if no format passes.
3. Validate the locked format/dose on all 540 validation prompts. Stop before
   training if validity does not generalize. Recompute gradients and probes
   in the selected format; do not reuse vectors from the earlier run.
4. Require the selected LoRA to pass **newly declared operational targets**:
   teacher-choice RMSE ≤ 0.04; minimum A/B mass ≥ 0.99; converged interior CPT
   fit; absolute errors ≤ 0.10 for curvature and weighting, ≤ 0.20 for loss
   aversion, ≤ 0.40 for inverse temperature, and ≤ 0.10 for A-label bias.
5. Build the LoRA footprint from training prompts. On validation prompts,
   choose the largest common norm no greater than the pretraining norm that
   passes answer-mass/norm checks for **all 23 additive directions**. If none
   passes, stop and leave frozen model responses unopened.
6. Lock the format, adapter, directions and dose before reading frozen model
   responses. Evaluate baseline, LoRA, 23 norm-matched interventions and four
   original-magnitude residual controls: **29 conditions × 540 prompts**.
   Original-magnitude controls are separate diagnostics and are excluded from
   the common-norm gate. No frozen-score feedback is used to retune this run.

The 23 directions cover ± gradients and random controls at layers 48/50,
± reward probe at layer 48, six nominated SAE features, the creativity sum,
± sparse SAE readout, the mean LoRA residual shift, and k=1/3/10 SAE preference
replays. This is a focused repair, not the full feature sweep or four new
component-specific adapter trainings. Selection by causal switching/curvature
effects is deferred until the anchors are usable.

These operational targets are **not** the unavailable external scientific
go/pivot rule. An operational pass would support proceeding with the pilot;
it would not prove that a feature encodes preferences. Sparse replay failure
also cannot isolate a dictionary limitation when the raw residual replay fails.

## Validation and execution

Local checks: **24 passed, two CUDA-only variants skipped**. Both two-GPU bf16
backward-path variants, including the expanded adapter, must run on the paid
host before the 70B job. A CPU fixture exercises all 29 condition files and
report generation; it explicitly bypasses scientific gates and is labeled as
software validation only. Early-stop reporting is tested separately.

The new session uses two H200s, a 300GB temporary container disk,
the existing authorized model credential, and the existing SSH key. The UI
currently offers restart at $9.18/hour for compute. Including the last observed
temporary-disk rate ($0.042/hour) and existing retained volume ($0.083/hour),
two hours is approximately **$18.61**; recheck the total before starting.
The approved cap is **$20 and two hours from the deployment request**, whichever
binds first. The user's instruction to proceed while they sleep followed the
concrete approval request. This is a new session; the previous approval covered
the completed pilot. Pod `f936ppziapfrzy` has an absolute stop deadline of
2026-09-17 08:19:26 UTC (1:19 a.m. Pacific). Its observed total rate is $9.222/hour.

An independent pod-side stop guard is armed before the experiment. Setup and
downloads count against the absolute deadline. The experiment stops at least
12 minutes before that deadline, reserving 30 minutes of its remaining runtime
for post-training comparisons. A local supervisor continuously copies and
SHA-256 verifies artifacts, then stops the pod after completion or failure;
it also stops at the ten-minute backup cutoff. Provider state is read back
after the stop request. Temporary disk is erased by stopping, so verified local
backup is required. The original retained volume continues its existing charge.

Reproducible entry points, from the repository root:

```bash
anchor_pilot/.venv/bin/python -m pytest -q anchor_pilot/test_core.py anchor_pilot/test_cpt.py anchor_pilot/test_modeling.py anchor_pilot/test_repair.py
anchor_pilot/.venv/bin/python -m anchor_pilot.repair --fixture --output anchor_pilot/outputs/NEW_FIXTURE --max-seconds 120 --reserve-seconds 0
anchor_pilot/.venv/bin/python -m anchor_pilot.repair_report --run PATH_TO_DOWNLOADED_RUN --bootstrap 100
```

The remote launcher uses `--runner run_repair.sh`; the watcher must use
`--stop-on-failure`. The frozen plan is in `outputs/repair-plan-v1/manifest.json`
and its hashed rows in `outputs/repair-plan-v1/rows.json`. Execution archives
its exact source, plan, calibration decisions, validation history, adapter,
directions, footprint and any completed frozen readouts.
