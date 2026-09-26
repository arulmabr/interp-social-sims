# The creativity anchor work, notes to be read aloud

These notes assume no prior knowledge of the project. Every term is explained at the point
where it first matters. Every number quoted here was produced by a script in this repository
and is recorded in the project's register of results alongside the script that made it.

An earlier set of notes covering the same method on the lottery and the ultimatum game states
that no creativity anchor was built and that the creativity arm of the paper is uncalibrated.
That statement was true when it was written and it is no longer true. Both anchors now exist
for creativity. The reasoning that produced the earlier position, and the reasoning that
replaced it, are both given in section 4 below.

---

## 1. The question behind all of this

The paper reports that reaching inside the model while it runs and turning up three of its
internal quantities makes its creative writing better. Five independent judges score the
writing and the scores go up.

That observation has two explanations and they are not the same claim.

The first is that the quantities turned up are the ones the model uses to be creative, so
turning them up engages the machinery of creativity. This is a claim about mechanism and it is
the claim the labels invite, because the three quantities carry labels about creative
expression and unconventional thinking.

The second is that turning up almost anything changes the writing, and the judges then prefer
the result for reasons that have nothing to do with the mechanism named on the label. The
writing might come out longer. It might come out with more list items. The judges might reward
either of those without anyone intending it.

Both explanations predict exactly the observation the paper reports. The purpose of this work
is to build a measurement that can separate them.

---

## 2. Why creativity is harder than the games the method was built for

The same method was first applied to two economic games and it is worth being precise about
why creativity is not a simple third case.

In the lottery game the model is offered a sure amount of money against a gamble and replies
with one letter. In the ultimatum game it is offered a share of a pot and replies with the
word Accept or the word Reject. In both games there are exactly two things the model can say,
so the model's own output already contains a number: how much more willing it was to say the
first thing than the second. Nothing has to be constructed. The number is there.

In the creativity tasks the model is asked to list creative uses for a brick, or to suggest
improvements to a stapler. It writes a paragraph. There is no second option it declined to
write. Nothing in its output is a creativity score. The score comes afterwards, from five
judges reading the paragraph.

This matters because the whole method depends on having a number read from the model itself. A
judge's opinion cannot serve, because the judge is outside the model and the question is what
is happening inside it. So before anything else could be done, a reading had to be built. That
is the first step below and it is the step that had no equivalent in the games.

---

## 3. What is inside the model, in plain terms

When the model processes text it carries forward a running internal state. At any one depth
inside the model this state is a list of 8,192 numbers. The list is called the residual
stream, and depth inside the model is called a layer. Everything in this work is measured at
two depths, layer 48 and layer 50, so that any result appearing at only one depth can be
recognised as depending on the depth chosen rather than on the model.

A direction is a list of 8,192 numbers as well, pointing a particular way through that space.
Turning up an internal quantity means adding some amount of a direction to the state. So every
method discussed here, the technique under test and the anchors used to test it, comes down to
a direction, and comparing two methods comes down to comparing two directions.

---

## 4. The idea of an anchor, and why one was thought impossible here

An anchor is a change whose nature is known in advance because it was built deliberately.

The comparison is the calibration of a thermometer. Before a thermometer is trusted on a
patient it is put in melting ice and then in boiling water. Those two temperatures are known
without needing the thermometer. If the instrument reports them correctly then its reading on
the patient can be believed.

Two anchors are used. The first is a change built to be nothing but a push toward more
original writing, containing no change in how the model values originality. The second is a
change built to move the valuation itself. Neither is built using the technique under test,
because a ruler made of the same material as the thing being measured settles nothing.

**Why this was first thought not to apply to creativity.** The method as originally built
needed a forced choice between two answer words, and creativity has none. One way to supply
one is to show the model two candidate uses for a brick and ask which is the more creative.
That design was written down and then withdrawn without any code being run. The reason is that
it measures a different ability. The paper's claim is about the quality of what the model
writes. Asking it to rank two things handed to it tests whether it can judge, and whether
judging transfers to writing is the open question rather than something available to assume.

**Why it turned out to apply after all.** The mistake in that reasoning was assuming a reading
has to be a choice the model makes. It does not. A reading only has to be a number taken from
the model without asking it anything. The model assigns a probability to every piece of text
it could produce, including text it has already produced, and that probability is available
without a question being put to it. The reading built in section 6 uses exactly that, and once
a reading exists both anchors follow in the ordinary way. The withdrawal was right about the
ranking design and wrong about the general case.

---

## 5. Where every ingredient came from

Nothing here was generated fresh for the purpose except the anchors themselves.

The two prompts are the paper's own prompts. The first asks the model to list creative uses
for a brick and the second asks it to suggest improvements to the stapler. The first is the
task the paper calls divergent creativity and the second is the task it calls product
innovation.

The responses are the paper's own recorded responses, written by the model during the
experiments the paper reports, across all of its conditions.

The judge scores are the paper's own scores from its own five judges. No new judging was done
and no judge was asked anything.

The model is Llama-3.3-70B-Instruct, loaded from weights held locally on this cluster. The
dictionary of internal quantities is a public checkpoint from Goodfire, pinned to one exact
version so that the same numbers come back on a rerun. It holds 65,536 quantities of which
3,632 are empty and carry no direction at all. No outside service is contacted anywhere in
this work.

---

## 6. What the judges do, and the first step of building a reading

### What the judges are

Five separate large language models score each response. They are GPT-5, Claude Sonnet 4.6,
Gemini 2.5 Pro, Kimi K2.6 and DeepSeek V4 Pro. Each one scores a response on four things:
how many relevant ideas it produced, how many different categories those ideas came from, how
unusual the ideas are, and how much each idea was developed. The paper calls those fluency,
flexibility, originality and elaboration. Each judge sees only the response and the task and
is not told which condition produced it.

The work below uses the third of those four, how unusual the ideas are, because that is the
one the anchors are about.

### What was done to build a reading

Take two responses to the same prompt, produced under the same condition, one that the judges
scored high on unusualness and one they scored low. Both are real text the model wrote.

Now give the model the prompt and make it read each of the two responses, and measure how
readily it would have produced each one. Every language model assigns a probability to each
word it might write next, so a whole paragraph has a probability too. Take the average over
the words of the paragraph, so that a longer paragraph is not penalised merely for having more
words to be uncertain about. The reading is the difference between the two averages:

> how readily the model would have produced the response the judges liked,
> minus how readily it would have produced the one they did not.

The model is never asked to choose and never asked to rate. It is asked only how natural each
piece of text is to it. That is what makes this a reading taken from the model rather than an
opinion elicited from it.

A pair was kept only where at least 3 judges had scored both sides. The brick task gave 42
pairs and the stapler task gave 40.

### What was found

On the brick task the reading came out at +0.0115 on average, and the pair to pair variation
was 0.208. On the stapler task the reading came out at +0.0049 with a variation of 0.246.

For context on how far apart the two sides of a pair are according to the judges, the brick
pairs differ by 1.048 points of judged unusualness and the stapler pairs by 1.835 points, on
the judges' own scale which runs from 1 to 10.

### What that means

The sign is the one the judges would predict. The model was on average more ready to produce
the response the judges preferred, on both tasks, without ever being told which one that was.
So the trait five judges score is visible in the model's own writing probabilities.

The size is the honest part and it needs saying plainly. On the brick task the average lean is
about 5 percent of the pair to pair variation. On the stapler task it is about 2 percent. Over
42 pairs the brick average sits about a third of a standard error away from zero. In the two
games the equivalent reading separates the two answers many times more cleanly.

So a creativity reading exists, it points the right way, and it is weak. Everything downstream
inherits that. A result of nothing measured against this reading is much less informative than
the same result measured against the ultimatum game's reading, and these notes say so at each
point rather than once.

For the paper, this is the piece that lets the creativity work be discussed in the same terms
as the rest. At present every creativity number in the paper passes through an outside judge,
so there is nothing internal for any of it to be checked against. This supplies one. The
sentence it supports is that the trait the judges score is present in the model's own
generation probabilities, stated next to how strongly, so that a reader can see the creativity
reading is the weaker of the two constructions.

---

## 7. The second step, building the direction that raises the reading

### What was done

A gradient is the direction of fastest increase. Standing on a hillside, the gradient is the
direction in which the ground rises most steeply.

Here the quantity to be increased is the reading from section 6. So the gradient is the
adjustment to the model's internal state that most efficiently raises the model's readiness to
produce the more original of the two responses rather than the less original one. It is
obtained by one pass forward through the model and one pass backward from the reading.

Each pair gives one such direction and they are averaged over pairs to give one per task per
layer. This is the first of the two anchors and it exists by construction: whatever it points
at, it is the fastest route to moving that particular reading.

### What was found

The averaged direction has a length of 0.00626 at layer 48 on the brick task and 0.02103 at
layer 48 on the stapler task, with layer 50 agreeing closely in both cases.

### What that means

Length is reported here for one reason. If the individual pairs had disagreed with each other
about which way to point then averaging them would have left something close to nothing, and
a near zero length would be the signature of that. The lengths are not near zero, and the
stapler direction is more than 3 times the brick direction, which says the stapler pairs
agreed with each other more about the direction even though the reading they were
differentiating moved less.

---

## 8. The third step, building a probe

### What was done

The paper steers creativity with probes as well as with the dictionary, and reports curves
showing how close the achieved score comes to a target score. But no probe direction is stored
anywhere in the project, so one had to be built before it could be compared with anything.

A probe is the simplest possible reader of the internal state. For each recorded response,
take the internal state averaged over the words of that response, with the prompt held fixed.
Because the prompt is the same for every response, this average is the only thing that
differs between them. Then find the single direction along which that average best predicts
the judged unusualness, using a standard regression with a small penalty that stops it chasing
noise. The direction it lands on is the probe.

The obvious objection is circularity. If the same judge's scores are used to build the probe
and then to test it, all that is measured is agreement with that judge's habits. So five
probes were built. Each was fitted on the average of four judges and then tested against the
fifth judge, whose scores it had never seen. 320 responses had at least four judges.

### What was found

Each probe was scored by how well it puts responses in the same order as the judge it never
saw. The measure used ranks the responses rather than using the raw scores, because the
question is whether the ordering matches and not whether the number matches. It runs from
minus one to plus one, where zero means the ordering is unrelated.

| the judge that was held out | agreement, layer 48 | agreement, layer 50 |
|---|---:|---:|
| Claude Sonnet 4.6 | 0.896 | 0.894 |
| Gemini 2.5 Pro | 0.865 | 0.866 |
| Kimi K2.6 | 0.841 | 0.838 |
| GPT-5 | 0.837 | 0.838 |
| DeepSeek V4 Pro | 0.794 | 0.798 |
| average of the five | 0.846 | 0.847 |

**What each row is.** One row per judge. The row named Claude Sonnet 4.6 means that judge's
scores were removed entirely, the probe was fitted on the average of the other four, and then
the probe's ordering was compared with what Claude Sonnet 4.6 actually gave.

**What each number says.** 0.896 in the first row means the probe put the responses in almost
the same order as a judge that contributed nothing to building it. 0.794 in the last row means
the probe is least like DeepSeek V4 Pro. The two columns differ by at most 0.005 from each
other, so nothing here depends on which of the two depths was used.

### What that means, and the two reasons it is an upper bound

The result is real in one respect. A single straight direction inside the model orders creative
writing much the way an independent judge orders it. That supports the paper's existing use of
probes as a linear control for creativity, and it supplies an evaluation protocol the paper
does not currently have, since its own probe figure reports achieved scores per judge without
any fit that held a judge out.

Two features of how it was computed push the number up, and neither is visible in the table.

The first is that the judge was held out but the responses were not. The number of responses
used to fit and the number used to test are both 320, meaning the probe was fitted on the very
texts it was then scored on, with only the source of the ratings changed. A fit with 8,192
knobs and 320 responses has enough freedom to learn those particular texts, so part of 0.846
is the fit recognising writing it has already seen.

The second is that the two tasks were pooled into one ranking. Brick responses run to about
300 words and stapler responses to about 100, and the two tasks sit at different judged levels.
A direction that does nothing but tell brick from stapler therefore earns ordering agreement
without knowing anything about creativity at all.

A recomputation that holds out responses as well as judges, and repeats the measurement inside
each task separately so the task cannot carry the ordering, is running and its result is not
yet available. Until it returns, 0.846 is the ceiling of what this probe achieves and not its
performance, and the paper should not quote it. What can be said now is narrower and still
worth saying: a single linear direction orders creative writing the way an independent judge
does, under a protocol that at minimum removes the circularity of training and testing on one
judge.

---

## 9. Two terms that appear in every result from here on

### The cosine

A cosine is one number between minus one and plus one that says how closely two directions
agree. Picture two arrows drawn from the same point. Plus one means the arrows lie on top of
each other. Zero means they are at right angles and unrelated. Minus one means one arrow is the
exact reverse of the other.

The cosine ignores length completely. A short arrow and a long arrow pointing the same way both
score plus one. This is deliberate. The question is whether two methods push the model in the
same direction, not whether they push it equally hard.

### The null

A cosine has no meaning on its own. Before knowing whether 0.09 is large, it has to be known
what an ordinary unrelated direction scores against the same target. In 8,192 dimensions two
directions chosen at random are nearly at right angles, so the answer is close to zero, but how
close depends on the target.

So 2,000 of the dictionary's own quantities were drawn at random and put through the identical
comparison. Two levels are then reported. One is the score that only 1 random draw in 20 beats.
The other is the score that only 1 in 100 beats. A result below the first level is a result
that an arbitrary quantity would reach one time in twenty, which is no result.

**These levels differ from target to target and the difference is large.** Against one of the
targets below an ordinary quantity reaches 0.151 and against another it reaches 0.074. A score
of 0.09 is therefore well above the level in the second case and well below it in the first.
No number in the tables below can be read without the column it sits in.

---

## 10. The fourth step, building the pure push

### What was done

The second anchor is a set of extra weights added to the model and trained until the model
behaves like a synthetic agent whose behaviour is known exactly. Such a small trainable addition
is called an adapter.

Three agents were written. The first is a reference with nothing changed. The second has a
constant push toward more original writing added after it has finished valuing the two
responses, so its valuation is untouched and only its overall lean moves. That is what makes it
a pure push. The third instead has its valuation changed, so it weighs judged unusualness more
heavily, which is a change of taste and not a push.

Three adapters were trained on the same 82 pairs in the same order with the same starting point
for the same 120 steps, one per agent. Because everything else is identical, the difference
between any two adapters is the planted change and nothing else.

The reference adapter exists so that the comparison is adapter against adapter. Comparing an
adapter against the untouched model would mix the planted change together with whatever
training does to a model in general.

### How the sizes were fixed, and why that matters

Every size in this step was set by a rule written down before the run and not adjusted
afterwards.

The model's own reading on these pairs has an average of +0.0055 and varies from pair to pair
by 0.2691. The agent's sensitivity was set so that the agent's reading varies by that same
amount, which makes the number 0.4376. The push was set to the same fraction of the variation
that the lottery anchor used, which makes it 0.0475. The smallest change considered worth
detecting was set to the lottery's fraction as well, which enters as an increase of 0.001669 in
the agent's weight on judged unusualness and moves the agent's reading by 0.0024.

### What went wrong the first time, and why it is reported here

The first attempt set the agent's sensitivity from a ratio of averages rather than a ratio of
variations, and produced 0.0039 instead of 0.4376. The consequence is worth stating in plain
terms. The agent was asked to vary by about 0.002 while the model it was being taught to
imitate varies by 0.269, so the signal it was supposed to carry was roughly 70 times smaller
than the noise it was sitting in. There was nothing for the adapter to learn.

All three adapters then failed completely, agreeing with their agents at −0.066, +0.020 and
−0.038, which is no agreement at all. The rule was corrected and the run repeated. Both the
before and the after are recorded in the project's log of deviations, because a rerun is only
allowed for a technical reason and the reason has to be written down.

### What was found about whether the adapters copied their agents

Before an anchor can be used, the adapters have to be shown to have actually learned their
agents. Two things are checked. The first is whether the adapted model orders the pairs the way
its agent does. The second is whether it moves as far as its agent does.

| adapter | does it order the pairs the same way | does it move as far | its average reading |
|---|---:|---:|---:|
| the standard that had to be met | 0.95 | 0.90 to 1.10 | |
| reference | 0.810 | 0.764 | +0.556 |
| preference | 0.797 | 0.759 | +0.561 |
| bias, the pure push | 0.798 | 0.824 | +0.612 |

**What each column is.** The first column asks whether the adapted model ranks the 82 pairs in
the same order as the agent it copied, where 1.0 would be a perfect match. The second column
asks how far it moves for each step the agent moves, where 1.0 means it moves exactly as far
and 0.76 means it moves about three quarters as far. The third column is the adapted model's
average reading over the pairs.

**What the first row is.** It is the standard, not a result. It is the bar that the lottery and
ultimatum adapters cleared and it is put first so that the shortfall below it is legible.

**What the numbers say.** All three adapters land between 0.797 and 0.810 where 0.95 was
required, and all three move between 0.759 and 0.824 as far as they should where between 0.90
and 1.10 was required. So the correction worked and the adapters genuinely track their agents,
which the first attempt did not. And they track them too loosely to be certified. The three
adapters also ended their training at nearly the same error, between 0.0411 and 0.0444, so no
one of them faced a harder problem than the others and the shortfall belongs to the task rather
than to one agent.

**No further training was run to close the gap.** The only reason to train longer would be that
the number came in below the standard, and changing a run because its result is unhelpful is
exactly what the project's rules forbid. The shortfall is the result and it is reported as one.

### What was found about whether the planted changes survived

The anchor is not any single adapter. It is the difference between two of them. So the planted
change is measured by taking the difference in the reading between the shifted adapter and the
reference adapter.

| the planted change | how much was planted | how much came back | how much it varied | share recovered |
|---|---:|---:|---:|---:|
| the pure push | +0.0475 | +0.0553 | 0.0619 | 116 percent |
| the change of taste | +0.0024 | +0.0043 | 0.0327 | 179 percent |

**What each column is.** The second column is what was built in on purpose, so it is the target.
The third is what was measured coming back out. The fourth is how much that measurement varied
from pair to pair, which is the noise the average has to be read against. The fifth is the third
divided by the second.

**The first row is usable.** A push of 0.0475 was planted and 0.0553 came back, which is 116
percent of it. Over 82 pairs, given the pair to pair variation of 0.0619, that average is about
8 times its own uncertainty away from zero. So this anchor works: a change built to be nothing
but a push toward more original writing is recognised as one, at slightly more than full
strength.

**The second row is not usable and the 179 percent must not be read as a stronger effect.** The
planted change of taste is 0.0024. The adapters clone at 0.80 rather than the required 0.95, and
the slack that shortfall leaves behind is about 0.0043. The plant is therefore smaller than the
error of the instrument measuring it, so this row is reading the noise floor and not the plant.
This pole is reported as unavailable rather than as a result.

### Turning an adapter into a direction

An adapter is a change of weights and has no direction, so it cannot be compared with a
direction as it stands. What it does have is an effect on the internal state. So the same
prompts were run under the reference adapter and then under each shifted adapter, and the
average change in the internal state was taken. That change is a direction and its length says
how far the adapter moves the state. This was done over 164 pieces of text per adapter.

The pure push moves the state by 1.543 at layer 48 and 1.657 at layer 50. The change of taste
moves it by 0.767 and 0.799, so the two differ by a factor of about 2, which is what two changes
of genuinely different kinds should do.

### How this anchor compares with the same anchor on the two games

| task | how far the pure push moves the state, layer 48 | layer 50 |
|---|---:|---:|
| lottery | 3.073 | 3.172 |
| ultimatum game | 6.512 | 6.756 |
| creativity | 1.543 | 1.657 |

The creativity adapter moves the model's internal state half as far as the lottery one and a
quarter as far as the ultimatum one. That follows from the push being small in reading units,
which follows in turn from the reading itself being weak, and it carries a consequence. A
shorter movement is a noisier estimate of its own direction, so anything compared against it in
the next section has a thinner margin to clear.

### What that means

For the paper this step supplies something the creativity sections do not have at all, which is
a change of known kind for a steering method to be compared against. The sentence it supports
is not that the equipment worked. It is that creativity permits a calibration target and that
the target is harder to build than for the games: a pure push can be planted in a synthetic
creative agent and 116 percent of it recovered, and a change of creative taste small enough to
be meaningful cannot be planted and still survive the error of the instrument. Put that way it
is a finding about what creativity allows as a measurement target.

---

## 11. The fifth step, placing the three quantities and the probe

### What was done

Every quantity in the dictionary has a direction of its own. The three the paper turns up for
creativity were taken one at a time:

| number | the label the paper gives it |
|---|---|
| 13142 | enabling or empowering creative expression and exploration |
| 20117 | descriptions of creative unconventional thinking, especially thinking outside the box |
| 4992 | professional innovation and creative problem solving |

The paper's appendix states that these three were identified because their labels correspond to
creativity related concepts. That is the point at issue. The probe direction from section 8 was
taken at both depths as well.

Each direction was then compared by cosine with each anchor. There are four anchor targets. Two
are the gradients of section 7, one per task. Two are the adapter movements of section 10, the
pure push and the change of taste.

### What was found against the gradients

The target here is the direction that raises the model's own readiness to produce more original
writing.

| direction | brick, layer 48 | brick, layer 50 | stapler, layer 48 | stapler, layer 50 |
|---|---:|---:|---:|---:|
| **the level 1 random draw in 20 reaches** | 0.025 | 0.025 | 0.027 | 0.026 |
| **the level 1 random draw in 100 reaches** | 0.036 | 0.036 | 0.039 | 0.039 |
| quantity 13142 | +0.001 | +0.001 | −0.008 | −0.004 |
| quantity 20117 | +0.001 | +0.002 | −0.011 | −0.012 |
| quantity 4992 | −0.004 | −0.005 | +0.002 | +0.003 |
| the probe, layer 48 | +0.016 | +0.019 | +0.031 | +0.030 |
| the probe, layer 50 | +0.012 | +0.014 | +0.033 | +0.032 |

### What was found against the adapter movements

| direction | pure push, layer 48 | pure push, layer 50 | change of taste, layer 48 | change of taste, layer 50 |
|---|---:|---:|---:|---:|
| **the level 1 random draw in 20 reaches** | 0.151 | 0.156 | 0.077 | 0.074 |
| **the level 1 random draw in 100 reaches** | 0.249 | 0.258 | 0.122 | 0.118 |
| quantity 13142 | +0.024 | +0.026 | +0.091 | +0.093 |
| quantity 20117 | −0.043 | −0.044 | +0.107 | +0.104 |
| quantity 4992 | −0.052 | −0.055 | +0.099 | +0.098 |
| the probe, layer 48 | +0.052 | +0.054 | +0.021 | +0.023 |
| the probe, layer 50 | +0.050 | +0.053 | +0.015 | +0.018 |

### What every column and row means

**The columns are the four anchor targets, each at both depths.** Scoring high in a brick column
means pointing along the direction that raises readiness to produce more original brick writing.
Scoring high in the pure push column means resembling a change that leans the model toward more
original writing without changing how it weighs originality. Scoring high in the change of taste
column would mean resembling a change in how heavily it weighs originality.

**The first two rows of each table are reference levels and not results.** Each column has its
own levels because each target has its own geometry, and between the two tables they differ by a
factor of 6.

**The three quantity rows** are the ones the paper turns up during writing, for both creativity
tasks. They are here to answer whether a direction chosen by reading a label has any measurable
relationship to a change of known kind.

**The two probe rows** are the direction from section 8, entered at both depths so that a result
appearing at one depth only can be recognised.

### What every number says

**The three quantities are inside the level a random draw reaches, against every target that can
be trusted.** Against both gradients every one of their twelve numbers falls between −0.012 and
+0.003 where a random draw reaches 0.025. Against the pure push, which is the one adapter target
whose plant came back, every one falls between −0.055 and +0.026 where a random draw reaches
0.151, so between a third and a sixth of that level. With respect to both anchors these three
directions cannot be told apart from arbitrary ones.

**The one place they do clear a level cannot be used, for four separate reasons.** All three
score between +0.091 and +0.107 against the change of taste, above the level that only 1 draw in
100 reaches. First, that is the target whose planted change of 0.0024 is smaller than the
instrument's error of 0.0043, so the direction it names is not reliably the change that was
planted. Second, all three land within 0.016 of each other, which is the signature of a
component they share with the prompt or with the shape of the responses rather than three
separate quantities each aligning in its own right. Third, the scores are flat between the two
depths, where a genuine alignment with a dictionary built at layer 50 would be expected to
favour layer 50. Fourth, that target is the shorter of the two adapter movements at 0.767, so it
is the noisier direction of the pair.

**The probe clears the level narrowly on one task and not the other.** Against the stapler
gradient it reaches +0.031 and +0.033 where 1 draw in 20 reaches 0.027 and 1 in 100 reaches
0.039, so it is above the first level and below the second. Against the brick gradient it
reaches between +0.012 and +0.019 and stays inside the level. Against the pure push it reaches
between +0.050 and +0.054 against a level of 0.151 and stays well inside it. So the probe has a
detectable relationship with the model's own generation direction on product innovation, none on
divergent creativity, and none with a planted push on either.

**Everything here is stable between the two depths.** No row changes by more than 0.005 from
layer 48 to layer 50, so nothing depends on the depth chosen.

### What that means

The framing that survives is about how a direction was selected and not about whether the
steering worked. The paper reports that turning these three quantities up raises judged scores
and none of this contradicts that. What it shows is that the directions being turned up have no
measurable relationship to the direction that moves the model's own readiness to write more
original text, and none to a change of known kind planted in a synthetic creative agent.
Whatever raises the scores is therefore not identified by these measurements, and the label a
quantity carries is not evidence that it is the mechanism.

The paper already reaches the edge of this from the other side. Its own section on these
quantities says that while they offer some extent of validation, their activation strength and
underlying logic need careful evaluation. This is what carrying that out looks like. The check
is against a change of known kind, and on creativity the answer is that the three do not stand
out from arbitrary ones.

So the sentences this supports are that choosing a direction by its label is a way of forming a
hypothesis and not a way of identifying a mechanism, and that a reported gain in score and a
claim about mechanism are two claims needing two pieces of evidence, the second of which is not
present here. The constructive half is the method rather than the verdict. A random draw level
and an anchor of known kind together turn a cosine from an impression into a test, and once the
anchor exists they cost no further model runs.

The probe result should keep its asymmetry rather than be averaged into one number. A direction
fitted on judged unusualness points measurably along the model's own generation direction on the
stapler task and not on the brick task, at one chance in twenty rather than one in a hundred.
That is weak evidence of a shared mechanism on one of two tasks, and it is more than the three
label chosen quantities achieve anywhere.

---

## 12. The same three quantities against the two games

This is a cross check rather than a new test. The three creativity quantities were also compared
with the anchors built for the lottery and the ultimatum game.

| direction | lottery, the answer part | lottery, the letter part | lottery, the push | ultimatum, the answer part | ultimatum, the push |
|---|---:|---:|---:|---:|---:|
| **the level 1 draw in 20 reaches** | 0.033 | 0.027 | 0.049 | 0.028 | 0.077 |
| quantity 13142 | +0.011 | +0.003 | −0.008 | +0.011 | −0.009 |
| quantity 20117 | +0.011 | +0.009 | −0.006 | +0.003 | +0.012 |
| quantity 4992 | +0.011 | +0.016 | −0.028 | +0.012 | +0.020 |

**What the columns are.** On the games the readout direction was split into the part that
survives swapping the two options, which must be about the answer itself, and the part that
reverses when the options are swapped, which must be about which letter gets typed. The push
columns are the pure push anchors for each game.

**What the numbers say.** Every one of the fifteen is inside the level a random draw reaches. So
the three creativity quantities have no measurable relationship to the direction that moves the
answer, the direction that moves the letter, or a planted push, on either game.

**Why this is worth having.** It closes the objection that the three were judged against the
wrong kind of target. They were judged against nine targets across three tasks and cleared none
of them.

---

## 13. What the judges' own scores already say, about length

### What was done

Every number above rests on the judges, so the judges were examined directly. No new model runs
were needed for this and no new judging was done. Two things were computed from the project's
own combined file of scores.

The first is how much of each judge's score is predictable from the length of the response and
nothing else. Each judge's score was regressed on the length of the response, per judge and per
task, and the fraction of the variation accounted for was recorded.

### What was found

| what was measured | brick | stapler |
|---|---:|---:|
| share of a judge's variation explained by length alone, lowest judge | 0.507 | 0.180 |
| share of a judge's variation explained by length alone, highest judge | 0.641 | 0.774 |
| points gained by doubling the length, lowest judge | 0.72 | 0.23 |
| points gained by doubling the length, highest judge | 1.60 | 0.78 |

**What the first two rows say.** For the judge most driven by length on the stapler task, 77
percent of the variation in that judge's scores across responses is predictable from how long
the response is. For the judge least driven by it, 18 percent is. Across all ten combinations of
judge and task the range runs from 18 percent to 77 percent. There is no combination in which
length is a minor factor.

**What the last two rows say.** These convert the same finding into units a reader can check
directly. On the brick task the judge most driven by length awards 1.60 more points to a
response for being twice as long. For comparison, the condition effects the paper reports on that
task run from −0.178 to +1.516. So the effect of doubling the length is comparable in size to
the largest effect any condition produces.

### What that means

The paper states that the capability scores come from a blind and length controlled protocol and
that the rubric scores idea quality rather than length. The first part holds. Each judge sees
only the response and the task, and that was verified. The second part is what this measures.
Length was not removed from the scores, and it accounts for between 18 and 77 percent of their
variation. Telling the judges in the rubric not to reward length did not make the scores
independent of length.

This is the creativity result most worth putting in the paper, because it changes how a number
already in the paper should be read rather than adding a new one. The sentence that says the
rubric scores quality rather than length becomes a measured statement of how much length it does
score, with the range given. Nothing about it requires withdrawing a condition effect. What it
does require is that a reported condition effect be given alongside the change in length that
came with it, because a condition that made responses longer had a route to a higher score that
has nothing to do with originality.

---

## 14. What the judges' own scores already say, about agreement

### What was done

The second thing computed from the same file is how much the judges agree with each other. There
are five judges, so there are ten pairs of judges. For each pair, how closely do they put the
responses in the same order.

This was computed inside one task and one condition at a time, and then also with the length
relationship removed from the scores first.

### What was found

| how the responses were grouped | lowest case | highest case |
|---|---:|---:|
| inside one task and one condition, as scored | 0.020 | 0.654 |
| inside one task and one condition, with length removed | 0.045 | 0.657 |
| pooled across all conditions, as the paper reports it | | 0.770 |

**What the first row says.** The lowest case is the stapler prompting condition at 0.020, which
is no agreement between the judges at all. The highest is the brick steering condition at 0.654.

**What the second row says.** Removing length first barely changes anything, from 0.045 to 0.657.
So the disagreement between the judges is not caused by length. These are two separate findings
and neither explains the other.

**What the third row is.** It is the figure the paper reports, computed by putting responses from
all conditions into one ranking. Every within condition case is below it and most are far below.

### What that means

Pooling responses from different conditions into one ranking means that any tendency the judges
share about conditions as a whole counts as agreement about individual responses. If the judges
all tend to score one condition higher, they will appear to agree even if they disagree
completely about which responses within that condition are the good ones.

The comparison the argument needs is agreement inside a condition, because that is the comparison
each condition effect is read from. There it runs from 0.020 to 0.654.

So the sentence in the paper saying the judges agree closely becomes a sentence with its grouping
named: agreement is 0.770 when conditions are pooled and between 0.020 and 0.654 within a
condition. This is ordinary reporting of method and it does not require withdrawing anything. It
does mean a condition effect drawn from a condition where the judges agree at 0.020 should not be
presented with the same confidence as one where they agree at 0.654.

---

## 15. One thing that does not yet add up, and is reported rather than resolved

Recomputing the condition effects from the project's combined file of scores does not reproduce
the numbers in the paper's own figure, and the difference is not small.

| what was compared | recomputed here | as the paper reports it |
|---|---:|---:|
| brick, the baseline level | 5.034 | 5.18 |
| brick, the change under steering | −0.178 | +0.39 |
| stapler, the baseline level | 5.768 | 5.23 |
| stapler, the change under steering | +0.455 | +1.02 |

On the brick task the recomputed change has the opposite sign from the reported one. The baseline
levels differ as well, in opposite directions on the two tasks.

The same recorded responses underlie both sets of numbers, so the difference is in how they were
combined and not in what the model wrote or what the judges said. The paper's way of combining
them has not been reproduced here, so this is a reconciliation still to be done and not a
correction. Neither set of numbers should be presented as replacing the other until it is.

One thing about the comparison is already settled and is worth keeping. The steering conditions
and the prompting conditions came out of two different generation pipelines with different
baseline levels, 5.034 against 6.120 on the brick task. Comparing a condition from one against a
baseline from the other was the source of an earlier error in this work and it is recorded as
such. Any table that puts steering and prompting side by side has to state which baseline each
was measured against.

---

## 16. How this compares with the setup already in the paper

### What is the same

The model is the same. The two prompts are the paper's own. The responses are the paper's own
recorded responses. The judges and their scores are the paper's own. The three quantities tested
are the three the paper turns up, identified by the numbers its appendix gives. Nothing here
tests a different system.

### The first difference is what is being asked

The paper asks whether turning these quantities up raises the judged score, and answers that it
does. This work asks a different question, which is whether the directions being turned up have
any measurable relationship to creativity as the model itself represents it. Those are separate
questions and the second does not overturn the first. A method can produce a real improvement
for a reason other than the one on its label.

### The second difference is what the comparison is made against

In the paper a steering result is compared with a baseline condition. Here every result is
compared with two further things. One is an anchor, a change built to be of a known kind. The
other is the level an arbitrary direction from the same dictionary reaches. Adding those two
turns a number that looks small or large into a number that is above or below a stated level.

### The third difference is where the evidence comes from

Every creativity number in the paper passes through the five judges. Every number in sections 6
through 12 here comes from inside the model and never consults a judge, except in choosing which
pairs of responses to use. That is why the two can be put next to each other: they are not two
measurements of the same thing.

### The fourth difference is what is not covered

The paper measures what steering does to the writing. This work measures where directions point.
Those are different tests and the second does not settle the first. No direction here was used
to steer anything at a dose matched to the anchor's own effect, which is the test that would
close the gap, and that is true of the game work as well.

---

## 17. What is deliberately not being claimed

That the three quantities do not raise creativity scores. They do, by the paper's own
measurement. What is shown is that they have no measurable relationship to either anchor, which
makes the mechanism unidentified rather than absent.

That the dictionary contains no creativity direction. The three tested were selected by label. No
search was run for a combination of quantities fitted numerically against the creativity
gradient, and on the two games it was exactly that kind of search that found structure where the
label chosen ones found none.

That these creativity anchors are as trustworthy as the ultimatum game's. The adapters copied
their agents at 0.80 where 0.95 was required, the change of taste target is unusable, and the
reading the gradient is built on moves by about 5 percent of its own variation. A result of
nothing measured against these targets is weaker evidence than the same result on the ultimatum
game.

That the probe's agreement figure is its held out performance. 0.846 was fitted and tested on the
same 320 responses and pooled across two tasks, so it is a ceiling. The recomputation is running.

What any of these directions do when used. Every comparison here is between directions. The
behavioural test, steering with each direction at a dose matched to the anchor's own effect and
comparing the change in judged score, has not been run for creativity and has not been run for
the two games either.

---

## 18. Every result, and what each one means

A reference list rather than something to read aloud.

### Building the reading and the gradient

| measurement | value | what it means |
|---|---|---|
| brick, average reading over 42 pairs | **+0.0115** | the model leans toward the writing the judges preferred, without being asked |
| brick, pair to pair variation | 0.208 | the lean is about 5 percent of the variation, so it is consistent and weak |
| stapler, average reading over 40 pairs | **+0.0049** | same direction, smaller |
| stapler, pair to pair variation | 0.246 | about 2 percent of the variation |
| brick, how far apart the judges put a pair | 1.048 points | the contrast the reading was asked to detect |
| stapler, the same | 1.835 points | a wider judged contrast, yet a smaller reading |
| length of the averaged gradient, brick | 0.00626 and 0.00602 | the pairs agreed on a direction rather than cancelling |
| length of the averaged gradient, stapler | 0.02103 and 0.02010 | more than 3 times brick, so the stapler pairs agreed more |

### Building the probe

| measurement | value | what it means |
|---|---|---|
| agreement with the judge that was held out, best case | **0.896** | a single direction orders writing much as an independent judge does |
| the same, worst case | 0.794 | the probe is least like DeepSeek V4 Pro |
| the same, average of five | **0.846** | a ceiling and not a performance, for the two reasons below |
| responses used to fit, and to test | 320 and 320 | the same texts, so part of the figure is the fit recognising them |
| tasks pooled into one ranking | 2 | telling brick from stapler earns agreement on its own |
| difference between the two depths | at most 0.005 | nothing depends on the depth chosen |

### Building the pure push

| measurement | value | what it means |
|---|---|---|
| the model's own reading, average and variation | +0.0055 and 0.2691 | the scale every constant below was set from |
| the agent's sensitivity, set by rule | 0.4376 | chosen so the agent varies as much as the model does |
| the same, in the first failed attempt | 0.0039 | 70 times too small, so there was nothing to learn |
| adapters copying their agents, first attempt | **−0.066, +0.020, −0.038** | complete failure, and the reason it failed was found |
| adapters copying their agents, corrected | **0.810, 0.797, 0.798** | they do track their agents now, and 0.95 was required |
| how far they move against how far they should | 0.764, 0.759, 0.824 | they move about four fifths as far, where 0.90 to 1.10 was required |
| training error, all three | 0.0411 to 0.0444 | no agent was harder than another, so the shortfall is the task's |
| the pure push planted, and recovered | **+0.0475 and +0.0553** | 116 percent of it came back, so this anchor works |
| how much that recovery varied | 0.0619 | over 82 pairs the average is about 8 times its own uncertainty |
| the change of taste planted, and recovered | +0.0024 and +0.0043 | the plant is smaller than the instrument's error, so unusable |
| how far the pure push moves the state | 1.543 and 1.657 | the direction the next section compares against |
| how far the change of taste moves it | 0.767 and 0.799 | half as far, which is what a different kind of change should do |
| the same push on the lottery, and the ultimatum | 3.073 and 6.512 | creativity's anchor is the weakest of the three |

### Placing the directions

| measurement | value | what it means |
|---|---|---|
| the three quantities against both gradients | **−0.012 to +0.003** | inside the 0.025 a random draw reaches, so no relationship |
| the three against the pure push | **−0.055 to +0.026** | inside the 0.151 a random draw reaches |
| the three against the change of taste | +0.091 to +0.107 | above its level, on the one target that cannot be trusted |
| how close those three are to each other | within 0.016 | a shared component rather than three separate alignments |
| the probe against the stapler gradient | **+0.031 and +0.033** | above the 0.027 a random draw reaches, below the 0.039 |
| the probe against the brick gradient | +0.012 to +0.019 | inside the level |
| the probe against the pure push | +0.050 to +0.054 | well inside the 0.151 |
| the three against nine targets on three tasks | inside every level | they clear none of them |
| change from layer 48 to layer 50, any row | under 0.005 | no result depends on the depth chosen |

### What the judges' scores already contain

| measurement | value | what it means |
|---|---|---|
| share of a judge's variation explained by length | **0.180 to 0.774** | length is a major factor for every judge on every task |
| points gained by doubling the length | 0.23 to 1.60 | comparable to the largest condition effect reported |
| judge agreement inside one condition | **0.020 to 0.654** | in the worst case the judges do not agree at all |
| the same with length removed first | 0.045 to 0.657 | the disagreement is not caused by length |
| judge agreement pooled across conditions | 0.770 | the figure in the paper, and grouping explains the difference |
| brick steering, recomputed against reported | −0.178 against +0.39 | opposite signs, and the combining method is not yet reconciled |
| stapler steering, recomputed against reported | +0.455 against +1.02 | same sign, less than half the size |

---

## 19. What would come next, in order

The first task is to finish the probe recomputation that holds out responses as well as judges
and works inside each task, so that the agreement figure can either be quoted or withdrawn. It
is running now and takes about twenty minutes once the model is loaded.

The second task is to reconcile the recomputed condition effects with the paper's own figure, so
that the two sets of numbers can appear in one document without contradicting each other. This
needs no model runs and only the files already present.

The third task is to search for a combination of dictionary quantities fitted numerically against
the creativity gradient, in the same way it was done on the two games. That is the test of the
dictionary itself rather than of three labelled quantities, and on the games it is what found
structure. The fit needs no new model runs.

The fourth task is the behavioural test. Steer with the probe and with each of the three
quantities at a dose chosen so that each one produces the same size of effect as the anchor does,
then compare the change in judged score rather than the angle between directions. This is the
test the comparisons above do not perform, and it is outstanding for the two games as well.

The fifth task is to retrain the creativity adapters on a longer schedule so that the copying
standard can be met. This has to be set up as a fresh construction of the anchor with its outcome
reported whichever way it falls, and not as an extension of the present run, because extending a
run whose result fell short is exactly the thing the project's rules prohibit.
