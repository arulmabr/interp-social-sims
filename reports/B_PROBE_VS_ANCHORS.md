# B_PROBE_VS_ANCHORS.md — the choice probe beside the anchors

**EXPLORATORY, SELECTION SPLIT, NOT PRE-REGISTERED.** Gate B2 stands failed, so no direction is certified preference-like here and none of this may be reported as a confirmatory result. Nothing touched the test split.


## The one-paragraph answer

Each direction was dosed to reproduce the bias adapter's shift of the legacy switching point (-91.14 tokens, from 210.08 unmodified to 118.94 under the bias adapter) on the calibration split, so every condition below moves behaviour by the same amount and any difference between them is a difference of *shape*. On that basis the choice probe is placed: **resembles bias_adapter**. The model-free fingerprint and the parametric shares are reported side by side because they do not always agree, and where they disagree that disagreement is itself the finding.


## Conditions, at matched behavioural dose

| condition | role | layer | scale | achieved shift | matched | D2 action | D2 payoff | D2 format | parametric top |
|---|---|---|---|---|---|---|---|---|---|
| `bias_adapter` | anchor | - | - | -91.14 | yes | 0.851 | 0.085 | 0.037 | preference 1.000 |
| `choice_probe_L48` | probe | 48 | 2.5000 | -91.12 | yes | 0.523 | 0.012 | 0.460 | format 1.000 |
| `choice_probe_L50` | probe | 50 | 1.1250 | -91.64 | yes | 0.575 | 0.003 | 0.368 | preference 1.000 |
| `diffmean_L48` | control | 48 | 0.0781 | -91.90 | yes | 0.034 | 0.012 | 0.928 | preference 1.000 |
| `diffmean_L50` | control | 50 | 0.0781 | -90.72 | yes | 0.159 | 0.020 | 0.793 | preference 1.000 |
| `random_a_L48` | control | 48 | - | - | **NO** | nan | nan | nan | not available nan |
| `random_a_L50` | control | 50 | - | - | **NO** | nan | nan | nan | not available nan |
| `random_b_L48` | control | 48 | 1.0000 | -20.15 | **NO** | 0.148 | 0.089 | 0.761 | format 1.000 |
| `random_b_L50` | control | 50 | - | - | **NO** | nan | nan | nan | not available nan |
| `readout_anchor_L48` | anchor | 48 | 0.0156 | -93.12 | yes | 0.014 | 0.018 | 0.906 | preference 1.000 |
| `readout_anchor_L50` | anchor | 50 | 0.0156 | -92.52 | yes | 0.009 | 0.019 | 0.927 | preference 1.000 |
| `reward_probe_L48` | control | 48 | 0.3750 | -90.16 | yes | 0.031 | 0.023 | 0.870 | format 1.000 |
| `reward_probe_L50` | control | 50 | 0.3750 | -93.86 | yes | 0.604 | 0.027 | 0.258 | preference 1.000 |

## Resemblance, in D2 space

| direction | distance to bias adapter | distance to readout anchor | closer to | beats the random band | verdict |
|---|---|---|---|---|---|
| `choice_probe_L48` | 0.5404 | 0.6794 | bias_adapter | yes | resembles bias_adapter |
| `choice_probe_L50` | 0.4396 | 0.7776 | bias_adapter | yes | resembles bias_adapter |
| `diffmean_L48` | 1.2113 | 0.0454 | readout_anchor_L48 | yes | resembles readout_anchor_L48 |
| `diffmean_L50` | 1.0267 | 0.1872 | readout_anchor_L48 | yes | resembles readout_anchor_L48 |
| `readout_anchor_L50` | 1.2267 | 0.0259 | readout_anchor_L48 | yes | resembles readout_anchor_L48 |
| `reward_probe_L48` | 1.1715 | 0.0430 | readout_anchor_L48 | yes | resembles readout_anchor_L48 |
| `reward_probe_L50` | 0.3465 | 0.8782 | bias_adapter | yes | resembles bias_adapter |

## What is not available, and why

- **D4 (certainty equivalents) and D6 (fact recall)** are implemented for synthetic agents: both take the intervened agent's *true* parameters, which a real direction does not have. Their model-side forms need CEs and recall elicited from the model, a prompt family this repo does not have. Reported as not available rather than filled with a synthetic stand-in.
- **4 direction(s) could not be dosed to the target** and are marked NO above: `random_a_L48`, `random_a_L50`, `random_b_L48`, `random_b_L50`. `ICLR_PLAN.md` B5: *a family that cannot reach a target without breaking outputs is recorded as such; that is a result.* Where these are the random controls, the null band is weakened or absent and every resemblance verdict above must be read with that in mind.
- No preference-like verdict is certified while Gate B2 stands failed.

## Provenance

| direction | source | sha256 |
|---|---|---|
| `bias_adapter` | `B3.2 adapter_bias.pt` | `n/a` |
| `choice_probe_L48` | `probe_reconstruction_L48.json` | `b43f07587b91855f` |
| `choice_probe_L50` | `probe_reconstruction_L50.json` | `c6a481efee62e9ad` |
| `diffmean_L48` | `probe_reconstruction_L48.json` | `b43f07587b91855f` |
| `diffmean_L50` | `probe_reconstruction_L50.json` | `c6a481efee62e9ad` |
| `random_a_L48` | `` | `n/a` |
| `random_a_L50` | `` | `n/a` |
| `random_b_L48` | `isotropic seed=48` | `n/a` |
| `random_b_L50` | `` | `n/a` |
| `readout_anchor_L48` | `grad_L48_legacy_sum.npy` | `ef2532fd98fb9b32` |
| `readout_anchor_L50` | `grad_L50_legacy_sum.npy` | `bb46e0e0988cd981` |
| `reward_probe_L48` | `probe_reconstruction_L48.json` | `b43f07587b91855f` |
| `reward_probe_L50` | `probe_reconstruction_L50.json` | `c6a481efee62e9ad` |

Baseline fit: `{'alpha': 0.45514439624515857, 'gamma': 1.3152352844089539, 'lambda': 2.25, 'tau': 0.3509908305345551, 'action': 0.0, 'position': 0.0, 'label': 0.0, 'kappa': 1.0}`. Trials: 2032. Generated 2026-09-23T00:12:51+00:00.
