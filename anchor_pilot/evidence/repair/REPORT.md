# Anchor recovery and format repair

Execution status: **completed**. Frozen model responses opened: **True**.

This follow-up has newly declared operational targets. The external scientific go/pivot rule remains unavailable; no scientific pass is assigned.

Selected format: `system_letter`. Common steering norm: 1.0.

Selected checkpoint: update 700. Validation teacher-choice RMSE: 0.03423. Operational validation recovery passed: True.

| Update | Training-audit RMSE | Validation RMSE | All validation recovery targets passed |
|---:|---:|---:|---|
| 1 | 0.38311 | 0.37042 | False |
| 100 | 0.07386 | 0.07801 | False |
| 200 | 0.05345 | 0.06068 | False |
| 300 | 0.03011 | 0.04186 | False |
| 400 | 0.02948 | 0.04029 | False |
| 500 | 0.02713 | 0.03614 | True |
| 600 | 0.02815 | 0.04035 | False |
| 700 | 0.02044 | 0.03423 | True |
| 800 | 0.02303 | 0.03717 | True |

Operational recovery requires teacher-choice RMSE ≤ 0.04, minimum A/B mass ≥ 0.99, a converged interior CPT fit, and parameter errors no larger than curvature 0.10, weighting 0.10, loss aversion 0.20, inverse temperature 0.40, and A-label bias 0.10. Every common-norm additive condition must have minimum A/B mass ≥ 0.95 and displacement error ≤ 2%.

Operational repair passed: **True**. Planted curvature 0.8, weighting 0.72, loss aversion 2.0, inverse temperature 3.0, A-label bias 0.0.

| Condition | Curvature | Weighting | Loss aversion | Teacher-choice RMSE | Min A/B mass |
|---|---:|---:|---:|---:|---:|
| baseline | 0.4745 | 1.5000 | 0.3000 | 0.3855 | 1.0000 |
| creativity_triple | 0.4749 | 1.5000 | 0.3000 | 0.3860 | 1.0000 |
| feature_13142 | 0.4728 | 1.5000 | 0.3000 | 0.3854 | 1.0000 |
| feature_184 | 0.4735 | 1.5000 | 0.3000 | 0.3848 | 1.0000 |
| feature_20117 | 0.4736 | 1.5000 | 0.3000 | 0.3850 | 1.0000 |
| feature_31935 | 0.4711 | 1.5000 | 0.3000 | 0.3856 | 1.0000 |
| feature_4237 | 0.4732 | 1.5000 | 0.3000 | 0.3866 | 1.0000 |
| feature_4992 | 0.4755 | 1.5000 | 0.3000 | 0.3874 | 1.0000 |
| gradient_l48_sign+1 | 0.5013 | 1.3269 | 0.3000 | 0.3718 | 1.0000 |
| gradient_l48_sign-1 | 0.4092 | 1.5000 | 0.3000 | 0.3979 | 1.0000 |
| gradient_l50_sign+1 | 0.5127 | 1.4352 | 0.3000 | 0.3735 | 1.0000 |
| gradient_l50_sign-1 | 0.4246 | 1.5000 | 0.3093 | 0.3955 | 1.0000 |
| lora_combined | 0.7992 | 0.7632 | 1.9637 | 0.0350 | 0.9999 |
| mean_delta | 0.4770 | 1.5000 | 0.3000 | 0.3811 | 1.0000 |
| mean_delta_fitted_magnitude | 0.4248 | 0.9407 | 0.4083 | 0.2728 | 1.0000 |
| random_l48_sign+1 | 0.4759 | 1.5000 | 0.3000 | 0.3857 | 1.0000 |
| random_l48_sign-1 | 0.4695 | 1.5000 | 0.3000 | 0.3859 | 1.0000 |
| random_l50_sign+1 | 0.4763 | 1.5000 | 0.3000 | 0.3848 | 1.0000 |
| random_l50_sign-1 | 0.4697 | 1.5000 | 0.3000 | 0.3859 | 1.0000 |
| reward_probe_l48_sign+1 | 0.4737 | 1.5000 | 0.3000 | 0.3880 | 1.0000 |
| reward_probe_l48_sign-1 | 0.4714 | 1.5000 | 0.3000 | 0.3829 | 1.0000 |
| sae_preference_k1 | 0.4737 | 1.5000 | 0.3000 | 0.3854 | 1.0000 |
| sae_preference_k10 | 0.4751 | 1.5000 | 0.3000 | 0.3842 | 1.0000 |
| sae_preference_k10_fitted_magnitude | 0.4965 | 1.5000 | 0.3000 | 0.3691 | 1.0000 |
| sae_preference_k1_fitted_magnitude | 0.4842 | 1.5000 | 0.3000 | 0.3819 | 1.0000 |
| sae_preference_k3 | 0.4744 | 1.5000 | 0.3000 | 0.3858 | 1.0000 |
| sae_preference_k3_fitted_magnitude | 0.4820 | 1.5000 | 0.3000 | 0.3874 | 1.0000 |
| sae_readout_k10_sign+1 | 0.4783 | 1.5000 | 0.3000 | 0.3901 | 1.0000 |
| sae_readout_k10_sign-1 | 0.4504 | 1.5000 | 0.3057 | 0.3831 | 1.0000 |

Mean residual-shift norm: 15.0094; ten-feature relative reconstruction error: 0.6956.

The constant mean shift accounts for 86.2% of the total squared per-prompt shift on discovery prompts. Its per-prompt relative reconstruction error is 0.3716. This measures information lost before the SAE projection; it does not by itself predict behavioral performance.

Post hoc geometric comparison using saved discovery residuals only. These vectors were not steered, did not enter checkpoint selection, and have no behavioral pass/fail result.

Greedy sparse discovery reconstruction errors: k=10, 0.6041; k=30, 0.5470. These alternative reconstructions have no behavioral evaluation in this run.

| Largest footprint feature | Cached label | Mean projection | Mean encoder change |
|---:|---|---:|---:|
| 11870 | System metadata header containing knowledge cutoff and current date | -9.8666 | 0.0000 |
| 18484 | The user is asking for a yes/no determination about factual consistency | 9.6361 | 0.2313 |
| 27289 | Formatting characters that separate items in structured text (commas, spaces, newlines) | 9.2941 | 0.3808 |
| 39110 | Chemical compound nomenclature and notation patterns | 9.2276 | 0.0269 |
| 29098 | The assistant should reject the user's request while remaining professional and helpful | 9.0052 | 0.0036 |
| 45026 | Text containing special characters or encoding challenges | -8.9792 | 0.0000 |
| 52426 | System header metadata containing knowledge cutoff and current dates | 8.9569 | 0.7434 |
| 19019 | Narrative transitions and temporal sequencing markers | 8.8460 | 0.7498 |
| 56637 | Hyphens in chemical nomenclature and technical terms | 8.7302 | 0.0000 |
| 28157 | The assistant should generate creative or explanatory content in response to prompts | -8.7031 | 0.0000 |

Descriptive fixed-feature analysis of discovery prompts; not intervention selection.

Feature 47380 matches the locally cached option-selection label; identity with the historical paper figure is not independently established.

| Nominated feature | Cached label | Readout cosine | Mean projection | Mean encoder change |
|---:|---|---:|---:|---:|
| 184 | Willing to take risks or make sacrifices for a goal | 0.0170 | 0.1056 | 0.0000 |
| 4237 | Executing potentially risky operations that require caution | 0.0149 | 0.5744 | 0.0000 |
| 31935 | Altruistic and selfless behavior or intentions | 0.0028 | -0.3638 | 0.0000 |
| 13142 | Enabling or empowering creative expression and exploration | 0.0263 | -0.4886 | 0.0000 |
| 20117 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | 0.0238 | 0.5458 | 0.0000 |
| 4992 | Professional innovation and creative problem-solving | 0.0245 | 1.1350 | 0.0000 |
| 47380 | The assistant should select between provided options | 0.0141 | 0.3112 | -0.0113 |

Limits: the larger adapter acts across layers and prompt positions; its mean residual replay is one vector at one layer and position. A sparse replay failure does not by itself isolate a dictionary limitation. Original-magnitude replays are separate diagnostics and are excluded from the common-norm gate. New reward levels use the same task template; repeated training seeds and external task generalization remain untested. Scenario bootstrap intervals describe variation across paired scenarios, not independent training runs.
