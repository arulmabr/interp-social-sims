# Repair results — September 17, 2026

**The format repair worked, and the LoRA passes the predeclared provisional
parameter-recovery checks. The tested SAE replays do not reproduce that LoRA.**
I recommend improving the residual replay and feature-selection method before
paying for a full SAE sweep. These results do not establish a general inability
of SAEs to represent preferences, and the external scientific go/pivot rule
is still unavailable.

The GPU is stopped. All 29 conditions × 540 frozen prompts are saved locally,
and all **83 remote files were SHA-256 verified**. The session lasted about
58 minutes from the initial start request to the stop confirmation. Its
conservative cost estimate is **$9.00**, including the existing retained volume
during that window, below the approved $20 cap. This is not a provider invoice.
The new pod has no ongoing compute or temporary-storage charge. The original
smoke pod's retained volume still costs about **$0.083/hour**.

## What was repaired

The previous run left substantial training and held-out error. This follow-up
used 2,160 training prompts, 540 separate validation prompts and 540 new frozen
prompts, with paired answer orders, gains, losses and mixed lotteries. The
frozen reward ratios were disjoint from both earlier evaluation grids.
Validation responses never entered optimizer updates.

The adapter expanded from rank-8 q/v projections in blocks 40–50 to rank-16
adapters in all seven attention/MLP projections in blocks 0–50. The base stayed
unquantized bf16 on the same pinned 70B model and released layer-50 SAE stack.
All 26 software checks passed on the two-H200 host, including the expanded
adapter's backward path across both GPUs. The actual 70B training also recorded
nonzero adapter gradients on each GPU and checked that base weights had no gradients.

Training stopped at update 800 after two consecutive passing validations.
Checkpoint **700** had the lowest qualifying validation cross entropy and was
selected before any frozen model responses were read. Format, adapter, vectors
and dose were locked before frozen evaluation.

## Frozen parameter recovery

| Parameter | Planted | Recovered | 95% scenario bootstrap interval |
|---|---:|---:|---:|
| Curvature | 0.800 | 0.799 | 0.791–0.810 |
| Probability weighting | 0.720 | 0.763 | 0.748–0.777 |
| Loss aversion | 2.000 | 1.964 | 1.927–2.021 |
| Inverse temperature | 3.000 | 2.702 | 2.632–2.744 |
| A-label bias | 0.000 | −0.027 | −0.040–−0.009 |

Teacher-choice probability RMSE is **0.03497**, below the declared 0.04 limit.
The fitted parameters meet the predeclared absolute-error tolerances, and
minimum A/B probability mass is **0.999947**. All 100 bootstrap fits converged.

This is approximate recovery, not exact recovery. Weighting, inverse temperature
and label bias retain deviations outside these descriptive intervals. The
intervals resample economic scenarios while preserving answer-order pairs;
they are not uncertainty across independent training runs. The operational
tolerances are in [REPAIR_PLAN.md](REPAIR_PLAN.md), and are not a substitute for
the missing external scientific rule.

The LoRA had **0/60 conditional-argmax dominance violations**. Mean absolute
answer-order probability gap fell from 0.2948 for the base model to 0.0282.
Conditional argmax reversed in 176/180 matched gain/loss pairs; four pairs did
not reverse. Those remaining imperfections should be retained in any scientific
assessment rather than hidden by the aggregate fit.

## Answer validity and norm matching

The strict system instruction to answer only A or B worked better than either
assistant prefill. On the 240 discovery calibration prompts, minimum A/B mass
was 0.8673 for the original format, 0.999998 for the strict instruction, 0.9801
for `Answer:`, and 0.00108 for `I choose option`.

The strict instruction was fixed for every condition. Both signs of the
gradients at layers 48/50 passed separate validation. After training, all
23 additive directions passed at the same residual norm, **rho = 1**, at the
final prompt token. All 15,660 frozen readouts, including the separate
original-magnitude controls, had A/B mass at least 0.999947. Maximum realized
norm error among the common-norm frozen conditions was **1.225%**, below the
declared 2% limit. Zero-dose identity was exact.

## Full adapter versus residual and SAE replay

Every row below uses the same 540 frozen prompts and CPT target. Lower RMSE
means closer choice probabilities to the planted agent.

| Intervention | Residual norm at edited token | Teacher-choice RMSE |
|---|---:|---:|
| Base model | — | 0.3855 |
| Full repaired LoRA | Distributed weight intervention | **0.0350** |
| Raw mean residual shift | 1 | 0.3811 |
| Raw mean residual shift, original magnitude | 15.009 | 0.2728 |
| Ten-feature SAE preference replay | 1 | 0.3842 |
| Ten-feature SAE preference replay, fitted magnitude | 10.784 | 0.3691 |

The full adapter reduces error by about 91% relative to baseline on this grid.
The nominated individual SAE features also remain near baseline at norm 1.
Restoring the raw shift's magnitude helps, but even that replay falls far short
of the LoRA and has 4/60 dominance violations.

This distinction matters: a fixed vector at one layer and token does not
reproduce the adapter's prompt-dependent computation across many layers and
positions. Failure already occurs before SAE compression. The sparse replay
therefore does not isolate a dictionary limitation.

The constant mean shift accounts for 86.2% of total squared discovery shift
energy, and the median promptwise cosine with that mean is 0.945. Nevertheless,
its behavioral replay is weak. Capturing residual energy is not equivalent to
capturing the behaviorally relevant change.

## What the SAE footprint says

All six nominated features had zero encoder activation before and after the
LoRA at the measured final-token positions on the discovery subset. Their
decoder projections were nonzero, demonstrating the difference between these
two footprint measurements. Feature 184's mean unit-decoder projection was
0.1056, versus 0.3112 for feature 47380. Feature 47380's mean encoder change was
−0.0113, with mean absolute change 0.1269.

Feature 47380 matches the cached option-selection label. Its identity with the
historical paper figure has not been independently verified. Several largest
geometric footprint features have metadata/formatting or unrelated cached
labels. These labels and projection magnitudes are interpretation aids, not
proof that those features causally implement the preference.

The nominated decoder/readout cosines range from 0.00284 to 0.02626; the
creativity sum is 0.03285 and the positive layer-48 reward probe is 0.000629.
The sparse ten-feature readout anchor has cosine 0.2472 with the raw gradient
and relative reconstruction error 0.9690. Low readout alignment by itself did
not make a nominated feature reproduce the preference anchor.

For the preference footprint, top-projection selection plus a joint coefficient
fit gave ten-feature relative reconstruction error **0.6956**. A separate,
post hoc CPU-only greedy sparse fit using the same discovery mean lowered
this to **0.6041 with ten features** and **0.5469 with thirty features**.
Those alternative vectors were not behaviorally tested and did not affect
checkpoint selection or any frozen intervention. This shows some room to
improve geometric selection; it does not establish a successful SAE preference
intervention.

## Recommended next experiment

First replay the adapter-induced layer-50 residual changes at all prompt
positions through the unchanged suffix, then restrict replay to the answer
position, then replace each prompt's shift with the mean. Use development
prompts and a newly frozen evaluation split. These checks would separate
implementation, position and averaging losses before introducing the SAE basis.
Then select SAE candidates by their causal effect on switching points or CPT
curvature across the discovery reward grid, retaining readout cosine as a
covariate. A large sweep of the current labeled features or the current
top-projection replay is not yet justified by these results.

The original four component-specific adapters remain documented in the
[first pilot results](PILOT_RESULTS.md). This repair trained one combined
adapter; it does not establish disentangled curvature, weighting and
loss-aversion SAE features. Other templates, task families, training seeds,
positions and sparse selection procedures remain untested here.

## Evidence and reproducibility

- [Full 29-condition report](evidence/repair/REPORT.md)
- [Comparison table](evidence/repair/comparison.csv)
- [Raw execution report and operational gates](evidence/repair/report.json)
- [Source and artifact integrity audit](evidence/repair/artifact_audit.json)
- [Grouped probability errors](evidence/repair/grouped_probability_errors.json)
- [Nominated feature footprints](evidence/repair/targeted_footprints.json)
- [Post hoc sparse geometry](evidence/repair/sparse_geometry_diagnostic.json)
- Session, cost estimate and verified shutdown (retained in the local operational archive)

Exact execution source, runtime versions, the selected adapter, discovery
residuals, unit directions, the pre-response selection lock and raw score
files are in the run directory. CPU postprocessing source is archived there
separately. The earlier pilot and refinement outputs remain unchanged.
