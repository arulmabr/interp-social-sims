# Provisional pilot results — September 16, 2026

**Execution is complete; the positive preference anchor is not yet validated.**
The real 70B pipeline ran successfully, but even the refined LoRA did not recover
the planted CPT parameters. The current sparse SAE replay does not reproduce
the adapter's behavior. My recommendation is to repair anchor recovery and
answer-format calibration before paying for a full feature sweep. This is a
research recommendation, not the missing externally specified go/pivot rule.

## Completed and saved

- Unquantized bf16 Llama-3.3-70B-Instruct and the released Goodfire layer-50 SAE
  on the same two-H200 stack; exact model and SAE revisions are recorded.
- 101 conditions × 720 prompts: raw gradients at layers 48/50, reward probes,
  random directions, persona directions and prompts, six requested features,
  the creativity sum, sparse readout anchors, four CPT LoRAs, their footprints,
  and both norm-matched and original-magnitude residual replays.
- A separately frozen 300-prompt refinement grid with 11 conditions, including
  the original and refined combined adapters on the same new prompts. This adds
  3,300 readouts to the 72,720 original readouts. A separate 720-row diagnostic
  re-evaluation is marked development-only.
- All 19 software checks passed on the GPU host. Synthetic teacher recovery
  succeeded before model training; that success was not treated as model recovery.
- **193 remote files were copied and SHA-256 verified.** Adapters, raw scores,
  directions, residual footprints, execution source, manifests and logs are local.
- The provider accepted the stop request and the Runpod UI showed **Not running,
  $0.00/hour** for both new pilot pods. The session took about **77.5 minutes**
  from the first deployment request to the stop confirmation. A conservative
  estimate at the displayed rates is **about $12.02**, below the approved $20
  cap; this is not a provider invoice. The original smoke pod's retained 300GB
  volume continues at **$0.083/hour**.

## What the LoRA learned

All four original adapters improved substantially over the base model but
failed close recovery of their planted parameters. The combined adapter's
first frozen fit was curvature 0.508, weighting 1.149, loss aversion 1.410,
against a target of 0.800, 0.720, 2.000. Those results remain unchanged.

The bounded refinement ran 600 additional updates. Its checkpoint at 500
additional updates had the lowest fixed training-audit loss. Neither the
original frozen rows nor the new evaluation rows were added to training.

| Parameter | Planted | Refined, fresh grid | 95% scenario bootstrap interval |
|---|---:|---:|---:|
| Curvature | 0.800 | 0.540 | 0.500–0.586 |
| Probability weighting | 0.720 | 0.889 | 0.817–0.978 |
| Loss aversion | 2.000 | 1.684 | 1.563–1.848 |
| Inverse temperature | 3.000 | 2.270 | 2.112–2.464 |
| A-label bias | 0.000 | 0.012 | −0.034–0.052 |

The first three planted parameters remain outside these descriptive intervals.
The intervals resample economic scenarios with paired answer orders; they are
not uncertainty across independent training runs. The refined adapter had no
conditional argmax dominance violations on the 40 fresh dominance prompts,
and its minimum A/B probability mass was 0.99958. These successes do not rescue
its parameter-recovery failure.

## Behavior versus residual replay

All entries below use the same 300 fresh prompts and the combined CPT teacher.
RMSE compares conditional risky-choice probabilities with the teacher; lower
is better. Invalid-answer counts mean full-vocabulary A/B mass below 0.95.
The residual replays in this table come from the refined adapter.

| Condition | Teacher-choice RMSE | Invalid-answer count |
|---|---:|---:|
| Base model | 0.3846 | 16 / 300 |
| Original combined LoRA | 0.1375 | 0 / 300 |
| Refined combined LoRA | 0.1142 | 0 / 300 |
| Raw mean residual shift, norm 1 | 0.3674 | 0 / 300 |
| Raw mean residual shift, original magnitude | 0.1978 | 0 / 300 |
| Ten SAE features, original fitted magnitude | 0.3802 | 1 / 300 |

Refinement improved teacher-choice RMSE by about 17% on the same fresh grid.
Restoring the raw shift's original magnitude helped substantially, so shrinking
it to norm 1 was an important source of attenuation. The ten-feature SAE replay
still performed near the base model. Its relative reconstruction error was
0.9736; the four original adapters had errors from 0.9721 to 0.9795.

This tests a particular signed, sparse selection and reconstruction method.
It does **not** show that the full SAE dictionary cannot represent preferences.
A fixed vector at one position also has less capacity than a LoRA acting across
several layers and all prompt positions. Even the raw replay did not match the
full adapter, so the behavioral gap cannot be attributed entirely to the SAE.

[Fresh-grid figure (PDF)](evidence/pilot/figures/fresh_grid_recovery.pdf) ·
[Dictionary geometry (PDF)](evidence/pilot/figures/dictionary_geometry.pdf)

## Readout anchor, fairness and feature identities

On the original frozen split, a two-offset action comparator predicted the
positive layer-50 gradient with RMSE 0.0468, versus 0.2995 for a CPT model fitted
on discovery and selection responses. For the original combined LoRA, the
ordering reversed: CPT 0.1106, action offsets 0.3097. This is consistent with
the intended contrast, but the action comparator spans only constant risky
and A-label offsets and does not establish a definitive classification.

The six requested features had readout cosines from −0.0038 to 0.0176;
the creativity triple was 0.0204. The layer-48 reward probe was −0.0135.
The signed ten-feature readout approximation had cosine 0.3103 and relative
residual error 0.9507. Its positive replay was also better predicted by the
limited action comparator than by CPT. Low cosine alone did not demonstrate
preference steering in any of the named features.

Additive edits achieved the requested residual norms closely: the largest
relative norm error across the saved original comparisons was **0.28%**.
However, **all three candidate doses failed answer-validity calibration**.
At norm 1, 132 of 720 calibration readouts had A/B mass below 0.95. The analysis
therefore labels norm-1 comparisons exploratory. In the full 720-prompt sweep,
the positive layer-50 gradient had zero such failures, and the negative
gradient had 218. This asymmetry must be resolved before a confirmatory
bidirectional steering test. The unedited baseline itself had 31 failures.

The nominated-feature audit includes index 47380, whose cached label matches
“The assistant should select between provided options.” This is a label match,
not a verified historical Fig. 3 identity. For the refined adapter, feature
184's decoder projection changed despite its encoder activation remaining
zero, illustrating why encoder thresholding can conceal residual shifts.
The option-selection label's projection and encoder change also differed
between the original and refined adapters. Labels are interpretation aids,
not ground truth for the semantic content of an intervention.

## Next research decision

Before a full sweep, obtain a LoRA that recovers the planted parameters on a
newly frozen grid and fix the baseline/steering answer-format failures. A
neutral CPT adapter would help separate common format learning from changes
in curvature, weighting and loss aversion. Then freeze the external go/pivot
criteria and test richer SAE reconstructions against matched raw replay
controls. The current reward probe is a provisional reward-magnitude probe,
not a reproduction of an externally specified pretrained probe.

Scientific go/pivot thresholds and automatic classifications remain unset.
No full 65,536-feature sweep was launched.

## Inspect or reproduce

- [Original comparison report](evidence/pilot/REPORT.md) and [all 101 conditions (CSV)](evidence/pilot/comparison.csv).
- [Fresh-grid refinement report](evidence/pilot/refinement/REPORT.md) and [11 conditions (CSV)](evidence/pilot/refinement/comparison.csv).
- [Nominated feature footprints](evidence/pilot/TARGETED_FOOTPRINTS.md) and [feature comparison (CSV)](evidence/pilot/targeted_feature_comparison.csv).
- [Integrity audit](evidence/pilot/artifact_audit.json), verified raw-file hashes (retained in the local operational archive), and GPU stop verification (retained in the local operational archive).
- [Executed source snapshot](evidence/pilot/execution_source/manifest.json), [protocol and deviations](PROTOCOL.md), [commands and package guide](README.md), and session record (retained in the local operational archive).

Raw `scores_*.json`, parameter fits, scenario intervals, switching curves,
selection locks, adapters and per-prompt residuals are in the linked run directory.
The first-pass failure and earlier engineering failures are retained for audit.
