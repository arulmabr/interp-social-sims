# Open-SAE Paragraph Activations

This repo replaces the deprecated Goodfire hosted paragraph-inspection API with
an explicit Open-SAE pipeline. The SAE itself is still Goodfire's open-source
`Goodfire/Llama-3.3-70B-Instruct-SAE-l50`; Neuronpedia is used only for cached
natural-language descriptions keyed by `feature_index`.

## Response-Level Scoring

The Open-SAE runner computes response-level feature scores from token-level SAE
activations:

1. Reconstruct the chat transcript from the saved prompt and generated response.
2. Tokenize the transcript with the Llama chat template.
3. Run `meta-llama/Llama-3.3-70B-Instruct`.
4. Capture hidden states at `model.layers.50`.
5. Exclude chat-template and control tokens.
6. Select the configured content scope.
7. Encode selected token hidden states through
   `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`.
8. Aggregate token-level feature activations into one response-level score per
   feature.
9. Rank top-k response-level features and attach Neuronpedia descriptions by
   stable `feature_index`.

The released outputs use these settings:

| Output family | Content scope | Feature aggregation | Threshold |
| --- | --- | --- | ---: |
| Saved creativity responses | `assistant_response` | `frequency` | 0.1 |
| Live creativity steering outputs | `assistant_response` | `frequency` | 0.1 |
| Safe-risk, ultimatum, and trust | `all_content` | `max` | 0.1 |

`frequency` counts selected content tokens whose SAE activation for a feature is
greater than the threshold. `max` takes the maximum selected-token activation for
each feature. Condition-level plots rank features by the mean of these
response-level scores across the relevant response units.

The runner records the scoring choices in each `open_sae_metadata.json` under
`activation_scope`, `feature_aggregation`, `activation_threshold`, and
`aggregation_rule`.

## Paper Wording

Suggested concise methods text:

> To replace the deprecated Goodfire hosted inspection API, we ran the base
> Llama 3.3 70B Instruct model locally, captured layer-50 hidden states, and
> encoded the selected content-token activations with Goodfire's open-source
> layer-50 SAE. Because SAE activations are token-level, we aggregate them to a
> response-level feature score before ranking top features: creativity analyses
> count response tokens whose feature activation exceeds 0.1, while game
> analyses use the maximum selected-token activation per feature. We then attach
> cached Neuronpedia descriptions using the stable SAE `feature_index`.

## Claim Boundary

The response-level Open-SAE scores are reproducible from open weights and saved
transcripts. Historical Goodfire labels are provenance from earlier hosted API
runs. Neuronpedia descriptions are interpretability annotations for the same
stable feature indices, not a guarantee that the wording will match old Goodfire
Ember labels exactly.
