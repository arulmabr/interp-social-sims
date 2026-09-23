# Bounded steering decision experiment

Frozen before the new GPU responses: `outputs/decision-plan-v2/manifest.json`.

The question is whether a prompt-independent layer-50 vector can express a specified CPT choice policy, and whether a ten-feature SAE subspace performs comparably to an unrestricted residual vector with the same norm and token scope. This is a stronger bounded test than reconstructing the LoRA's average activation change. A negative result applies to this recipe and optimization budget.

The pinned bf16 model, pinned SAE and saved rank-16 combined-CPT LoRA are reused. No new LoRA is trained. The LoRA is an independent positive control, never a source of per-test steering activations.

## Design

- Discovery: 216 prompts; selection: 96 prompts. All three frames, paired answer orders and multiple probabilities, stakes and reward ratios.
- Frozen: 108 new economic scenarios, each rendered with two answer orders and two wording templates: 432 prompts. Economics and wording are separated from prior responses.
- Targets: combined CPT `(curvature .8, weighting .72, loss aversion 2, temperature 3)` and neutral CPT `(1,1,1,3)`. The two targets help distinguish a targeted policy from generic task/format improvement, but do not replace a matched neutral LoRA.
- Causal screen: 37 fixed candidates, each at positive and negative norm 16, at the last token and at all nonpadding tokens. Rank by discovery expected answer cross entropy over the complete economic grid. Feature/readout cosine is recorded separately.
- Fit ten-feature SAE and unrestricted residual directions for each target and scope, with two seeds. Frozen model weights, 160 Adam updates, batch 8, norm-16 sphere. Adam step size `.2/sqrt(dimension)`; initial direction is the saved mean LoRA footprint or its projection, plus a small seeded perturbation. Selection checkpoints every 40 updates.
- Select one **shared** scope and norm from `{1,4,16}` per target, minimizing selection error averaged over both methods and seeds. Both methods therefore face the same scope and dose in the primary comparison. We retain all selection results to expose tradeoffs.
- Controls: base, saved LoRA, raw mean readout gradient, its sparse SAE approximation, negative gradient and three random directions. Forty-eight separate arithmetic, probability-comparison and certain-outcome questions assess elementary instruction/comprehension retention.

## Operational rule

For each selected method/seed/target and each held-out template: teacher-probability RMSE ≤ .06; held-out prediction from selection-fitted CPT RMSE ≤ .06; CPT advantage over a selection-fitted action-shortcut model ≥ .01; preference-parameter errors ≤ (.12, .12, .25); answer mass ≥ .99; mean answer-order gap ≤ .05; dominance violations ≤ .05; control-accuracy drop from base ≤ .05; mean realized norm error ≤ .05. Both seeds, both targets and both templates must pass for a robust method-level positive.

The shortcut model includes separate frame intercepts and positive temperatures, plus answer-A bias. Before GPU execution, synthetic calibration rejected 20/20 known action shortcuts and detected 7/7 planted preference changes. This finite deterministic check is not a general false-positive-rate guarantee.

Teacher-RMSE uncertainty uses paired-economic-scenario bootstrap intervals, preserving both orders and templates. A negative with the lower bound above .06 rules out the declared accuracy target on this scenario distribution; it does not show that every optimization, layer or SAE fails.

## Stop interpretation

- Valid anchors/rule and robust SAE success: proceed to a larger confirmatory study within the demonstrated scope.
- Dense success, SAE failure: pivot the tested sparse recipe.
- LoRA success, both constrained methods fail: pivot constant-vector steering, while retaining optimization/candidate limitations.
- LoRA transfer failure, uninformative action control or failed calibration: evaluation/generalization remains inconclusive; repair that prerequisite before any larger sweep.

These thresholds are an explicitly provisional operational rule. The collaborator's full scientific go/pivot rule has not been supplied. There is no universal SAE impossibility claim.

## Resource control

At most two H200 GPUs, $20 and two hours. Independent provider shutdown is armed before uploading the adapter. Outputs are continuously copied to the local workspace with SHA-256 verification; successful completion triggers a final backup and immediate GPU stop. Existing retained storage is preserved.

## Pre-frozen refinement amendment

At 23:30 UTC on September 18, while initial fits were still running and before frozen responses were inspected, `outputs/decision-refinement-plan-v1.json` declared a second optimization stage. Initial dense selection error was still improving at 160 updates. Both methods and both seeds in each target's jointly selected scope receive 480 additional updates with the same optimizer scale. The original checkpoint remains eligible, and checkpoint/dose selection uses selection data only. Initial-stage frozen score files are sealed and never read by refinement. Final discovery scores are saved as an optimization/generalization diagnostic. The final rule and all numeric thresholds remain unchanged.

Positive and negative readout controls at norms 1 and 4 in both scopes are added as fixed action-calibration conditions. The complete two-stage run uses the original spending cap and shutdown deadline.
