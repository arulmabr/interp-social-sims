# B8 — Track B's anchors applied to the SAE steering pilot

The pilot in `anchor_pilot/` asks whether a small fixed residual edit changes risk
preferences or merely answer bias, and answers it by the RMSE of each condition's
risky-choice probabilities against a planted target. It concludes that dense and ten-feature
SAE steering each passed 0 of 8 cells.

This report re-reads the pilot's own saved evidence with Track B's instrument. No model was
re-run for Section 1, no pilot file was modified, and every number comes from
`anchor_pilot/evidence/decision/frozen_scores_*.json` and `frozen_rows.json`. Code is
`cv_bench/anchors/pilot_bridge.py` with tests in `cv_bench/tests/test_pilot_bridge.py`.
Values are registered as `MANIFEST_B.csv:B8.*`.

---

## 1. The finding that changes how the pilot's null should be read

**Every condition in the decision experiment removes most of the model's response to the
payoff, and the ones under test remove more of it than random directions do.**

Regressing each condition's change in logit on the baseline logit gives a slope. A slope of
zero means the intervention added something without touching how the model responds to the
payoff. A slope of minus one means it removed that response entirely. What survives, one
plus the slope, is the share of the payoff signal the measurement still has to work with.

| condition | slope | signal retained | correlation | sd after |
|---|---:|---:|---:|---:|
| readout gradient, norm 16 | -0.938 | **0.062** | -0.999 | 0.69 |
| SAE ten-feature, seed 31 | -0.904 | **0.096** | -1.000 | 0.92 |
| SAE ten-feature, seed 73 | -0.908 | **0.092** | -1.000 | 0.88 |
| dense, seed 31 | -0.857 | **0.143** | -0.992 | 1.65 |
| dense, seed 73 | -0.871 | **0.129** | -0.994 | 1.50 |
| LoRA anchor | -0.844 | **0.156** | -0.987 | 1.91 |
| random 19, norm 16 | -0.495 | **0.505** | -0.973 | 4.79 |
| random 41, norm 16 | -0.428 | **0.572** | -0.965 | 5.39 |
| random 89, norm 16 | -0.395 | **0.605** | -0.952 | 5.70 |

The baseline logit has a standard deviation of 9.23. After ten-feature SAE steering at norm
16 it is 0.92. The model has stopped distinguishing between the gambles almost entirely.

**Three things follow.**

**The correlations are near perfect, between -0.95 and -1.000.** This is not a noisy tendency.
Each intervention is, to an extremely good approximation, a linear compression of the
baseline signal toward a constant, plus an offset.

**The directions under test destroy three to six times more signal than random directions of
the same norm.** Random directions at norm 16 retain 0.505 to 0.605. The SAE vectors retain
0.081 to 0.096. A comparison in which the null control preserves the measured quantity better
than the treatment does is not measuring what it was built to measure.

**It is the dose, and the dose ladder shows it.** The same gradient direction at three
strengths:

| dose | signal retained |
|---|---:|
| norm 1 | 0.611 |
| norm 4 | 0.215 |
| norm 16 | 0.062 |

Retention falls monotonically with strength. Norm 16 is the dose at which every dense and
SAE comparison in the decision experiment was made.

**What this means for the pilot's conclusion.** "0 of 8 cells passed" is consistent with the
SAE dictionary lacking preference capacity, and it is equally consistent with the dose having
flattened the payoff response before any preference could be expressed. The evidence cannot
separate those, because the quantity the criterion is computed on has largely been destroyed
in every cell. The pilot's own qualification, that a failed optimizer and candidate budget is
not proof that no vector exists, understates this: the measurement regime itself is the
problem.

**The remedy is already specified.** Plan item A9 asks for an iso-behavioural dose, scaling
each direction so that it produces the same shift of the behavioural measure, and then asking
what moved underneath. Track B's lottery anchors are dosed that way, and the doses that
achieve a matched shift differ across directions by about 150 times. Matching on norm, as
here, compares very different amounts of intervention.

---

## 2. The attribution, and why the anchor itself reads as a sharpness change

Running Track B's five-family attribution over the pilot's frozen conditions puts **noise**,
a change in how sharply the agent acts on differences, top for almost every condition
including the LoRA anchor. That is the correct answer and it is diagnostic rather than
surprising.

The pilot's combined target plants four parameters at once: alpha 0.8, gamma 0.72, lambda 2
and **beta 3**. Beta is the temperature. Planting it at 3 is planting a sharpness change
directly, so the anchor is a preference change and a noise change combined, and on this grid
the noise part dominates. The estimator reports the dominant mechanism, and here the dominant
mechanism is the one that was planted alongside the preference.

**This is the second structural point.** Track B plants **one** parameter at a time, at a
declared minimum detectable change, with a separate bias adapter as the negative control,
because an anchor that moves four parameters has no single known true value to recover. The
pilot's own result reflects this: its recovered curvature was 0.643 against a planted 0.8,
and its teacher RMSE rose from 0.042 to 0.115 across wording. An anchor measured against the
base model, with four parameters moved together, cannot separate "became a prospect-theory
agent at all" from "has the planted parameters".

Attribution numbers at these doses are reported in `reports/b8_pilot_attribution.json` for
completeness, and they should not be quoted as evidence about the SAE dictionary until the
dose question in Section 1 is settled.

---

## 3. Where the two frameworks already agree, which is worth saying out loud

**On the control.** The pilot classifies the raw readout gradient as action-like and passes
it as its action control. Track B builds the readout gradient anchor to be action-like by
construction and uses it as one of its two poles. Two instruments built independently, with
different statistics and different decision rules, place the same direction in the same
category. That is real calibration evidence for both.

**On geometry not being the test.** The pilot found SAE steering vectors with readout cosines
of only 0.068 to 0.073 that still failed its behavioural checks, and concluded that low
cosine alone is insufficient as a preference test. Track B reaches the same conclusion from
the other side in `B_ANCHORS_README.md` section 5.3: the distance that matters is not
geometric but the distance between what two directions **do** to the choice, measured in the
space of the model-free variance decomposition. Both say that how a direction points does not
settle what it does.

---

## 4. What Track B adds that the pilot does not have

**A planted bias.** The pilot's only negative control is the readout gradient, a direction.
Track B also trains a **bias adapter**, a weight-space change that is a constant push and
nothing else, matched to the gradient anchor in activation space. Without one, a finding that
SAE steering looks shortcut-like can only be stated as a failure to be preference-like. With
one it can be stated as a positive attribution against a calibrated example. This is being
measured on the pilot's own prompts; see Section 5.

**An order-decomposed gradient.** The pilot uses one raw readout direction. Track B computes
it separately for each option order and keeps the sum as the anchor and the difference as a
position control. On the lottery the two orders agree at only +0.727, so the position
component is real and the order-invariant part is 2.4 times it. An undecomposed gradient
therefore mixes an answer effect with a position effect, and the decomposition supplies a
third pole that is pure format, which is the category the pilot's own shortcut finding points
at and which it currently has no example of.

**A second task.** The pilot is lottery only. Track B now has the ultimatum responder as
well, in `B7_ULTIMATUM_ANCHORS_README.md`, and the two tasks fail in opposite places. On the
lottery a planted bias is attributed to preference at 0.000 and the gate fails at one
detectable change, passing only at three. On the ultimatum a planted bias reaches 0.581 and
the gate passes at one. A benchmark that reports its own blind spots differing by task is a
stronger claim than either task alone.

---

## 5. Both anchors run against the pilot, and both say something

### 5.1 The readout gradient on an A/B answer format is mostly a letter direction

Computing the gradient separately for each option order on the pilot's own prompt text,
with `cv_bench/anchors/pilot_gradient.py`, 168 prompts per order:

| prompt format | answer tokens | cos between the two orders | order-invariant part | label part | ratio |
|---|---|---:|---:|---:|---:|
| pilot, layer 48 | **A / B** | **-0.889** | 9.128 | 37.682 | **0.24** |
| pilot, layer 50 | A / B | -0.893 | 8.416 | 35.383 | 0.24 |
| Track B lottery, layer 48 | safe / risky | +0.727 | 22.678 | 9.191 | 2.47 |
| Track B ultimatum, layer 48 | Accept / Reject | +0.953 | 18.421 | 2.869 | 6.42 |

**The sign is the whole story.** On the pilot's prompts the two option orders give gradients
that are 89 percent antisymmetric, so they very nearly cancel. On Track B's prompts they
agree. The cause is mechanical rather than a defect: the pilot's answer is a **letter**, and
which letter means "take the gamble" swaps with the order. The quantity being differentiated
is therefore `log P(A) - log P(B)` in one half of the grid and its negation in the other, so
the gradient flips with it. Track B's answers are the words naming the options, which do not
swap when the print order does, so only the position changes and the content direction
survives.

**What survives is small.** The part that does not flip has length 9.128 against 37.682 for
the part that does. A readout gradient computed on a letter-answer format is, to about four
parts in five, a direction that pushes the model toward emitting one letter rather than the
other, independently of what that letter stands for.

**Why this matters for the pilot's conclusions.** Its raw readout gradient is its action
control, and it classified that gradient as action-like. On this evidence the direction is
not merely action-like but largely **label-identity-like**, which is a narrower and stronger
statement. Its 37 candidate features were also screened partly by readout cosine against that
direction, and a cosine taken against a vector that is four fifths letter identity is mostly
measuring alignment with letter identity.

**The three formats give a clean ordering** that is a methodological result in its own right:
word labels tied to the content give an order-invariant gradient, Accept and Reject give the
cleanest of all at 6.4 times, and bare letters invert it to 0.24. Anyone computing a readout
direction on a multiple-choice letter format is mostly computing a letter direction.

One caveat on comparability: this gradient is computed on the pilot's prompt text with Track
B's chat-template rendering and an empty answer stem, which need not match how the pilot
built its own vector. The valid comparison is of the same quantity computed the same way
across three prompt formats, not a claim about the pilot's exact vector.

### 5.2 The SAE directions placed against the decomposed anchor

The gradient anchor from 5.1 splits into a part about the answer and a part about which
letter is emitted. Asking which of the two each SAE direction aligns with is a sharper
question than the pilot's single cosine against their sum. Pure geometry, on the pinned
public checkpoint `Goodfire/Llama-3.3-70B-Instruct-SAE-l50` at revision `128ee921`, with no
service contacted and no model run.

The null is 2,000 randomly drawn live dictionary features put through the identical
construction. 3,632 of the 65,536 features are dead and were excluded.

The bias anchor carries no direction in its file, so its pole is its **activation-space
displacement**: the mean change in the residual stream between the reference adapter and the
bias adapter, measured on the same prompts by `cv_bench/anchors/bias_direction.py`. That is
what plan item A5 means by a weight-space control matched to the gradient anchor in
activation space.

| direction | cos, gradient answer part | cos, gradient letter part | cos, bias anchor |
|---|---:|---:|---:|
| **random feature, 95th percentile** | 0.033 | 0.027 | 0.049 |
| **random feature, 99th percentile** | 0.056 | 0.048 | 0.078 |
| feature 184, the paper's lottery feature | **-0.001** | **+0.016** | **-0.005** |
| feature 4237, the paper's second lottery feature | **+0.004** | **+0.000** | **+0.004** |
| feature 31935, the paper's ultimatum feature | **+0.004** | **+0.004** | **+0.017** |
| the pilot's fitted ten-feature vector, combined target, seed 31 | **+0.067** | -0.006 | +0.031 |
| the same, seed 73 | **+0.075** | -0.003 | -0.013 |
| the pilot's fitted vector, neutral target, seed 31 | **+0.091** | +0.002 | -0.013 |
| the same, seed 73 | **+0.096** | +0.004 | -0.004 |
| the pilot's sparse fit of the raw readout direction | **+0.269** | +0.037 | -0.008 |

**Nothing aligns with the bias pole.** Every direction, including the pilot's fitted vectors,
sits inside the 95th percentile of the null against it. So on this measurement the SAE
directions are not bias-like either; the only structure any of them shows is alignment with
the answer component of the readout.

**How much that last point is worth is limited, and the limit is measurable.** The bias
displacement was captured on the pilot's wording, where Section 5.3 shows the adapter's
behavioural contrast has collapsed from a planted +0.600 to -0.022. Its displacement norm is
3.073 at layer 48 against 2.521 for the preference adapter, so the two adapters move the
residual stream by similar amounts on these prompts when they are supposed to differ in kind.
That similarity is the geometric signature of the same transfer failure. A null result
against this pole therefore says less than a null result against the gradient pole, which was
computed from the prompts themselves and does not depend on any adapter.

Layer 50 gives the same picture throughout, within 0.005.

**The three features the paper steers with are geometrically indistinguishable from random
dictionary features.** Every one of them sits inside the 95th percentile of the null against
both parts of the readout direction. Choosing them by label semantics, which is what the
paper describes, selects directions with no measurable relationship to the direction that
drives the answer.

**The pilot's fitted vectors did find the answer component.** They reach 0.067 to 0.096
against it, above the 99th percentile of the null, while sitting at or below the null against
the letter component. So the optimisation worked in the sense of locating the answer
direction rather than the letter direction, which is a positive result for their method and
one their own single-cosine measurement could not have shown.

**This also explains their sparse reconstruction failing.** They report a relative residual
norm of 0.961 for the ten-feature fit of the raw readout direction and call it a poor sparse
approximation. The decomposition says why. The raw readout direction is dominated by the
letter part, which is 37.7 long against 9.1 for the answer part, and the dictionary
represents the answer part at 0.269 while barely reaching the null on the letter part at
0.037. The fit fails because the component it is mostly trying to match is not in the
dictionary, not because the dictionary is generally poor at this. That is a different and
more useful conclusion than the one available without the decomposition.

### 5.3 The LoRA anchors do not transfer across the wording

Reading Track B's three trained lottery adapters on the pilot's 432 frozen prompts, with
`cv_bench/anchors/pilot_read.py`:

| quantity | planted | measured on the pilot's prompts |
|---|---:|---:|
| bias contrast, mean | **+0.600** | **-0.022**, sd 0.914 |
| preference contrast, mean | positive | **-0.285**, wrong sign |
| signal retained by the reference adapter | | 0.350 |

The readout itself is sound: the unmodified model measured this way correlates **0.957** with
the pilot's own baseline margins, so the two readouts agree about what they are measuring.
The adapters are also plainly active, since the spread of the logit falls from 12.45
unmodified to 4.36 under the reference adapter. What does not survive is the **planted
contrast**. The bias adapter's constant push, worth +0.600 on the grid it was trained on,
is indistinguishable from zero here.

**This is a negative result for the plan of getting a bias pole onto the pilot's scale
cheaply.** It cannot be done by reading existing adapters. It requires training them on the
pilot's own grid, which is a two-hour job and has not been run.

**It also corroborates the pilot from the other side.** The pilot found its own LoRA's
teacher RMSE rising from 0.042 to 0.115 across wording and its recovered curvature falling
from a planted 0.8 to 0.643. Two teams, two independent implementations, the same conclusion:
**a LoRA anchor is bound to the prompt format it was trained on.** That is a property of the
method rather than a defect in either build, and it is what the pilot's own recommended next
step calls for, a LoRA trained across several phrasings and answer orders.

---

## 6. What this supports in the paper

The pilot's current claim is that one SAE steering recipe failed to reproduce a planted
agent. That is a negative result about a recipe, heavily and correctly qualified.

With Section 1 the claim becomes sharper and positive: at the doses used in the field's
standard practice, feature steering removes most of the model's sensitivity to the thing
being decided, and it does so more than a random direction of the same size. That is a
statement about steering as it is actually practised, it is measured rather than argued, and
it motivates the iso-behavioural protocol as the fix rather than as a preference.
