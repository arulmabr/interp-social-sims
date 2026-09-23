# Replay results — September 17, 2026 (Pacific)

**Verdict: retain the provisional LoRA preference anchor, but change the method
for turning it into SAE steering before a full feature sweep.** The replay
implementation works. Restricting the intervention to one token, averaging
across prompts, and SAE approximation each lose behavioral fidelity in the
tested sequence. No tested SAE replay meets the declared reproduction target.

This is a completed diagnostic with 16 conditions on 540 new frozen prompts,
plus 36 development prompts. It reused the saved repair adapter; no new LoRA
was trained. All 8,640 frozen readouts and 576 development readouts are saved.
The new GPU pod is stopped at $0/hour. The conservative session estimate is
**$2.07**, including the older retained volume during this session, below the
$20/two-hour ceiling. The estimate is not a provider invoice. The original
smoke pod's retained volume remains approximately $0.083/hour.

## What the new test resolves

The LoRA changes only blocks 0–50. We captured its complete output at block 50,
disabled the adapter, and inserted that state into the base model before the
unchanged suffix. Both exact replacement and adding the full residual difference
matched the LoRA's risky-choice probabilities exactly on every development and
frozen prompt: maximum measured difference **0.0**.

The earlier replay failure therefore does not indicate that a layer-50
intervention is inherently unable to reproduce this adapter. Its full state can
do so. The restrictions imposed by the earlier replay matter.

Every number below uses the same new 540-prompt grid. Lower RMSE is better.
The teacher is the planted CPT decision-maker; agreement with LoRA is a separate
metric because the LoRA itself remains an approximate fit to that teacher.

| Intervention | RMSE to LoRA | RMSE to teacher |
|---|---:|---:|
| Base model | 0.36805 | 0.37756 |
| Full LoRA | 0.00000 | **0.03436** |
| Raw full-state replay, all positions | **0.00000** | **0.03436** |
| Raw prompt-specific replay, final position only | 0.11705 | 0.12258 |
| Raw prompt-specific replay, context positions only | 0.23925 | 0.24996 |
| Raw discovery mean, final position, original magnitude | 0.25053 | 0.26187 |
| Raw discovery mean, final position, norm 1 | 0.36241 | 0.37212 |
| SAE encoder-difference replay, all positions | **0.09711** | **0.10487** |
| SAE encoder-difference replay, final position | 0.21424 | 0.22311 |
| SAE 30-feature subspace replay, all positions | 0.13801 | 0.15105 |
| SAE 30-feature subspace replay, final position | 0.26121 | 0.27252 |
| SAE 30-feature fixed mean, final position | 0.33676 | 0.34714 |

The full 16-condition table, including the 10-feature methods, is in the linked
report below. No SAE condition met the predeclared provisional target of RMSE
to LoRA <=0.01 with minimum A/B mass >=0.99. Every condition retained answer
validity; the minimum across all frozen readouts was **0.999949**.

Restricting raw replay to the final position increased RMSE to LoRA by 0.11705
(95% paired-scenario interval 0.11192–0.12203). Replacing that prompt-specific
change with the discovery mean increased it by a further 0.13347
(0.11837–0.14935). Reducing the mean's norm to 1 added another 0.11189
(0.09856–0.12412). These are sequential ablation contrasts, not an additive
decomposition of independent causal mechanisms. The intervals use 1,000
bootstrap resamples of economic scenarios, preserving paired A/B orders; they
do not cover variation across training runs.

## What this says about the SAE

The SAE replay carries part of the adapter's behavioral effect: using
encoder differences across all positions reduced teacher RMSE to 0.10487,
compared with 0.37756 for the base model. However, it still fell well short of
the full adapter's 0.03436. The 30-feature all-position replay also improved
substantially over the fixed-vector versions, without meeting reproduction.

These prompt-specific SAE replays use LoRA activations from each evaluated
prompt. **They are oracle representation diagnostics, not independent steering
methods.** Success would demonstrate an ability to represent that change; it
would not by itself identify a reusable preference feature. The encoder method
uses all latent differences, while the 10/30-feature methods use fixed supports
selected geometrically from earlier discovery residuals, with coefficients
fitted per prompt and token. The mean controls use one fixed vector.

The experiment preserves original changes except the explicitly named norm-1
control. All-position interventions affect more tokens and have different total
displacement from final-token interventions. This tests replay fidelity, rather
than replacing the earlier norm-matched family comparison.

The result does not show that all SAEs or all fixed directions must fail.
It shows that these encoder and sparse-replay methods do not recover this
adapter closely enough, and that the earlier failure already had substantial
causes before SAE compression.

## The preference anchor still passes its provisional checks

| Parameter | Planted | Recovered on new grid |
|---|---:|---:|
| Curvature | 0.800 | 0.791 |
| Probability weighting | 0.720 | 0.744 |
| Loss aversion | 2.000 | 1.951 |
| Inverse temperature | 3.000 | 2.824 |
| A-label bias | 0.000 | -0.040 |

The fit converged without boundary parameters and remained within the earlier
repair's absolute-error tolerances. Teacher RMSE 0.03436 remained below 0.04.
The LoRA had 0/60 dominance violations, and its mean A/B answer-order gap was
0.02848. These remain approximate, provisional results under one prompt
template and one training seed. The new evaluation varies reward ratios within
the same task family; it is not evidence of broad task generalization.

## Research decision

Keep the repaired LoRA as the positive reference. Do not treat its average
final-token residual as an interchangeable preference anchor, and do not scale
the existing fixed-feature sweep on that assumption.

For the next scientific stage, develop a rule for choosing SAE interventions
from the base model's prompt/activations, without consulting LoRA states at test
time. Test token scope and causally select a bounded candidate set by switching
or fitted-curvature effects over the discovery reward grid, keeping readout
cosine as a covariate. Recalibrate common norms and token scope across the raw
readout, random, probe and SAE families. Then freeze a separate evaluation.
The full external scientific go/pivot rule is still required for confirmatory
classification; this report does not substitute a new rule for it.

## Verification and artifacts

All 32 software checks passed on the two-H200 host, including bf16 replay across
the device boundary and unequal prompt lengths. All **124 files** in the remote
transfer manifest verified locally by SHA-256. The audit also checked frozen
row counts, agreement with the locked plan, paired answer orders, all probability
metrics recalculated from raw scores, and exact execution-source hashes.

The first startup stopped before model loading because a local credential name
was incorrectly requested on the remote host. It was corrected to use the
already supplied environment credential and rerun in the same guarded session.
The failed attempt remains archived and collected no frozen model responses.
The final job exited with code 0. Automatic stop was confirmed by the provider
and the Runpod UI showed compute and temporary storage both not running.

- [Predeclared plan](REPLAY_PLAN.md)
- [Full results table](evidence/replay/REPORT.md)
- [Raw execution report](evidence/replay/report.json)
- [Locally recomputed analysis and intervals](evidence/replay/replay_analysis.json)
- [Integrity and completeness audit](evidence/replay/replay_audit.json)
- [LoRA operational recovery check](evidence/replay/lora_recovery.json)
- Session, shutdown and cost record (retained in the local operational archive)
- [Prior repair findings](REPAIR_RESULTS.md)
