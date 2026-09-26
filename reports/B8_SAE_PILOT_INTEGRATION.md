# Running the anchors on SAE steering: what was done and what was found

A point by point account. Each step says how it was run, then gives the table, then says what
every column and row and cell means, then what may be claimed from it.

Model: Llama-3.3-70B-Instruct, loaded from local weights. Dictionary:
`Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, the public checkpoint pinned at revision
`128ee921`, 65,536 features of which 3,632 are dead. No hosted service is contacted anywhere.

Two tasks. The **lottery** is 432 prompts, 108 economic scenarios in gain and loss and mixed
frames, each shown in two answer orders and two wordings, answered with the bare letter **A**
or **B**. The **ultimatum responder** is 120 prompts answered with the words **Accept** or
**Reject**.

---

## Step 1. Build the readout gradient anchor

### How it was done, in detail

The model reads a prompt and, at the final prompt token, holds an internal state of 8,192
numbers called the residual stream. Write `h` for that state at a chosen layer.

Define the readout as the log-odds of one answer against the other:

```
z = log P(gamble token) - log P(sure token)
```

taken from the model's output distribution at the position immediately after the prompt.
Differentiating gives `dz/dh`, a vector of 8,192 numbers: the direction in which a small
change to the internal state raises `z` fastest. This is obtained by a single forward pass
with a hook that retains the activation at the chosen layer, then one backward pass from `z`.

Each prompt yields one such vector. They are averaged over prompts to give one direction per
layer.

**Computed twice per layer, and why.** Each economic scenario appears in both option orders.
Let `g1` be the average gradient over prompts where the gamble is the first option and `g2`
where it is second. Two combinations are formed:

```
g1 + g2   the part identical in both orders
g1 - g2   the part that reverses when the order reverses
```

Catch trials, where one option plainly dominates, are excluded. Lottery, 168 prompts per
order, 11m16s. Ultimatum, 30 prompts per order, 5m34s. Code is
`cv_bench/anchors/pilot_gradient.py` and `cv_bench/anchors/gradient.py`.

### The table

| task | answer tokens | cosine between the orders | sum length | difference length | ratio |
|---|---|---:|---:|---:|---:|
| lottery, layer 48 | A / B | **-0.889** | 9.128 | 37.682 | **0.24** |
| lottery, layer 50 | A / B | -0.893 | 8.416 | 35.383 | 0.24 |
| ultimatum, layer 48 | Accept / Reject | **+0.953** | 18.421 | 2.869 | **6.42** |
| ultimatum, layer 50 | Accept / Reject | +0.956 | 17.271 | 2.614 | 6.61 |

### What every column means

**task** names the game and the depth inside the model. Layers 48 and 50 are the two the
project steers at, so both are reported and neither is chosen after the fact.

**answer tokens** is the pair of words whose probabilities form the readout. This column is in
the table because it turns out to explain the rest of the row.

**cosine between the orders** is the agreement between `g1` and `g2`, computed as their dot
product divided by the product of their lengths. It runs from minus one to plus one. Plus one
means the two are the same direction, zero means unrelated, minus one means exact opposites.

**sum length** is the length of `g1 + g2`, computed as the square root of the sum of its
squared entries. Because this half survives the option order changing, it is the part of the
push that is about **which option is preferred**.

**difference length** is the length of `g1 - g2`, the part that only exists because of how the
question was laid out.

**ratio** is sum length divided by difference length. Above one means the choice-relevant part
dominates. Below one means the presentation-relevant part does.

### What every row and cell says

**Lottery at layer 48.** A cosine of −0.889 means the two orders are 89 percent exact
opposites. They nearly cancel when added, which is why the sum is short at 9.128 while the
difference is long at 37.682. The ratio of 0.24 says the presentation part is about four times
the choice part.

**Lottery at layer 50** repeats it at −0.893 and 0.24, so the result is not an artefact of the
depth chosen.

**Ultimatum at layer 48.** A cosine of +0.953 means the two orders nearly coincide. Adding
them keeps almost everything, giving 18.421, while subtracting them leaves only 2.869. The
ratio of 6.42 is the reverse of the lottery's.

**Ultimatum at layer 50** repeats it at +0.956 and 6.61.

### Why this happens, and the honest framing

On the lottery the answer is a bare letter and which letter names the gamble swaps with the
order. So the quantity being differentiated is `log P(A) - log P(B)` on half the prompts and
its exact negation on the other half. The gradient flips with it. On a letter format this is
**structurally expected** rather than a defect discovered, and the sum is the informative
quantity because it is what survives once token identity is removed.

On the ultimatum the answers are words that keep their meaning wherever printed, so the
target does not flip and the residual difference of 2.869 is a genuine position effect.

A quality check: within a single order the individual prompt gradients agree with their own
average at 0.851 and 0.844 at layer 48, so each half is one consistent direction rather than
an average of unrelated things.

### What may be claimed in the paper

That a readout gradient computed on a multiple-choice letter format is, on this model, about
four parts in five a token-identity direction, and that the same computation on word answers
inverts that balance. Any cosine reported against an undecomposed readout direction on a
letter format is therefore largely reporting alignment with token identity, and the answer
format should be stated wherever such a cosine appears.

The constructive version is that a readout direction intended to represent the choice should
be built as the sum over both option orders, which costs one extra forward pass per prompt.

---

## Step 2. Build the weight push anchor and check it holds

### How it was done, in detail

A synthetic decision maker is written as a formula whose latent is the log-odds of one answer
against the other. The bias version changes exactly one term:

```
z = (value of one option - value of the other) / range / tau
z += action        # 0 for the reference agent, 0.6 for the bias agent
```

`action` is added after the valuation, so the agent's view of the options is untouched and only
its tendency to emit one answer moves. That is what makes it a pure push by construction.

For every training prompt the agent's exact probability of each answer is computed, not
sampled. A rank-16 low-rank addition on the attention and feed-forward projections is then
trained so the model's own probability at the answer token matches those numbers, with a
cross-entropy taken over the whole vocabulary so that mass on any third token is penalised.
Three adapters are trained on the same data in the same order with the same seed, one per
agent, so the difference between any two is the planted change and nothing else.

An adapter carries no direction. To compare it with a feature direction, its **displacement**
is measured: run the same prompts under the reference adapter and under the bias adapter, and
take the average difference in the residual stream at layers 48 and 50. Lottery, 7m56s to read
and 11m32s to displace. Ultimatum, part of a 52m27s pass. Code is `cv_bench/anchors/lora.py`,
`pilot_read.py` and `bias_direction.py`.

### The table

| quantity | planted | lottery prompts | ultimatum prompts |
|---|---:|---:|---:|
| bias contrast, mean | +0.600 | **-0.022** | **+0.462** |
| preference contrast, mean | positive | **-0.285** | +0.331 |
| bias displacement, layer 48 | | 3.073 | 6.512 |
| preference displacement, layer 48 | | 2.521 | 5.930 |

### What every row and cell means

**bias contrast** is the average difference in the readout between the bias adapter and the
reference adapter, over the prompts of that task. The planted value is 0.600 by construction.
A recovered value near 0.600 means the adapter carries its planted push on those prompts.

On the **lottery** it reads −0.022. That is indistinguishable from zero, so the planted push
did not survive. On the **ultimatum** it reads +0.462, which is 77 percent of what was planted.

**preference contrast** is the same difference for the adapter with a preference parameter
shifted instead. On the lottery it comes out at −0.285, the wrong sign entirely. On the
ultimatum it is +0.331 and the right sign.

**bias displacement** and **preference displacement** are the lengths of the average change
each adapter makes to the residual stream. They are how the adapters enter the geometry in
Step 3. Two changes of genuinely different kinds should move the state differently. On the
ultimatum they differ, 6.512 against 5.930. On the lottery they sit close together, 3.073
against 2.521, which is the geometric echo of the contrast failure above.

### Why the lottery failure is a transfer failure rather than a measurement failure

Three checks separate those two explanations. The unmodified model measured this way agrees
with the experiment's own recorded baseline at a correlation of 0.957, so the reading is
sound. The spread of the readout falls from 12.45 to 4.36 under the reference adapter, so the
adapters are plainly acting. What fails is only the planted difference. These adapters were
trained on different prompt wording from the lottery prompts used here.

### What may be claimed in the paper

That an anchor adapter trained on one prompt wording does not carry its planted meaning to
another, measured as a planted push of 0.600 reading back at −0.022. The wording an anchor was
trained on must therefore be reported, and any anchor used on new wording must be revalidated
there rather than assumed.

Comparisons made against the ultimatum pole may be quoted. Comparisons made against the
lottery pole should be described as unavailable rather than as null results.

---

## Step 3. Place the SAE directions against both poles

### How it was done, in detail

Every feature in the dictionary has a direction, which is its column in the decoder matrix,
itself 8,192 numbers. A steering vector built from several features is the sum of each
feature's column multiplied by its coefficient. Three kinds of direction were built: the
features named in the paper taken singly, the ten-feature combinations the steering experiment
fitted numerically, and its sparse reconstruction of the raw readout direction.

Each was compared with each pole by cosine, the dot product divided by the product of the
lengths. This step needs no model and no GPU. It is arithmetic on the dictionary file.

**The null.** A cosine has no meaning without knowing what an ordinary feature scores. So
2,000 live features were drawn at random and put through the identical comparison. The 95th
percentile is the score only one random feature in twenty beats and the 99th is the score only
one in a hundred beats. Code is `cv_bench/anchors/sae_geometry.py`.

### The tables

Lottery poles.

| direction | choice part | presentation part | weight push |
|---|---:|---:|---:|
| **random feature, 95th percentile** | 0.033 | 0.027 | 0.049 |
| **random feature, 99th percentile** | 0.056 | 0.048 | 0.078 |
| feature 184 | **-0.001** | **+0.016** | **-0.005** |
| feature 4237 | **+0.004** | **+0.000** | **+0.004** |
| feature 31935 | **+0.004** | **+0.004** | **+0.017** |
| fitted ten-feature, combined target, seed 31 | **+0.067** | -0.006 | +0.031 |
| fitted ten-feature, combined target, seed 73 | **+0.075** | -0.003 | -0.013 |
| fitted ten-feature, second target, seed 31 | **+0.091** | +0.002 | -0.013 |
| fitted ten-feature, second target, seed 73 | **+0.096** | +0.004 | -0.004 |
| sparse reconstruction of the raw readout | **+0.269** | +0.037 | -0.008 |

Ultimatum poles.

| direction | choice part | presentation part | weight push |
|---|---:|---:|---:|
| **random feature, 95th percentile** | 0.028 | 0.026 | 0.077 |
| **random feature, 99th percentile** | 0.038 | 0.039 | 0.126 |
| feature 184 | +0.022 | -0.020 | -0.005 |
| feature 4237 | -0.004 | +0.007 | +0.016 |
| feature 31935 | **+0.013** | **+0.010** | **-0.044** |
| fitted ten-feature, combined target, seed 31 | -0.049 | -0.013 | **+0.184** |
| fitted ten-feature, combined target, seed 73 | -0.049 | -0.009 | **+0.215** |
| fitted ten-feature, second target, seed 31 | -0.062 | -0.027 | **+0.226** |
| fitted ten-feature, second target, seed 73 | -0.064 | -0.029 | **+0.220** |
| sparse reconstruction of the raw readout | -0.133 | -0.002 | +0.091 |

### What every column means

**choice part** is the cosine with `g1 + g2` from Step 1, the half of the readout direction
that survives swapping the options. Scoring high here means pointing along the direction that
moves which option is preferred.

**presentation part** is the cosine with `g1 - g2`, the half that reverses with the layout.
Scoring high here means pointing along the direction that moves which token is emitted.

**weight push** is the cosine with the bias adapter's displacement from Step 2. Scoring high
here means resembling a change that pushes one answer and does nothing else.

**The first two rows of each table are the reference levels**, not results. Note that each
column has its own level, because the poles have different geometry. A score of 0.05 is above
the one-in-twenty level for the choice part and below it for the weight push on the ultimatum.

### What every row means

**feature 184** is labelled "willing to take risks or make sacrifices for a goal" and
**feature 4237** "executing potentially risky operations that require caution". These are the
two the paper steers with on the lottery. **Feature 31935**, "altruistic and selfless behavior
or intentions", is the one it steers with on the ultimatum. All three were chosen by reading
the labels.

**The fitted ten-feature rows** are combinations found numerically rather than by label, two
optimisation seeds by two target agents. They are included because a fitted combination and a
hand-picked feature are different objects.

**The sparse reconstruction row** is the ten-feature approximation of the raw readout
direction, included because the experiment reported it leaving 96 percent unaccounted for
without being able to say why.

### What the cells say

**The three features the paper steers with sit inside the one-in-twenty level everywhere.**
Every cell in those three rows, across both tables and all three poles, is below the level a
randomly drawn feature reaches. This includes feature 31935 measured against the anchor built
from its own game, which removes the objection that it was judged on the wrong task.

**The fitted combinations do carry structure, and it differs by task.** On the lottery they
reach 0.067 to 0.096 against the choice part, above the one-in-a-hundred level of 0.056, and
sit at the level everywhere else. On the ultimatum they instead reach 0.184 to 0.226 against
the weight push, above its one-in-a-hundred level of 0.126.

**The reconstruction row explains the 96 percent.** It reaches 0.269 against the choice part
and only 0.037 against the presentation part. Since the raw readout direction is mostly the
presentation part, at 37.682 against 9.128, the reconstruction fails because the component it
is mostly trying to match is not representable in the dictionary, not because the dictionary is
generally poor here.

### One column that is omitted from the tables and should not be

A fourth pole exists, the displacement of the **preference** adapter. Against it the fitted
combinations score −0.336 to −0.377 on the lottery, where the one-in-twenty level is 0.142. So
they point strongly **away** from the planted preference change. On the ultimatum that column
reads +0.187 to +0.248 while the weight push column reads +0.184 to +0.226, so those two poles
do not separate on that task and neither can be read alone there.

### What may be claimed in the paper

That the three features selected by label semantics are, on this model and this dictionary,
indistinguishable from randomly drawn dictionary features with respect to the direction that
drives the answer, the direction that drives the token, and a planted answer push. Selecting a
steering direction by reading its label produced directions with no measurable relationship to
any of them.

That fitting a combination numerically does find structure, and what it finds depends on the
task: the answer direction on the lottery and a constant push on the ultimatum. The second of
those is a positive identification of a mechanism rather than a failure to find one.

That a sparse dictionary's failure to reconstruct a readout direction should be reported
against the decomposed halves, since it may reflect the dictionary lacking a token-identity
component rather than lacking the behaviourally relevant one.

Every one of these is a claim about geometry. None of them is a claim about what the
directions do when used, which is Step 4 and is not settled by cosines.

---

## Step 4. Measure what the steering does, not only where it points

### How it was done, in detail

For each condition the change in the readout is regressed on its unsteered value:

```
(z_steered - z_unsteered) = slope * z_unsteered + intercept
```

A slope of zero means something was added without touching how the model responds to the
payoff. A slope of minus one means that response was removed entirely. What survives, `1 +
slope`, is the share of the payoff signal the measurement still has to work with.

On the lottery this reads the experiment's own saved per-prompt readouts, with the edit applied
at **every position** at a per-position strength of 16. On the ultimatum it is newly generated,
with the edit applied at the **last position only**, in units of the median residual stream
norm at layer 50, measured at 21.12, over a ladder of six strengths.

### The lottery table

| condition | signal retained | correlation |
|---|---:|---:|
| readout gradient | **0.062** | -0.999 |
| SAE ten-feature, both seeds | **0.092 to 0.096** | -1.000 |
| dense vector, both seeds | **0.129 to 0.143** | -0.99 |
| preference adapter | **0.156** | -0.987 |
| **random directions, same size** | **0.505 to 0.605** | -0.95 to -0.97 |

**signal retained** is `1 + slope`. Read it as the fraction of the model's sensitivity to the
payoff that is still there after the intervention. **Correlation** is how closely the points
follow the fitted line, where minus one means every point lies exactly on it.

The unsteered spread is 9.23 and after ten-feature steering it is 0.92, so the model has almost
stopped distinguishing a good gamble from a bad one. The correlations near minus one mean this
is an almost exact linear flattening rather than a tendency.

The **random row is the important one**. Random directions of the same size retain three to six
times more of the signal than the directions under test. A comparison in which the control
preserves the measured quantity better than the treatment is not measuring the treatment.

The dose ladder identifies the cause. The same gradient direction retains 0.611 at strength 1,
0.215 at strength 4 and 0.062 at strength 16, and strength 16 is where every comparison in the
experiment was made.

### The ultimatum table

| direction | strength | shift in mean readout | signal retained |
|---|---:|---:|---:|
| feature 31935 | 0.20 | +0.408 | 1.032 |
| feature 31935 | 0.80 | **+1.814** | **1.174** |
| readout gradient | 0.20 | +10.028 | 3.209 |
| readout gradient | 0.80 | -1.381 | **3.574** |
| random live feature | 0.20 | -0.349 | 0.974 |
| random live feature | 0.80 | +0.154 | **0.977** |

**strength** is in multiples of the typical size of the model's internal state at that layer,
so 0.80 means adding a vector 80 percent as long as the state itself. **shift in mean readout**
is how far the average log-odds moved. **signal retained** is as above, and here it is mostly
**above** one, meaning the model responded more sharply rather than less.

Feature 31935 moved the answer by 1.814 while changing the shape of the response by 17 percent.
That is the profile of a push toward one answer rather than a change in what the responder
considers fair. The readout gradient, a pure push by construction, did the same thing more
strongly, raising the spread from 7.86 to 28.21. A random feature did nothing at either
strength, which is the control behaving correctly.

### Why the two tables look nothing alike

The per-position strength is nearly identical, 16 on the lottery against 0.80 times 21.12 which
is 16.9 on the ultimatum. What differs is that the lottery applies the edit at every position
and the ultimatum at one. So the flattening is a property of the all-position regime rather
than of magnitude, and results from the two arrangements must never be pooled.

### What may be claimed in the paper

That at the strength used throughout the lottery conditions, every intervention including the
anchors retains under 0.16 of the model's responsiveness to the payoff, while random directions
of the same size retain 0.505 to 0.605. Any null result obtained in that regime is about the
regime and not about the dictionary.

That interventions should be compared at a **matched behavioural effect** rather than at a
matched vector length. On this project's own measurements the strengths needed to produce an
equal behavioural change differ across directions by about a factor of 150.

That where an edit is applied changes its character and not merely its size, evidenced by
comparable per-position strengths producing flattening in one arrangement and sharpening in the
other.

---

## What this establishes

- On a letter-answer format the readout direction is about four fifths token identity. The same
  computation on word answers gives the reverse balance. This is a property of the answer
  format rather than of the model.
- The three features named in the paper sit inside a random-feature null against every pole on
  both tasks.
- Fitted feature combinations align with the choice direction on the lottery and with the
  planted push on the ultimatum, both above the one-in-a-hundred level.
- At the strength used throughout the lottery conditions, every intervention retains under 0.16
  of the model's response to the payoff and random directions retain three to six times more.
- An anchor adapter trained on one wording does not carry its planted contrast to another.

## What this does not establish

- **What the SAE directions do**, as opposed to where they point, on the lottery. Every
  placement there is a cosine, and geometry is not the test.
- **That feature 31935 is an answer push**, as opposed to consistent with being one. The
  ultimatum run saved per-strength summaries rather than per-trial readouts, so the formal
  attribution could not be computed. Fixing it is a rerun of the same 52 minutes.
- **That the dictionary lacks preference capacity.** The lottery null is equally consistent
  with the strength having removed the payoff response before any preference could appear.
- **A usable weight push comparison on the lottery.** Those columns rest on a pole whose
  planted meaning did not survive the change of wording.

## What would come next

1. Rerun the ultimatum steering keeping per-trial readouts, so the attribution can be computed.
   52 minutes.
2. Retrain the anchors on the lottery prompts so a trustworthy push pole exists there. Two
   hours.
3. Repeat the lottery placement at strengths 1 and 4, where the payoff response still exists.
4. Scale every direction to a matched behavioural effect before comparing, rather than to a
   matched vector length.
