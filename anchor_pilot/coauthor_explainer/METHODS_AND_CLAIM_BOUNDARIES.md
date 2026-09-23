# Methods and claim boundaries for coauthor review

This note explains the completed `decision-refined-20260918T235147Z` run. It does
not introduce a new experiment, re-fit results, or alter the saved decision rule.
The companion PDF is the visual explanation; `MESSAGE_TO_COAUTHORS.md` is a
paste-ready message. All numerical results below are from the saved analysis.

## A glossary tied to this implementation

- **LLM:** Large Language Model. The checkpoint is Llama-3.3-70B-Instruct.
- **bf16:** bfloat16, a 16-bit floating-point format. This describes computation
  precision, not a new model or a guarantee of identical results across hardware.
- **Residual stream / hidden state:** the vector of internal activations at an
  edited transformer block. Our latest edits use zero-based block-output 50.
- **Logit:** the model's score for an answer token before converting scores into
  probabilities. Risky/safe labels are mapped back from A/B for each prompt.
- **Gradient:** sensitivity of the risky-minus-safe logit difference to the
  hidden state. We average prompt-specific discovery gradients and normalize.
  This can move answer readout without demonstrating a stable preference policy.
- **SAE:** Sparse Autoencoder. We use the released Goodfire layer-50 dictionary.
  Its decoder columns are feature directions; the ten-feature edit is a signed
  combination of those columns. This is not necessarily a feasible edit to
  nonnegative encoder activations. We do not replace the state with its SAE
  reconstruction, so decoder reconstruction error is not added to the baseline.
- **LoRA:** Low-Rank Adaptation. Trained low-rank weight updates supplement
  frozen base weights. Our saved adapter was trained in an earlier repair run;
  it was reused, not retrained, in the latest comparison.
- **CPT:** Cumulative Prospect Theory. The original framework is described by
  [Tversky and Kahneman (1992)](https://doi.org/10.1007/BF00122574). The specific
  restricted family implemented here is documented below from `cpt.py`.
- **RMSE:** Root Mean Squared Error: square prediction differences, average
  them, and take the square root. A probability RMSE of 0.05 is five percentage
  points on that scale. It is not a 5% wrong-answer rate or mean absolute error.
- **Seed:** an optimization initialization. Two steering seeds do not constitute
  two independently trained base models or two independently trained LoRAs.

## What the synthetic teacher specifies

Outcomes are changes from a zero reference. Their numerical magnitude is divided
by 100 tokens. For normalized outcome x, our value function is:

```
v(x) = x^alpha                  for x >= 0
v(x) = -lambda * (-x)^alpha    for x < 0
w(p) = p^gamma / [p^gamma + (1-p)^gamma]^(1/gamma)
```

For each option, outcomes are ranked and cumulative probability intervals are
formed separately for gains and losses. A decision weight is the difference of
w at the interval endpoints; option value V is the sum of these weights times
v(x). For s_A = +1 when risky is labeled A and -1 otherwise:

```
p_CPT(risky) = sigmoid(beta * [V_risky - V_safe] + b * s_A)
```

The five fitted quantities are alpha (curvature), gamma (probability weighting),
lambda (loss aversion), beta (choice sensitivity) and b (A-label bias). Curvature
and probability weighting are shared across gains/losses. Reference point and
normalization are fixed. This is narrower than the general CPT framework.

Combined target: alpha=0.8, gamma=0.72, lambda=2, beta=3, b=0.
Neutral target: alpha=1, gamma=1, lambda=1, beta=3, b=0. The neutral target has
linear values and undistorted probabilities, but finite beta keeps its choices
stochastic. Neither target is inferred from humans in this study.

Even a LoRA that reproduces the teacher does not by itself prove an internal
mechanism corresponding to those preference parameters. It is a validated
behavioral reference if it passes; its intended role is not assumed from the
fact that its weights were trained.

## Training and evaluation are distinct operations

The latest run reused the combined-CPT LoRA. It trained new dense directions and
new coefficients in selected ten-feature SAE subspaces on the base model. The
37 candidates included earlier footprint-derived features and specified paper
features. Single-feature interventions of both signs were scored over the full
discovery reward grid; selection was by expected answer cross entropy, not
readout-gradient attribution. It was also not yet the direct switching-point or
curvature-based selection proposed by the collaborator.

There were 16 initial fits: two targets, two methods, two token scopes and two
seeds, each with 160 updates. Eight fits in the selected scopes received 480
additional updates. This refinement was declared before frozen responses were
inspected. Checkpoint and dose choice used selection data. Stage-one frozen
scores were excluded from the final analysis and refinement.

Both targets ultimately selected all nonpadding prompt positions and residual
norm 16 per edited position. Dense and sparse directions share that norm and
scope; equal norm does not equalize functional strength, search difficulty or
global norm across different prompt lengths. The LoRA is a weight-space
reference, not another equal-norm residual direction.

Discovery: 216 prompts. Selection: 96. Frozen: 108 new economic scenarios x two
answer orders x two phrasings = 432 prompts per condition, not 432 independent
economic scenarios or human subjects. All three gain/loss/mixed frames are used.
The second wording family appears only in the frozen set. There are 28 final
conditions and 48 separate elementary control prompts per condition.

The response measure is the next-token probability of the risky answer,
renormalized over A and B. A separate answer-mass check requires that the model
actually assigns almost all next-token mass to these valid answers. This avoids
mistaking normalized probabilities from invalid-format outputs for good choices.

## Two errors answer different questions

1. **Teacher error:** compare the intervention's observed risky probabilities
   with the known planted teacher. The latest operational limit is RMSE <=0.060.
2. **Explanatory error:** fit a behavioral model on selection responses, then
   compare its predicted probabilities with actual frozen intervention responses.
   This is what the bias-versus-CPT plot reports. A low bias-model error does not
   mean the intervention successfully matched the teacher.

The CPT explanatory fit has the five parameters above. The competing model is:

```
logit p_bias(risky) = a_frame * logit p_base(risky) + c_frame + b * s_A
```

There are three positive a terms and three c terms, one each for gain, loss and
mixed frames, plus one A-label term: seven fitted parameters. `p_base` is the
base model's response to the same prompt, including held-out wording. This
comparison therefore uses baseline predictions as a covariate at test time.
Multiplying log-odds is an explanatory confidence transformation, not a change
to the generation temperature used to collect this run.

Both explanatory fits use selection data, not frozen responses. Their predictive
errors are computed on the frozen set. The bias model has more parameters and
receives useful baseline information; it is not an equal-capacity mechanistic
test. A better score cannot prove that reward preferences were unchanged, that
one feature has a specific meaning, or that every other preference model fails.

## What was actually observed

- SAE explanatory RMSE: bias model 0.0377-0.0558; CPT 0.1111-0.1641, across the
  eight target/seed/wording combinations. These are observed ranges, not
  confidence intervals or a formal significance test of the model difference.
- LoRA teacher RMSE: 0.0416 original wording; 0.1147 new wording. It passed all
  latest provisional gates only in the original wording. New wording failed
  target recovery, CPT prediction, parameter tolerances and answer-order gap.
- Dense and SAE each passed 0/8 complete target-recovery evaluations. Each also
  passed 0/8 on the separate preference-like check that omits exact teacher
  recovery. Individual gates can pass even when the complete evaluation fails.
- SAE answer-order gaps remained 0.0735-0.1100. However, base-model gaps were
  larger (0.2784 original; 0.1732 new wording). These data do not show that SAE
  steering introduced or increased all label bias. Residual sensitivity still
  violates the declared invariance criterion.
- The combined-target SAE seeds each scored 43/48 on elementary controls versus
  46/48 for base; the losses were arithmetic items. The LoRA scored 47/48.
- The ten-feature readout approximation had relative residual norm 0.961.
  This is not a full-dictionary span test. Low readout cosine is not sufficient
  for preference control: combined-target SAE cosines were 0.068-0.073.

The teacher-error scenario-bootstrap lower bounds exceeded 0.060 for all eight
cells of each steering method. Resampling preserves paired answer orders within
economic scenarios. It does not establish uncertainty across all phrasings,
model families or LoRA training seeds.

## What the operational rule did

The complete target-recovery rule checks teacher RMSE <=0.060, held-out CPT
prediction RMSE <=0.060, CPT RMSE advantage over the bias model >=0.010,
parameter errors within (0.12,0.12,0.25) for alpha/gamma/lambda, minimum valid
answer mass >=0.99, mean answer-order gap <=0.05, dominance violation rate
<=0.05, elementary-control accuracy drop <=0.05, valid control answer mass,
realized norm tolerance, and converged/interior fits. The separate preference-like
check drops teacher/parameter recovery and requires an observable effect.

The raw gradient's action-control pass means at least one valid-dose gradient
condition had an observable effect, favored the shortcut explanation by the
declared margin in both phrasings, and did not pass the preference-like check.
It is not a preference pass. That action-control gate does not require every
comprehension criterion or an absolute shortcut-RMSE limit.

Synthetic calibration rejected 20/20 specified action nulls and detected 7/7
specified CPT alternatives. This finite check is not a population false-positive
rate estimate. The collaborator's full scientific go/pivot rule was unavailable;
these are provisional operational thresholds. The older repair rule used a
stricter 0.040 teacher-error limit; both wording sets miss it on this new grid.

## Dense control, original probe, and feature interpretation

Both dense and probe steering add a dense residual direction. The current dense
control learns it by backpropagating target choice loss. In the repository's
original probe implementation, a standardized linear logistic classifier supplies
the direction. The earlier layer-48 description came from a repository default. Shreyas
subsequently reported a layer-50 probe experiment with a ramp over the final
20% of positions; the current selected control uses block-output 50 and all
prompt positions. See ERRATA.md; a matched rerun was not performed here.
The original pipeline also samples generated answers, while this pilot reads
next-token probabilities. These differences must be reconciled with Shreyas;
the original probe was not rerun as a matched condition here.

Goodfire trained the SAE dictionary. Available feature descriptions are cached
Neuronpedia annotations, as documented in `SAE/docs/LABELS.md`. They are not
independently validated semantic interpretations produced by this pilot.
Behavioral intervention effects provide evidence about effects in the tested
setting, not a complete semantic account of the features.

The full proposal's layer-48 reward-probe comparison, persona direction,
component-specific validated LoRAs and direct switching-point/curvature feature
selection remain outside the validated scope of this latest run.

## Decision and next discriminating experiment

Defer a full SAE sweep. Validate the positive LoRA reference across fresh
wording families and economic grids first. If that fails, pause the preference
claim. If it passes, compare small matched dense and SAE interventions, also
aligning the original probe setup before drawing conclusions about probes.

- LoRA and dense pass; sparse SAE fails: evidence against the tested sparse
  candidate set/fitting recipe, not every SAE dictionary.
- LoRA passes; dense and SAE fail: change the constant-vector intervention
  format before blaming the dictionary.
- Robust SAE success: supports a bounded confirmation, not universal control.

## Evidence index

All experiment evidence is local to the repository. No Slack message or external
publication was sent as part of preparing this explanation.

- `anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/decision_analysis.json`: complete metrics and failed gates.
- Same run: `decision_comparison.csv`, `plan.json`, `selection_lock.json`,
  `readout_geometry.json`, `direction_alignment.csv`, `delivery_audit.json`.
- `anchor_pilot/cpt.py`, `decision_analysis.py`, `decision_report.py`: definitions,
  explanatory fits and operational classifications.
- `Probes/probes.py`, `Probes/models.py`, `Probes/config.py`: current repository
  implementation of the original probe pipeline; confirm historical settings
  with its authors before treating source defaults as a matched rerun.
- `figure_data.csv`: the exact eight pairs plotted in the visual brief.
- `provenance.json`: source hashes and public references.

Primary method references: [CPT](https://doi.org/10.1007/BF00122574),
[LoRA](https://arxiv.org/abs/2106.09685),
[Goodfire SAE](https://huggingface.co/Goodfire/Llama-3.3-70B-Instruct-SAE-l50).
