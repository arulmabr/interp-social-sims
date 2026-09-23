# The anchor work, explained from scratch

This document covers the anchors only. It assumes no prior knowledge of the project and
defines every term the figures use. It is organised as the three steps the work actually
takes: **inject a known change**, **train an adapter to copy it**, **compare the probe
against it**.

Every number here comes from a script that reads raw logs and is registered in
`MANIFEST_B.csv` with its script, its inputs and the commit it was computed at.

---

## 0. The problem this exists to solve

When a steering direction makes an agent more willing to gamble, at least three different
things could have happened inside the model:

1. its **preference** changed, meaning it genuinely dislikes risk less than before;
2. its **answer** was pushed, meaning it says the word "risky" more often without valuing
   anything differently;
3. its **reading of the payoff** changed, meaning it now perceives the numbers differently.

All three produce the same shape of behaviour curve. Nothing in the existing figures can
separate them.

The remedy is to stop guessing. Build changes whose nature is known in advance, put them
inside the model, and check whether the measurement recognises them correctly. If it can,
it can be trusted when it speaks about the probe. That is what an **anchor** is: a change
of known kind and known size, used as a reference point.

### The task all of this is measured on

One lottery, repeated at many reward levels. The agent chooses between

- a **sure option** paying **50 tokens**, and
- a **risky option** paying the **risky reward** half of the time and nothing otherwise.

Because the gamble pays out half the time, the two options are worth the same on average
when the risky reward is **100 tokens**. That number matters throughout.

**Switching point.** The risky reward at which the agent becomes equally likely to gamble
or take the sure thing. Above 100 the agent is demanding a premium to gamble, which is
risk aversion. Below 100 it is paying a premium to gamble, which is risk seeking.

---

## 1. Step one: inject a change of known kind into a synthetic agent

### 1.1 The reference agent

A synthetic decision maker is defined first, using cumulative prospect theory. It has four
parameters:

| parameter | value | what it controls |
|---|---|---|
| **alpha** | 0.88 | curvature of the value function, `v(x) = x^alpha`. Lower means large payoffs are discounted more, which is risk aversion. |
| **gamma** | 0.61 | probability weighting. Controls whether stated odds are taken at face value. |
| **lambda** | 2.25 | loss aversion. Only active on trials involving losses. |
| **tau** | 0.1186 | temperature of the choice rule. Controls how sharply the agent acts on small differences. |

This agent computes a quantity called **z**, the log-odds of choosing the risky option:

```
z = ( utility(risky) - utility(safe) ) / utility_range / tau
z = z + action          <- a constant push, zero for the reference agent
z = z + position        <- a pull toward whichever option is shown second
z = z + label           <- a pull toward the option labelled "Risky"
```

Positive z means a pull toward the gamble. `utility_range` is the spread of value across
everything on offer in that trial, so the agent judges options relative to what is
available rather than on an absolute scale.

**This reference agent switches at 133.9 tokens.** A purely rational agent that maximises
expected value switches at exactly 100. So the reference agent demands about a third more
than fair value before it will gamble. That is deliberate, because the real model behaves
that way too.

### 1.2 MDC, the minimum detectable change

**MDC stands for minimum detectable change.** It is the smallest change in a parameter the
method commits in advance to being able to detect.

```
MDC = { alpha: 0.10,  gamma: 0.10,  lambda: 0.30 }
```

It is **declared, not derived**. The plan fixes these values so they cannot be adjusted
after seeing a result. It does three jobs:

- it **sets the size of the planted change**, so the test is the hardest honest one;
- it is the **unit errors are reported in**, so "0.13 MDC" means the estimate landed about
  an eighth of the way from the truth to the edge of what the method claims to resolve;
- it **sets the gate thresholds**.

If a gate fails, the plan says to change the design, never the MDC.

### 1.3 The two injected changes

Two variants of the reference agent are built. Each differs from it in exactly one
parameter.

**The preference implant.** `alpha` is raised from 0.88 to 0.98, which is a shift of
exactly one MDC. A higher exponent discounts large payoffs less, so the agent becomes
more willing to gamble. Its switching point moves from 133.9 to 121.0.

**The bias implant.** `action` is raised from 0 to 0.6, and nothing else is touched. This
adds a flat 0.6 to z on every trial. The agent's valuation of the options is completely
unchanged. Only its tendency to emit the word "risky" moves. Its switching point moves
from 133.9 to 112.1.

### 1.4 Why these two are different in kind, which is the crux

The bias adds the same amount everywhere. The preference change does not:

| risky reward | z, reference | change from the preference implant | change from the bias implant |
|---|---|---|---|
| 30 | -6.169 | **-0.113** | +0.600 |
| 50 | -4.885 | **+0.000** | +0.600 |
| 70 | -2.724 | +0.207 | +0.600 |
| 110 | -0.666 | +0.319 | +0.600 |
| 150 | 0.340 | **+0.334** | +0.600 |
| 230 | 1.345 | +0.312 | +0.600 |

The preference change is **negative at 30, zero at 50, and positive above that**. It
changes sign. This is correct behaviour for a change in risk attitude: it shows up where
the decision is genuinely contested and does almost nothing where the answer is obvious.
The bias, by contrast, pushes toward "risky" even on a gamble paying 30 against a sure 50,
which no attitude to risk would find appealing.

**This single fact drives everything that follows.** A constant offset survives averaging
intact. A change of shape partly cancels against itself. Averaging the change in z
therefore detects the bias and is close to blind to the preference shift.

One further property worth knowing: the preference implant is **scale invariant**. Trials
at the same ratio of prize to sure amount give identical z and identical shift, whether
the stakes are 20 against 12 or 100 against 60. Doubling all amounts changes nothing.

---

## 2. Step two: train an adapter to copy each agent

### 2.1 What an adapter is

An **adapter** is a small set of extra weights trained on top of a frozen model so that
the model behaves in some chosen way. The technique is called low rank adaptation, usually
abbreviated LoRA. Training one is cheap and the original model is left untouched.

Three adapters were trained on Llama 3.3 70B Instruct, one per agent:

- the **reference adapter**, which makes the model choose the way the reference agent would;
- the **preference adapter**, for the agent with alpha raised by one MDC;
- the **bias adapter**, for the agent with the constant push.

Training uses soft-label cross-entropy against the synthetic agent's own choice
probabilities, on 1,872 prompts drawn from the discovery and calibration splits. The
selection split is held out entirely so the check below is on prompts never seen.

### 2.2 Cloning, and whether it worked

**Cloning** means how closely an adapter reproduces the agent it was trained on, measured
only on held-out prompts. An adapter counts as a faithful copy when

- the **correlation** between the model's choice tendency and the agent's is at least 0.95, and
- the **calibration slope** lies between 0.9 and 1.1, meaning it tracks the target one for
  one rather than merely ranking trials in the same order.

All three passed, on 1,016 held-out rows:

| adapter | correlation | slope | verdict |
|---|---|---|---|
| reference | 0.9915 | 0.9567 | passes |
| preference | 0.9938 | 0.9618 | passes |
| bias | 0.9933 | 0.9359 | passes |

So the model was successfully taught to imitate three decision makers whose rules were
known in advance.

### 2.3 The anchor is the contrast, not the adapter

This is the point most often misunderstood, and it is worth stating flatly.

**The anchor is not any single adapter. The anchor is the difference between the shifted
adapter and the reference adapter.** That difference is a change whose size was chosen
deliberately, so it is the only thing with a known true value. An adapter on its own is
just a model that behaves like some agent.

### 2.4 A third anchor, which is not an adapter

Steps one and two produce two anchors that live in **trained weights**. A third anchor
stands beside them in the comparisons and is built by a completely different route, so it
needs its own account.

**What it is.** The readout gradient anchor is a **direction in the model's activation
space**. A direction here is a list of 8,192 numbers, one for each dimension of the
residual stream, which is the running internal state the model carries from one layer to
the next. It is used by adding a multiple of it to that state while the model runs. No
weight is changed.

**How it is computed.** It is the **gradient** of the choice log-odds with respect to the
residual stream at a chosen layer, averaged over prompts. A gradient is the direction in
which a small change to the internal state raises a quantity fastest, so this is the
direction that most directly pushes the written answer from safe toward risky. It was
computed at **layer 48 and layer 50**.

**Why it is computed twice at each layer.** A model can favour an answer. It can also
separately favour whichever option is printed second. To hold those apart, the gradient
was taken **once for each of the two orders the options can be listed in**, which gives
one direction per order.

**How far the two orders agree.** The agreement is reported as a **cosine**, a number
between minus one and one, where one means the two directions point the same way, zero
means they are unrelated, and minus one means they point opposite ways. The two orders
agree at **+0.727 at layer 48** and **+0.739 at layer 50**. Agreement this far above zero
means the direction is mostly about which answer is chosen rather than about where the
answer sits on the page.

**What is kept from the two.** The anchor is the **sum** of the two orders, which is the
part they have in common and therefore does not depend on presentation order. Its length
at layer 48 is 22.678. The **difference** of the two orders is the part that flips when
the order flips, so it is kept separately as a position control. Its length at layer 48 is
9.191. The order independent part is **2.4 times the size** of the position part, which is
the right way round for a direction that is meant to be about the answer.

**One further check.** Within a single order the gradients taken on individual prompts
agree with their own average at 0.882 at layer 48. The direction is therefore not an
average over prompts that disagree with each other.

**A withdrawn value.** An earlier computation returned a cosine of minus 0.814 at layer 48
and a position part 2.6 times the order independent part, which is the opposite conclusion.
That run used prompts in which the word naming the gamble swapped between the two orders,
so the direction that raises the log-odds swapped with it. The value is withdrawn in full
rather than qualified, and the corrected figures above replace it.

---

## 3. What the figures show, term by term

### 3.1 `B3_contrasts_plain.png`

This table reports what happened when the two contrasts were measured by taking the
**mean of the change in z**.

| column | meaning |
|---|---|
| **Contrast** | which difference is being measured. "preference − reference" is the preference adapter minus the reference adapter. "bias − reference" is the bias adapter minus the reference adapter. |
| **Planted** | the size of the change that was built in, in units of z. |
| **Measured** | what the method recovered. |
| **95% interval** | the uncertainty on that measurement. A 95 percent confidence interval is the range the true value would fall in 95 times out of 100 if the measurement were repeated. |

The values shown:

| Contrast | Planted | Measured | 95% interval |
|---|---|---|---|
| preference − reference | 0.0302 | 0.0474 | [−0.0291, +0.1239] |
| bias − reference | 0.6000 | 0.4968 | [+0.4178, +0.5759] |

**What to look at is the sign of the lower end of each interval.** The preference interval
begins below zero, so on this measurement the planted preference change could not be
distinguished from no change at all. The bias interval lies entirely above zero, so the
planted bias was clearly detected.

The reason is size, not correctness. The planted bias is about twenty times larger than
the planted preference change, and each adapter carries its own imprecision even when it
clones almost perfectly.

**Two corrections apply to this figure and it should be regenerated before use.**

1. It was computed on **240 prompts**. Using all 1,016 available narrows the interval.
2. It assumed the two adapters' imprecisions are **independent**. They are not, by design:
   the protocol gives all three adapters the same data order and the same random seed, so
   their errors are correlated at **+0.576**. Measuring that correlation rather than
   assuming it away lowers the noise floor from 0.5806 to 0.3805.

With both corrections the preference interval becomes **[+0.0054, +0.0522]**, which no
longer contains zero.

### 3.2 Table 1, the anchor gate at two sizes

This table reports the same two anchors measured a **different way**, and the change of
method is the important part.

**Why the method changed.** As [Section 1.4](#14-why-these-two-are-different-in-kind-which-is-the-crux) shows, the planted preference change is a
change of shape whose effect varies with the payoff and changes sign. Averaging it is
close to meaningless, because a perfectly faithful adapter could average to nearly zero.
So the gate now **fits the parametric model to each adapter separately and compares the
fitted alpha values**, rather than averaging the difference in z. That decision was taken
on this structural ground and was written down and committed **before the three times
result was read**.

| column | meaning |
|---|---|
| **Anchor** | which of the two planted preference changes is being reported. |
| **Planted** | the size of the shift built into the synthetic agent, in units of the alpha parameter. 0.1000 is one MDC, 0.3000 is three. |
| **Recovered** | the shift the estimator actually found, by fitting the reference and shifted adapters separately and taking the difference in fitted alpha. |
| **Error** | the gap between planted and recovered, expressed in MDC. 0.13 MDC means the estimate landed about an eighth of a detectable change from the truth. |
| **Attributed to preference** | the second step of the analysis. Having measured that something changed, attribution asks what **kind** of change it was. Five competing explanations are fitted and each receives a share of the evidence between 0 and 1. This column is the share going to preference. The bar for passing is 0.8. |
| **Gate** | the verdict of the decision rule fixed in the plan, which requires both an accurate recovery **and** a correct attribution. |

| Anchor | Planted | Recovered | Error | Attributed to preference | Gate |
|---|---|---|---|---|---|
| One times the MDC | 0.1000 | +0.0874 | 0.13 MDC | 0.268 with belief ahead at 0.346 | FAIL |
| Three times the MDC | 0.3000 | +0.2987 | 0.01 MDC | 1.000 with action rejected | PASS |

**The five competing explanations** the attribution step chooses between are:

- **preference**, a change in alpha, gamma or lambda;
- **action**, a constant push toward one answer;
- **belief**, a change in how the stated odds are read;
- **format**, a pull toward a position on the page or a particular label;
- **noise**, a change in how sharply the agent acts on differences.

"0.268 with belief ahead at 0.346" means the preference explanation received 27 percent of
the evidence and was beaten by the belief explanation at 35 percent. "1.000 with action
rejected" means preference took all of the weight and the action explanation was ruled out
on a cluster bootstrap at the 0.95 level.

**What this table establishes.** Recovery is excellent at both sizes. Attribution collapses
at one MDC and is perfect at three. Since the only thing that changed between the rows is
the size of the planted effect, **the attribution problem is one of sensitivity, not of
principle**. The method degrades at its own declared limit, which is the expected
behaviour of a calibrated instrument.

**And one control that is not in the table but answers the obvious objection.** A weight of
1.000 on preference might simply be what this classifier always says. It is not. Run the
**bias** contrast through the identical fit and it returns **preference 0.000**, with the
weight going to format at 0.509 and action at 0.491. The attribution step gives a known
preference change full weight and a known bias none at all.

### 3.3 Table 2, the probe placed against the anchors

This table is the third step, and everything about it is **exploratory**. It sits on the
selection split, it is not pre-registered, and no verdict from it is certified.

| column | meaning |
|---|---|
| **Direction** | what was steered with. The **choice probe** is the paper's own direction, a linear direction trained to separate the two answers. The **difference of means** is the average activation on risky trials minus the average on safe trials, which is the simplest possible direction of that kind. The **reward probe** is trained to predict the reward on offer rather than the answer. The **readout anchor at layer 50** is the same gradient anchor built one layer higher, carried here as a check on itself. |
| **Distance to the bias anchor** | how far that direction sits from the adapter built to be a pure push toward one answer. |
| **Distance to the readout anchor** | how far it sits from the gradient at layer 48 that most directly drives the answer. |
| **Placed with** | whichever of the two preceding numbers is smaller. |

**What the distance actually measures.** Each direction's effect is summarised by four
numbers that add up to one. They are the shares of the variation it produces that are
carried by a constant push, by the wording of the prompt, by the payoff on offer, and by a
change in how sharply the agent acts on differences. The distance between two directions
is the ordinary straight line distance between their two sets of four numbers. Zero means
the two summaries are identical. The largest value reachable is about 1.41, which is what
two summaries putting all their weight on different single terms would give.

| Direction | Distance to the bias anchor | Distance to the readout anchor | Placed with |
|---|---|---|---|
| Choice probe at layer 48 | 0.540 | 0.679 | the bias anchor |
| Choice probe at layer 50 | 0.440 | 0.778 | the bias anchor |
| Difference of means at layer 48 | 1.211 | 0.045 | the readout anchor |
| Difference of means at layer 50 | 1.027 | 0.187 | the readout anchor |
| Reward probe at layer 48 | 1.172 | 0.043 | the readout anchor |
| Reward probe at layer 50 | 0.346 | 0.878 | the bias anchor |
| Readout anchor at layer 50 | 1.227 | 0.026 | the readout anchor |

The first four rows are the ones shown in the figure. The last three are the remaining
directions that were run, reported here because every direction that runs is reported.

**Two of those additions change what the table says.** The reward probe lands with the
readout anchor at layer 48 and with the **bias anchor** at layer 50, so where a direction
is placed can depend on the layer it was read from. The readout anchor built at layer 50
sits 0.026 from the one built at layer 48, which is close to identical, so the measurement
recognises the same direction when it is handed to it twice.

**The null band, which decides whether any of this counts.** Random directions were put
through the identical procedure. The smallest distance any of them reached to a pole is
**1.009**, and that number is the null band. A direction is only recorded as resembling a
pole if it gets closer than a random direction managed, since anything a random direction
achieves is available for free. All seven rows above are inside 1.009 of the pole they are
placed with. The band itself rests on very few controls, which Section 4 states as a
limitation.

**The readout anchor** is the gradient anchor, the direction that most directly pushes the
written answer from safe to risky. **The bias anchor** is the bias adapter from Step 2.
Those two are the poles everything else is measured against, and they sit far apart, which
is what makes any placement between them meaningful.

**Distances are measured in the space of the model free variance decomposition.** That
decomposition splits the change an intervention produces into the part that is a constant
push, the part that depends on the wording, and the part that depends on the payoff. A
constant push indicates a bias. A dependence on payoff indicates a preference change.

**Every direction was given a dose matched on behaviour, not on size.** Each was scaled so
that it produces the same shift of the switching point as the bias adapter, which is 91
tokens, from 210.08 unmodified down to 118.94. The doses that achieve this differ by a
factor of about 150 across directions, so comparing at equal vector length would have
compared very different amounts of intervention.

**The preference adapter is deliberately absent from this table.** At the time this ran,
the preference contrast had not resolved, so it could not serve as a pole. Using an anchor
whose own measurement is unresolved would put an unknown quantity on both sides of the
comparison. Adding it is the next step and has not been done.

---

## 4. What is established and what is not

**Established.**

- Three adapters clone their target agents on held-out prompts, at correlations of 0.99.
- The estimator recovers the size of a planted preference change accurately at both one
  and three times the MDC, with errors of 0.13 and 0.01 MDC.
- The attribution step is specific **against the planted anchors**: it gives a planted
  preference change full weight and a planted bias none.
- At three times the MDC the anchor gate passes on all criteria.

**Not established.**

- Attribution on **arbitrary real directions**. In the probe comparison, which fits a
  steered real model against the unmodified model rather than one adapter against another,
  the classifier returns preference for almost every direction. That is a different fit on
  a different problem and it is not specific.
- Anything about the probe. The placement in Table 2 is exploratory and the classifier
  that would certify it has failed its own calibration test.
- A working null band. Three of four random control directions could not be dosed at all,
  because they saturate the model into always choosing the sure option before reaching the
  required shift. The plan already prescribes the fix, which is covariance matched random
  directions rather than isotropic ones.

**One limitation that applies to all of it.** Every anchor number is measured with the
**logit readout**, which infers the choice from the probability the model assigns to each
answer token rather than from text it writes. A separate check found the readout and free
generation disagreeing substantially. So these are statements about the readout instrument
until confirmed by sampled generation.

---

## 5. Four descriptions that need correcting

### 5.1 The bias was not implanted as an embedding vector

This is the most important correction, because the mental model it leaves behind is wrong
in a way that changes what the result means.

The bias implant has been described as fetching the encoding of some scenarios, building
an embedding vector out of them, and adding that vector into the model's internal
representations at layer 48 or 50. That description invites the question of what specific
text was used to produce the encoding.

**No text was encoded and no vector was added to the model's activations.** There is no
scenario text behind the bias implant and no embedding built from one. The mechanism is
the one in Sections 1 and 2 of this document:

1. a synthetic agent is defined with one parameter changed, `action` moved from 0 to 0.6,
   which adds a flat 0.6 to its choice log-odds on every trial;
2. that agent's choice probabilities are computed on 1,872 training prompts;
3. a LoRA adapter is trained with cross-entropy so the model's own answer-token
   probabilities match those numbers.

The bias lives in **trained weights**, not in an added activation vector. Nothing is
injected at layer 48 or 50 at any point in building it.

**Where the confusion comes from is understandable**, because the project does contain a
vector of exactly the kind described, and it sits next to the bias adapter in the same
tables. That is the **readout gradient anchor**. It genuinely is a direction in the
model's activation space, it genuinely is computed at layers 48 and 50, and it genuinely
is applied by adding a multiple of it to the activations while the model runs.

So the two anchors work by completely different mechanisms:

| anchor | what it is | how it is applied |
|---|---|---|
| **readout gradient anchor** | a vector in activation space, computed as the gradient of the choice log-odds with respect to the residual stream at a given layer | added to the activations at layer 48 or 50 during the forward pass |
| **bias adapter** | a small set of trained weights | loaded as an adapter; nothing is added to activations |

One consequence follows and is worth stating. It would be natural to evaluate how well the
bias was implanted by testing how behaviour shifts after the vector is added.
For the bias adapter there is no such step. The equivalent check is the **cloning** check
in [Section 2.2](#22-cloning-and-whether-it-worked), which asks whether the adapter reproduces its target agent's choices on
held-out prompts. It does, at a correlation of 0.9933.

### 5.2 What preference was defined as, and what it was not

What counts as preference is the right question to ask, and one extreme answer to it is an
agent that takes the gamble regardless of expected value, because it does not care what
the expectation is.

**That is not what was implanted, and the distinction is worth keeping.** The preference
implant raises `alpha` from 0.88 to 0.98, which bends the value function. Its effect
depends on how attractive the gamble is, and it changes sign, as the table in [Section 1.4](#14-why-these-two-are-different-in-kind-which-is-the-crux)
shows. It moves the switching point from 133.9 to 121.0, toward the rational 100 but not
past it.

That extreme version, take the gamble whatever the numbers say, is much closer to what the
**bias** implant does. The bias adds the same push even to a
gamble paying 30 against a sure 50, which no attitude to risk would find appealing. So the
intuition offered for preference in fact describes the control.

This matters because the two implants only work as a contrast if preference is the thing
that bends with the payoff and bias is the thing that does not. Defining preference as
indifference to expected value would collapse the distinction the whole design rests on.

### 5.3 The distances between directions are not cosine distances

The numbers in Table 2 are sometimes read as cosine distances, which would make them a
measure of the angle between two directions in the model's activation space. They are not.

**What they are.** As [Section 3.3](#33-table-2-the-probe-placed-against-the-anchors)
sets out, each direction is first reduced to four numbers that add up to one, the shares
of its effect carried by a constant push, by the wording, by the payoff, and by the
sharpness of the response. The distance is the straight line distance between two such
sets of four numbers, computed as `numpy.linalg.norm(v - w)` in
`cv_bench/anchors/analysis_b33.py`.

**Why the difference matters.** A cosine distance compares the directions themselves, so
two directions that do quite different things to behaviour can still look close if they
happen to point a similar way. The distance used here compares what each direction **does
to the model's choices**. Two directions can point almost the same way and still sit far
apart on this measure, which is the intended behaviour, because the question being asked
is whether a direction acts like a bias or like a change in how the payoff is weighed.

A cosine does appear elsewhere in this work. It is the agreement between the two option
orders used to build the readout gradient anchor, in
[Section 2.4](#24-a-third-anchor-which-is-not-an-adapter).

### 5.4 A correction to the step counts on the instrument figure

This concerns the instrument figure rather than the anchors, but the same reading of it
would otherwise propagate.

The step counts on that figure are sometimes read as meaning that one step is five tokens
and that 34 steps corresponds to the range 10 to 180, with 25 steps a shorter range chosen
where the curve stabilises.

That is not what those numbers are. **They are the gap between two crossing points, not a
plotted range:**

```
legacy     readout 234.1  -  free generation  62.6  =  171.5 tokens  /5 = 34.3 steps
strict     readout 234.1  -  free generation 110.0  =  124.1 tokens  /5 = 24.8 steps
decision   readout 234.1  -  free generation  63.2  =  170.9 tokens  /5 = 34.2 steps
```

The resemblance to the range 10 to 180 is a coincidence of 170 being close to 171. The
step is five tokens because that is the spacing of the reward ladder, and the standard set
in advance for calling the two instruments in agreement was that their crossings fall
**within one step** of each other.
