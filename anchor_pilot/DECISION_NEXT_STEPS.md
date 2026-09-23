# Next experiment after the matched steering test

This is a proposal, not an additional completed run. Read `DECISION_RESULTS.md`
for the measured results. The current frozen prompts have now been inspected;
they are development evidence for any future experiment, never a fresh test set.

The immediate decision is to defer a full SAE feature sweep. The saved LoRA's
teacher-probability RMSE rose from 0.0416 on fresh economic scenarios with the
original wording to 0.1147 on the alternative wording. Both the matched dense
vectors and ten-feature SAE vectors also missed the two planted targets. This
does not isolate a limitation of the SAE dictionary.

## 1. Repair and validate the positive anchor first

Train the combined-CPT LoRA on several economically equivalent phrasings, both
answer orders, and gain/loss/mixed choices. Keep the current model revision,
reference point, outcome normalization, answer-token convention and teacher
parameters explicit. If recovering stochastic choice probabilities is the
objective, train against those probabilities or enough sampled choices to
estimate them; one deterministic label per unique gamble does not fully specify
that probability target.

Use a selection set that varies wording as well as economic parameters. Reserve
new wording families and new probability/stake/reward combinations for a single
fresh final test. Audit semantic equivalence, including reference points and
whether outcomes are gains, losses, or total wealth. Recover the teacher's
parameters from synthetic responses on that exact design before GPU work.

Freeze the acceptance rule before opening final responses. Report per-wording
teacher error, parameter uncertainty, predictive CPT fit, label-order sensitivity,
dominance, answer validity and elementary comprehension separately. Keep the
earlier strict recovery rule distinct from the latest provisional comparison
rule. Include an independent LoRA training seed if making a replicated claim.

**Stop condition:** if this bounded anchor repair still fails held-out wording
transfer, pause the SAE preference claim and investigate the anchor, task wording
and estimator. Do not compensate with a larger feature sweep.

## 2. Validate the intervention format before judging the dictionary

Only after the anchor passes, repeat a small, norm- and position-matched dense
versus sparse comparison with features and coefficients chosen on development
data. Choose doses that preserve comprehension and answer validity. Preserve
selection curves and multiple optimization seeds; finite training failure is
not an existence proof.

Full prompt-specific LoRA state replay remains an oracle fidelity diagnostic.
It must not be counted as an independently usable preference intervention,
because it requires the adapted model's state for each test prompt. If constant
dense vectors again fail while LoRA passes, investigate a prompt-conditioned
controller or another intervention location before attributing failure to the
SAE dictionary. Such a controller must itself be fitted on development data
and evaluated without test-time LoRA states.

## 3. Use the outcomes to make a bounded decision

| Fresh result | Defensible next decision |
|---|---|
| Positive anchor fails | Repair or pause the measurement/anchor setup; no dictionary verdict. |
| Anchor passes; dense and SAE methods fail | Pivot the tested intervention format; no isolated dictionary verdict. |
| Anchor and dense pass; sparse SAE fails | Evidence against this feature set, sparsity and fitting recipe; test one targeted alternative before a broad sweep. |
| Anchor and sparse SAE pass across seeds and wording | Proceed to a bounded independent confirmation and component-specific tests. |

Exact planted-parameter recovery and any preference-like pattern are separate
outcomes. A method can miss the planted policy without being purely an action
shortcut. Conversely, a low cosine to the logit gradient alone does not establish
preference steering. Use both behavioral comparisons and geometry. The latest
screen ranked 37 candidates by full-grid teacher-probability loss, not directly
by recovered curvature or switching-point change. That is a causal intervention
screen, but it can still favor confidence/answer-bias changes and miss feature
interactions. A later targeted selection test should explicitly separate those
effects, with the gradient cosine retained as a covariate.

Curvature-only, weighting-only and loss-aversion-only adapters, the layer-48
reward probe, persona comparison, and a full feature sweep belong after these
gates. The latest run did not validate all of those parts of the collaborator's
full proposal. The current test gives a concrete reason to stop scaling this
recipe, while leaving the broader scientific claim open.
