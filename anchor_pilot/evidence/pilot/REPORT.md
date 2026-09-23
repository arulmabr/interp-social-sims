# Provisional action–preference anchor pilot

**Real bf16 model diagnostic run.**

Recorded 101 conditions across 720 prompts. GPU execution status: `gpu_execution_complete_analysis_pending`.

Scientific go/pivot remains **unset**: the full decision rule was not supplied. Raw-gradient and LoRA labels describe intended control roles, not demonstrated classifications.

**Dose calibration failed; steering comparisons are exploratory at the provisional norm.**

## Frozen-split parameter recovery

| Condition | Curvature | Weighting | Loss aversion | Inverse temperature | A-label bias | CPT fit RMSE |
|---|---:|---:|---:|---:|---:|---:|
| baseline | 0.5042 | 1.5000 | 0.3000 | 9.4978 | -1.2877 | 0.3022 |
| gradient_l48_sign+1 | 0.5095 | 1.1777 | 0.3000 | 9.0705 | -1.3632 | 0.2840 |
| gradient_l48_sign-1 | 0.4813 | 1.5000 | 0.3000 | 7.6514 | -0.6478 | 0.3454 |
| gradient_l50_sign+1 | 0.5025 | 1.1966 | 0.3000 | 9.1636 | -1.3666 | 0.2858 |
| gradient_l50_sign-1 | 0.4845 | 1.5000 | 0.3000 | 7.7572 | -0.6835 | 0.3450 |
| lora_combined | 0.5082 | 1.1489 | 1.4103 | 1.6795 | 0.0850 | 0.1013 |
| lora_curvature_only | 0.5158 | 1.1494 | 0.6696 | 1.9952 | 0.1085 | 0.0903 |
| lora_loss_aversion_only | 0.6444 | 1.1786 | 1.4517 | 1.5513 | 0.1101 | 0.1258 |
| lora_weighting_only | 0.5987 | 1.0721 | 0.6051 | 1.1526 | 0.1843 | 0.0812 |

## Training diagnostics

| Agent | Best training-audit CE | Target entropy floor | Excess CE |
|---|---:|---:|---:|
| combined | 0.5195 | 0.4771 | 0.0424 |
| curvature_only | 0.5548 | 0.5225 | 0.0324 |
| weighting_only | 0.5928 | 0.5399 | 0.0530 |
| loss_aversion_only | 0.4950 | 0.4419 | 0.0530 |

## Preference anchor versus residual replay

Frozen conditional-choice RMSE against each planted agent; lower is better. This is diagnostic, not a pass threshold. Consult answer mass before interpreting conditional probabilities.

| Agent | Base model | Full LoRA | Raw mean delta | SAE k=1 | SAE k=3 | SAE k=10 |
|---|---:|---:|---:|---:|---:|---:|
| combined | 0.4223 | 0.1570 | 0.4051 | 0.4248 | 0.4144 | 0.4139 |
| curvature_only | 0.3863 | 0.1353 | 0.3719 | 0.3824 | 0.3846 | 0.3773 |
| weighting_only | 0.4097 | 0.1776 | 0.3946 | 0.4112 | 0.4072 | 0.4003 |
| loss_aversion_only | 0.4220 | 0.1703 | 0.4076 | 0.4200 | 0.4241 | 0.4180 |

## Sparse footprint reconstruction

| Agent | Mean delta norm | Relative error k=1 | Relative error k=3 | Relative error k=10 |
|---|---:|---:|---:|---:|
| combined | 7.0617 | 0.9938 | 0.9877 | 0.9732 |
| curvature_only | 8.4975 | 0.9931 | 0.9857 | 0.9721 |
| weighting_only | 9.3977 | 0.9939 | 0.9888 | 0.9795 |
| loss_aversion_only | 8.0356 | 0.9939 | 0.9866 | 0.9756 |

## Original-magnitude replay

Coefficients and norms come from discovery footprints, with no tuning to frozen outcomes. These controls deliberately use their fitted magnitudes instead of the common rho=1.

| Agent | Raw mean delta | SAE k=1 | SAE k=3 | SAE k=10 |
|---|---:|---:|---:|---:|
| combined | 0.2244 | 0.4251 | 0.4141 | 0.4118 |
| curvature_only | 0.1934 | 0.3827 | 0.3833 | 0.3764 |
| weighting_only | 0.2099 | 0.4106 | 0.4058 | 0.3953 |
| loss_aversion_only | 0.2149 | 0.4202 | 0.4242 | 0.4160 |

## Similarity across the trained agents

Cosines between discovery mean residual shifts. Similarity can reflect common answer-format and calibration learning; these single-seed comparisons do not establish disentangled preference axes.

| Agent | combined | curvature_only | weighting_only | loss_aversion_only |
|---|---:|---:|---:|---:|
| combined | 1.000 | 0.825 | 0.714 | 0.810 |
| curvature_only | 0.825 | 1.000 | 0.807 | 0.792 |
| weighting_only | 0.714 | 0.807 | 1.000 | 0.699 |
| loss_aversion_only | 0.810 | 0.792 | 0.699 | 1.000 |

## Interpretation boundaries

- Parameter fits at their bounds or with poor probability fit are model misspecification diagnostics, not evidence for a preference shift.
- The CPT family uses shared gain/loss curvature, shared TK92 weighting, a zero reference point, and logistic choice noise. Other preference families remain untested.
- The full adapter and a fixed layer-50 vector have different capacity. Compare the raw mean-delta replay with its SAE approximation before attributing failure to the dictionary.
- Sparse reconstructions use signed decoder coefficients. They need not be feasible edits of nonnegative SAE encoder activations.
- Three random directions per layer provide a pilot control, not a well-powered null distribution.
- Bootstrap intervals resample economic scenarios together with both answer orders. They measure scenario variability, not repeated stochastic LLM sampling.
- Training targets are the exact expected answer-token loss under the planted stochastic CPT agent; frozen reward levels never train or select adapters.
- The reward probe is a new pilot reward-magnitude probe. Its standardized weights are mapped back to raw residual coordinates.

See `comparison.csv` for all conditions, `analysis.json` for fits, crossings and uncertainty, `labeled_footprints.json` for cached Goodfire labels, `selection_lock.json` for choices frozen before evaluation, and raw `scores_*.json` for reproducibility.
