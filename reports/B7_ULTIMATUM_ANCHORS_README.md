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
stays locked.

---
