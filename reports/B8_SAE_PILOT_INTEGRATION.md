# Running the anchors on SAE steering: what was done and what was found

A point by point account. Each step says what was run, on what, and what came out. The
explained-from-scratch version, which defines every term, is `B8_SAE_ANCHORS_README.md`.
Every value is registered in `MANIFEST_B.csv` under `B8.*`.

Model: Llama-3.3-70B-Instruct, loaded locally. Dictionary:
`Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, the public checkpoint pinned at revision
`128ee921`, 65,536 features of which 3,632 are dead. No hosted service is contacted at any
point.

Two tasks are covered. The **lottery** uses 432 prompts, 108 economic scenarios in gain, loss
and mixed frames, each in two answer orders and two wordings, answered with the bare letter
**A** or **B**. The **ultimatum responder** uses 120 prompts answered with the words
**Accept** or **Reject**.

---

## Step 1. Build the readout gradient anchor

**What was run.** The gradient of the answer log-odds with respect to the residual stream at
the final prompt token, at layers 48 and 50, averaged over prompts. Computed **separately for
each option order**, then combined: their sum is the part independent of the labelling, their
difference is the part that flips with it. Catch trials excluded. Lottery, 168 prompts per
order, 11m16s. Ultimatum, 30 prompts per order, 5m34s.

**What was found.**

| task | answer tokens | cosine between the orders | sum length | difference length | ratio |
|---|---|---:|---:|---:|---:|
| lottery, layer 48 | A / B | **-0.889** | 9.128 | 37.682 | **0.24** |
| lottery, layer 50 | A / B | -0.893 | 8.416 | 35.383 | 0.24 |
| ultimatum, layer 48 | Accept / Reject | **+0.953** | 18.421 | 2.869 | **6.42** |
| ultimatum, layer 50 | Accept / Reject | +0.956 | 17.271 | 2.614 | 6.61 |

On the lottery the two orders are 89 percent antisymmetric and very nearly cancel. The cause
is the answer format: which letter means "take the gamble" swaps with the order, so the
quantity being differentiated flips sign. On the ultimatum the answer is a word, which does
not swap, and the two orders agree.

**Consequence.** On a letter-answer format the readout direction is about four parts in five a
direction that pushes toward emitting one character, independently of what it stands for.
Any cosine measured against an undecomposed version of it is mostly measuring alignment with
letter identity. Within-order coherence is 0.851 and 0.844 at layer 48, so each half is a
well determined direction rather than an average of noise.

---

## Step 2. Build the bias anchor and check it holds

**What was run.** Three adapters trained to imitate agents whose rules are known: a reference,
one with a preference parameter shifted, and one whose only change is a constant push toward
one answer. Read on the task's prompts to recover the contrast, then run again capturing the
residual stream at layers 48 and 50 so the adapter's mean displacement can be taken. That
displacement is the pole, since trained weights carry no direction of their own. Lottery,
7m56s and 11m32s. Ultimatum, part of a 52m27s pass.

**What was found.**

| quantity | planted | lottery prompts | ultimatum prompts |
|---|---:|---:|---:|
| bias contrast | +0.600 | **-0.022** | **+0.462** |
| preference contrast | positive | **-0.285**, wrong sign | +0.331 |
| bias displacement, layer 48 | | 3.073 | 6.512 |
| preference displacement, layer 48 | | 2.521 | 5.930 |

**The lottery pole does not hold.** The adapters were trained on different wording. Reading
them on these prompts, a constant push worth 0.600 comes out indistinguishable from zero. The
reading itself is sound, since the unmodified model measured this way agrees with the
experiment's own baseline at a correlation of 0.957, and the adapters are plainly active,
since the spread of the log-odds falls from 12.45 to 4.36. What fails is the transfer of the
planted contrast. The displacement norms say the same thing: 3.073 against 2.521 for two
changes that are supposed to differ in kind.

**The ultimatum pole holds.** It recovers 77 percent of the planted push, and the two
displacements separate more cleanly at 6.512 against 5.930. Comparisons against this pole
carry weight; comparisons against the lottery one do not.

---

## Step 3. Place the SAE directions against both poles

**What was run.** Each direction built from the decoder as the sum of coefficient times
feature column, then compared by cosine with the answer part, the letter part and the bias
displacement. Three kinds of direction: the features named in the paper, taken singly; the
ten-feature combinations fitted by the steering experiment; and its sparse reconstruction of
the raw readout direction. The null is 2,000 randomly drawn live features through the
identical construction. CPU only.

**What was found, lottery poles.**

| direction | answer part | letter part | bias anchor |
|---|---:|---:|---:|
| **random feature, 95th percentile** | 0.033 | 0.027 | 0.049 |
| **random feature, 99th percentile** | 0.056 | 0.048 | 0.078 |
| feature 184 | **-0.001** | **+0.016** | **-0.005** |
| feature 4237 | **+0.004** | **+0.000** | **+0.004** |
| feature 31935 | **+0.004** | **+0.004** | **+0.017** |
| fitted ten-feature, combined, seed 31 | **+0.067** | -0.006 | +0.031 |
| fitted ten-feature, combined, seed 73 | **+0.075** | -0.003 | -0.013 |
| fitted ten-feature, second target, seed 31 | **+0.091** | +0.002 | -0.013 |
| fitted ten-feature, second target, seed 73 | **+0.096** | +0.004 | -0.004 |
| sparse fit of the raw readout | **+0.269** | +0.037 | -0.008 |

**What was found, ultimatum poles.**

| direction | answer part | letter part | bias anchor |
|---|---:|---:|---:|
| **random feature, 95th percentile** | 0.028 | 0.026 | 0.077 |
| **random feature, 99th percentile** | 0.038 | 0.039 | 0.126 |
| feature 184 | +0.022 | -0.020 | -0.005 |
| feature 4237 | -0.004 | +0.007 | +0.016 |
| feature 31935 | **+0.013** | **+0.010** | **-0.044** |
| fitted ten-feature, combined, seed 31 | -0.049 | -0.013 | **+0.184** |
| fitted ten-feature, combined, seed 73 | -0.049 | -0.009 | **+0.215** |
| fitted ten-feature, second target, seed 31 | -0.062 | -0.027 | **+0.226** |
| fitted ten-feature, second target, seed 73 | -0.064 | -0.029 | **+0.220** |
| sparse fit of the raw readout | -0.133 | -0.002 | +0.091 |

**Three results.**

**The features named in the paper are indistinguishable from random ones.** Features 184, 4237
and 31935 sit inside the 95th percentile of the null against every pole on both tasks,
including feature 31935 measured against the anchor built from its own game. Selecting a
direction by reading its label produced directions with no measurable relationship to the
direction that drives the answer, the direction that drives the letter, or a planted bias.

**The fitted combinations align with the answer part on the lottery**, at 0.067 to 0.096,
above the 99th percentile, and with nothing else there.

**On the ultimatum they align with the planted bias**, at 0.184 to 0.226 against a
99th-percentile null of 0.126. This is the only above-null alignment with a bias pole in the
whole exercise. Vectors fitted on the lottery to imitate a decision agent point, on the social
task, at the direction of a constant push toward one answer. It is a positive attribution
rather than a failure to be preference-like, and it is the reason the bias pole was worth
building.

**A fourth result falls out.** The sparse reconstruction of the raw readout direction was
reported as leaving a relative residual of 0.961, a poor approximation. The decomposition
explains it: the raw direction is mostly the letter part, and the dictionary represents the
answer part at 0.269 while barely reaching the null on the letter part at 0.037. The fit
fails because the component it is mostly trying to match is not in the dictionary.

---

## Step 4. Measure what the steering does, not only where it points

**What was run.** For each condition, the change in answer log-odds is regressed on the
unsteered value. A slope of zero means something was added without touching how the model
responds to the payoff. A slope of minus one means that response was removed. What survives,
one plus the slope, is the share of the signal the measurement still has. On the lottery this
reads the saved conditions, edits applied at **every position** at a per-position strength of
16. On the ultimatum it is newly generated, edits applied at the **last position only**, in
units of the median residual stream norm of 21.12, over a ladder of six strengths.

**Lottery.**

| condition | signal retained | correlation |
|---|---:|---:|
| readout gradient | **0.062** | -0.999 |
| SAE ten-feature, both seeds | **0.092 to 0.096** | -1.000 |
| dense vector, both seeds | **0.129 to 0.143** | -0.99 |
| preference adapter | **0.156** | -0.987 |
| **random directions, same size** | **0.505 to 0.605** | -0.95 to -0.97 |

The unsteered spread is 9.23; after ten-feature steering it is 0.92. The correlations near
minus one mean each intervention is close to an exact linear flattening toward a constant.
The directions under test destroy three to six times more signal than random ones of the same
size. The dose ladder confirms the cause: the same gradient retains 0.611, 0.215 and 0.062 at
strengths 1, 4 and 16, and strength 16 is where every comparison was made.

**Ultimatum.**

| direction | strength | shift in mean log-odds | signal retained |
|---|---:|---:|---:|
| feature 31935 | 0.20 | +0.408 | 1.032 |
| feature 31935 | 0.80 | **+1.814** | **1.174** |
| readout gradient | 0.20 | +10.028 | 3.209 |
| readout gradient | 0.80 | -1.381 | **3.574** |
| random live feature | 0.20 | -0.349 | 0.974 |
| random live feature | 0.80 | +0.154 | **0.977** |

Nothing flattens here. Retention above one means the model responded more sharply rather than
less. Feature 31935 moves the answer by 1.814 while changing the shape of the response by 17
percent, which is the profile of a push toward one answer rather than a change in what the
responder considers fair. The readout gradient, a pure push by construction, does the same far
more violently, raising the spread from 7.86 to 28.21. A random feature does nothing at any
strength.

**The two tasks differ because of where the edit lands, not how large it is.** Per-position
strength is comparable, 16 against 0.80 times 21.12 which is 16.9. The lottery applies it at
every position and the ultimatum at one. The flattening is a property of the all-position
regime, and results from the two regimes must not be pooled.

---

## What this establishes

- On a letter-answer format the readout direction is about four fifths letter identity. The
  same computation on word answers gives +0.953. This is a property of the answer format.
- The three features named in the paper sit inside a random-feature null against every pole
  on both tasks.
- Fitted feature combinations align with the answer direction on the lottery and with the
  planted bias on the ultimatum, both above the 99th percentile of the null.
- At the strength used throughout the lottery conditions, every intervention retains under
  0.16 of the model's response to the payoff, and random directions of the same size retain
  three to six times more.
- A bias anchor trained on one wording does not carry its planted contrast to another.

## What this does not establish

- **What the SAE directions do**, as opposed to where they point, on the lottery. Every
  placement there is a cosine, and geometry is not the test.
- **That feature 31935 is an answer-push**, as opposed to consistent with being one. The
  ultimatum run saved per-dose summaries rather than per-trial log-odds, so the five-family
  attribution cannot be computed from it. Fixing this is a re-run of the same 52 minutes
  keeping the per-trial values.
- **That the dictionary lacks preference capacity.** The lottery null result is equally
  consistent with the dose having removed the payoff response before any preference could
  show.
- **A usable bias comparison on the lottery.** Those columns rest on a pole whose planted
  meaning does not survive the change of wording.

## What would come next

1. Re-run the ultimatum steering keeping per-trial log-odds, so the attribution can be
   computed. 52 minutes.
2. Retrain the anchors on the lottery prompts so a bias pole exists in that wording. Two
   hours.
3. Repeat the lottery placement at strengths 1 and 4, where the payoff response still exists.
4. Scale every direction to produce the same behavioural shift before comparing, rather than
   the same vector length. The strengths that achieve a matched shift differ across
   directions by about a factor of 150.
