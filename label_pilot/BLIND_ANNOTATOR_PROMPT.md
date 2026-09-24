# Blind feature annotation — ready to send

Give a separate annotator only the prompt below and
the `explanation_inputs.json` exported from the **new plan-v3 harvest**. This
packet is available at `outputs/blind-interpretation-v3/explanation_inputs.json`. Do not use the superseded plan-v2 packet for the
new altruism/fairness study. Use a person or isolated
model session that has not seen the Goodfire labels or the coordinator's review.
Do not send the whole folder, this conversation, the CSV, private files, or
held-out challenges. This prompt itself contains no feature meanings.

Save the unedited returned JSON as `independent_descriptions.json`. Record the
annotator/model identity and version, date, exact prompt, and generation settings
when available. Lock the descriptions with a SHA-256 checksum before evaluation.

## Prompt

You are interpreting anonymous sparse-autoencoder features from observed token
activations. Use only the attached JSON. Each feature has an anonymous alias,
token contexts, the final token being measured, activation values, and coverage
counts. Contexts come from a narrow task corpus and can be highly repetitive.

For each alias, propose a short description of the pattern that predicts
activation on the measured token. Compare positive and zero-activation examples.
Distinguish topical content, token/phrase patterns, discourse roles, and decision
behavior when the examples support that distinction. Do not infer a personality
trait, causal role, or steering effect from activation alone. Do not search for
the feature or use an external feature dictionary.

If there are no positive examples, return `insufficient_evidence` and a null
description. For sparse or ambiguous evidence, state alternatives and low
confidence. Do not invent an interpretation to complete the list.

Return valid JSON only: one object per feature alias, with exactly these fields:

```json
[
  {
    "feature_alias": "feature_000",
    "status": "provisional",
    "description": "A short falsifiable description, or null if unsupported",
    "evidence": ["Specific observed patterns supporting the description"],
    "counterevidence": ["Observed exceptions or ambiguity"],
    "alternative_explanations": ["Plausible alternatives"],
    "confidence": "low"
  }
]
```

Allowed status values are `provisional` and `insufficient_evidence`; allowed
confidence values are `low`, `medium`, and `high`. Include every alias exactly
once. Explanations will later be tested on unseen contexts. Do not request those
contexts or modify the descriptions after seeing evaluation outcomes.

## Coordinator's next action

After saving and locking the returned descriptions, use a different evaluator
context containing only those descriptions and `heldout_challenges.json`. Ask it
to predict whether each measured final token has activation strictly above zero,
returning exactly one `{ "id": "...", "predicted_active": true }` record per
challenge. Do not provide activation values or private truth. Keep predictions
fixed before scoring with `label_pilot.interpret score`.

Repeat the same evaluation with the Goodfire descriptions, matching aliases and
challenge items. Use separate evaluator contexts for the two description sources
and anonymize source names. Keep evaluator model, settings, and decision rule
the same. Report feature-level results and no-coverage features, not just a pooled
accuracy. The sampled task contexts limit interpretation generality.
