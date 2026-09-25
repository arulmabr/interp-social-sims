# The SAE anchor work, notes to be read aloud

These notes assume no prior knowledge of the project. Every term is explained at the point
where it first matters. Every number quoted here was produced by a script in this repository
and is recorded in the project's register of results alongside the script that made it.

---

## 1. The question behind all of this

A large language model can be made to behave differently by reaching inside it while it runs
and adjusting one of its internal quantities. The claim usually attached to that is a claim
about mechanism. If the quantity being adjusted has been labelled "willing to take risks"
and the model then takes more gambles, the natural conclusion is that the model's attitude
to risk has been changed.

There is a cheaper explanation that predicts exactly the same observation. The adjustment
may simply be making the model more likely to type one particular word, with nothing about
risk involved anywhere.

Consider what that difference means in practice. Imagine a person who is offered a coin flip
for a hundred pounds against a certain forty pounds. If their attitude to risk changes then
the amount at which they switch from the certain money to the coin flip moves. If instead
somebody has simply told them to answer with the word on the left hand side of the page then
their answers also change, but nothing about how they value money has moved at all. Both
people give different answers than before. Only one of them has changed their mind.

The whole purpose of this work is to build a measurement that can tell those two situations
apart, and then to apply it to the technique we actually use in the paper.

---

## 2. The idea of an anchor

An anchor is a change whose nature is known in advance because it was built deliberately.

The comparison is the calibration of a thermometer. Before a thermometer is trusted to
report the temperature of a patient it is placed in melting ice and then in boiling water.
Those two temperatures are known without needing the thermometer. If the instrument reports
them correctly then its reading on the patient can be believed. If it reports melting ice as
thirty degrees then nothing it says about the patient matters.

Two anchors are used here and they play the roles of the ice and the boiling water.

The first is a change built to be nothing but a push toward one answer. It contains no
opinion about gambles whatsoever. If the measurement cannot recognise this one as a pure
push then it cannot be trusted to recognise a push when it meets one in the wild.

The second is a change built to move an actual preference, meaning the agent's valuation of
the options rather than its tendency to say a particular word.

Both anchors are constructed without using the technique under test. A ruler made out of the
same material as the thing being measured would settle nothing.

---

## 3. What is inside the model, in plain terms

When the model processes a prompt it carries forward a running internal state. At any one
layer of the model this state is simply a list of 8,192 numbers. This list is called the
residual stream. Think of it as the model's working notes at that point in its processing.

The model used throughout is called Llama-3.3-70B-Instruct. It was loaded from a local copy
of its weights on the cluster. It was never accessed over the internet.

---

## 4. What a sparse autoencoder is

A sparse autoencoder is a separate and much smaller network whose only job is to rewrite
that list of 8,000 numbers as a combination of simpler parts, with only a handful of those
parts active at any moment. The abbreviation SAE is used for it from here on.

The intuition is a recipe. A finished dish can be described as a list of measurements of
every chemical it contains, which is accurate and completely unreadable. It can instead be
described as one onion and two cloves of garlic and a pinch of saffron. The second
description is a combination of a small number of named ingredients drawn from a large
pantry. The sparse autoencoder is an attempt to build that pantry for the model's internal
state.

The pantry used here has 65,536 entries. Each entry is called a feature and each feature has
its own direction, which is again a list of 8,192 numbers. Three 1,632 of those entries turn
out to be dead. A dead entry is one whose direction is entirely zeros. Every dead entry is
excluded from everything that follows.

Steering with a feature means taking that feature's direction and adding a multiple of it to
the model's running internal state while the model is generating its answer.

---

## 5. Where every ingredient came from

The dictionary of features is a published file, released by the company Goodfire for layer
fifty of this particular model. It was downloaded from the public model repository at a
fixed published version rather than at whichever version happened to be current. Fixing the
version matters because it means anybody repeating this work receives the identical file.
The file is about four and a third gigabytes.

That version was not chosen freshly. It was read out of the existing experiment's own source
code so that both pieces of work use the same dictionary.

The prompts came from two places. The lottery prompts are the 432 already used by the
earlier steering experiment. The ultimatum prompts are the 120 from this project's own
responder grid.

---

## 6. The branch this was built on, and what is already in it

None of this started from nothing. There is a branch in the repository called the SAE anchor
pilot, and the work in these notes sits directly on top of it. Six directories on that branch are
relevant here.

### What the branch already contains

**The anchor code itself.** A directory called probe anchor holds the code that builds both
anchors. It also holds the gate they have to pass and the analysis that places a direction
against them.
It is the same code used for the measurements described in these notes, published with the
machine-specific file paths replaced by placeholders so that it can be read by anybody. That
directory is the reason the work here is an extension rather than a fresh start.

**A completed SAE steering experiment.** A directory called anchor pilot holds an experiment
run over three days in September. It trained a small set of extra weights to imitate a
decision maker with known parameters, then asked whether steering the model with sparse
autoencoder features could reproduce that same decision maker. It saved 432 frozen prompts and the 28 conditions run over
them. It also saved the exact strengths and feature numbers used, together with the released
dictionary version it pinned.

**A local replication of the paper's own runs.** A directory called paper replication holds a
runner that regenerates the responses behind the published figures using the model and the
released dictionary on our own machines, without calling Goodfire's service. It preserves the
original prompts and the original sampling settings.

**A bridge to the survey library.** A directory called EDSL local SAE connects that survey
library to the local runner, so that a survey can be described once in the usual way while
every model call is answered on hardware we control.

**A label-guided pilot.** A directory called label pilot follows a specific chain, from a
human-readable label, to a candidate feature, to independent evidence that the feature
actually activates, to a controlled intervention, to a held-out behavioural check. It reports
one result that bears on the rest of these notes. Of 20 positive edits, all 20 displaced the
model's internal state. Of 20 negative edits, all 20 produced no displacement at all. That asymmetry is a
consequence of the edit being clipped at zero.

**The historical data.** Three further directories hold the earlier prompting runs, the probe
results and the original SAE work, kept as a record.

### What this work took from the branch

Four things, all read rather than modified.

The 432 frozen lottery prompts, which is why the measurements here sit on the same prompts as
the earlier experiment rather than on a set of our own.

The 28 saved conditions, which is what made the flattening result in section 12 possible
without running the model at all.

The feature numbers and the fitted coefficients, so that the directions placed against the
anchors are the directions that were actually steered with.

The pinned version of the dictionary, read out of the branch's own source, so that both
pieces of work use the identical file.

### What this work added

The readout anchor was computed on the branch's own prompts and then split into the part about
the answer and the part about the letter, which had not been done before and which changes
how the earlier cosine measurements should be read.

The weight anchor was read on those prompts too, which established that it does not carry its
planted meaning across a change of wording.

Both anchors were then built for the ultimatum game, which the branch's experiment never
covered, and the steering on that game was generated fresh.

Every direction was placed against both anchors on both games, with 2,000 randomly drawn
features setting the level an ordinary feature reaches.

### What this work has not touched

The local runner and the survey bridge were read but not used. The ultimatum steering in these
notes was performed by our own code rather than by the branch's runner, and the two apply their
edit in slightly different ways. Ours adds the feature's direction to the internal state
directly. The branch's runner raises the feature's activation and then rebuilds the state
around it while keeping what the dictionary cannot represent. It then clips the result at
zero. If the
two sets of numbers are ever to sit in one table then the run should be repeated on the
branch's runner.

---

## 7. What Expected Parrot and EDSL are, and why they never appear here

Expected Parrot is a company that publishes a Python library called EDSL, which stands for
Experimental Design Specification Language. The library helps a researcher describe a survey
once and then send it to many different language models, keeping track of the questions and
the respondents and the answers. It can also route the actual model calls through Expected
Parrot's own servers rather than through hardware the researcher controls.

Goodfire is a separate company. It publishes the sparse autoencoder file described above and
it also runs a hosted service of its own, through which a researcher can ask a model to be
steered by naming a feature and giving a strength.

The distinction that matters is between a file and a service. Downloading a published file
and running it on your own machine leaves you in full control of what happens. Sending a
request to somebody else's server means the important step happens somewhere you cannot
inspect.

Neither Expected Parrot nor EDSL nor Goodfire's hosted service was used anywhere in the work
described in these notes. Prompts were turned into text by the model's own tokenizer and fed
to a locally loaded copy of the model. The only thing obtained from Goodfire is the
dictionary file, which can be downloaded and checked and pinned to a revision like any other
file.

---

## 8. The first step, building the answer direction

### What was done

The first anchor is called the readout gradient. A gradient is simply the direction of
fastest increase. If you are standing on a hillside then the gradient is the direction in
which the ground rises most steeply.

Here the quantity being increased is the odds that the model gives one answer rather than
the other. So the readout gradient is the adjustment to the model's internal state that most
efficiently pushes the written answer from one option toward the other. By construction it
has nothing to do with preferences. It is the shortest route to changing what gets typed.

It was computed at two depths inside the model, referred to as layer forty eight and layer
fifty, and averaged across prompts.

### Why it was done twice for every prompt set

A model can favour a particular answer. It can also separately favour whichever option
happens to be printed second. Those are different things and they are easily confused.

To keep them apart the gradient was computed once for each of the two possible orders in
which the options can appear. The two results were then combined in two ways. Adding them
gives the part that the two orders have in common, which cannot depend on the ordering and
so must be about the answer itself. Subtracting them gives the part that reverses when the
order reverses, which must be about position or labelling rather than about the answer.

### How the two are compared

The comparison is reported as a cosine. A cosine is a single number between -1 and +1 that
says how closely two directions agree. Plus one means they point the same way. Zero means
they are unrelated. Minus one means they point in exactly opposite directions.

Picture two arrows drawn from the same point. A cosine of +1 means the arrows lie on top of
each other. A cosine of zero means they are at right angles. A cosine of -1 means one arrow
is the reverse of the other.

### What was found

On the lottery the two orders gave a cosine of -0.889 at layer forty eight and -0.893 at
layer fifty. The part common to both orders had a length of 9.128, while the part that
reverses had a length of 37.682.

On the ultimatum game the same computation gave +0.953 and +0.956. There the common part had
a length of 18.421 and the reversing part only 2.869.

### What that means

On the lottery the two orders come close to cancelling each other out. The explanation is
the answer format. The lottery prompts ask the model to reply with a single letter, either A
or B, and which letter stands for the gamble changes from prompt to prompt. So the thing
being measured flips its meaning when the ordering flips, and the direction flips with it.

The ultimatum prompts ask for the word Accept or the word Reject. Those words keep their
meaning no matter which option is printed first, so nothing flips and the two orders agree.

On a prompt that asks for a bare letter, about four parts in five of the readout direction
is about which character gets typed rather than about what that character stands for. Any
measurement taken against an undecomposed version of that direction is therefore mostly
measuring alignment with letter identity.

Within a single ordering the individual prompts agreed with their own average at 0.851,
which means the direction is a consistent thing rather than an average of unrelated noise.

The lottery computation took 11 minutes and 16 seconds. The ultimatum computation took 5
minutes and 34 seconds.

---

## 9. The second step, building the pure push

### What was done

The second anchor is a set of extra weights added to the model and trained so that the model
behaves like an agent whose only difference from normal is a constant push toward one
answer. The same amount is added on every single trial regardless of the amounts of money
involved. This kind of small trainable addition is called an adapter.

Three adapters were trained together on identical data with an identical schedule. One is a
reference with nothing changed. One has the constant push. One has a genuine preference
shifted instead.

### Why a reference adapter exists at all

If the pushed adapter were compared against the plain unmodified model then the comparison
would mix two different things together. It would mix the effect of the push with the effect
of the model having been taught to behave like a decision making agent at all. Comparing the
pushed adapter against a reference adapter that received the same training without the push
removes the second effect and leaves only the first.

### How the anchor is turned into a direction

An adapter is a collection of weights. It has no direction in it that could be compared with
a feature. So its direction has to be measured rather than read off. The same prompts were
run twice. The first run used the reference adapter and the second used the pushed adapter.
The average change in the model's internal state between the two runs was recorded. That
average change is the adapter's displacement and it lives in the same space as the feature
directions, so the two become comparable.

### What was found

The size of the push that was built in is 0.6 in units of the answer log-odds, which is
defined in the next section.

On the ultimatum prompts the measurement recovered +0.462 of that planted 0.6, which is
about 77 percent. The displacement had a length of 6.512.

On the lottery prompts the same measurement recovered -0.022, which is indistinguishable
from nothing at all. The preference adapter came out at -0.285, which is the wrong sign
entirely.

### Why the lottery result is a failure rather than a finding about the model

These adapters were trained on prompts with different wording from the lottery prompts used
here. The reading itself was sound, because the unmodified model measured this way agreed
with the experiment's own recorded baseline at a correlation of 0.957. The adapters were
also clearly doing something, because the spread of the model's answers dropped from 12.45
to 4.36 under them.

What failed to survive the change of wording is the planted difference. The displacement
lengths tell the same story. The pushed adapter moved the internal state by 3.073 and the
preference adapter by 2.521, which are close to each other when two changes of genuinely
different kinds should not be.

An adapter trained on one phrasing does not carry its planted meaning to another phrasing.
Comparisons against the ultimatum version of this anchor can be believed. Comparisons
against the lottery version cannot.

---

## 10. Two terms that appear in every result from here on

### Log-odds

When the model has finished reading a prompt it holds a probability for each possible next
word. The log-odds is a way of writing the balance between two of those probabilities as a
single number. A log-odds of zero means the two options are equally likely. A positive
number means the first option is favoured and a negative number means the second is. The
further from zero, the more lopsided the model's preference between the two words.

The reason for using log-odds rather than a plain probability is that it does not get stuck
near the ends. A probability cannot go above 100 percent, so once a model is very confident
the probability stops moving even when the underlying pressure keeps growing. The log-odds
keeps growing, which makes it a better ruler.

### The null

Whenever a number is reported for how closely a feature matches an anchor, that number is
meaningless without knowing what an ordinary feature would score. So 2,000 features were
drawn at random from the dictionary and put through the identical comparison.

The intuition is a lottery. Being told that somebody holds a winning ticket means nothing
until you are told how many tickets were sold. The random draw plays the role of counting
the tickets.

Two levels are quoted. The ninety fifth percentile is the score that only one random feature
in twenty beats. The ninety ninth percentile is the score that only one in a hundred beats.
Anything below those levels is doing no better than a feature picked out of the pantry
blindfolded.

---

## 11. The third step, placing the features against the anchors

### What was done

Three kinds of direction were compared against both anchors on both games.

The first kind is the individual features we name and steer with in the paper. Feature 184
is labelled "willing to take risks or make sacrifices for a goal". Feature 4,237 is labelled
"executing potentially risky operations that require caution". Feature 31,935 is labelled
"altruistic and selfless behavior or intentions". These were chosen by reading the labels.

The second kind is combinations of 10 features whose weights were fitted numerically rather
than chosen by reading labels.

The third kind is an attempt to rebuild the readout direction itself out of 10 features.

This step needed no model at all. It is arithmetic performed on the dictionary file.

### What was found on the lottery

Against the answer part of the readout direction the null sits at 0.033 for one feature in
20.056 for one in a hundred.

Feature 184 scored -0.001. Feature 4,237 scored +0.004. Feature 31,935 scored +0.004.

The fitted ten feature combinations scored between +0.067 and +0.096.

The attempt to rebuild the readout direction scored +0.269.

### What was found on the ultimatum game

Against that game's own answer direction the null sits at 0.028 and 0.038. Feature 31,935
scored +0.013.

Against that game's pure push anchor the null sits at 0.077 and 0.126. The same feature
scored -0.044. The fitted combinations scored between +0.184 and +0.226.

### What all of that means

The 3 features we actually steer with score below the level that one random feature in
twenty reaches. This holds against every anchor on both games. It holds for the altruism
feature even when it is measured against the anchor built from the ultimatum game rather
than from the lottery, which removes the obvious objection that it was being judged on the
wrong task. Choosing a direction by reading its label produced directions with no measurable
relationship to anything the anchors represent.

The fitted combinations do better. On the lottery they align with the answer direction above
the level that only one random feature in a hundred reaches. On the ultimatum game they
align instead with the pure push anchor, scoring up to +0.226 against a one in a hundred
level of 0.126.

It is the only positive identification anywhere in this work. Vectors that were fitted on
the lottery in order to imitate a decision making agent turn out, when examined on the
social task, to point at the direction of a constant push toward one answer. That is a
statement about what they are rather than a statement about what they failed to be.

### A number that was previously unexplained

We had reported that rebuilding the readout direction out of 10 features left 96 percent of
it unaccounted for, and had described this as a poor approximation without being able to say
why. The decomposition explains it. The readout direction on those prompts is mostly the
letter identity part. The dictionary can represent the answer part reasonably well at +0.269
but barely reaches the null on the letter part at +0.037. The rebuilding fails because the
component it is mostly trying to match is simply not in the pantry.

---

## 12. The fourth step, measuring what the steering actually does

### Why pointing is not enough

Everything in the previous step is about where directions point. That is not the same as
what they do. Two directions can point similarly and have very different effects on
behaviour.

### What was done

For every steering condition the change in the model's log-odds was compared against its
unsteered value using a straight line fit. The slope of that line carries the information.

The intuition is the difference between a volume knob and a mute button. If an intervention
adds something without touching how the model responds to the amounts of money on offer,
then the slope is zero and the model is still listening to the payoffs. If the intervention
removes that responsiveness entirely then the slope is -1 and the model has been muted. What
is left over, which is one plus the slope, is the share of the payoff signal that the
measurement still has to work with.

### What was found on the lottery

The unsteered spread of the model's answers was 9.23. After steering with the ten feature
combination it was 0.92.

The share of signal remaining was 0.062 for the readout direction, between 0.092 and 0.096
for the ten feature combinations, and between 0.129 and 0.143 for the dense vectors.

Random directions of the same size retained between 0.505 and 0.605.

The straight line fits were almost exact. The measure of how closely the points follow the
line ran between -0.95 and -1, where -1 means every point lies on the line.

### What that means

Every one of these interventions flattens the model's response toward a constant, and the
fit to a straight line is close enough that little else is happening. The model has almost
stopped distinguishing between a good gamble and a bad one.

The comparison with random directions is what decides how much the rest can be believed. The
directions under test destroyed between three and six times more of the signal than randomly
chosen directions of the same size did. A situation in which the control preserves the
measured quantity better than the treatment does is not a situation in which anything can be
concluded about the treatment.

The cause is the strength. The identical direction retains 0.611 at strength one, 0.215 at
strength 4.062 at strength sixteen. Strength sixteen is where we made every comparison in
the original experiment.

### What was found on the ultimatum game

Here the steering was generated fresh because the earlier experiment never covered this
game. The strengths were expressed in units of the typical size of the model's internal
state at that layer, which was measured at 21.12.

The altruism feature shifted the answer by +1.814 at the highest strength while leaving the
shape of the response almost unchanged, with a retention figure of 1.174.

The readout direction at the same strength gave a retention figure of 3.574 and raised the
spread of the answers from 7.86 to 28.21.

A randomly chosen live feature gave a retention figure of 0.977 and moved the average answer
by +0.154. Both of those are close enough to no change that the feature can be said to have
done nothing.

### What that means

A retention figure above one means the model responded more sharply rather than less. So
nothing was flattened on this game.

The altruism feature moved the answer by 1.814 while changing the shape of the response by
17 percent. That is the signature of a push toward one answer rather than a change in what
the responder considers a fair split. The readout direction, which is a pure push by
construction, did the same thing more strongly, raising the spread of the answers from 7.86
to 28.21.

The two games differ because of where the adjustment is applied rather than how large it is.
The strength applied at each position is close to the same in both cases, sixteen in 17.9 in
the other. The lottery conditions apply the adjustment at every position in the prompt while
the ultimatum conditions apply it only at the final position. The flattening is therefore a
property of applying an adjustment everywhere at once, and results from the two arrangements
should never be combined.

---

## 13. How this setup compares with the one we already use in the paper

Our own steering procedure is described in the appendix of the paper. The two agree on the
model and the dictionary and the features. They differ in how the steering is applied and
how the answer is read, and those differences decide what each one can claim.

### What the two have in common

Both use the same model, which is Llama-3.3-70B-Instruct.

Both use the same dictionary of features, the sparse autoencoder published for layer fifty
of that model.

Both reach into the model at the same depth, which is layer fifty.

Both steer with the same features. In the paper we use feature 184 and feature 4,237 for the
lottery and feature 31,935 for the ultimatum game. Those are exactly the features placed
against the anchors in these notes.

So the disagreement between the two is not about which model or which dictionary or which
features. It is about how the steering is applied and how the answer is read.

### The first difference is where the work happens

In the paper our runs are sent to a service operated by Goodfire. We name a feature and give
a strength and the service returns the model's reply. The steering itself happens on
somebody else's machine.

The work in these notes downloads the published dictionary file and runs everything on the
project's own hardware. The steering is performed by code in this repository that can be
read line by line.

This matters for a practical reason. The strength we send to the service is a number between
zero and one, and the service's interpretation of that number is not published. It is
possible to record what the number achieved, because the logs show that a strength of one
half drove the targeted feature from outside the ten most active features to a level of 175,
against ninety eight for the strongest feature when nothing is steered. But it is not
possible to reconstruct the rule that turned one into the other. Running locally removes the
question entirely, because the code performing the edit is the code you wrote.

### What a position is, in concrete terms

A prompt is not one thing to the model. It is a sequence of tokens, and the model holds a
separate internal state at each one. A position simply means one of those token slots.

Here is the tail of a real ultimatum prompt. The whole thing is 121 tokens long and it ends
like this:

| position | token | what it is |
|---|---|---|
| 114 | end of turn | closes the scenario text |
| 115 | start of header | the model's turn begins |
| 116 | assistant | names whose turn it is |
| 117 | end of header | |
| 118 | blank line | |
| 119 | Answer | the word Answer |
| 120 | : | the colon, and the final position |

The 100 and fourteenth token closes the scenario text. The next four are the marks that tell
the model its turn has begun. The 100 and nineteenth token is the word Answer and the 100
and twentieth is the colon after it.

That colon is the final position. It is the last token of the prompt and the point at which
the model has read everything and is about to produce its first word. The answer is read
from exactly there, by comparing the probability the model gives to one option word against
the probability it gives to the other.

So applying the adjustment at the final position means adding the direction to the model's
internal state at that colon and nowhere else. The model reads the entire scenario normally
and is nudged only at the instant of committing to an answer.

Applying it at every position means adding it at all 121 tokens. The model reads the size of
the offer and the consequence of refusing through an internal state that has already been
altered.

### The second difference is where the edit lands

The controller we use in the paper applies its adjustment at every position in the prompt.
The configuration field that would restrict it to particular positions is left empty, which
means no restriction.

The ultimatum runs in these notes apply the adjustment only at the final position of the
prompt, which is the moment just before the model commits to an answer.

The strength per position is close to the same in the two arrangements. What differs is how
many positions receive it. Section 12 measures the consequence. Applying
the adjustment everywhere flattens the model's response to the amounts of money almost
completely, while applying it at the last position alone does not flatten it at all. Results
from the two arrangements should never be combined into one comparison.

### The third difference is how the answer is read

In the paper we let the model write a reply and then read the choice out of the text. A
helper library picks whichever of the two option names appears.

The work in these notes reads the answer from the model's own probabilities at the moment of
answering, without letting it write anything. The measure used is the balance between the
probability of one option word and the probability of the other.

Reading the probabilities is the more sensitive of the two. A written reply gives one
observation, and to see a small shift you need many agents. The probabilities give a graded
quantity on every single trial, so a shift that would be invisible in the text is visible
immediately. That sensitivity is what makes the anchor measurements possible at all. The
cost is that a probability is not the same thing as what the model would actually have
written, and a separate check in this project found the two giving different answers often
enough that neither can stand in for the other.

### The fourth difference is what question is being asked

This difference is not one of engineering.

In the paper we ask whether steering a feature changes the behaviour. We answer yes, and the
answer is correct.

These notes ask what kind of change it was. They do that by building two changes whose
nature is known in advance and asking where the feature sits relative to them. That question
cannot be answered by watching behaviour move, however carefully, because a push toward a
word and a change of preference both move behaviour.

So the two setups are not competing accounts of the same experiment. In the paper we
establish that the lever does something. The work here asks what the lever is connected to,
and for the 3 features we name, it finds no measurable connection to either of the two
things it could sensibly be connected to.

---

## 14. A figure from the neighbouring method, and why it is not the same claim

There is a figure in the project showing the calibration of the other method. It is often
read as evidence about the question these notes are asking. It is not evidence about that
question, and the reason is set out below.

### What the figure shows

The figure concerns the other steering method used in the project, which is called a probe.
A probe is a direction found by training a small classifier to separate the internal states
that precede one answer from those that precede the other. It is a different way of
obtaining a direction from the sparse autoencoder route described above.

Before a probe is used it is calibrated. Calibration means searching for the strength at
which the probe moves the model's behaviour to a chosen point. The chosen point here is the
switching point, which is the amount of money at which the agent becomes equally likely to
take the gamble or to take the certain sum. So the researcher says in advance that the agent
should switch at 106 tokens, and the search hunts for the strength that achieves it.

The figure asks whether that hunt succeeded. Each dot is one calibration target. Its
position from left to right is where the agent was aimed and its position from bottom to top
is where the agent actually ended up. The straight line running corner to corner is where a
dot would sit if the aim were perfect. Distance from that line is the calibration error
measured in tokens.

### Why this particular view was drawn

Our released data reports the strength that the search returned for each target. That is the
inverse view and it is much weaker than it looks, because a search returns a number whether
or not it actually arrived anywhere. Reporting the strength it settled on says what the
procedure did rather than whether the procedure worked.

The forward view answers the question directly. It goes back to the raw counts of how many
agents chose each option at each amount of money, with 40 agents at every level, finds the
amount at which the choice curve crosses one half, and compares that to the target. Nothing
is taken on trust from the search.

### What was found

On the lottery game 10 targets were set, spaced from 30 tokens up to 200. At the deeper of
the two positions inside the model the average miss was 2.13 tokens and the worst single
miss was 4.5 tokens. At the other position the average miss was 2.57 tokens and the worst
was 5 tokens.

On the ultimatum game 4 targets were set, from 30 tokens up to sixty. The average miss was
1.15 tokens at the first position and 1.8 tokens at the second.

### What that does and does not establish

It establishes that the probe steering is accurate. When the procedure aims the agent at a
switching point of 106 tokens the agent switches at 104 and a half. Across a range that
spans nearly 200 tokens the aim is off by about two on average. As a piece of engineering
the aim is accurate and it should be reported that way.

It does not establish what inside the model was changed. Landing on a target switching point
says the intervention moved behaviour to the right place. It says nothing about whether the
model's valuation of money changed or whether the model was simply pushed toward typing a
particular word. Recall the person from the opening section who was told to answer with
whatever was printed on the left. Their switching point could be moved to any chosen value
with enough pressure, and their attitude to risk would never have entered into it.

The gap between hitting a behavioural target and having changed the thing you named is the
gap the anchors close. The calibration figure shows the aim is good. The anchor work asks
what was actually moved, and for the features examined in these notes the answer is that
nothing distinguishable from a randomly chosen direction was moved at all.

---

## 15. What this adds up to

Four things are established.

The readout direction on a prompt that asks for a bare letter is about four parts in five
about which character gets typed. The identical computation on a prompt that asks for a word
gives the opposite balance. This is a property of how the question is asked rather than a
property of the model.

The 3 features we steer with cannot be distinguished from randomly chosen features by any of
the anchors on either game.

Feature combinations that were fitted numerically do carry structure. On the lottery they
match the answer direction. On the ultimatum game they match the pure push anchor.

At the strength we use throughout the original experiment every intervention removed more
than 84 percent of the model's responsiveness to the payoffs, while randomly chosen
directions of the same size removed far less.

---

## 16. What is deliberately not being claimed

The lottery placements are comparisons of direction rather than of effect, and pointing is
not doing.

The altruism feature behaving like a push is consistent with the evidence but not
established by it. The ultimatum run recorded summaries for each strength rather than the
individual trial values, so the formal attribution could not be computed. Correcting that is
a rerun of the same 52 minutes with the individual values kept.

Nothing here shows that the dictionary is incapable of representing a preference. The
lottery result is equally consistent with the strength having removed the payoff response
before any preference had a chance to appear.

The pure push comparisons on the lottery rest on an anchor whose planted meaning did not
survive the change of wording, and they should be read as unavailable rather than as null.

---

## 17. Every result, and what each one means

A reference list rather than something to read aloud. Each row gives the measurement, the
value it came out at, and the sentence that value supports.

### Step one, the answer direction

| measurement | value | what it means |
|---|---|---|
| lottery, agreement between the two option orders at layer 48 | **-0.889** | the two orders almost cancel, so the direction is mostly about which letter is typed |
| lottery, the same at layer 50 | -0.893 | the result does not depend on the depth chosen |
| lottery, length of the part common to both orders | 9.128 | the part that is about the answer |
| lottery, length of the part that flips with the order | **37.682** | the part that is about the letter, four times larger |
| ultimatum, agreement between the two orders at layer 48 | **+0.953** | the two orders agree, so the direction is about the answer |
| ultimatum, the same at layer 50 | +0.956 | again independent of depth |
| ultimatum, common part against flipping part | 18.421 against 2.869 | the balance is reversed, six times in favour of the answer |
| agreement of single prompts with their own average | 0.851 and 0.844 | each half is one consistent direction rather than an average of noise |

### Step two, the pure push

| measurement | value | what it means |
|---|---|---|
| size of the push built in | 0.600 | the target every recovery below is measured against |
| ultimatum, push recovered | **+0.462** | 77 percent of the planted amount survives, so the anchor holds on this game |
| ultimatum, preference recovered | +0.331 | the other planted change survives as well |
| ultimatum, displacement of the push against the preference | 6.512 against 5.930 | the two changes move the model differently, which is what two different kinds should do |
| lottery, push recovered | **-0.022** | indistinguishable from nothing, so the anchor does not survive the change of wording |
| lottery, preference recovered | -0.285 | the wrong sign entirely |
| lottery, unmodified reading against the earlier baseline | 0.957 | the reading itself is sound, so the failure is not in the measurement |
| lottery, spread under the reference adapter | 12.45 falls to 4.36 | the adapters are plainly doing something, so the failure is not inactivity |
| lottery, displacement of the push against the preference | 3.073 against 2.521 | too close together for two changes that differ in kind |

### Step three, placing the features

The level an ordinary feature reaches is the comparison for every row. On the lottery that
level is 0.033 against the answer direction and 0.049 against the push. On the ultimatum it
is 0.028 and 0.077.

| measurement | value | what it means |
|---|---|---|
| feature 184 against all three poles, lottery | -0.001 and +0.016 and -0.005 | below the level an ordinary feature reaches |
| feature 4237 against all three poles, lottery | +0.004 and +0.000 and +0.004 | below that level |
| feature 31935 against all three poles, lottery | +0.004 and +0.004 and +0.017 | below that level |
| feature 31935 against the ultimatum poles | +0.013 and +0.010 and -0.044 | below that level on its own game as well, which removes the objection that it was judged on the wrong task |
| fitted combinations against the lottery answer direction | **+0.067 to +0.096** | above the level only one feature in a hundred reaches, so the fitting located the answer direction |
| fitted combinations against the lottery push | -0.013 to +0.031 | below the level, so they are not push-like on this game |
| fitted combinations against the ultimatum push | **+0.184 to +0.226** | above the one in a hundred level of 0.126, the only positive identification in the whole exercise |
| fitted combinations against the ultimatum answer direction | -0.049 to -0.064 | they point away from it on this game |
| rebuilt readout direction against the answer part | **+0.269** | the dictionary can represent the answer part |
| the same against the letter part | +0.037 | it barely reaches the ordinary level on the letter part |
| unexplained share of the rebuilt direction | 96 percent | the rebuilding fails because what it is mostly matching is the letter part, which is not in the dictionary |

### Step four, what the steering did

On the lottery the edit is applied at every position at a strength of 16. On the ultimatum it
is applied at the last position only, in units of the typical size of the model's internal
state, which was measured at 21.12.

| measurement | value | what it means |
|---|---|---|
| lottery, spread of the unmodified answers | 9.23 | the quantity every intervention is measured against |
| lottery, spread after ten-feature steering | **0.92** | the model has almost stopped telling a good gamble from a bad one |
| lottery, share of the response left by the readout direction | **0.062** | it removed almost all of it |
| lottery, share left by the ten-feature combinations | 0.092 to 0.096 | the same |
| lottery, share left by the dense vectors | 0.129 to 0.143 | the same |
| lottery, share left by the preference adapter | 0.156 | the same |
| lottery, share left by random directions of that size | **0.505 to 0.605** | the control preserved three to six times more than the treatment did |
| lottery, closeness of each fit to a straight line | -0.95 to -1.000 | each intervention is very close to an exact flattening rather than a tendency |
| lottery, share left at strengths 1 and 4 and 16 | 0.611 and 0.215 and 0.062 | the flattening is caused by the strength, and 16 is where every comparison was made |
| ultimatum, unmodified average and spread | +1.632 and 7.860 | the starting point for the ladder |
| ultimatum, feature 31935 at the top strength | shift +1.814 with 1.174 left | it moved the answer while leaving the shape of the response almost unchanged, which is the profile of a push |
| ultimatum, readout direction at the top strength | 3.574 left, spread rises to 28.21 | a pure push by construction does the same thing more strongly |
| ultimatum, random live feature at the top strength | 0.977 left, shift +0.154 | it did nothing, which is the control behaving correctly |
| ultimatum, strength compared with the lottery | 16.9 against 16 | the strength per position is close to the same, so the difference between the two games is where the edit lands rather than how large it is |

---

## 18. What would come next, in order

The first task is to rerun the ultimatum steering while keeping the individual trial values,
which takes 52 minutes and converts the strongest suggestive result into a measured one.

The second task is to retrain the anchors on the lottery prompts so that a trustworthy pure
push anchor exists for that game as well. That takes about two hours.

The third task is to repeat the lottery placement at strengths one and four, where the model
still responds to the payoffs at all.

The fourth task is to stop matching interventions by their size and start matching them by
how much they change behaviour. On this project's own measurements the strengths needed to
produce an equal behavioural change differ between directions by a factor of about 150, so
matching on size compares quantities that are not comparable.