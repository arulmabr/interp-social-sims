# The ultimatum anchor work, explained from scratch

The companion to `B_ANCHORS_README.md`, which covers the lottery. Same three steps, same
questions, a different game. Read either on its own.

Every decision here was recorded in `logs/B_DECISIONS.md` as BD54 and BD55 **before any
number in this document existed**, and every value is registered in `MANIFEST_B.csv` under
`B7.*`.

---

## 0. The problem this exists to solve

A direction can be pushed into a model's internals and the model's behaviour will change.
The question that matters is **what kind of change it is**. A direction might simply push
the model toward writing one word. Or it might change what the model actually wants.
Those are different claims and they are easy to confuse, because both move the same
behavioural number.

An anchor is a change of **known kind** built on purpose, so that a method claiming to tell
the two apart can be tested against something whose answer is already known. If the method
cannot place a change that was built to be a preference change, it cannot be trusted on a
direction whose nature is unknown.

### The task all of this is measured on

The **ultimatum game, responder role**. A proposer is given a pie and offers part of it. The
responder either accepts, keeping the offer while the proposer keeps the rest, or rejects,
in which case both get nothing. The prompt states all three facts, because a responder shown
only "reject: nothing, accept: 30 tokens" is not playing a social game at all:

```
A proposer was given 100 tokens and has decided to offer you 30 tokens out of their 100
tokens.
If you accept, you keep the proposed amount and the proposer keeps the rest.
If you reject, both of you get 0 tokens.
```

The grid runs over **three pies**, 20, 100 and 1,000 tokens, and over offers from nothing to
the whole pie. Offers of **half or more are catch trials**: rejecting one costs the responder
money in order to punish a split that already favours them, which no preference in range
explains. They are the social counterpart of a dominated gamble.

**Acceptance threshold.** The offer share at which the responder becomes equally likely to
accept or reject. A higher threshold means a responder who insists on a fairer split before
taking anything. This is the number every intervention is measured against, and it plays the
role the lottery's switching point plays in the companion document.

---

## 1. Step one: inject a change of known kind into a synthetic agent

### 1.1 The reference agent

Prospect theory, which drives the whole lottery side of this work, **cannot describe this
choice**. Accepting pays the offer for certain and rejecting pays nothing for certain, so an
agent that looks only at its own payoff accepts every positive offer and has no threshold at
all. Rejecting a low offer is precisely the behaviour the risk parameterisation cannot
express. A different decision model is needed, not a different parameter.

The model used is **Fehr-Schmidt inequity aversion**, chosen by the authors from three
options put to them:

```
u_accept = offer - beta_adv * max(pie - 2*offer, 0)
u_reject = 0
z        = (u_accept - u_reject) / pie / tau  +  action  +  position  +  label
```

`beta_adv` is the weight the responder puts on **being worse off than the proposer**. When
the offer is under half the pie the responder is behind by `pie - 2*offer`, and that shortfall
is subtracted from the value of accepting. Above half there is no shortfall and the term
vanishes.

`z` is the accept-minus-reject log-odds. Positive means leaning toward accepting. Dividing
by the pie is the social counterpart of the contextual normalisation used on the risk side,
and it makes the agent **scale invariant**: the same offer share gives the same z whether the
pie is 20 tokens or 1,000.

The reference agent is **`beta_adv` = 0.60**, whose threshold is `beta_adv / (1 + 2*beta_adv)`
= **27.27 percent of the pie**. `tau` is 0.1186, carried over from the risk side's
calibration and declared rather than fitted here.

### 1.2 MDC, the minimum detectable change

The **minimum detectable change** is the smallest change the method is designed to be able to
see. It is fixed in advance so that it cannot be adjusted after a result is known.

On the lottery it is a shift of 0.10 in the curvature parameter. Here the authors chose to
fix it by **matching that shift's behavioural size** rather than by copying its number, so
that one MDC means the same amount of behaviour change on both games. One lottery MDC moves
the switching point from 133.9 to 121.0, which is 12.9 tokens across a grid spanning 20 to
240, or **5.86 percent of that grid**. The ultimatum offer grid spans nothing to the whole
pie, so the matched target is a threshold move of 5.86 percent of the pie.

Inverting the threshold formula gives the answer:

| quantity | value |
|---|---|
| reference `beta_adv` | 0.6000 |
| reference threshold | 27.27% of the pie |
| target threshold after one MDC | 21.40% of the pie |
| shifted `beta_adv` | 0.3742 |
| **one MDC on this task** | **0.2258** |

Computed by `cv_bench/estimator/social_mdc.py` from the grid and the reference parameter
alone. No model output enters it.

### 1.3 The two injected changes

**The preference implant.** `beta_adv` falls from 0.60 to 0.3742, one MDC, and nothing else
is touched. A responder who cares less about being behind accepts splits it would previously
have refused. This is a change in what the agent wants.

**The bias implant.** `action` rises from 0 to 0.6 and nothing else is touched. This adds the
same amount to the accept-minus-reject log-odds on every trial regardless of the split. The
agent's view of fairness is unchanged; only its tendency to emit the word "Accept" moves.
The value is identical to the lottery's bias implant, so the two negative controls are
directly comparable.

### 1.4 How the two differ, and where this game is harder than the lottery

| offer share | z, reference | change from the preference implant | change from the bias implant |
|---|---|---|---|
| 0.00 | -5.059 | **+1.904** | +0.600 |
| 0.10 | -3.204 | +1.523 | +0.600 |
| 0.20 | -1.349 | +1.142 | +0.600 |
| 0.25 | -0.422 | +0.952 | +0.600 |
| 0.30 | +0.506 | +0.761 | +0.600 |
| 0.40 | +2.361 | +0.381 | +0.600 |
| 0.50 | +4.216 | **+0.000** | +0.600 |
| 0.70 | +5.902 | +0.000 | +0.600 |
| 0.90 | +7.589 | +0.000 | +0.600 |

The bias adds the same amount everywhere. The preference change does not: it is largest when
the offer is most unfair and falls to exactly zero once the offer reaches half the pie, where
there is no longer any shortfall to care about.

**This is a weaker separation than the lottery has, and the difference matters.** On the
lottery the preference implant is **negative at a reward of 30 and positive at 150**. It
changes sign, and nothing that adds a constant can imitate that. Here the preference implant
is non-negative everywhere. It is a declining positive function against a flat positive one,
and over the offers where behaviour is actually uncertain, a tenth to four tenths of the pie,
it runs from 1.52 down to 0.38 with a mean near 0.9, which a flat 0.6 approximates well.

**The region where they genuinely differ is saturated.** From half the pie upward the
preference implant does nothing while the bias still adds 0.600. That is the region that
could tell them apart. But the reference agent already accepts there with probability 0.985
and above, so an extra 0.600 moves behaviour by less than one percent. Across the whole grid
only **96 of 384** trials sit where the choice is genuinely uncertain.

This property was measured before any GPU time was spent, and `reports/B7_RECOVERY.md`
records what it does to the method on synthetic data, where the agents' parameters are known
exactly.

---

## 2. Step two: train an adapter to copy each agent

### 2.1 What an adapter is

The synthetic agent from step one is a formula. It is not the model whose internals are
being studied. To put the injected change **inside the real model**, the model is taught to
imitate the agent.

An **adapter**, here a LoRA adapter, is a small set of extra weights added alongside the
model's own. The original weights are untouched; only the adapter is trained, which is why
three of them can be trained on one 70B model without three copies of it.

For each of the three agents, reference and preference and bias, the agent's exact
probability of accepting is computed for every training prompt, and an adapter is trained so
that the model's own probability of answering "Accept" at the answer token matches it. The
loss is a cross-entropy over the whole vocabulary, so probability placed on any token that
is neither option is penalised.

Training uses **264 prompts** from the discovery and calibration splits. The selection split
is held out entirely, giving **120 prompts** the adapters have never been fitted on, which is
where cloning is judged. The test split is not touched.

### 2.2 Cloning, and whether it worked

Cloning asks a simple question: on prompts it never saw, does the adapter make the choices
its target agent would make? Three numbers say so.

- **r**, the correlation between the model's log-odds and the agent's across held-out
  prompts. The bar fixed in advance is 0.95.
- **slope**, from regressing the model's log-odds on the agent's. One means the model matches
  the agent's strength of preference, not merely its direction. The bar is 0.9 to 1.1.
- **residual SD**, the spread of what is left over, which sets the noise floor on every
  contrast that follows.

### 2.3 The anchor is the contrast, not the adapter

The same point as on the lottery, and worth repeating.

**The anchor is not any single adapter. The anchor is the difference between the shifted
adapter and the reference adapter.** That difference is a change whose size was chosen
deliberately, so it is the only thing with a known true value. An adapter on its own is just
a model that behaves like some agent, and how faithfully it does so is a separate question
with its own error.

### 2.4 A third anchor, which is not an adapter

The **readout gradient anchor** is built by a completely different route and stands beside
the two adapters in the comparisons.

**What it is.** A direction in the model's activation space, a list of 8,192 numbers, one for
each dimension of the residual stream, which is the running internal state the model carries
from one layer to the next. It is used by adding a multiple of it to that state while the
model runs. No weight is changed.

**How it is computed.** It is the gradient of the accept-minus-reject log-odds with respect to
the residual stream at a chosen layer, averaged over prompts. A gradient is the direction in
which a small change to the internal state raises a quantity fastest, so this is the
direction that most directly pushes the written answer from "Reject" toward "Accept". It was
computed at **layer 48 and layer 50**, the same two layers as on the lottery.

**Why it is computed twice at each layer.** A model can favour an answer, and it can
separately favour whichever option is printed second. To hold those apart the gradient is
taken once for each of the two orders the options can be listed in. The **sum** of the two is
the part they have in common and is the anchor; the **difference** flips when the order flips
and is kept as a position control.

**Which prompts it is averaged over.** Responder prompts on the discovery and calibration
splits with the catch trials removed, for the same reason dominated gambles are removed on
the risk side. The calibration split alone leaves only 12 usable prompts once catch trials
go, too few to average a direction over, so discovery was added. Discovery is not used by the
cloning check, so no set that any later number depends on is touched, and the test split
stays locked. That gives 30 prompts per option order.

**What it found, and it is cleaner here than on the lottery.**

| quantity | ultimatum, layer 48 | ultimatum, layer 50 | lottery, layer 48 |
|---|---|---|---|
| agreement between the two option orders | **+0.953** | **+0.956** | +0.727 |
| length of the order-invariant sum | 18.421 | 17.271 | 22.678 |
| length of the position difference | 2.869 | 2.614 | 9.191 |
| sum as a multiple of the difference | **6.4x** | **6.6x** | 2.4x |
| coherence within one order | 0.851 and 0.844 | 0.853 and 0.847 | 0.882 |

The agreement between the two option orders is reported as a **cosine**, a number between
minus one and one where one means the two directions point the same way, zero means they are
unrelated and minus one means they point opposite ways.

At 0.953 the two orders are nearly the same direction, against 0.727 on the lottery, and the
order-invariant part is 6.4 times the size of the position part rather than 2.4 times. **The
accept-or-reject readout direction is almost entirely about which answer is given and barely
about where the answer sits on the page.** Coherence within a single order, the agreement
between the per-prompt gradients and their own average, is 0.84 to 0.85 on 30 prompts against
0.88 on the lottery's 88, so the direction is well determined despite the smaller prompt set.

This is the one place where the ultimatum task is the easier of the two.

---

## 3. What the runs found, term by term

Llama-3.3-70B-Instruct, rank 16 adapters, 500 training steps, the step used for each adapter
chosen by its own cloning curve. Gradient anchor 5m34s on four GPUs, adapters 2h00m.

### 3.1 Cloning, the three adapters

| adapter | r | slope | clones | lottery's r |
|---|---|---|---|---|
| reference | **0.9977** | 0.9802 | yes | 0.9915 |
| preference | **0.9974** | 0.9327 | yes | 0.9938 |
| bias | **0.9981** | 0.9342 | yes | 0.9933 |

All three clear the bar fixed in advance, r at or above 0.95 and slope between 0.9 and 1.1,
on 120 selection-split prompts none of them was trained on. The correlations are **higher
than the lottery's** on every adapter, so the model imitates a fairness rule at least as
readily as it imitates a prospect-theory one. The slopes sit at the lower end of the band for
the two shifted adapters, meaning they reproduce the direction of their agent's preference
slightly more weakly than its full strength.

So the model was successfully taught to behave like three responders whose rules were known
in advance.

### 3.2 The anchor gate

| column | meaning |
|---|---|
| **Planted** | the reduction in `beta_adv` built into the synthetic agent, in parameter units. 0.2258 is one MDC. |
| **Recovered** | the shift the estimator found, by fitting the reference and shifted adapters separately and taking the difference in fitted `beta_adv`. |
| **Error** | the gap between planted and recovered, expressed in MDC. |
| **Attributed to preference** | having measured that something changed, attribution asks what **kind** of change it was. Five competing explanations are fitted and each receives a share of the evidence between 0 and 1. The bar is 0.8. |
| **Action rejected** | whether the constant-push explanation is ruled out on a cluster bootstrap at the 0.95 level. Both this and the share must hold. |
| **Gate** | the verdict of the decision rule fixed in the plan. |

| Anchor | Planted | Recovered | Error | Attributed to preference | Action rejected | Gate |
|---|---|---|---|---|---|---|
| One times the MDC | 0.2258 | +0.2096 | **0.07 MDC** | **1.000** | yes, at 1.000 | **PASS** |

The five competing explanations are **preference**, a change in the weight on being worse off
than the proposer; **action**, a constant push toward one answer; **belief**, a change in how
the offer is read; **format**, a pull toward a position on the page; and **noise**, a change
in how sharply the responder acts on differences.

**This passes where the lottery failed.** The lottery anchor at one MDC returns an error of
0.13 MDC and a preference share of 0.268, beaten by belief at 0.346, and it fails. Here the
error is 0.07 MDC and the share is 1.000. On this task the method works at its own declared
detection limit rather than at three times it.

**A three times anchor does not exist on this task, and the reason is arithmetic.** Three MDCs
is 0.6773 while `beta_adv` starts at 0.60, so a three times reduction requires a negative
weight on inequity. The lottery's second anchor exists because its parameter has room above
it. Here there is no room below. A three times anchor is available only in the opposite
direction, as a **more** inequity-averse responder, which is not what was declared.

### 3.3 The control that decides how much of this to believe

A weight of 1.000 on preference might simply be what this classifier always says. On the
lottery that objection is answered completely: the **bias** contrast run through the identical
fit returns preference **0.000**. The same control here:

| contrast | preference | action | belief | format | noise | action rejected |
|---|---|---|---|---|---|---|
| preference, a known preference change | **1.000** | 0.000 | 0.000 | 0.000 | 0.000 | yes, at 1.000 |
| bias, a known constant push | **0.581** | 0.415 | 0.004 | 0.000 | 0.000 | **no, at 0.735** |
| bias, the same control on the lottery | 0.000 | 0.491 | not run | 0.509 | not run | not run |

**Read the two criteria separately, because they disagree.**

The **decision rule is specific**. Applied to the known bias it fails both of its tests: the
preference share of 0.581 is under the 0.8 bar, and the bootstrap does not reject the action
explanation, reaching only 0.735 against the 0.95 required. A planted bias would not be
certified as a preference change.

The **share on its own is not specific**. A known pure bias still collects 0.581 of the
evidence on preference, more than the action explanation it actually is. On the lottery the
same number is 0.000. So on this task the preference share cannot be read as a measure of how
preference-like something is; only the full rule, share and bootstrap together, carries
weight.

The size of the bias is recovered well: the action model fits **+0.523** against a planted
0.600.

**Why the share behaves worse here.** Section 1.4 has the reason. The planted preference
change never changes sign across the offer grid, so it is a declining positive function set
against a flat positive one, and over the offers where behaviour is uncertain the two are
close. The lottery's implant changes sign, which nothing constant can imitate.

`reports/B7_RECOVERY.md` predicted this from the geometry alone, before any GPU time, and on
simulated binary choices it was worse still, 0.984 on preference for a known bias. Fitting
the model's continuous log-odds rather than sampled choices recovers a great deal of the
separation, from 0.984 down to 0.581, without restoring it fully.

---

## 4. What is established and what is not

**Established.**

- Three adapters clone their target responders on held-out prompts, at correlations of 0.997
  to 0.998, higher than the lottery's on every adapter.
- The estimator recovers the size of a planted inequity shift to **0.07 MDC** at one times the
  detection limit, where the lottery version needs three times it.
- The readout gradient at layers 48 and 50 is **order-invariant to a cosine of 0.953 and
  0.956**, with the order-independent part 6.4 times the position part. On the lottery the
  same ratio is 2.4.
- The decision rule is specific against the planted bias. Applied to a known constant push it
  certifies nothing, failing both the share bar and the bootstrap.

**Not established.**

- **That the preference share means what it means on the lottery.** A known pure bias collects
  0.581 of the evidence on preference here against 0.000 there. The share is not a usable
  measure on this task on its own, and any later use of it needs the bootstrap beside it.
- **A second anchor at a larger size.** Three times the MDC is not representable in the
  declared direction, so there is no sensitivity curve here of the kind the lottery has.
- **Anything about a probe or an SAE feature.** No real direction has been placed against
  these anchors. The lottery's Table 2 has no counterpart yet.
- **A null band.** No random control directions were run on this task.
- **Transfer between the two games.** Whether a direction that looks preference-like on the
  lottery also looks preference-like here is the specificity test the plan asks for at B7,
  and it has not been run.

**Two limitations that apply to all of it.**

Every number is measured with the **logit readout**, which infers the choice from the
probability the model assigns to each answer token rather than from text the model writes.
The gap between the two is large on the lottery and unmeasured here.

The grids are **small**. 264 training prompts and 120 for cloning, against 1,872 and 1,016 on
the lottery, and 30 prompts per option order for the gradient against 88. The gate passes
comfortably at these sizes, but the intervals behind every number are wider than the
lottery's.

---

## 5. How the two tasks compare, in one table

| | lottery | ultimatum |
|---|---|---|
| decision model | cumulative prospect theory | Fehr-Schmidt inequity aversion |
| preference parameter | `alpha`, curvature of value | `beta_adv`, weight on being behind |
| reference value | 0.88 | 0.60 |
| one MDC | 0.10 | 0.2258 |
| behavioural size of one MDC | 12.9 tokens of switching point | 5.86% of the pie of threshold |
| planted effect changes sign | **yes** | no |
| training prompts | 1,872 | 264 |
| cloning prompts | 1,016 | 120 |
| cloning r, worst adapter | 0.9915 | **0.9974** |
| recovery error at one MDC | 0.13 MDC | **0.07 MDC** |
| preference share at one MDC | 0.268, fails | **1.000, passes** |
| gate at one MDC | **FAIL** | **PASS** |
| gate at three MDC | PASS | not representable |
| known bias attributed to preference | **0.000** | 0.581 |
| readout gradient, order agreement | +0.727 | **+0.953** |

**The two tasks fail in opposite places, and that is the useful part.** The lottery's implant
is hard to detect and easy to tell apart from a bias. The ultimatum implant is easy to detect
and harder to tell apart from a bias. Neither task on its own would have shown that the two
halves of the method have different weak points, and a benchmark built on one game would have
reported whichever weakness that game happens to have.

---

## 6. What would come next

1. **Place a real direction against these anchors**, which is the lottery's Table 2 and has no
   counterpart here yet. The machinery exists in `cv_bench/anchors/probe_vs_anchors.py` and
   needs a social dose target, which is the acceptance threshold rather than the switching
   point.
2. **Run random controls** to establish a null band, which neither task has in usable form.
3. **The cross-game specificity test** the plan asks for at B7: a social direction should
   leave the lottery fingerprint inside the random band, and a risk direction should leave
   the acceptance threshold there.
4. **A second anchor in the upward direction**, a more inequity-averse responder, which is
   the only way to get a sensitivity curve on this task. It is a change to what was declared
   and so is an author decision.
