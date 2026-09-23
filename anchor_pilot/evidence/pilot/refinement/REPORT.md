# Combined-anchor refinement

The first pilot did not recover its planted parameters closely. This follow-up retains that result and evaluates a bounded 600-update refinement on 300 new prompts. Original frozen prompts were not added to training.

Planted curvature **0.8**, weighting **0.72**, loss aversion **2.0**, inverse temperature **3.0**, A-label bias **0**.

| Condition | Curvature | Weighting | Loss aversion | Planted-choice RMSE | Min A/B mass |
|---|---:|---:|---:|---:|---:|
| baseline | 0.5155 | 1.5000 | 0.3610 | 0.3846 | 0.6234 |
| lora_combined_original | 0.5283 | 0.9186 | 1.6668 | 0.1375 | 0.9989 |
| lora_combined_refined | 0.5395 | 0.8890 | 1.6844 | 0.1142 | 0.9996 |
| mean_delta_common_norm | 0.5297 | 1.5000 | 0.3636 | 0.3674 | 0.9821 |
| mean_delta_fitted_magnitude | 0.5623 | 1.0163 | 0.8908 | 0.1978 | 0.9999 |
| sae_k10_common_norm | 0.5222 | 1.5000 | 0.3729 | 0.3818 | 0.8756 |
| sae_k10_fitted_magnitude | 0.5261 | 1.5000 | 0.3821 | 0.3802 | 0.9100 |
| sae_k1_common_norm | 0.5238 | 1.5000 | 0.3746 | 0.3803 | 0.0323 |
| sae_k1_fitted_magnitude | 0.5246 | 1.5000 | 0.3752 | 0.3801 | 0.0374 |
| sae_k3_common_norm | 0.5221 | 1.5000 | 0.3714 | 0.3819 | 0.3612 |
| sae_k3_fitted_magnitude | 0.5236 | 1.5000 | 0.3732 | 0.3811 | 0.2362 |

## Refined footprint

Mean residual-shift norm: 7.4247. Ten-feature relative reconstruction error: 0.9736.

| Feature | Cached label | Mean decoder projection | Mean encoder change |
|---|---|---:|---:|
| 39254 | Formatting newlines for visual text organization | -1.0108 | -0.4470 |
| 28889 | The assistant needs to maintain professional boundaries or request clarification | -0.9842 | -0.1720 |
| 8752 | The assistant is formatting its response with structured spacing and lists | -0.8827 | -0.1704 |
| 1079 | The assistant is providing a structured multi-part response | -0.7805 | 0.0033 |
| 4448 | Colons that introduce answers or explanations in structured text | -0.7387 | -0.0097 |
| 54007 | The assistant should structure its response with line breaks for clarity | -0.7328 | -0.1599 |
| 3244 | The assistant is providing a list of options | -0.6791 | 0.0000 |
| 63793 | The assistant should give a binary yes/no or single-word response | -0.6564 | -0.2287 |
| 53691 | Syntactical sugar in programming languages | 0.6526 | 0.0000 |
| 50314 | Explanatory prose structure and connecting phrases | -0.6459 | -0.1186 |

## Limits

- Original and refined adapters are compared on the SAME fresh grid. Original first-pass results on the earlier grid remain unchanged.
- Checkpoints use training-audit loss only. Fresh evaluation reward ratios and synthetic recovery checks were fixed before the refinement ran.
- Scenario bootstrap intervals are in analysis.json; these are not repeated independent model training runs.
- Common-norm and original-magnitude replays are separate controls. Even original-magnitude replay changes one position at one layer; the full adapter changes several layers and all prompt positions.
- Sparse failure while raw replay also fails cannot isolate an SAE dictionary limitation.
- New reward levels test numerical generalization within the same prompt template, stakes, probabilities, and reference point; other task families remain untested.
- Cached feature labels are interpretation aids, not behavioral ground truth.
- Feature 47380 matches the cached option-selection label text; its identity with the historical Fig. 3 feature is not independently established. See ../TARGETED_FOOTPRINTS.md.
- The external scientific go/pivot rule remains unavailable. No automatic confirmatory pass is assigned.
