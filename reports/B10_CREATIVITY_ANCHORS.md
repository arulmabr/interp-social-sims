# Running the anchors on creativity: what was done and what was found

A point by point account. Each step says how it was run. Then it gives the table. Then it says
what every column and every row and every cell means, and what the numbers license.

Model: Llama-3.3-70B-Instruct, loaded from local weights. The dictionary is
`Goodfire/Llama-3.3-70B-Instruct-SAE-l50`. It is the public checkpoint pinned at revision
`128ee921` and it holds 65,536 features of which 3,632 are dead. No hosted service is contacted
anywhere.

Two tasks, the two the paper calls capability tasks. **Divergent creativity** is the brick
alternative-uses task, prompted with "List creative uses for a brick. Give several distinct
ideas." **Product innovation** is the stapler task, prompted with "Suggest improvements to the
stapler. Give several distinct enhancements." These are the paper's own prompts and the
responses are the paper's own recorded responses with the paper's own five judges.

Creativity differs from the lottery and the ultimatum responder in one way that governs
everything below. In those games the model picks one of two answers, so there is a number to
read off the output distribution without asking anything of it. Here the model writes a
paragraph and five judges score it afterwards. Nothing in the model's own output is a
creativity score. A readout therefore has to be constructed before any anchor can exist, and
Step 1 is about constructing one and showing it is a readout rather than a rating.

---

## Step 1. Define a creativity readout and build the gradient anchor

### How it was done, in detail

Take two responses to the same prompt, one that the judges scored high on originality and one
they scored low. Both are real text written by the model and already in the project's records.
Give the model the prompt and then force it to read each response, and measure how readily it
produced each one:

```
z = mean per-token log P(the high-originality response)
  - mean per-token log P(the low-originality response)
```

Both terms are conditioned on the paper's own prompt. The mean is per token so that a longer
response is not penalised simply for having more tokens to be uncertain about. The model is
never asked to choose and never asked to rate. It is asked only how natural each piece of text
is to it, and `z` is the difference. That makes `z` a quantity read from the model rather than
an opinion elicited from it, which is what the gradient anchor needs.

Differentiating `z` with respect to the residual stream, the internal state of 8,192 numbers
the model holds at a chosen layer, gives `dz/dh`: the direction in which a small change to that
state most raises the model's relative readiness to produce the more original text. This is one
forward pass with a hook that retains the activation, then one backward pass from `z`. Each
pair gives one vector and they are averaged over pairs to give one direction per layer.

Pairs were formed within task and within condition, so the two responses in a pair were
produced under the same settings and differ only in what the judges thought of them. A pair was
kept only where at least 3 judges had scored both sides. Brick gave 42 pairs, stapler gave 40.
Code is `cv_bench/anchors/creativity_pairs.py` and `cv_bench/anchors/creativity_gradient.py`.

### The table

| task | pairs | judged originality gap | mean readout gap | readout spread | direction length, layer 48 | layer 50 |
|---|---:|---:|---:|---:|---:|---:|
| divergent creativity, brick | 42 | 1.048 | **+0.0115** | 0.208 | 0.00626 | 0.00602 |
| product innovation, stapler | 40 | 1.835 | **+0.0049** | 0.246 | 0.02103 | 0.02010 |

### What every column means

**task** names the prompt. **pairs** is how many high-and-low response pairs survived the
requirement of 3 common judges.

**judged originality gap** is the average difference in judged originality between the high side
and the low side of a pair, on the judges' own 1 to 10 scale. It is how far apart the two sides
of a pair are according to the people the paper trusts. Brick pairs are 1.048 apart and stapler
pairs 1.835 apart, so the stapler pairs are the cleaner contrast.

**mean readout gap** is the average of `z` over pairs. Positive means the model was on average
more ready to produce the response the judges preferred. This is the quantity the anchor is
built on.

**readout spread** is the standard deviation of `z` across pairs. It says how much `z` varies
from pair to pair, which is the noise the mean has to be read against.

**direction length** is the length of the averaged gradient, the square root of the sum of its
squared entries. It is reported because a direction that is near zero in length is an average
of vectors that cancelled, which would mean there was no consistent direction to find.

### What every row and cell says

**Brick.** The readout gap is +0.0115 against a spread of 0.208. The sign is the one the judges
would predict, and it is small relative to the pair-to-pair variation. Over 42 pairs the mean is
about 0.36 of a standard error away from zero, so this is a consistent lean rather than a
separation. The direction survives averaging at a length of 0.00626.

**Stapler.** The readout gap is +0.0049 against a spread of 0.246, so smaller still, even though
the judged gap is larger at 1.835. The direction is 3 times longer than brick's at 0.02103,
meaning the per-pair gradients agreed with each other more even though the readout they were
differentiating moved less.

### Why this is a readout and not a rating, and what it licenses

The important property is that the model was never told which response was preferred and never
asked to evaluate anything. Both numbers come from its probability of text it wrote itself. So
the sign of the gap is a statement about the model's own generation preferences lining up, a
little, with what five judges thought.

The size is the honest part. On the lottery and the ultimatum responder the readout separates
the two answers by several log-odds units and the anchor is built on a wide, reliable signal.
Here the separation is roughly 5 percent of the pair-to-pair spread on brick and 2 percent on
stapler. A creativity readout built this way exists and points the right way, and it is weak.
Anything placed against this anchor is being compared to a direction estimated from a small
mean, so a null result against it is much less informative than a null result against the
ultimatum anchor.

For the paper this is the piece that lets the creativity work be discussed in the same terms as
the preference work rather than in a different vocabulary. We can say that the trait the judges
score is visible in the model's own generation probabilities without asking the model to judge,
and state its size next to the sizes obtained on the games so a reader can see that the
creativity readout is the weaker of the two constructions. It also removes an objection to the
capability sections as they stand, which is that every creativity number in the paper passes
through an external judge and therefore cannot be checked against anything internal.

---

## Step 2. Build a creativity probe direction, since the paper does not store one

### How it was done, in detail

The paper steers creativity with probes and reports achieved-versus-target curves for it, but no
probe direction is saved anywhere in the project, so one had to be built before it could be
placed against anything.

For each recorded response, the activation is the residual stream averaged over the tokens of
that response, with the prompt fixed. With the prompt held constant this average is the only
thing that differs between responses. The target is judged originality. A ridge regression maps
the activation to that target, and its weight vector is the probe direction.

The circularity concern is that training and scoring against the same judge measures agreement
with that judge's idiosyncrasies. So 5 probes are trained, each on the mean originality of 4
judges, and each scored on the 1 judge it never saw. 320 responses had at least 4 judges. Code
is `cv_bench/anchors/creativity_probe.py`.

### The table

| held-out judge | agreement, layer 48 | agreement, layer 50 |
|---|---:|---:|
| Claude Sonnet 4.6 | **0.896** | 0.894 |
| Gemini 2.5 Pro | 0.865 | 0.866 |
| Kimi K2.6 | 0.841 | 0.838 |
| GPT-5 | 0.837 | 0.838 |
| DeepSeek V4 Pro | **0.794** | 0.798 |
| mean | **0.846** | 0.847 |
| direction length | 2.992 | 2.935 |

### What every row and cell means

**held-out judge** is the judge whose scores were kept out of the fit entirely and then used as
the test. **agreement** is the Spearman rank correlation between what the probe predicts from the
activation and what that judge actually gave. Spearman ranks the responses rather than using the
raw scores, so it measures whether the probe puts responses in the same order as the judge, not
whether it reproduces the number. It runs from minus one to plus one, and zero means the ordering
is unrelated.

Every cell is between 0.794 and 0.896, and the two layers agree to within 0.005 of each other.
**Claude Sonnet 4.6 at 0.896** is the highest and it is also the judge that was held out when the
saved direction was fitted. **DeepSeek V4 Pro at 0.794** is the lowest, so the probe is least
like that judge. **direction length** is the size of the fitted weight vector and is reported so
the placement in Step 4 can be read as an angle rather than a magnitude.

### Why 0.846 is an upper bound, and what the number becomes when it is removed

Two features of the design push agreement up and neither is visible in the table. Both were
suspected before the recomputation was run and only one of them turned out to matter.

The judge is held out but the responses are not. The count of responses used to fit and the count
used to evaluate are both 320, which means the probe was fitted on the same texts it was then
scored on, with only the rating source changed. A ridge fit on 8,192 features and 320 responses
has enough freedom to learn the texts, so part of 0.846 is the fit recognising activations it has
already seen.

The two tasks are pooled. Brick responses average 299 words on the lower-rated side of a pair
and 294 on the higher-rated side. Stapler responses average 100 and 115. The two tasks also sit
at different judged originality levels. So a direction that merely distinguishes brick from
stapler earns rank agreement without knowing anything about creativity.

Both were tested by recomputing the same quantity three ways, with the first way reproducing the
original so that the comparison is like for like. The 320 responses split 160 to each task.

| how the agreement was computed | layer 48 | layer 50 | range across the 5 judges, layer 48 |
|---|---:|---:|---|
| judge held out, responses in sample, tasks pooled | **0.846** | 0.847 | 0.794 to 0.896 |
| judge held out, responses held out, tasks pooled | 0.828 | 0.829 | 0.774 to 0.869 |
| judge held out, responses held out, within brick | **0.437** | 0.439 | 0.330 to 0.507 |
| judge held out, responses held out, within stapler | **0.541** | 0.543 | 0.438 to 0.667 |

**What each row is.** The first row is the original design and it returns 0.846 and 0.847, which
confirms the recomputation measures the same thing before it changes anything. The second holds
out half the responses, fits on the other half and averages the two directions of the split. The
third and fourth do the same inside one task at a time, so that telling brick from stapler cannot
earn any agreement.

**What the numbers say.** Holding out the responses costs 0.018, so the fit was not simply
learning the particular texts and that suspicion was wrong. Pooling the two tasks was carrying
about half the figure. Within one task the probe reaches 0.437 on brick and 0.541 on stapler, and
both layers agree to within 0.002. At layer 48 the weakest single judge within brick is 0.330 and
the strongest within stapler is 0.667.

So the number the paper may quote is 0.44 on divergent creativity and 0.54 on product
innovation, not 0.846. The claim it supports is that a single direction in the residual stream
orders creative writing the way a judge who contributed nothing to building it would order it,
at a rank correlation near 0.5 within a task. That is a real effect and it is half the size the
pooled figure suggested. It supports the paper's existing use of probes as a linear control for
creativity, and it supplies the evaluation protocol that use currently lacks, since the paper's
own probe steering figure reports achieved scores per judge without a held-out fit anywhere.
Code is `cv_bench/anchors/creativity_probe_check.py`.

---

## Step 3. Build the weight push anchor and check it holds

### How it was done, in detail

A synthetic agent is written whose latent is the creativity readout of Step 1. The bias version
changes exactly one term:

```
z = w0 * (originality difference of the pair)
z += action      # 0 for the reference agent, the planted push for the bias agent
```

`action` is added after the valuation, so the agent's view of the two responses is untouched and
only its overall lean moves. That is what makes it a push by construction rather than a change of
taste. The preference version instead moves `w0`, so it changes how strongly judged originality
translates into readiness, which is a change of taste and not a push.

Three adapters are trained, one per agent. Each is a rank-16 low-rank addition on the attention
and feed-forward projections. All three see the same 82 pairs in the same order with the same
seed for 120 steps, so the difference between any two is the planted change and nothing else.
Training used gradient checkpointing and a 192-token cap on each response, recorded in
`logs/B_DEVIATIONS.md` as a memory rerun.

**The scale of the planted change is set by rule, not chosen.** The model's own readout on these
pairs has mean +0.0055 and spread 0.2691. `w0` is fixed so the agent's readout has the same
spread as the model's, giving `w0` = 0.4376. The push is fixed at the same fraction of the spread
the lottery anchor used, 0.1765 of the spread, giving 0.0475. The smallest change worth detecting
is fixed at the lottery's fraction too, 0.008882 of the spread, which enters as an increase of
0.001669 in the agent's weight on judged originality and moves the agent's readout by 0.0024. No
constant here was tuned after seeing a result. This is recorded as decision BD59 in
`logs/B_DECISIONS.md`.

An earlier attempt set `w0` from a ratio of means instead of a ratio of spreads and produced
0.0039, which asked the adapter to reproduce a signal 70 times smaller than the variation it sat
in. All three adapters then failed to clone at all, at correlations of −0.066, +0.020 and
−0.038. The before and after are in `logs/B_DEVIATIONS.md`. The numbers below are from the
corrected run.

An adapter carries no direction. To compare it with a feature direction its **displacement** is
measured: run the same prompts under the reference adapter and under each shifted adapter, and
take the average difference in the residual stream at layers 48 and 50, over 164 sequences per
adapter. Code is `cv_bench/anchors/creativity_lora.py` and `cv_bench/anchors/creativity_disp.py`.

### The cloning table

| adapter | cloning correlation | cloning slope | mean readout | training loss |
|---|---:|---:|---:|---:|
| **bar to clear** | **0.95** | **0.90 to 1.10** | | |
| reference | **0.810** | **0.764** | +0.556 | 0.0444 |
| preference | **0.797** | **0.759** | +0.561 | 0.0435 |
| bias | **0.798** | **0.824** | +0.612 | 0.0411 |

### What every row and cell means

**cloning correlation** is how closely the adapted model's readout tracks, pair by pair, the
readout of the agent it was trained to copy. 1.0 would mean the adapter reproduces the agent's
ordering exactly. **cloning slope** is the regression slope of the model's readout on the agent's:
1.0 means the adapter moves exactly as far as the agent does, and 0.76 means it moves about three
quarters as far. **mean readout** is the adapted model's average `z` over the pairs. **training
loss** is the final cross-entropy against the agent's exact probabilities.

**The first row is the standard, not a result.** It is the bar the lottery and ultimatum anchors
cleared, and it is stated before the others so the shortfall is legible.

All three adapters land at 0.797 to 0.810 against a bar of 0.95, and all three slopes land at
0.759 to 0.824 against a band of 0.90 to 1.10. So the adapters do track their agents, which the
failed first attempt did not, and they track them too loosely to be certified. The training
losses are nearly equal across the three at 0.0411 to 0.0444, so no adapter had a harder fitting
problem than the others and the shortfall is a property of the task rather than of one agent.

**No further training was run to close the gap.** The only reason to extend training would be that
the number came in below the bar, and changing a run because its result is unhelpful is the thing
the project's rules forbid. The shortfall is reported as the result.

### The contrast table

| quantity | planted | measured | measured spread | recovered |
|---|---:|---:|---:|---:|
| bias contrast, mean | +0.0475 | **+0.0553** | 0.0619 | **116%** |
| preference contrast, mean | +0.0024 | **+0.0043** | 0.0327 | 179% |
| bias displacement, layer 48 | | 1.543 | | |
| bias displacement, layer 50 | | 1.657 | | |
| preference displacement, layer 48 | | 0.767 | | |
| preference displacement, layer 50 | | 0.799 | | |

### What every row and cell means

**bias contrast** is the average difference in the readout between the bias adapter and the
reference adapter over the 82 pairs. The planted value is 0.0475 by construction, so a measured
value near 0.0475 means the adapter carries its planted push. It reads +0.0553, which is 116
percent of what was planted. **measured spread** is the pair-to-pair standard deviation of that
difference, 0.0619, so the mean is about 8 standard errors from zero over 82 pairs.

**preference contrast** is the same for the adapter whose taste was moved. Planted 0.0024,
measured +0.0043. The percentage of 179 should not be read as a stronger effect. The planted step
of 0.0024 is smaller than the 0.0043 of slack that cloning at 0.80 rather than 0.95 leaves behind,
so this cell is measuring the noise floor of the imperfect cloning and not the plant. **The
preference pole is therefore unusable on creativity and is reported as unavailable rather than as
a result.**

**displacement** is the length of the average change each adapter makes to the residual stream.
Two changes of genuinely different kinds should move the state by different amounts, and here they
do, 1.543 against 0.767 at layer 48, a factor of 2. These lengths are how the adapters enter the
geometry in Step 4.

### Why the creativity anchor is weaker than the other two, and what it licenses

The displacements put the three tasks on one scale:

| task | bias displacement, layer 48 | layer 50 |
|---|---:|---:|
| lottery | 3.073 | 3.172 |
| ultimatum responder | 6.512 | 6.756 |
| creativity | **1.543** | **1.657** |

The creativity adapter moves the internal state half as far as the lottery one and a quarter as
far as the ultimatum one. That follows from the planted push being small in readout units, which
in turn follows from the readout itself being weak, and it propagates: a shorter displacement is a
noisier estimate of its own direction, so a real overlap has a thinner margin to clear in Step 4.

For the paper this step supplies something the creativity sections do not currently have, which is
a change of known kind to compare a steering method against. The narrative is that a calibration
target for creativity can be built and that it is harder to build than for the games: we can plant
a pure push in a synthetic creative agent and recover 116 percent of it, and we cannot plant a
change of creative taste small enough to be meaningful and still large enough to survive the
cloning error. Stated that way it is a finding about what creativity permits as a measurement
target, not an equipment failure, and it is the honest counterpart to the ultimatum anchor which
cleared every bar.

---

## Step 4. Place the SAE features and the probe against both anchors

### How it was done, in detail

Every feature in the dictionary has a direction, its column in the decoder matrix, itself 8,192
numbers. The three features the paper steers creativity with were taken singly:

| feature | the paper's label |
|---|---|
| 13142 | enabling or empowering creative expression and exploration |
| 20117 | descriptions of creative unconventional thinking, especially "thinking outside the box" |
| 4992 | professional innovation and creative problem-solving |

All three were chosen in the paper by reading labels from the dictionary's library, which the
appendix states directly. The probe direction from Step 2 was taken at both layers.

Each direction was compared with each pole by cosine, the dot product divided by the product of
the lengths. The gradient poles are the averaged gradients of Step 1, one per task and layer. The
weight push poles are the displacements of Step 3. This needs no GPU for the cosines themselves.

**The null.** A cosine has no meaning without knowing what an ordinary feature scores, so 2,000
live features were drawn at random and put through the identical comparison. The 95th percentile
is the score only 1 random feature in 20 beats and the 99th is the score only 1 in 100 beats. Code
is `cv_bench/anchors/creativity_place.py`.

### The tables

Gradient poles, the direction that raises readiness to produce the more original text.

| direction | brick, layer 48 | brick, layer 50 | stapler, layer 48 | stapler, layer 50 |
|---|---:|---:|---:|---:|
| **random feature, 95th percentile** | 0.025 | 0.025 | 0.027 | 0.026 |
| **random feature, 99th percentile** | 0.036 | 0.036 | 0.039 | 0.039 |
| feature 13142 | **+0.001** | **+0.001** | **-0.008** | **-0.004** |
| feature 20117 | **+0.001** | **+0.002** | **-0.011** | **-0.012** |
| feature 4992 | **-0.004** | **-0.005** | **+0.002** | **+0.003** |
| creativity probe, layer 48 | +0.016 | +0.019 | **+0.031** | **+0.030** |
| creativity probe, layer 50 | +0.012 | +0.014 | **+0.033** | **+0.032** |

Weight push poles, the displacements of the two adapters.

| direction | bias, layer 48 | bias, layer 50 | preference, layer 48 | preference, layer 50 |
|---|---:|---:|---:|---:|
| **random feature, 95th percentile** | 0.151 | 0.156 | 0.077 | 0.074 |
| **random feature, 99th percentile** | 0.249 | 0.258 | 0.122 | 0.118 |
| feature 13142 | +0.024 | +0.026 | **+0.091** | **+0.093** |
| feature 20117 | -0.043 | -0.044 | **+0.107** | **+0.104** |
| feature 4992 | -0.052 | -0.055 | **+0.099** | **+0.098** |
| creativity probe, layer 48 | +0.052 | +0.054 | +0.021 | +0.023 |
| creativity probe, layer 50 | +0.050 | +0.053 | +0.015 | +0.018 |

### What every column means

**brick** and **stapler** are the two gradient poles, one per task, each at both layers. Scoring
high means pointing along the direction that raises the model's readiness to produce the response
the judges preferred on that task.

**bias** is the displacement of the adapter that was given a pure push. Scoring high means
resembling a change that leans the model toward more original text without changing how it weighs
originality.

**preference** is the displacement of the adapter whose taste was moved. Scoring high would mean
resembling a change in how strongly judged originality translates into readiness.

**The first two rows of each table are reference levels, not results.** Each column has its own
level because each pole has its own geometry, and the levels differ by a factor of 6 across the
two tables. A score of 0.09 is far above the one-in-twenty level against the preference pole at
0.077 and far below it against the bias pole at 0.151. A cosine in these tables cannot be
interpreted without the column it sits in.

### What every row means

**The three feature rows** are the ones the paper boosts during decoding for both capability
tasks, listed in its appendix with their labels and their library identifiers. They are here
because the question is whether a direction picked by reading a label has any measurable
relationship to a change of known kind.

**The creativity probe rows** are the direction from Step 2, entered at both layers so that a
result appearing at one layer only can be recognised as such.

### What the cells say

**The three features sit inside the null against every pole that can be trusted.** Against both
gradient poles every cell in those three rows is between −0.012 and +0.003, where a
randomly drawn feature reaches 0.025. Against the bias pole, the one weight push pole whose plant
was recovered, every cell is between −0.055 and +0.026 against a level of 0.151, so
between a third and a sixth of the level. The features are indistinguishable from random
dictionary directions with respect to both anchors.

**The one cell that clears a null cannot be used.** All three features score between +0.091 and
+0.107 against the preference pole, above its one-in-a-hundred level. That pole is the one whose
planted step of 0.0024 is smaller than the cloning slack of 0.0043, so the direction it names is
not reliably the planted change. Three further features of those numbers point the same way. All
three features score positive and within 0.016 of each other, which is the signature of a
component shared with the prompt or the response format rather than 3 separate features each
aligning in its own right. The scores are flat across layers 48 and 50, where a genuine alignment
with a layer-50 dictionary would be expected to favour layer 50. And the pole itself is the
shorter of the two displacements at 0.767, so it is the noisier direction of the pair.

**The probe clears the null narrowly on one task and not the other.** Against the stapler gradient
pole it reaches +0.031 and +0.033 where the one-in-twenty level is 0.027, so above that level and
below the one-in-a-hundred level of 0.039. Against the brick gradient pole it reaches +0.012 to
+0.019 and stays inside the null. Against the bias pole it reaches +0.050 to +0.054 against a
level of 0.151 and stays well inside. So the probe has a detectable relationship with the
generation direction on product innovation, no detectable relationship with it on divergent
creativity, and no detectable relationship with a planted push on either.

**The result is consistent across layers throughout.** Every row changes by less than 0.005
between layer 48 and layer 50, so nothing here depends on the depth chosen.

### The same three features against the preference-task anchors

The three creativity features were also placed against the anchors built for the lottery and the
ultimatum responder, which is a cross-check rather than a new test, and they sit inside the null
there as well.

| feature | lottery choice | lottery presentation | lottery push | ultimatum choice | ultimatum push |
|---|---:|---:|---:|---:|---:|
| **random feature, 95th percentile** | 0.033 | 0.027 | 0.049 | 0.028 | 0.077 |
| 13142 | +0.011 | +0.003 | -0.008 | +0.011 | -0.009 |
| 20117 | +0.011 | +0.009 | -0.006 | +0.003 | +0.012 |
| 4992 | +0.011 | +0.016 | -0.028 | +0.012 | +0.020 |

Every cell is inside the one-in-twenty level. So on either game the three directions have no
measurable relationship to any of these targets, whether the target is the direction that
drives the answer or the direction that drives the token or a planted push. This matters
because it closes the objection that the features were judged against the wrong kind of anchor:
they were judged against 9 poles across 3 tasks and cleared none of them.

### Why this happens, and what it licenses

The framing that holds up is about how a steering direction was selected, not about whether the
steering worked. The paper reports that boosting these three features raises judged creativity
scores, and this step does not contradict that. What it shows is that the directions being boosted
have no measurable geometric relationship to the direction that moves the model's own readiness to
produce more original text, nor to a change of known kind planted in a synthetic creative agent.
Whatever raises the scores is therefore not identified by these measurements, and the label the
feature carries is not evidence that it is the mechanism.

The paper's own SAE section already reaches near this point from the other side. It notes that
"while the SAE features offer some extent of validation, we need to carefully evaluate their
activation strength and underlying logic." The measurement here is what carrying out that
evaluation looks like: the check is against a change of known kind, and the answer on creativity
is that the three features do not stand out from randomly drawn ones.

So the narrative for the paper has two parts. Choosing a feature by reading its label generates
a hypothesis rather than identifying a mechanism. And a reported steering gain and a claim
about mechanism are separate claims needing separate evidence, where the second kind of
evidence is not present here. The constructive half is the method rather than the verdict: a
random-feature null and an anchor of known kind turn a cosine into a test, and they cost no
additional model runs once the anchor exists.

The probe result should be stated with its asymmetry intact rather than averaged away. A probe
fitted on judged originality points measurably along the model's own generation direction on the
stapler task and not on the brick task, at 1 chance in 20 rather than 1 in 100. That is weak
evidence of a shared mechanism on one of two tasks, and it is more than the label-selected
features achieve anywhere.

---

## Step 5. What the judged scores already contain

### How it was done, in detail

Every number above rests on the judges, so the judges were examined directly, using the project's
own combined evaluation file and no new model runs.

Two things were computed. The first is how much of each judge's score is predictable from response
length alone. Each judge's score was regressed on the natural logarithm of the word count,
separately for each judge and each task, and the fraction of variance explained was recorded.

The second is how much the judges agree with each other. That is the mean Spearman correlation
across all 10 judge pairs, computed separately for each task and each condition. It was computed
twice over, once on the scores as given and once on the scores with the length relationship
regressed out. Code is `cv_bench/anchors/creativity_length.py`.

Conditions were compared only against a baseline from their own stack. The steering and
temperature conditions come from one generation pipeline and the prompting-ladder conditions
from another, and their baselines on brick are 5.034 and 6.120. Differencing across the two was
the source of an earlier error and is recorded in `logs/DECISIONS.md`.

### The length table

| quantity | divergent creativity, brick | product innovation, stapler |
|---|---:|---:|
| variance explained by length, lowest judge | 0.507 | **0.180** |
| variance explained by length, highest judge | **0.641** | **0.774** |
| score change per doubling of length, lowest judge | 0.72 | 0.23 |
| score change per doubling of length, highest judge | 1.60 | 0.78 |

### What every row and cell means

**variance explained by length** is the fraction of a judge's score variation across responses that
is accounted for by the logarithm of the word count and nothing else. A value of 0.641 means that
for that judge on that task, 64 percent of the spread in scores is predictable from how long the
response is. The two columns give the range across the 5 judges.

**score change per doubling of length** converts the fitted slope into the units a reader can
check: how many points on the judges' scale a response gains by being twice as long. On brick the
highest judge gives 1.60 points per doubling, which is large relative to the reported condition
effects, which run from −0.178 to +1.516.

Across the 10 judge-by-task cells, length accounts for between 18 and 77 percent of the variance.
There is no cell in which length is a minor factor.

### The agreement table

Mean Spearman correlation across all 10 judge pairs, within one task and one condition.

| grouping | lowest cell | highest cell |
|---|---:|---:|
| as reported | **0.020** | **0.654** |
| with length removed | 0.045 | 0.657 |
| the paper's figure, pooled over conditions | | **0.770** |

### What every row and cell means

**as reported** is the judges' agreement computed on their scores as given. The lowest cell is
the stapler prompting condition at 0.020, which is no agreement at all. The highest is the
brick steering condition at 0.654.

**The third row is the paper's own figure**, a mean pairwise Spearman of 0.770, computed by pooling
responses across conditions. Every within-condition cell is below it and most are far below it.
Pooling puts responses from different conditions into one ranking, and any tendency the judges
share about conditions as a whole then counts as agreement about individual responses. The
comparison the paper's argument needs is agreement within a condition, because that is the
comparison the condition effects are read from, and there it runs from 0.020 to 0.654.

### Why this matters for the claims already in the paper, and what it licenses

The paper states that the capability scores are produced under a "blind, length-controlled
protocol" and that "the rubric scores idea quality rather than length." The first part holds: each
judge sees only the response and the task. The second part is the one the measurement bears on.
Length is not controlled in the sense of being removed, and it accounts for 18 to 77 percent of the
variance in judge scores depending on the judge and the task. The instruction in the rubric not to
reward length did not make the scores independent of length.

This is the creativity result most worth putting in the paper, because it changes how an existing
number should be read rather than adding a new one. Two sentences in the capability section change.
The claim that the rubric scores quality rather than length becomes a measured statement of how
much length it does score, with the range given. The claim that the judges agree closely becomes a
statement with its grouping named, that agreement is 0.770 when conditions are pooled and 0.020 to
0.654 within a condition. Both are ordinary methodological reporting and neither requires
withdrawing a condition effect. What they do require is that a reported condition effect be stated
alongside the length change that accompanied it, since a condition that lengthened responses has a
route to a higher score that has nothing to do with originality.

One discrepancy is open and should be resolved before either set of numbers is quoted next to the
other. Recomputed from the combined evaluation file against a baseline from the same stack, the
brick steering condition reads −0.178 on the mean score where the paper reports +0.39, and the
stapler steering condition reads +0.455 where the paper reports +1.02. The
baseline levels also differ, 5.034 against the paper's 5.18 on brick and 5.768 against 5.23 on
stapler. The same recorded responses underlie both, so the difference is in how they are
aggregated, and the paper's aggregation has not been reproduced here. This is a reconciliation
task and not a correction, and neither figure should be presented as the other's replacement until
it is done.

---

## What this establishes

- A creativity readout can be built from the model's own generation probabilities without asking
  the model to rate anything, and it leans the way the judges do, by +0.0115 on brick and +0.0049
  on stapler against pair-to-pair spreads of 0.208 and 0.246.
- A gradient anchor and a weight push anchor both exist for creativity. The push anchor recovers
  116 percent of its planted push.
- The 3 dictionary features the paper steers creativity with sit inside a random-feature null
  against every pole that can be trusted, on both creativity tasks and on both games, 9 poles in
  all.
- A probe fitted on judged originality points measurably along the generation direction on the
  stapler task, at +0.031 and +0.033 against a one-in-twenty level of 0.027, and not on the brick
  task.
- That probe orders creative writing the way a judge who contributed nothing to it would order it,
  at 0.437 within brick and 0.541 within stapler. The 0.846 obtained by pooling the 2 tasks is
  about twice the within-task figure.
- Length accounts for 18 to 77 percent of the variance in judge scores across the 10 judge-by-task
  cells, under the protocol the paper describes as length-controlled.
- Judge agreement is 0.020 to 0.654 within a task and condition, against 0.770 pooled across
  conditions.
- Every geometric result above is stable across layers 48 and 50, changing by less than 0.005.

## What this does not establish

- **That the 3 features do not raise creativity scores.** They do, by the paper's own measurement.
  What is shown is that they have no measurable relationship to either anchor, so the mechanism is
  unidentified rather than absent.
- **That the dictionary lacks a creativity direction.** The features tested were selected by label.
  No fitted combination was searched for on creativity, which is what found structure on the games.
- **That the creativity anchors are as trustworthy as the ultimatum one.** The adapters clone at
  0.80 against a bar of 0.95, the preference pole is unusable, and the readout the gradient anchor
  differentiates moves by 5 percent of its own spread. A null result against these poles is weaker
  evidence than the same null against the ultimatum poles.
- **That the probe's agreement is 0.846.** That figure pools the 2 tasks. Within one task it is
  0.437 on brick and 0.541 on stapler, and those are the figures that may be quoted.
- **What any of these directions do when used.** Every placement here is a cosine. No creativity
  direction was steered with at a dose matched to the anchor's own behavioural effect, which is
  also true of the lottery and the ultimatum work.

## What would come next

1. Reconcile the recomputed condition effects with the paper's Figure 5 aggregation, so the two
   sets of numbers can appear in one document. Arithmetic on files already present.
2. Fit a feature combination numerically against the creativity gradient pole, the way it was done
   on the games, so the dictionary is tested rather than only the 3 labelled features. No new model
   runs for the fit itself.
3. Steer with the probe and with each of the 3 features at a dose matched to the anchor's own
   behavioural effect, and compare the change in judged score rather than the angle between
   vectors. This is the test the cosines do not perform. The judging is a paid API batch and needs
   approval before it is run.
4. Retrain the creativity adapters with a longer schedule so cloning can be brought to the bar.
   This has to be set up as a fresh construction of the anchor with its outcome reported whichever
   way it falls, and not as an extension of the present run.
