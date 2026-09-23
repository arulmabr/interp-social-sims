# Replay diagnostic results

This is a provisional representation diagnostic. The full external scientific go/pivot rule remains unavailable.

540 new frozen prompts, 16 conditions; saved repair checkpoint 700; no retraining.

## Main comparison

| Intervention | RMSE to full LoRA | RMSE to planted teacher | Minimum A/B mass |
|---|---:|---:|---:|
| Base model | 0.36805 | 0.37756 | 0.999998 |
| Full LoRA | 0.00000 | 0.03436 | 0.999949 |
| Raw: all positions, exact replacement | 0.00000 | 0.03436 | 0.999949 |
| Raw: all positions, additive difference | 0.00000 | 0.03436 | 0.999949 |
| Raw: final position, prompt-specific | 0.11705 | 0.12258 | 0.999998 |
| Raw: context positions only | 0.23925 | 0.24996 | 0.999979 |
| Raw: discovery mean, original magnitude | 0.25053 | 0.26187 | 0.999998 |
| Raw: discovery mean, norm 1 | 0.36241 | 0.37212 | 0.999998 |
| SAE encoder difference: all positions | 0.09711 | 0.10487 | 0.999983 |
| SAE encoder difference: final position | 0.21424 | 0.22311 | 0.999998 |
| SAE 10-feature subspace: all positions | 0.27320 | 0.28486 | 0.999998 |
| SAE 10-feature subspace: final position | 0.33902 | 0.34985 | 0.999998 |
| SAE 30-feature subspace: all positions | 0.13801 | 0.15105 | 0.999997 |
| SAE 30-feature subspace: final position | 0.26121 | 0.27252 | 0.999998 |
| SAE 10-feature fixed mean: final position | 0.36187 | 0.37228 | 0.999998 |
| SAE 30-feature fixed mean: final position | 0.33676 | 0.34714 | 0.999998 |

## Interpretation limits

All-position raw replacement and addition are engineering identity controls. Prompt-specific raw and SAE replays use adapted activations from the same prompt; they do not establish independent steering.
The encoder method uses all latent differences, with no top-k restriction. The 10/30-feature supports were selected geometrically from an earlier discovery mean. Their coefficients vary per prompt and token in the subspace conditions. Mean conditions use one fixed vector.
Original magnitudes are retained, except the explicitly named norm-1 mean control. All-position and final-token comparisons change intervention scope and are not common-total-norm comparisons.
Failure of these SAE methods does not establish that no sparse preference intervention exists. Causal feature reselection remains separate work.
Bootstrap intervals in replay_analysis.json resample answer-order-paired scenarios, not training seeds. These are interpolated reward levels under the same prompt template, not task-family generalization.

## Full LoRA fitted parameters

| Parameter | Planted | Recovered |
|---|---:|---:|
| curvature | 0.80000 | 0.79066 |
| weighting | 0.72000 | 0.74438 |
| loss_aversion | 2.00000 | 1.95078 |
| inverse_temperature | 3.00000 | 2.82450 |
| label_bias | 0.00000 | -0.04041 |

## Integrity

All 124 files listed in the remote transfer manifest verified. Raw-score metrics were recomputed locally; both development and frozen complete-state identity gates passed.
See replay_audit.json, replay_analysis.json, comparison.csv, raw score files, and execution_source/.
