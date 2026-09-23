# SAE steering decision experiment

**Do not launch the full SAE feature sweep yet.** The current steering recipe failed, and the LoRA anchor did not generalize reliably to new wording. The broader verdict about SAE preference capacity remains inconclusive.

**Operational verdict:** `INCONCLUSIVE_EVALUATION_OR_ANCHOR_TRANSFER`. This applies to the fixed candidate set, layer, doses, token scopes and optimization budget below. It is not a universal result about SAEs.

LoRA anchor across both wordings: **Fail**. Raw readout action control: **Pass**. The question was whether a small fixed residual edit changes risk preferences consistently, rather than merely changing answer bias.

## What was tested

A pinned bf16 Llama-3.3-70B and its released layer-50 SAE; the saved combined-CPT LoRA; 37 candidate features at both signs and two token scopes; 16 initial fits covering two targets, two methods, two scopes and two seeds. Each initial fit used 160 updates. The eight fits in the jointly selected scopes then received 480 additional updates. No LoRA was retrained.

The ten SAE features were chosen by intervention performance across the discovery reward grid. Coefficients were then trained on discovery prompts. Both dense and sparse methods shared the selected norm and scope for each target. None used adapted activations from frozen prompts. Extra optimization was declared during stage-one training, before frozen outputs were inspected; stage-one frozen scores were sealed and excluded from refinement and selection.

Discovery had 216 prompts and selection 96. The frozen set had 108 new economic scenarios, each tested with both answer orders and two wording templates (432 prompts per condition). Forty-eight separate elementary comprehension questions were also evaluated.

## Held-out target error

RMSE of risky-choice probabilities against the planted target; lower is better. The declared limit was 0.060. Ranges show the two independently fitted vectors, not uncertainty intervals.

| Target | Intervention | Original wording | New wording |
|---|---|---:|---:|
| combined | baseline | 0.364 | 0.380 |
| combined | lora | 0.042 | 0.115 |
| combined | dense | 0.129–0.151 | 0.224–0.225 |
| combined | sae10 | 0.202–0.208 | 0.220–0.224 |
| neutral | baseline | 0.386 | 0.462 |
| neutral | dense | 0.1319–0.1323 | 0.241–0.248 |
| neutral | sae10 | 0.2035–0.2043 | 0.2532–0.2533 |

## Decision checks

- **dense:** 0/8 target × seed × template cells passed all criteria. In 8/8 cells, the scenario-bootstrap lower bound on teacher RMSE exceeded 0.060.
  Preference-like behavior without requiring the exact planted parameters: 0/8 cells; replicated across both seeds and wordings for a target: False.
- **sae10:** 0/8 target × seed × template cells passed all criteria. In 8/8 cells, the scenario-bootstrap lower bound on teacher RMSE exceeded 0.060.
  Preference-like behavior without requiring the exact planted parameters: 0/8 cells; replicated across both seeds and wordings for a target: False.
- **combined matched comparison:** scope `all`, per-position norm 16.
- **neutral matched comparison:** scope `all`, per-position norm 16.

The complete checks include held-out CPT prediction, comparison with frame-specific answer-bias/temperature models, parameter recovery, answer-order sensitivity, dominance, answer mass, elementary comprehension and realized bf16 displacement norms. See the numerical table for every condition; failed checks are retained.

## Anchor recovery and generalization

| Wording | α curvature | γ weighting | λ loss aversion | β temperature | Earlier strict repair rule |
|---|---:|---:|---:|---:|---|
| original | 0.762 | 0.755 | 2.100 | 2.819 | Fail |
| transfer | 0.643 | 0.698 | 2.447 | 2.497 | Fail |

Planted combined values: α=0.8, γ=0.72, λ=2, β=3, A-label bias=0. The earlier strict repair rule used teacher RMSE ≤0.04 and tighter parameter tolerances. It is reported separately from this predeclared operational comparison; the two rules must not be conflated.

## What the result means

The LoRA passed all of the latest provisional criteria on the original wording. On the new wording it failed teacher accuracy (RMSE 0.1147), held-out CPT prediction (0.1149), parameter recovery, and answer-order sensitivity (mean gap 0.0532 versus the 0.050 limit). Its recovered curvature was 0.643 instead of 0.8, and loss aversion was 2.447 instead of 2.0. The earlier reported LoRA pass concerned a different, original-wording test grid; this finding narrows that generalization claim.

Both steering methods improved over the base model, but all eight cells for each method missed exact target recovery and the separate preference-like criterion. Every teacher-error bootstrap lower bound exceeded 0.060. This is evidence against the tested recipe across both optimization seeds, not proof that no suitable vector exists. Because the dense control also failed, the result cannot isolate a limitation of the SAE dictionary.

The SAE interventions were better predicted by the specified frame/label/temperature shortcut model (held-out RMSE 0.038–0.056) than by the CPT model (0.111–0.164). This supports a shortcut-like interpretation within those competing models. Both combined-target SAE seeds also scored 43/48 on elementary controls, versus 46/48 for the base model; the loss came from arithmetic items. All trained steering vectors exceeded the mean answer-order gap limit.

The ten-feature SAE reconstruction of the raw readout direction had relative residual norm **0.961**. That is a poor sparse approximation under this budget, not evidence that the full dictionary cannot span the direction. The combined-target SAE steering vectors had readout cosines only 0.068–0.073, yet failed the behavioral checks. Low cosine alone is therefore insufficient as a preference test here.

## Recommended next decision

First validate a LoRA trained across several phrasings and answer orders on entirely new wording families and economic scenarios. If that bounded repair fails, pause the preference claim. If it passes, repeat the small matched dense-versus-SAE comparison before expanding the sweep. A passing dense vector with a failing sparse vector would isolate the sparse recipe more convincingly; failure of both would motivate changing the intervention format.

[Detailed staged follow-up and stop conditions](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/DECISION_NEXT_STEPS.md). No further GPU session was started.

## Qualifications

- This tests one constant signed decoder combination per target. It does not test prompt-conditioned SAE controllers, larger feature sets, other layers or all dictionaries.
- Failure to recover the particular planted agent is not itself proof of absent preference-like behavior. The separate preference-like check omits teacher accuracy and planted-parameter tolerances; a replicated passing pattern blocks a strong negative capacity interpretation.
- A failed optimizer/candidate budget is not a proof that no vector exists. Checkpoint histories and both seeds are included so optimization limits remain visible.
- The single saved LoRA training seed remains a limitation; no matched neutral LoRA was trained. Two planted steering targets help test specificity but do not establish a preference-only mechanism.
- The action model covers the declared frame, label and temperature shortcuts. It does not cover every possible shortcut. Synthetic calibration detected 7/7 preference alternatives and rejected 20/20 specified action nulls; this is not a population error-rate guarantee.
- Bootstrap intervals resample the designed economic scenarios while keeping answer orders and templates together. They do not establish generalization to every possible wording, task or model.
- The 37-feature screen used full-grid teacher-probability loss, rather than direct switching-point or curvature selection. It can favor confidence/bias changes and miss joint feature effects. This round did not validate the layer-48 reward probe, persona direction or all component-specific LoRAs from the broader proposal.
- The collaborator’s full scientific go/pivot rule was unavailable. These are explicitly declared operational thresholds.

## Execution and evidence

The run completed all 28 frozen conditions. 396 remote files were verified locally by SHA-256. Provider shutdown was confirmed; the pod has been stopped.
Estimated new session cost: **$14.55**, within the $20/two-hour ceiling. The stopped session pod shows $0.00/hour. Previously retained smoke-pod storage remains approximately $0.083/hour, separately.

Software checks: 33 local tests passed with three GPU-only skips; all 36 passed on the GPU stack. These checks establish execution correctness, not the scientific claim.

[Complete comparison table](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/decision_comparison.csv) · [Machine-readable decisions and failed gates](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/decision_analysis.json) · [Delivery audit](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/delivery_audit.json)

[Feature screening and readout cosines](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/feature_screen.csv) · [Fitted SAE coefficients](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/selected_feature_coefficients.csv) · [Direction alignment](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/direction_alignment.csv) · [Locked analysis source manifest](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/analysis_manifest.json)

![Fresh original wording](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/decision_curves_original.png)

![Fresh alternative wording](/Users/arul/Desktop/my_repos/social-sim-open-sae/anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z/decision_curves_transfer.png)
