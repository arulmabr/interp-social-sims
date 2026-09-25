# The SAE anchor work, notes to be read aloud

These notes assume no prior knowledge of the project. Every term is explained at the point
where it first matters. Every number quoted here was produced by a script in this repository
and is recorded in the project's register of results alongside the script that made it.

---

## 1. The question behind all of this

A large language model can be made to behave differently by reaching inside it while it runs
and adjusting one of its internal quantities. The claim usually attached to that is a claim
about mechanism. If the quantity being adjusted has been labelled "willing to take risks" and
the model then takes more gambles, the natural conclusion is that the model's attitude to
risk has been changed.

There is a cheaper explanation that predicts exactly the same observation. The adjustment may
simply be making the model more likely to type one particular word, with nothing about risk
involved anywhere.

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

The comparison is the calibration of a thermometer. Before a thermometer is
trusted to report the temperature of a patient it is placed in melting ice and then in
boiling water. Those two temperatures are known without needing the thermometer. If the
instrument reports them correctly then its reading on the patient can be believed. If it
reports melting ice as thirty degrees then nothing it says about the patient matters.

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
layer of the model this state is simply a list of eight thousand one hundred and ninety two
numbers. This list is called the residual stream. Think of it as the model's working notes at
that point in its processing.

The model used throughout is called Llama-3.3-70B-Instruct. It was loaded from a local copy
of its weights on the cluster. It was never accessed over the internet.

---

## 4. What a sparse autoencoder is

A sparse autoencoder is a separate and much smaller network whose only job is to rewrite that
list of eight thousand numbers as a combination of simpler parts, with only a handful of
those parts active at any moment. The abbreviation SAE is used for it from here on.

The intuition is a recipe. A finished dish can be described as a list of measurements of
every chemical it contains, which is accurate and completely unreadable. It can instead be
described as one onion and two cloves of garlic and a pinch of saffron. The second
description is a combination of a small number of named ingredients drawn from a large
pantry. The sparse autoencoder is an attempt to build that pantry for the model's internal
state.

The pantry used here has sixty five thousand five hundred and thirty six entries. Each entry
is called a feature and each feature has its own direction, which is again a list of eight
thousand one hundred and ninety two numbers. Three thousand six hundred and thirty two of
those entries turn out to be dead. A dead entry is one whose direction is entirely zeros.
Every dead entry is excluded from everything that follows.

Steering with a feature means taking that feature's direction and adding a multiple of it to
the model's running internal state while the model is generating its answer.

---

## 5. Where every ingredient came from

The dictionary of features is a published file, released by the company Goodfire for layer
fifty of this particular model. It was downloaded from the public model repository at a
fixed published version rather than at whichever version happened to be current. Fixing the
version matters because it means anybody repeating this work receives the identical file. The
file is about four and a third gigabytes.

That version was not chosen freshly. It was read out of the existing experiment's own source
code so that both pieces of work use the same dictionary.

The prompts came from two places. The lottery prompts are the four hundred and thirty two
already used by the earlier steering experiment. The ultimatum prompts are the one hundred
and twenty from this project's own responder grid.

---

## 6. What Expected Parrot and EDSL are, and why they never appear here

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
to a locally loaded copy of the model. The only thing obtained from Goodfire is the dictionary
file, which can be downloaded and checked and pinned to a revision like any other file.

---

## 7. The first step, building the answer direction

### What was done

The first anchor is called the readout gradient. A gradient is simply the direction of
fastest increase. If you are standing on a hillside then the gradient is the direction in
which the ground rises most steeply.

Here the quantity being increased is the odds that the model gives one answer rather than the
other. So the readout gradient is the adjustment to the model's internal state that most
efficiently pushes the written answer from one option toward the other. By construction it
has nothing to do with preferences. It is the shortest route to changing what gets typed.

It was computed at two depths inside the model, referred to as layer forty eight and layer
fifty, and averaged across prompts.

### Why it was done twice for every prompt set

A model can favour a particular answer. It can also separately favour whichever option
happens to be printed second. Those are different things and they are easily confused.

To keep them apart the gradient was computed once for each of the two possible orders in
which the options can appear. The two results were then combined in two ways. Adding them
gives the part that the two orders have in common, which cannot depend on the ordering and so
must be about the answer itself. Subtracting them gives the part that reverses when the order
reverses, which must be about position or labelling rather than about the answer.

### How the two are compared

The comparison is reported as a cosine. A cosine is a single number between minus one and
plus one that says how closely two directions agree. Plus one means they point the same way.
Zero means they are unrelated. Minus one means they point in exactly opposite directions.

Picture two arrows drawn from the same point. A cosine of plus one means the arrows lie on
top of each other. A cosine of zero means they are at right angles. A cosine of minus one
means one arrow is the reverse of the other.

### What was found

On the lottery the two orders gave a cosine of minus zero point eight eight nine at layer
forty eight and minus zero point eight nine three at layer fifty. The part common to both
orders had a length of nine point one two eight, while the part that reverses had a length of
thirty seven point six eight two.

On the ultimatum game the same computation gave plus zero point nine five three and plus zero
point nine five six. There the common part had a length of eighteen point four two one and
the reversing part only two point eight six nine.

### What that means

On the lottery the two orders come close to cancelling each other out. The explanation is the
answer format. The lottery prompts ask the model to reply with a single letter, either A or
B, and which letter stands for the gamble changes from prompt to prompt. So the thing being
measured flips its meaning when the ordering flips, and the direction flips with it.

The ultimatum prompts ask for the word Accept or the word Reject. Those words keep their
meaning no matter which option is printed first, so nothing flips and the two orders agree.

On a prompt that asks for a bare letter, about four parts in five of the readout direction is
about which character gets typed rather than about what that character stands for. Any measurement taken against an
undecomposed version of that direction is therefore mostly measuring alignment with letter
identity.

Within a single ordering the individual prompts agreed with
their own average at zero point eight five one, which means the direction is a consistent
thing rather than an average of unrelated noise.

The lottery computation took eleven minutes and sixteen seconds. The ultimatum computation
took five minutes and thirty four seconds.

---

## 8. The second step, building the pure push

### What was done

The second anchor is a set of extra weights added to the model and trained so that the model
behaves like an agent whose only difference from normal is a constant push toward one answer.
The same amount is added on every single trial regardless of the amounts of money involved.
This kind of small trainable addition is called an adapter.

Three adapters were trained together on identical data with an identical schedule. One is a
reference with nothing changed. One has the constant push. One has a genuine preference
shifted instead.

### Why a reference adapter exists at all

If the pushed adapter were compared against the plain unmodified model then the comparison
would mix two different things together. It would
mix the effect of the push with the effect of the model having been taught to behave like a
decision making agent at all. Comparing the pushed adapter against a reference adapter that
received the same training without the push removes the second effect and leaves only the
first.

### How the anchor is turned into a direction

An adapter is a collection of weights. It has no direction in it that could be compared with
a feature. So its direction has to be measured rather than read off. The same prompts were
run twice. The first run used the reference adapter and the second used the pushed adapter.
The average change in the model's internal state between the two runs was recorded. That average change is the
adapter's displacement and it lives in the same space as the feature directions, so the two
become comparable.

### What was found

The size of the push that was built in is zero point six in units of the answer log-odds,
which is defined in the next section.

On the ultimatum prompts the measurement recovered plus zero point four six two of that
planted zero point six, which is about seventy seven percent. The displacement had a length of
six point five one two.

On the lottery prompts the same measurement recovered minus zero point zero two two, which is
indistinguishable from nothing at all. The preference adapter came out at minus zero point two
eight five, which is the wrong sign entirely.

### Why the lottery result is a failure rather than a finding about the model

These adapters were trained on prompts with different wording from the lottery prompts used
here. The reading itself was sound, because the unmodified model measured this way agreed
with the experiment's own recorded baseline at a correlation of zero point nine five seven.
The adapters were also clearly doing something, because the spread of the model's answers
dropped from twelve point four five to four point three six under them.

What failed to survive the change of wording is the planted difference. The displacement
lengths tell the same story. The pushed adapter moved the internal state by three point zero
seven three and the preference adapter by two point five two one, which are close to each
other when two changes of genuinely different kinds should not be.

An adapter trained on one phrasing does not carry its planted meaning to another phrasing. Comparisons against the ultimatum version of this anchor can be
believed. Comparisons against the lottery version cannot.

---

## 9. Two terms that appear in every result from here on

### Log-odds

When the model has finished reading a prompt it holds a probability for each possible next
word. The log-odds is a way of writing the balance between two of those probabilities as a
single number. A log-odds of zero means the two options are equally likely. A positive number
means the first option is favoured and a negative number means the second is. The further
from zero, the more lopsided the model's preference between the two words.

The reason for using log-odds rather than a plain probability is that it does not get stuck
near the ends. A probability cannot go above one hundred percent, so once a model is very
confident the probability stops moving even when the underlying pressure keeps growing. The
log-odds keeps growing, which makes it a better ruler.

### The null

Whenever a number is reported for how closely a feature matches an anchor, that number is
meaningless without knowing what an ordinary feature would score. So two thousand features
were drawn at random from the dictionary and put through the identical comparison.

The intuition is a lottery. Being told that somebody holds a winning ticket means nothing
until you are told how many tickets were sold. The random draw plays the role of counting the
tickets.

Two levels are quoted. The ninety fifth percentile is the score that only one random feature
in twenty beats. The ninety ninth percentile is the score that only one in a hundred beats.
Anything below those levels is doing no better than a feature picked out of the pantry
blindfolded.

---

## 10. The third step, placing the features against the anchors

### What was done

Three kinds of direction were compared against both anchors on both games.

The first kind is the individual features we name and steer with in the paper. Feature one
hundred and eighty four is labelled "willing to take risks or make sacrifices for a goal".
Feature four thousand two hundred and thirty seven is labelled "executing potentially risky
operations that require caution". Feature thirty one thousand nine hundred and thirty five is
labelled "altruistic and selfless behavior or intentions". These were chosen by reading the
labels.

The second kind is combinations of ten features whose weights were fitted numerically rather
than chosen by reading labels.

The third kind is an attempt to rebuild the readout direction itself out of ten features.

This step needed no model at all. It is arithmetic performed on the dictionary file.

### What was found on the lottery

Against the answer part of the readout direction the null sits at zero point zero three three
for one feature in twenty and zero point zero five six for one in a hundred.

Feature one hundred and eighty four scored minus zero point zero zero one. Feature four
thousand two hundred and thirty seven scored plus zero point zero zero four. Feature thirty
one thousand nine hundred and thirty five scored plus zero point zero zero four.

The fitted ten feature combinations scored between plus zero point zero six seven and plus
zero point zero nine six.

The attempt to rebuild the readout direction scored plus zero point two six nine.

### What was found on the ultimatum game

Against that game's own answer direction the null sits at zero point zero two eight and zero
point zero three eight. Feature thirty one thousand nine hundred and thirty five scored plus
zero point zero one three.

Against that game's pure push anchor the null sits at zero point zero seven seven and zero
point one two six. The same feature scored minus zero point zero four four. The fitted
combinations scored between plus zero point one eight four and plus zero point two two six.

### What all of that means

The three features we actually steer with score below the level that one random
feature in twenty reaches. This holds against every anchor on both games. It holds for the
altruism feature even when it is measured against the anchor built from the ultimatum game
rather than from the lottery, which removes the obvious objection that it was being judged on
the wrong task. Choosing a direction by reading its label produced directions with no
measurable relationship to anything the anchors represent.

The fitted combinations do better. On the lottery they align with the answer direction above
the level that only one random feature in a hundred reaches. On the ultimatum game they align
instead with the pure push anchor, scoring up to plus zero point two two six against a
one in a hundred level of zero point one two six.

It is the only positive identification anywhere in this work. Vectors that were fitted on the lottery in order to imitate a decision making
agent turn out, when examined on the social task, to point at the direction of a constant
push toward one answer. That is a statement about what they are rather than a statement about
what they failed to be.

### A number that was previously unexplained

We had reported that rebuilding the readout direction out of ten features left ninety six
percent of it unaccounted for, and had described this as a poor approximation without being
able to say why. The decomposition explains it. The readout
direction on those prompts is mostly the letter identity part. The dictionary can represent
the answer part reasonably well at plus zero point two six nine but barely reaches the null on
the letter part at plus zero point zero three seven. The rebuilding fails because the
component it is mostly trying to match is simply not in the pantry.

---

## 11. The fourth step, measuring what the steering actually does

### Why pointing is not enough

Everything in the previous step is about where directions point. That is not the same as what
they do. Two directions can point similarly and have very different effects on behaviour.

### What was done

For every steering condition the change in the model's log-odds was compared against its
unsteered value using a straight line fit. The slope of that line carries the information.

The intuition is the difference between a volume knob and a mute button. If an intervention
adds something without touching how the model responds to the amounts of money on offer, then
the slope is zero and the model is still listening to the payoffs. If the intervention
removes that responsiveness entirely then the slope is minus one and the model has been
muted. What is left over, which is one plus the slope, is the share of the payoff signal that
the measurement still has to work with.

### What was found on the lottery

The unsteered spread of the model's answers was nine point two three. After steering with the
ten feature combination it was zero point nine two.

The share of signal remaining was zero point zero six two for the readout direction, between
zero point zero nine two and zero point zero nine six for the ten feature combinations, and
between zero point one two nine and zero point one four three for the dense vectors.

Random directions of the same size retained between zero point five zero five and zero point
six zero five.

The straight line fits were almost exact. The measure of how closely the points follow the
line ran between minus zero point nine five and minus one, where minus one means every point
lies on the line.

### What that means

Every one of these interventions flattens the model's response toward a constant, and the fit
to a straight line is close enough that little else is happening. The model has almost stopped distinguishing between a good gamble and a
bad one.

The comparison with random directions is what decides how much the rest can be believed. The directions under test
destroyed between three and six times more of the signal than randomly chosen directions of
the same size did. A situation in which the control preserves the measured quantity better
than the treatment does is not a situation in which anything can be concluded about the
treatment.

The cause is the strength. The identical direction retains zero point six one one at strength
one, zero point two one five at strength four and zero point zero six two at strength sixteen.
Strength sixteen is where we made every comparison in the original experiment.

### What was found on the ultimatum game

Here the steering was generated fresh because the earlier experiment never covered this game.
The strengths were expressed in units of the typical size of the model's internal state at
that layer, which was measured at twenty one point one two.

The altruism feature shifted the answer by plus one point eight one four at the highest
strength while leaving the shape of the response almost unchanged, with a retention figure of
one point one seven four.

The readout direction at the same strength gave a retention figure of three point five seven
four and raised the spread of the answers from seven point eight six to twenty eight point
two one.

A randomly chosen live feature gave a retention figure of zero point nine seven seven and
moved the average answer by plus zero point one five four. Both of those are close enough to
no change that the feature can be said to have done nothing.

### What that means

A retention figure above one means the model responded more sharply rather than less. So
nothing was flattened on this game.

The altruism feature moved the answer by one point eight one four while changing the shape of
the response by seventeen percent. That is the signature of a push toward one answer rather than a change in what the
responder considers a fair split. The readout direction, which is a pure push by
construction, did the same thing more strongly, raising the spread of the answers from seven
point eight six to twenty eight point two one.

The two games differ because of where the adjustment is applied rather than how large it is.
The strength applied at each position is close to the same in both cases, sixteen in one and
sixteen point nine in the other. The lottery conditions apply the adjustment at every position in the prompt while the
ultimatum conditions apply it only at the final position. The flattening is therefore a
property of applying an adjustment everywhere at once, and results from the two arrangements
should never be combined.

---

## 12. How this setup compares with the one we already use in the paper

Our own steering procedure is described in the appendix of the paper. The two agree on the
model and the dictionary and the features. They differ in how the steering is applied and how
the answer is read, and those differences decide what each one can claim.

### What the two have in common

Both use the same model, which is Llama-3.3-70B-Instruct.

Both use the same dictionary of features, the sparse autoencoder published for layer fifty of
that model.

Both reach into the model at the same depth, which is layer fifty.

Both steer with the same features. In the paper we use feature one hundred and eighty four and
feature four thousand two hundred and thirty seven for the lottery and feature thirty one
thousand nine hundred and thirty five for the ultimatum game. Those are exactly the features
placed against the anchors in these notes.

So the disagreement between the two is not about which model or which dictionary or which
features. It is about how the steering is applied and how the answer is read.

### The first difference is where the work happens

In the paper our runs are sent to a service operated by Goodfire. We name a feature and give a
strength and the service returns the model's reply. The steering itself happens on somebody
else's machine.

The work in these notes downloads the published dictionary file and runs everything on the
project's own hardware. The steering is performed by code in this repository that can be read
line by line.

This matters for a practical reason. The strength we send to the service is a number between
zero and one, and the service's interpretation of that number is not published. It is
possible to record what the number achieved, because the logs show that a strength of one half
drove the targeted feature from outside the ten most active features to a level of one hundred
and seventy five, against ninety eight for the strongest feature when nothing is steered. But
it is not possible to reconstruct the rule that turned one into the other. Running locally
removes the question entirely, because the code performing the edit is the code you wrote.

### What a position is, in concrete terms

A prompt is not one thing to the model. It is a sequence of tokens, and the model holds a
separate internal state at each one. A position simply means one of those token slots.

Here is the tail of a real ultimatum prompt. The whole thing is one hundred and twenty one
tokens long and it ends like this:

| position | token | what it is |
|---|---|---|
| 114 | end of turn | closes the scenario text |
| 115 | start of header | the model's turn begins |
| 116 | assistant | names whose turn it is |
| 117 | end of header | |
| 118 | blank line | |
| 119 | Answer | the word Answer |
| 120 | : | the colon, and the final position |

The one hundred and fourteenth token closes the scenario text. The next four are the marks
that tell the model its turn has begun. The one hundred and nineteenth token is the word
Answer and the one hundred and twentieth is the colon after it.

That colon is the final position. It is the last token of the prompt and the point at which
the model has read everything and is about to produce its first word. The answer is read
from exactly there, by comparing the probability the model gives to one option word against
the probability it gives to the other.

So applying the adjustment at the final position means adding the direction to the model's
internal state at that colon and nowhere else. The model reads the entire scenario normally
and is nudged only at the instant of committing to an answer.

Applying it at every position means adding it at all one hundred and twenty one tokens. The
model reads the size of the offer and the consequence of refusing through an internal state
that has already been altered.

### The second difference is where the edit lands

The controller we use in the paper applies its adjustment at every position in the prompt. The
configuration field that would restrict it to particular positions is left empty, which means
no restriction.

The ultimatum runs in these notes apply the adjustment only at the final position of the
prompt, which is the moment just before the model commits to an answer.

The strength per position is close to the same in the two arrangements. What differs is how
many positions receive it. Section eleven shows that this is not a small matter. Applying the
adjustment everywhere flattens the model's response to the amounts of money almost completely,
while applying it at the last position alone does not flatten it at all. Results from the two
arrangements should never be combined into one comparison.

### The third difference is how the answer is read

In the paper we let the model write a reply and then read the choice out of the text. A helper
library picks whichever of the two option names appears.

The work in these notes reads the answer from the model's own probabilities at the moment of
answering, without letting it write anything. The measure used is the balance between the
probability of one option word and the probability of the other.

Reading the probabilities is the more sensitive of the two. A written reply gives one
observation, and to see a small shift you need many agents. The probabilities give a graded
quantity on every single trial, so a shift that would be invisible in the text is visible
immediately. That sensitivity is what makes the anchor measurements possible at all. The cost
is that a probability is not the same thing as what the model would actually have written, and
a separate check in this project found the two giving different answers often enough that
neither can stand in for the other.

### The fourth difference is what question is being asked

This difference is not one of engineering.

In the paper we ask whether steering a feature changes the behaviour. We answer yes, and the
answer is correct.

These notes ask what kind of change it was. They do that by building two changes whose nature
is known in advance and asking where the feature sits relative to them. That question cannot
be answered by watching behaviour move, however carefully, because a push toward a word and a
change of preference both move behaviour.

So the two setups are not competing accounts of the same experiment. In the paper we establish
that the lever does something. The work here asks what the lever is connected to, and for the
three features we name, it finds no measurable connection to either of the two things it could
sensibly be connected to.

---

## 13. A figure from the neighbouring method, and why it is not the same claim

There is a figure in the project showing the calibration of the other method. It is often read
as evidence about the question these notes are asking. It is not evidence about that
question, and the reason is set out below.

### What the figure shows

The figure concerns the other steering method used in the project, which is called a probe. A
probe is a direction found by training a small classifier to separate the internal states that
precede one answer from those that precede the other. It is a different way of obtaining a
direction from the sparse autoencoder route described above.

Before a probe is used it is calibrated. Calibration means searching for the strength at which
the probe moves the model's behaviour to a chosen point. The chosen point here is the
switching point, which is the amount of money at which the agent becomes equally likely to
take the gamble or to take the certain sum. So the researcher says in advance that the agent
should switch at one hundred and six tokens, and the search hunts for the strength that
achieves it.

The figure asks whether that hunt succeeded. Each dot is one calibration target. Its position
from left to right is where the agent was aimed and its position from bottom to top is where
the agent actually ended up. The straight line running corner to corner is where a dot would
sit if the aim were perfect. Distance from that line is the calibration error measured in
tokens.

### Why this particular view was drawn

Our released data reports the strength that the search returned for each target. That is the
inverse view and it is much weaker than it looks, because a search returns a number whether or
not it actually arrived anywhere. Reporting the strength it settled on says what the procedure
did rather than whether the procedure worked.

The forward view answers the question directly. It goes back to the raw counts of how many
agents chose each option at each amount of money, with forty agents at every level, finds the
amount at which the choice curve crosses one half, and compares that to the target. Nothing is
taken on trust from the search.

### What was found

On the lottery game ten targets were set, spaced from thirty tokens up to two hundred. At the
deeper of the two positions inside the model the average miss was two point one three tokens
and the worst single miss was four point five tokens. At the other position the average miss
was two point five seven tokens and the worst was five tokens.

On the ultimatum game four targets were set, from thirty tokens up to sixty. The average miss
was one point one five tokens at the first position and one point eight tokens at the second.

### What that does and does not establish

It establishes that the probe steering is accurate. When the procedure aims the agent at a
switching point of one hundred and six tokens the agent switches at one hundred and four and a
half. Across a range that spans nearly two hundred tokens the aim is off by about two on
average. As a piece of engineering the aim is accurate and it should be reported that way.

It does not establish what inside the model was changed. Landing on a target switching point says the intervention moved behaviour to the right
place. It says nothing about whether the model's valuation of money changed or whether the
model was simply pushed toward typing a particular word. Recall the person from the opening
section who was told to answer with whatever was printed on the left. Their switching point
could be moved to any chosen value with enough pressure, and their attitude to risk would
never have entered into it.

The gap between hitting a behavioural target and having changed the thing you named is the
gap the anchors close. The calibration figure shows the aim is good. The
anchor work asks what was actually moved, and for the features examined in these notes the
answer is that nothing distinguishable from a randomly chosen direction was moved at all.

---

## 14. What this adds up to

Four things are established.

The readout direction on a prompt that asks for a bare letter is about four parts in five
about which character gets typed. The identical computation on a prompt that asks for a word
gives the opposite balance. This is a property of how the question is asked rather than a
property of the model.

The three features we steer with cannot be distinguished from randomly chosen features by any
of the anchors on either game.

Feature combinations that were fitted numerically do carry structure. On the lottery they
match the answer direction. On the ultimatum game they match the pure push anchor.

At the strength we use throughout the original experiment every intervention removed more than
eighty four percent of the model's responsiveness to the payoffs, while randomly chosen
directions of the same size removed far less.

---

## 15. What is deliberately not being claimed

The lottery placements are comparisons of direction rather than of effect, and pointing is
not doing.

The altruism feature behaving like a push is consistent with the evidence but not established
by it. The ultimatum run recorded summaries for each strength rather than the individual trial
values, so the formal attribution could not be computed. Correcting that is a rerun of the
same fifty two minutes with the individual values kept.

Nothing here shows that the dictionary is incapable of representing a preference. The lottery
result is equally consistent with the strength having removed the payoff response before any
preference had a chance to appear.

The pure push comparisons on the lottery rest on an anchor whose planted meaning did not
survive the change of wording, and they should be read as unavailable rather than as null.

---

## 16. What would come next, in order

The first task is to rerun the ultimatum steering while keeping the individual trial values,
which takes fifty two minutes and converts the strongest suggestive result into a measured
one.

The second task is to retrain the anchors on the lottery prompts so that a trustworthy pure
push anchor exists for that game as well. That takes about two hours.

The third task is to repeat the lottery placement at strengths one and four, where the model
still responds to the payoffs at all.

The fourth task is to stop matching interventions by their size and start matching them by
how much they change behaviour. On this project's own measurements the strengths needed to
produce an equal behavioural change differ between directions by a factor of about one
hundred and fifty, so matching on size compares quantities that are not comparable.
