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

## 5. Still running

Track B's three lottery adapters are being read on the pilot's 432 frozen prompts, in the
pilot's wording and its own logit-margin units, so that the planted bias and the planted
preference sit on one scale with the pilot's conditions. Code is
`cv_bench/anchors/pilot_read.py`. Results will be added here.

---

## 6. What this supports in the paper

The pilot's current claim is that one SAE steering recipe failed to reproduce a planted
agent. That is a negative result about a recipe, heavily and correctly qualified.

With Section 1 the claim becomes sharper and positive: at the doses used in the field's
standard practice, feature steering removes most of the model's sensitivity to the thing
being decided, and it does so more than a random direction of the same size. That is a
statement about steering as it is actually practised, it is measured rather than argued, and
it motivates the iso-behavioural protocol as the fix rather than as a preference.
