# Provisional pilot protocol, version 1

This extends the completed engineering smoke. It does not substitute for the
full go/pivot plan, which was not supplied. Scientific pass/fail thresholds
remain unset. This protocol is fixed before collecting new frozen responses.

## Design and measurement

- 720 prompts: 360 economic scenarios, each with risky=A and risky=B.
- Gains, losses, mixed gambles; five probabilities (0.1, 0.25, 0.5, 0.75, 0.9),
  two stakes (25, 75), twelve reward/stake ratios (0.4 through 6).
- Discovery: 360 prompts. Selection: 180. Frozen: 180. Reward levels differ
  across splits within each grid; both answer orders stay in the same split.
- Zero reference point; utility units of 100 tokens. Shared gain/loss power
  curvature, shared TK92 cumulative probability weighting, loss multiplier,
  logistic inverse temperature, and A-label logit bias are the five parameters.
- Frozen response probabilities never select directions, doses, adapters, or
  features. A rerun after viewing frozen results is exploratory on this split.
- Score risky-minus-safe logits, conditional choice probability, and full-vocab
  A/B mass. Fractional cross entropy fits model probabilities; scenario
  bootstrapping keeps both answer orders. This is not repeated LLM sampling.

Synthetic validation recovered all planted parameters to below 0.000001
absolute error on all splits for all four agents. All five parameters have
full local Jacobian rank. Twenty stochastic recovery runs per agent used
64 independent synthetic choices per prompt. Combined-agent median absolute
errors: 0.0061 curvature, 0.0106 weighting, 0.0324 loss aversion, 0.0590
inverse temperature, 0.0115 label bias. These validate the simulator/estimator,
not the real model or arbitrary CPT families.

## Common stack and controls

Llama-3.3-70B-Instruct revision
`6f6073b423013f6a7d4d9f39144961bfbfbc386b`, unquantized bf16, SDPA,
two GPUs. Goodfire layer-50 SAE revision
`128ee921ecd1b8b3a87d776cbcc357c0855da134`. Layer numbers mean zero-based
block-output hooks, consistent with this repository's residual-post dictionary.
Input model cards: [Meta Llama 3.3](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct)
and [Goodfire layer-50 SAE](https://huggingface.co/Goodfire/Llama-3.3-70B-Instruct-SAE-l50).

Explicit PyTorch transfers connect fixed weight partitions. Accelerate's
inference dispatch hooks are removed before training. Frozen base weights
stay bf16; LoRA and optimizer states are float32. CPU fixtures verify adapter
gradients, base restoration, save/reload, and left-padding invariance. The
actual two-GPU backward path must still pass runtime checks.

Every residual edit affects only the final prompt position. At layers 48 and
50: discovery-mean raw readout gradient, reward-magnitude probe, persona
contrast, and three isotropic random directions. Standardized probe weights
map back as w/scale. This is a new pilot reward-magnitude probe, not the paper's
existing probe. Cautious, neutral and adventurous prompts use the same stack.

SAE columns: 184, 4237, 31935, 13142, 20117, 4992; equal-latent-weight
creativity sum; highest-positive-cosine feature; signed OMP readout matches
at k=1,3,10. No reconstruct-baseline substitution or activation clamping.

Common rho comes from 0.25, 1, 4 using selection-only gradient edits of both
signs at both layers. Require A/B mass >=0.95 and realized bf16 displacement
within 2% of requested norm for every calibration prompt. Choose valid rho
nearest 1. If none passes, retain the calibration failure and continue
exploratory comparisons at the prespecified rho nearest 1. These are engineering criteria, not scientific
preference thresholds. Every condition reports its own answer mass and norms;
gradient calibration alone does not certify other directions. Every residual
direction runs at both signs of the same rho.

Rank the six candidate features by absolute discovery curvature change over
the whole discovery grid. Record switching points, fit quality, bounds and
readout cosine; cosine never determines causal ranking. This is not the full
65,536-feature sweep. Poor/boundary fits invalidate a preference interpretation.

## Weight-space anchors and dictionary footprints

Four rank-8 q/v LoRAs in layers 40–50 inclusive, scaling alpha=16:

| Agent | Curvature | Weighting | Loss aversion | Inverse temperature |
|---|---:|---:|---:|---:|
| Combined | 0.8 | 0.72 | 2 | 3 |
| Curvature only | 0.8 | 1 | 1 | 3 |
| Weighting only | 1 | 0.72 | 1 | 3 |
| Loss aversion only | 1 | 1 | 2 | 3 |

Planted label biases are zero. Optimize expected prompt-to-answer-token cross
entropy under each stochastic agent: the analytic expectation of Bernoulli
choice examples, preserving choice noise without synthetic sampling error.
Full-vocabulary softmax penalizes invalid answer mass. Training uses discovery
and selection rows, 200 updates, batch 8, AdamW learning rate 0.0002, weight
decay 0.01, gradient clip 1, nonreentrant gradient checkpointing. Save the best
checkpoint on a fixed training-audit subset, never frozen responses. Training
audit loss is explicitly not validation performance.

Compare base/adapted final-position layer-50 residuals on discovery rows.
Record decoder projections and encoded latent differences, join cached labels,
and save per-prompt delta h. Replay normalized mean delta h. Rank largest
mean geometric footprints; jointly fit their columns to mean delta h at
k=1,3,10, then replay normalized vectors. Record error before scaling. Signed
coefficients need not be feasible nonnegative encoder-activation changes.
Failure of k<=10 does not imply failure of the full dictionary.

Adapters affect several layers and all prompt positions; fixed residual
replay has smaller capacity. Raw mean-delta replay exposes part of this gap.
Parameter-specific adapters are comparisons against the same base, not clean
causal derivatives around a separately trained neutral CPT adapter.

## Outputs and interpretation

Default real run: 85 conditions x 720 prompts = 61,200 final readouts, plus
discovery, calibration and training. Save adapters, raw scores, directions,
footprints, source hashes, versions and a selection lock before frozen scoring.
CPU analysis after GPU stop produces CSV comparisons, parameter fits, scenario
bootstrap intervals for anchors, switching points, labeled footprints and a
Markdown report.

Readout and LoRA are intended action/preference controls. Recovery, fit
quality, dominance, label stability and predictive errors must support these
roles; no automatic scientific classification. Compare held-out prediction
from CPT with two action offsets (constant risky bias and constant A-label
bias) applied to actual baseline logits. That comparator cannot cover every
possible action shortcut. The full externally specified go/pivot rule is
still required for its confirmatory decision.

## Authorized compute session

The user approved **up to two hours, capped at $20 for this session**. The
original stopped pod's host had only one H200 available, so the expanded
pilot uses two H200s on pod `rmn7zfyflnjjos`, at $9.18/hour for GPUs plus
$0.042/hour for its 300GB temporary container disk. It has no retained volume.
An initial failed launch on `8uul9a2d36yhdc` was backed up and stopped.

The absolute provider stop deadline is **2026-09-17 06:21:49 UTC**. A local
supervisor copies and hashes artifacts every 30 seconds and stops the pod
when the queued jobs finish, or at 06:11:49 UTC to leave a transfer margin.
Independent provider-stop guards remain armed. Temporary disk contents are
lost on stop, so verified local backup precedes shutdown. The original smoke
pod `9xc474y2j2oumc` remains stopped; its previously retained 300GB volume
continues at $0.083/hour. Neither failed attempts nor refinement extend the
session's original deadline or budget.

## Runtime corrections before any frozen evaluation

- The first expanded launch failed before evaluation because HF BatchEncoding
  did not match a plain-dict tensor transfer. The fix handles all Mapping
  containers, with a regression test. Outputs were backed up and GPUs stopped.
- The retry observed a 0.375-logit single-versus-batch bf16 difference. The
  earlier 0.3 engineering cutoff was overly strict. The runner now records
  both logits and probability differences, verifies exact zero-dose batch
  identity, and computes each prompt gradient in the same padded batches as
  intervention scoring. A CPU derivative test verifies no cross-example
  mixing or unintended division by batch size. This changes no scientific
  selection threshold; none has been specified.
- The actual two-GPU bf16 tiny-model backward test passed. These software
  repairs preceded all training and frozen-response evaluation.

- The all-prompt dose gate failed before training/frozen evaluation. Runtime
  now saves dose-specific mass and norm diagnostics, records this as a failed
  calibration, and continues the requested provisional comparisons at rho=1
  if no dose passes. This is an explicit exploratory continuation, not a
  calibration success or scientific pass. LoRA parameter recovery remains a
  separate test. Actual displacement norms are now saved per prompt rather
  than assigning every prompt its batch mean.

## Discovery-magnitude replay controls

The discovery LoRA mean residual shifts were approximately 7–9 units, much
larger than common rho=1. Before inspecting frozen outcomes, a second set of
16 controls was specified: each of the four agents' raw mean delta and k=1,3,10
SAE reconstructions at their original fitted magnitudes. These are separate
from the norm-matched family, with norms and scope explicitly labeled. They
distinguish simple dose attenuation from sparse reconstruction loss. The
selection rule uses discovery residuals only. See `outputs/fidelity_plan.json`.
The complete run therefore targets 101 conditions, 72,720 final readouts.

## Bounded combined-anchor refinement

First-pass frozen fits failed to recover the planted parameters closely. The
original outcomes are retained as failed first-pass evidence; their frozen
split is now inspected development evidence. One combined-anchor refinement
is fixed before its fresh evaluation: 600 additional updates, learning rate
0.00005, unchanged rank/layers, original discovery+selection training only.
A new 300-prompt grid uses ratios 0.55, 1.25, 2.3, 3.3, 6.5, each absent from
the original grid; 6.5 extends the original maximum. Its hash and synthetic
recovery checks are saved before training in `outputs/refinement-plan`.
Checkpoint selection uses training-audit loss only. The fresh grid evaluates
base, original and refined LoRAs on the same fresh prompts, and raw/SAE replay
at common and fitted magnitudes. This
is a separately reported refinement, never a rewrite of the original result.

## Descriptive nominated-feature audit

After the first-pass evaluation, a descriptive measurement was added for the
six requested features and feature 47380, whose cached label is "The assistant
should select between provided options." This is a released-dictionary label
match; the repository's historical crosswalk lacks an independently verified
Fig. 3 index. The audit uses saved discovery residuals and records decoder
projections and encoder changes for all four original adapters and the refined
combined adapter. It does not select interventions or checkpoints. Its results
are distinct from the prespecified causal feature ranking.
