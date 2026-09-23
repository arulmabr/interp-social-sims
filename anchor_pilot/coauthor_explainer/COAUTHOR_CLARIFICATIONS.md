# Prompt and feature provenance: response to coauthor questions

This note was checked against the saved decision run and its archived execution code. It clarifies the existing pilot; no new model inference, feature interpretation, training, or collaborator contact was performed.

Later clarification: Shreyas reported that his actual probe experiment used
layer 50. The layer-48 default discussed below is a code-default observation,
not the configuration of his reported run. See [ERRATA.md](ERRATA.md).

## 1. Where the 216 prompts came from

They were generated programmatically for this new pilot by `anchor_pilot/decision_plan.py::build_decision_rows`, using the original wording function in `anchor_pilot/design.py::render`. They are not 216 observations drawn from the original paper or 216 independent people.

The discovery grid is:

| Component | Values | Count |
|---|---|---:|
| Frame | gain, loss, mixed | 3 |
| Probability | 0.15, 0.50, 0.85 | 3 |
| Stake scale | 30, 70 tokens | 2 |
| Reward/stake ratio | 0.3, 0.7, 1.3, 2.3, 4.3, 7.3 | 6 |
| Answer order | risky option A or risky option B | 2 |

Thus 3 × 3 × 2 × 6 = 108 economic scenarios, rendered in two answer orders = **216 prompts**. Reward = stake × ratio.

- Gain: certain gain of the stake versus a probability of gaining the reward, otherwise zero.
- Loss: certain loss of the stake versus a probability of losing the reward, otherwise zero.
- Mixed: zero for sure versus a probability of gaining the reward, otherwise losing the stake.

These rows screened features and fitted dense/SAE directions against artificial Cumulative Prospect Theory (CPT) choice probabilities. The saved LoRA adapter was trained in an earlier run; 216 is not its training-set size.

The separate selection grid has 48 economic scenarios × 2 orders = 96 prompts. The frozen evaluation has 108 new economic scenarios × 2 orders × 2 wording templates = 432 prompts. Selection probabilities are 0.20/0.65, stakes 40/60, ratios 0.5/1.5/3.5/6.5. Frozen probabilities are 0.18/0.42/0.78, stakes 35/65, ratios 0.38/0.88/1.68/2.88/4.88/7.88.

This was a bounded synthetic pilot, not a direct reproduction of the original paper's task distribution or the full proposed experiment.

## 2. Exact wording comparison

The following is one actual frozen economic scenario. Both templates retain identical option outcomes and probabilities, and both are also evaluated with A/B swapped.

Original user message:

> All outcomes are changes from your current token balance, which is the reference point. You have enough tokens to cover any losses. Choose the option you prefer.  
> Option A: 100% chance to gain 35 tokens.  
> Option B: 42% chance to gain 100.8 tokens; 58% chance to gain or lose 0 tokens.  
> Answer with exactly one letter: A or B.

Alternative user message:

> Consider changes in a token account. The current balance is the zero reference; the account can cover every possible loss. Select your preferred offer.  
> A) 100% chance to gain 35 tokens.  
> B) 42% chance to gain 100.8 tokens; 58% chance to gain or lose 0 tokens.  
> Which offer do you take? Reply A or B only.

Both use the same system message:

> Choose between the two options. Your answer must contain only the option letter A or B. Do not explain.

This is **one mild wording-and-format variant**. It changes the introduction, option prefix and response instruction together. It does not establish robustness across many paraphrases, nor isolate which textual change caused the observed difference. “Zero reference” could also change how a language model interprets the framing even though the intended economic reference is identical. Both wording sets use the same frozen numeric scenarios, so their paired difference is not a change in payoffs.

The frozen results show LoRA sensitivity to this particular variant, not a universal inability to generalize.

## 3. How features were actually chosen

The candidate pool contained 37 feature IDs:

1. Thirty decoder directions previously selected to approximate the discovery mean hidden-state difference between the base and adapted model.
2. Seven additional prespecified IDs: 184, 4237, 31935, 13142, 20117, 4992 and 47380.

For every candidate, the code tested positive and negative additions at norm 16, at final-token and all-prompt positions. For each target and scope it ranked candidates by discovery expected answer cross-entropy against CPT probabilities, then selected ten. It fitted a signed linear combination of their decoder directions. Neuronpedia label text was not an input to this ranking or fitting.

For the final all-position settings, both targets selected the same ten IDs (in different rank orders):

30498, 60415, 17838, 62440, 23671, 33404, 15307, 38516, 55751, 47503.

None is one of the six original named risk/altruism/creativity steering features. The two optimization seeds change fitted coefficients, not the ten selected IDs.

This does not establish that these ten features encode risk preferences. The candidate pool is narrow and partly dependent on the imperfect LoRA anchor. Ranking by target answer loss can reward confidence/answer-bias changes and miss useful combinations of individually weak features. It is also different from selecting features directly by changes to fitted curvature or switching points, as originally proposed.

## 4. Historical Goodfire labels: what is recoverable

A partial provenance mapping already exists in:

- `SAE/data/processed/steering_feature_label_crosswalk.csv`
- `SAE/data/processed/paper_activation_label_crosswalk.csv`
- `SAE/reports/PAPER_ACTIVATION_LABEL_CROSSWALK.md`

Two directly rechecked examples from saved controller metadata are:

| Recorded feature ID | Historical Goodfire description | Cached Neuronpedia description |
|---:|---|---|
| 184 | Willing to take risks or make sacrifices for a goal | sacrifice for or at |
| 4237 | Executing potentially risky operations that require caution | before activities or anything |

The old descriptions and `index_in_sae` fields occur together in `model.controller` in `SAE/data/raw/games/safe_risky/results_20251008_225522/safe_risky_lite_steering_10.csv`. Thus these associations are recorded IDs, not inferred from similar wording.

The paper activation crosswalk contains 62,340 rows: 3,478 have recovered index mappings and 58,862 retain only old labels. Those counts include repeated activation observations. Exact mappings cover five unique historical labels in that table; the broader steering provenance also includes creativity feature 13142.

Identifier provenance and semantic validation are distinct. A matching index must be tied to the correct model/layer/SAE revision, and neither company's description establishes what steering that feature causally controls. Approximate label-search matches in the repository are explicitly not identity matches. A complete mapping for labels whose original IDs were not retained remains unresolved.

## 5. Reinterpreting an existing SAE

Yes: keeping Goodfire's trained SAE fixed while collecting activation examples and generating new explanations is different from training a new SAE.

Goodfire's published pipeline collects token contexts across activation strengths, asks Claude to explain their common pattern, and tests whether the explanation distinguishes activating examples from nonactivating distractors. This supports replicating the *interpretation procedure*; it does not mean rephrasing existing labels or asking Claude what an unexplained feature number means.

Source: https://www.goodfire.com/research/understanding-and-steering-llama-3

A suitable next pass would:

- Start with the original named features and the ten actually tested features.
- Collect strong, moderate and inactive examples from a separate interpretation corpus, including lottery and non-lottery contexts.
- Hide the old descriptions while generating candidate explanations.
- Score those explanations on unseen activation examples and challenging distractors.
- Separately test whether interventions produce predicted economic changes, with wording/order controls.

These steps are proposed, not completed. A successful activation explanation still does not by itself demonstrate stable causal control of risk preferences.

## 6. Dense direction versus existing probes

Both operate by adding a dense direction to a hidden-state vector. “Dense” therefore does not mean fundamentally different from probe steering.

| Aspect | Current pilot | Repository probe implementation |
|---|---|---|
| Direction learned from | Direct optimization of CPT answer loss | Standardized logistic classifier on labeled activations |
| Llama layer | 50 | 48 by default; code also permits a layer search |
| Position scope | All nonpadding prompt positions in the selected setting | Last 20% of positions with a 0.5-to-1 ramp |
| Response measurement | Next-token A/B probabilities | Generated-response pipeline |

These are code-level differences, not a measured comparison of their behavior. Shreyas's latest experiments may differ from the checked repository code. No matched head-to-head was run here and no contact with Shreyas was made during this audit.

## 7. Corrected claim

The supported statement is: **this specific constant-vector, ten-feature setup did not demonstrate stable CPT-like preference control.** The fitted bias/confidence model predicted its outputs better than the restricted CPT model, but the former has more parameters and uses base-model outputs. That comparison is descriptive evidence, not proof of an internal answer-bias mechanism.

Feature semantics remain unvalidated; the candidate set and optimization are limited; the dense control also failed; and the intended LoRA reference was sensitive to the wording variant. None supports a general conclusion that SAE steering is “just bias.”

## Evidence and exports

- Saved run: `anchor_pilot/outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z`
- `discovery_prompts_exact.csv`: all 216 saved discovery prompts.
- `frozen_wording_pairs_exact.csv`: 216 matched pairs, one per economic scenario and A/B order.
- `selected_features_exact.csv`: saved final feature IDs and coefficients.
- Archived `decision_plan.py`, `decision.py`, `design.py` and `repair_design.py` were checked against the local code and matched.
