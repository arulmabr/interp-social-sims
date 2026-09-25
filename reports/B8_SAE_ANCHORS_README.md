# The SAE anchor work, explained from scratch

The third of three. `B_ANCHORS_README.md` covers the lottery, `B7_ULTIMATUM_ANCHORS_README.md`
the ultimatum game, and this one covers what happens when the same anchors are turned on
**sparse autoencoder steering**, which is the interpretability method the paper actually uses.

Read it on its own. Every term is explained where it is used. Every value is registered in
`MANIFEST_B.csv` under `B8.*`, and the findings-only version, written for a reader who
already knows the machinery, is `B8_SAE_PILOT_INTEGRATION.md`.

---

## 0. The problem this exists to solve

The paper's central method is to reach inside a language model, turn up one interpretable
feature, and watch the agent's behaviour change. The claim attached to that is about
**mechanism**: turning up a feature labelled "willing to take risks" is said to make the agent
more risk-taking.

There is a cheaper explanation for the same observation. The intervention might simply be
pushing the model toward writing one word rather than another, with nothing about risk
involved. Both stories predict that behaviour moves. They differ in what the movement means,
and the difference decides whether the method is measuring an attitude or nudging a keystroke.

An **anchor** is a change whose kind is known because it was built on purpose. If an
instrument cannot correctly place a change that was constructed to be a pure answer-push, it
cannot be trusted when it reports on a feature whose nature is unknown.

### What is being tested, and on what

The subject is an SAE steering experiment on a lottery task: 108 economic scenarios, each
shown in two answer orders and two wordings, giving **432 prompts**. The gambles come in
three frames, gains, losses and a mix of the two. The model answers with a single letter,
**A or B**, and which letter means "take the gamble" changes from prompt to prompt. That
last detail turns out to matter more than anything else here.

---

## 1. The pieces, defined

### 1.1 What a sparse autoencoder is

A **sparse autoencoder**, or SAE, is a separate small network trained to rewrite the model's
internal state as a combination of many simple parts, of which only a few are active at once.
The internal state at one layer of this model is a list of **8,192 numbers**, called the
residual stream, which the model carries forward from layer to layer. The SAE used here
rewrites that as a combination drawn from a dictionary of **65,536 features**, at layer 50.

Each feature has a **direction**, which is its column in the SAE's decoder matrix, itself a
list of 8,192 numbers. Steering with a feature means adding a multiple of its direction to
the residual stream while the model runs.

The dictionary is a published file, `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, pinned here at
revision `128ee921`. Nothing in this work contacts a hosted service. **3,632 of the 65,536
features are dead**, meaning their direction is all zeros, and they are excluded throughout.

### 1.2 What the features under test are

The paper names three: feature **184**, labelled "willing to take risks or make sacrifices for
a goal", feature **4237**, "executing potentially risky operations that require caution", and
feature **31935**, "altruistic and selfless behavior or intentions". They were chosen by
reading the labels.

The pilot experiment additionally **fitted** ten-feature combinations, choosing features by
how well they reproduced a target behaviour and then solving for their coefficients. Those
are tested here alongside the named ones, because a fitted combination and a hand-picked
feature are different objects and may behave differently.

### 1.3 What the two anchors are

**The readout gradient anchor.** The direction in which a small change to the model's internal
state most quickly raises the odds of one answer over the other. A gradient is simply the
direction of fastest increase, so this is by construction the most efficient way to push the
written answer, and nothing about it involves preferences. It is computed at layers 48 and
50.

**The bias anchor.** A set of extra weights trained so that the model behaves like an agent
whose only change is a constant push toward one answer, the same amount on every trial,
regardless of the payoffs. Where the gradient anchor is a direction found by differentiation,
this one is a behaviour taught by training. It has no direction in its file, so to compare it
with a feature direction its **displacement** is measured: run the same prompts with and
without it, and take the average change in the residual stream.

Both anchors are built without any SAE. That is deliberate. A yardstick built from the same
dictionary as the thing being measured would prove nothing.

---

## 2. Why the gradient anchor is computed twice at every layer

A model can favour an answer, and it can separately favour whichever **letter** carries that
answer. Those are different things and they are easy to confuse, so the gradient is computed
once for each of the two orders the options can appear in, and the two are then combined:

- their **sum** is the part they have in common, which does not depend on the labelling, and
  is therefore about the answer;
- their **difference** is the part that flips when the labelling flips, and is therefore about
  the letter.

**The agreement between the two orders decides which part dominates**, and it is reported as a
**cosine**: a number between minus one and one, where one means the two point the same way,
zero means unrelated, and minus one means opposite.

| prompt format | answer tokens | cosine between orders | answer part | letter part | ratio |
|---|---|---:|---:|---:|---:|
| **this experiment, layer 48** | **A / B** | **-0.889** | 9.128 | 37.682 | **0.24** |
| this experiment, layer 50 | A / B | -0.893 | 8.416 | 35.383 | 0.24 |
| the lottery work, layer 48 | safe / risky | +0.727 | 22.678 | 9.191 | 2.47 |
| the ultimatum work, layer 48 | Accept / Reject | +0.953 | 18.421 | 2.869 | 6.42 |

**The sign is the whole story.** Here the two orders very nearly cancel. The reason is
mechanical rather than a mistake: when the answer is a bare letter, which letter means "take
the gamble" swaps with the order, so the quantity being differentiated flips sign and the
gradient flips with it. In the other two studies the answer is a word naming the option, and
words do not swap when the print order does.

**What survives is small.** The part that does not flip is 9.128 long against 37.682 for the
part that does. **A readout direction computed on a letter-answer format is about four parts
in five a direction that pushes toward emitting one letter rather than the other**,
independently of what that letter stands for.

---

## 3. What the measurements found

### 3.1 Where the SAE directions sit relative to the two anchors

Each direction's alignment with each anchor, as a cosine. The comparison that makes these
numbers readable is the **null**: 2,000 randomly chosen live dictionary features put through
the identical construction. Anything inside the null is doing no better than a feature picked
at random.

| direction | gradient, answer part | gradient, letter part | bias anchor |
|---|---:|---:|---:|
| **random feature, 95th percentile** | 0.033 | 0.027 | 0.049 |
| **random feature, 99th percentile** | 0.056 | 0.048 | 0.078 |
| feature 184, "willing to take risks" | **-0.001** | **+0.016** | **-0.005** |
| feature 4237, "risky operations" | **+0.004** | **+0.000** | **+0.004** |
| feature 31935, "altruistic and selfless" | **+0.004** | **+0.004** | **+0.017** |
| fitted ten-feature vector, seed 31 | **+0.067** | -0.006 | +0.031 |
| fitted ten-feature vector, seed 73 | **+0.075** | -0.003 | -0.013 |
| fitted vector, second target, seed 31 | **+0.091** | +0.002 | -0.013 |
| fitted vector, second target, seed 73 | **+0.096** | +0.004 | -0.004 |
| sparse fit of the raw readout direction | **+0.269** | +0.037 | -0.008 |

**The three features the paper steers with are indistinguishable from random ones.** Every one
sits inside the 95th percentile of the null against all three poles. Choosing a direction by
reading its label produced directions with no measurable relationship to the direction that
drives the answer, to the direction that drives the letter, or to a planted bias.

**The fitted vectors did find something, and it is the answer component.** They reach 0.067 to
0.096 against it, above the 99th percentile of the null, while sitting at the null against
the letter component and against the bias. So the fitting worked, in the narrow sense of
locating the direction that moves the answer.

**This explains a number the pilot could not account for.** It reports that a ten-feature
sparse reconstruction of the raw readout direction left a relative residual of **0.961**, and
calls it a poor approximation. The decomposition says why: the raw direction is mostly the
letter part, and the dictionary represents the answer part at 0.269 but barely reaches the
null on the letter part at 0.037. The reconstruction fails because the component it is mostly
trying to match is not in the dictionary, which is a narrower and more useful conclusion than
the dictionary being generally poor.

### 3.2 What the steering actually did to the model

Separately from where the directions point, there is the question of what happens when they
are used. Regressing each condition's change in the answer log-odds on its unsteered value
gives a slope. A slope of zero means something was added without touching how the model
responds to the payoff. A slope of minus one means that response was removed entirely. What
is left, one plus the slope, is the share of the payoff signal the measurement still has.

| condition | signal retained | correlation |
|---|---:|---:|
| readout gradient at the dose used | **0.062** | -0.999 |
| SAE ten-feature, both seeds | **0.092 to 0.096** | -1.000 |
| dense vector, both seeds | **0.129 to 0.143** | -0.99 |
| the preference anchor adapter | **0.156** | -0.987 |
| **random directions of the same size** | **0.505 to 0.605** | -0.95 to -0.97 |

The unsteered log-odds have a spread of 9.23. After ten-feature SAE steering it is 0.92. The
model has almost stopped distinguishing between the gambles.

**The correlations near minus one mean this is not a tendency.** Each intervention is, to a
very good approximation, a linear flattening of the signal toward a constant.

**The directions under test destroy three to six times more signal than random ones of the
same size.** A comparison in which the control preserves the measured quantity better than
the treatment is not measuring what it was built to measure.

**It is the dose, and the ladder shows it.** The same direction at three strengths:

| strength | signal retained |
|---|---:|
| 1 | 0.611 |
| 4 | 0.215 |
| 16 | 0.062 |

Strength 16 is where every SAE comparison in the experiment was made.

### 3.3 Whether the bias anchor survives the change of prompts

The bias anchor was trained on a different wording. Reading it on these 432 prompts tests
whether it still carries its planted meaning.

| quantity | planted | measured here |
|---|---:|---:|
| bias contrast, mean | **+0.600** | **-0.022** |
| preference contrast, mean | positive | **-0.285**, wrong sign |
| signal retained by the reference adapter | | 0.350 |

The reading itself is sound: the unmodified model measured this way agrees with the
experiment's own baseline at a correlation of **0.957**. The adapters are plainly doing
something, since the spread falls from 12.45 to 4.36. What does not survive is the **planted
contrast**. A constant push worth 0.600 on the wording it was trained on is indistinguishable
from zero here.

The displacement norms say the same thing geometrically. The bias adapter moves the residual
stream by 3.073 and the preference adapter by 2.521, which are similar, when two changes of
different kinds should not be.

### 3.4 The same measurements on the ultimatum game

Everything above is the lottery. The steering experiment never covered the social task, so
that side was generated here on the responder grid, where the anchors were trained and
therefore hold their planted meaning. 120 trials, the edit applied at the **last prompt
position only**, with strength in units of the median residual stream norm at layer 50, which
is 21.12.

**The ultimatum bias pole works, where the lottery one did not.**

| quantity | planted | measured |
|---|---:|---:|
| bias contrast | +0.600 | **+0.462** |
| preference contrast | positive | **+0.331** |
| bias displacement at layer 48 | | 6.512 |
| preference displacement at layer 48 | | 5.930 |

The bias adapter recovers 77 percent of its planted push and the two displacements differ by
more than they did on the lottery, 6.51 against 5.93. So comparisons against this pole mean
something, which is not true of the lottery pole in Section 3.3.

**Feature 31935 adds a near-constant push toward accepting, and little else.**

| direction | strength | shift in mean log-odds | signal retained |
|---|---:|---:|---:|
| feature 31935, the paper's ultimatum feature | 0.20 | +0.408 | 1.032 |
| | 0.80 | **+1.814** | **1.174** |
| readout gradient | 0.20 | +10.028 | 3.209 |
| | 0.80 | -1.381 | **3.574** |
| random live feature | 0.20 | -0.349 | 0.974 |
| | 0.80 | +0.154 | **0.977** |

Signal retained above one means the intervention made the model respond **more** sharply to
the offer rather than less. The random feature does nothing at any strength, which is the
control behaving correctly.

**Three readings of this.** The paper's ultimatum feature moves the answer by 1.814 in
log-odds while changing the shape of the response by 17 percent, which is the profile of a
push toward one answer rather than a change in what the responder considers fair. The readout
gradient, which is a pure answer-push by construction, does the same thing far more violently,
raising the spread from 7.86 to 28.21. And the compression that dominates every lottery
condition does not appear here at all.

**That last difference is informative rather than contradictory.** The lottery conditions
apply their edit at **every position**; this one applies it at the **last position only**, at
a comparable per-position strength. So the flattening in Section 3.2 is a property of the
all-position regime rather than of magnitude alone. The two are not interchangeable and
should not be pooled.

**What is missing from this run.** Only per-dose summaries were saved, not the per-trial
log-odds, so the full five-family attribution cannot be computed from it. Establishing that
feature 31935 is action-like rather than merely consistent with being action-like needs a
re-run that keeps the per-trial values.

---

## 4. What is established and what is not

**Established.**

- Feature 31935, measured against the **ultimatum** readout direction rather than the lottery
  one, gives +0.013 on the answer part against a 95th-percentile null of 0.028. It is
  indistinguishable from a random feature even on its own game.
- On the ultimatum responder the bias anchor recovers +0.462 of its planted +0.600, so a
  working bias pole exists on that task.
- Steering with feature 31935 at the last position shifts the answer log-odds by 1.814 while
  leaving the shape of the response nearly unchanged, and a random live feature at the same
  strength does nothing.
- On a letter-answer format the readout direction is about four fifths letter identity, with
  the two orders anti-correlated at -0.889. The same computation on word answers gives +0.727
  and +0.953, so this is a property of the format rather than of the model.
- The three features the paper steers with sit inside a random-feature null against every
  pole tested.
- Fitted feature combinations align with the answer component above the 99th percentile of
  that null, and with nothing else.
- At the strength used throughout the experiment, every intervention retains under 0.16 of
  the model's response to the payoff, and random directions of the same size retain three to
  six times more.
- A bias anchor trained on one wording does not carry its planted contrast to another.

**Not established.**

- **Anything about what the SAE directions do**, as opposed to where they point. Every
  placement here is a cosine. Both of the companion documents argue that geometry is not the
  test and that the behavioural decomposition is, and that measurement has not been run.
- **That the dictionary lacks preference capacity.** The experiment's null result is
  consistent with that and equally consistent with the dose having flattened the payoff
  response before any preference could show. These measurements cannot separate the two.
- **A bias pole on this wording.** The transfer failure means the bias comparisons in §3.1
  rest on a pole whose planted meaning is in doubt. The gradient comparisons do not have this
  problem, since the gradient is computed from the prompts alone.
- **That feature 31935 is action-like**, as opposed to consistent with being action-like. Its
  profile in Section 3.4, a shift of 1.814 with the response shape barely changed, is what a
  push toward one answer looks like, but the run saved per-dose summaries only and the
  attribution needs per-trial values.

---

## 5. Three descriptions that need correcting

### 5.1 The raw readout gradient is not simply action-like

It is usually described as action-like, meaning it pushes the answer rather than changing a
preference. On a letter-answer format that understates it. The direction is mostly
**letter-identity-like**: it pushes toward emitting one character, and the connection to what
that character means is the smaller part. Any cosine measured against it, including the
feature screening cosines of 0.068 to 0.073 reported in the experiment, is mostly measuring
alignment with letter identity.

### 5.2 Matching interventions by size does not make them comparable

Setting every direction to the same vector length looks even-handed and is not. Equal length
produces very different amounts of behaviour change, which §3.2 measures directly. The
alternative is to scale each direction so that it produces the **same shift in behaviour**,
and then ask what moved underneath. On the lottery work the strengths that achieve a matched
shift differ across directions by a factor of about 150.

### 5.3 A null result at one strength is not a result about the method

Reporting that no cell passed is accurate. Reporting it as evidence about what a sparse
dictionary can represent is not, when at that strength the quantity the criterion is computed
on has been reduced to a sixteenth of its unsteered spread in every cell, including the
controls.

---

## 6. What would come next

1. **The behavioural placement**, which is the measurement this document repeatedly says is
   missing. Scale each SAE direction so it shifts behaviour by the same amount as the anchor,
   then decompose what changed. About an hour of computation.
2. **Retrain the anchors on these prompts**, so a bias pole exists in this wording. About two
   hours, and a precondition for item 1 being interpretable.
3. **Repeat the placement at strengths 1 and 4**, where the payoff response still exists. The
   existing evidence covers only the regime where it does not.
4. **Compute a readout direction for the ultimatum game** before drawing any conclusion about
   feature 31935.
