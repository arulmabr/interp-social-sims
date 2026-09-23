# Clarifications to the September 18 explainer

Prepared by Codex from the saved records and the collaborator clarification
provided in this task. The PDFs are preserved as the versions originally
shared; read them together with this note and [the concrete prompt and feature
provenance](COAUTHOR_CLARIFICATIONS.md).

- **Actual probe layer:** the earlier description used the repository's
  layer-48 default. Shreyas subsequently reported that the experiment under
  discussion used layer-50 last-token activations. His experiment-specific
  account supersedes that description. This pilot did not run a matched
  evaluation of his probe. The pilot's separately named layer-48 reward-probe
  conditions remain correctly identified in their historical reports.
- **Prompt origin:** 216 discovery prompts means 108 generated economic
  scenarios in two answer orders, not 216 people or prompts sampled from the
  original paper. The 432 frozen prompts are 108 new scenarios in two orders
  and two wording templates. The alternative is one modest wording-and-format
  variant, not a broad paraphrase evaluation.
- **Feature selection:** the final ten IDs were selected by intervention loss
  from a fixed 37-feature pool, not by searching Neuronpedia descriptions.
  Neither original risk feature 184 nor 4237 was in the selected ten.
- **Interpretation:** neither the historical Goodfire labels nor the cached
  Neuronpedia labels were independently validated here. Feature identity,
  activation-based explanations and causal preference control are separate
  claims. A high cosine with the readout gradient is a diagnostic rather than
  proof of a pure answer-bias mechanism.
- **Conclusion:** the results concern the tested constant-vector recipe.
  Dense-control failure and LoRA wording sensitivity prevent isolating a
  dictionary-wide SAE limit. Retain the completed dense result as diagnostic
  evidence even if further dense optimization is deprioritized.

No new probe comparison, automated feature-interpretation run or model training
was performed while preparing these publication clarifications.
