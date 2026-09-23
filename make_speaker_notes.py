"""Build the speaker notes document.

Navigation: every section uses a built-in Heading style, so the Google Docs
outline pane and the Word navigation pane both populate. The contents list at
the top carries internal hyperlinks to bookmarks on each heading.

Voice: passive throughout. No first person.

Run:  python make_speaker_notes.py
"""
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from docx.shared import Inches, Pt, RGBColor

INK = RGBColor(0x1A, 0x1A, 0x1A)
MUTED = RGBColor(0x5A, 0x5A, 0x5A)
ACCENT = RGBColor(0x6B, 0x3A, 0x8C)
LINK = RGBColor(0x1A, 0x4C, 0x8C)

RISK = Path("/home/guna23/shrey/risk")
TRACKB = Path("/home/guna23/shrey/risk-trackB")
OUT = RISK / "Speaker_Notes_Evidence.docx"

doc = Document()
sec = doc.sections[0]
sec.page_width, sec.page_height = Inches(8.5), Inches(11)
sec.top_margin = sec.bottom_margin = Inches(0.7)
sec.left_margin = sec.right_margin = Inches(0.8)

normal = doc.styles["Normal"]
normal.font.name = "Calibri"
normal.font.size = Pt(11)
normal.font.color.rgb = INK
normal.paragraph_format.space_after = Pt(7)
normal.paragraph_format.line_spacing = 1.18

for lvl, size, col in ((1, 17, INK), (2, 13, INK), (3, 11.5, RGBColor(0x33, 0x33, 0x33))):
    st = doc.styles[f"Heading {lvl}"]
    st.font.name = "Calibri"
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = col
    st.paragraph_format.space_before = Pt(20 if lvl == 1 else 12)
    st.paragraph_format.space_after = Pt(6)
    st.paragraph_format.keep_with_next = True

_bk = [0]
TOC = []


def heading(text, level=1, nav=True):
    """A real Heading style so both outline panes populate, plus a bookmark."""
    p = doc.add_heading(text, level=level)
    if nav:
        _bk[0] += 1
        name = f"sec{_bk[0]}"
        start = OxmlElement("w:bookmarkStart")
        start.set(qn("w:id"), str(_bk[0]))
        start.set(qn("w:name"), name)
        end = OxmlElement("w:bookmarkEnd")
        end.set(qn("w:id"), str(_bk[0]))
        p._p.insert(0, start)
        p._p.append(end)
        TOC.append((text, name, level))
    return p


def link_para(text, anchor, indent=0.0):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.left_indent = Inches(indent)
    h = OxmlElement("w:hyperlink")
    h.set(qn("w:anchor"), anchor)
    r = OxmlElement("w:r")
    rPr = OxmlElement("w:rPr")
    for tag, val in (("w:color", "1A4C8C"), ("w:u", "single")):
        e = OxmlElement(tag)
        e.set(qn("w:val"), "single" if tag == "w:u" else val)
        rPr.append(e)
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "21")
    rPr.append(sz)
    r.append(rPr)
    t = OxmlElement("w:t")
    t.text = text
    r.append(t)
    h.append(r)
    p._p.append(h)
    return p


def para(text, size=11, color=INK, bold=False, italic=False, after=7):
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(after)
    r = p.add_run(text)
    r.font.size, r.font.color.rgb, r.bold, r.italic = Pt(size), color, bold, italic
    return p


# Spoken lead-ins. Nothing in this document is a stage direction, because the
# whole of it is meant to be read out as written and understood on hearing.
LEAD = {
    "Open with": "",
    "The analogy": "Here is a way to picture it. ",
    "Land this": "The point to take away is this. ",
}


def cue(label, text):
    """A spoken paragraph. The label picks a transition and is never printed."""
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(7)
    r = p.add_run(LEAD.get(label, "") + text)
    r.font.size, r.font.color.rgb = Pt(11), INK
    r.bold = (label == "Land this")
    return p


def bullet(text):
    p = doc.add_paragraph(style="List Bullet")
    p.paragraph_format.space_after = Pt(4)
    r = p.add_run(text)
    r.font.size, r.font.color.rgb = Pt(10.5), INK
    return p


def figure(path, width_in, cap):
    doc.add_picture(str(path), width=Inches(width_in))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    para(cap, size=9, color=MUTED, italic=True, after=11)


def table(headers, rows, note=None):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(headers):
        cell = t.rows[0].cells[i]
        cell.text = ""
        r = cell.paragraphs[0].add_run(h)
        r.bold, r.font.size = True, Pt(9)
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            r = cells[i].paragraphs[0].add_run(str(v))
            r.font.size = Pt(9)
    if note:
        para(note, size=9, color=MUTED, italic=True, after=10)
    return t


# ================================================================ title
ttl = doc.add_paragraph()
r = ttl.add_run("Speaker Notes")
r.bold, r.font.size, r.font.color.rgb = True, Pt(24), INK
para("Interpreting and Steering LLM Agents for Social Simulations. Three figures, the evidence behind "
     "them, and the argument they support.", size=12, color=MUTED, after=10)
para("This is written to be read out as it stands. Every sentence is meant to be spoken and "
     "understood on hearing, so numbers are written out in words and every idea is introduced before "
     "it is used. Every figure and every table is described in full, so that a listener who cannot "
     "see the screen still follows the argument.", size=10.5, color=MUTED)
para("One definition comes first, because every figure depends on it. The switching point is "
     "the size of the risky reward at which an agent becomes equally likely to gamble or to take the "
     "sure fifty tokens. The gamble pays out half of the time, so expected value is equal at one "
     "hundred tokens. A switching point above one hundred means a premium is being demanded to "
     "gamble, which is risk aversion. A switching point below one hundred means a premium is being "
     "paid to gamble, which is risk seeking.", size=10.5, after=14)

toc_anchor = doc.add_paragraph()
rr = toc_anchor.add_run("Contents")
rr.bold, rr.font.size, rr.font.color.rgb = True, Pt(13), INK
toc_placeholder_index = len(doc.paragraphs)

# ================================================================ 2
heading("1. The problem being solved", 1)
cue("Open with", "When an agent is steered toward the gamble, what changed inside it is unknown.")
para("This is the point the whole argument rests on. At least three different things could "
     "have happened inside the model. The agent's dislike of risk might have changed. The agent might "
     "have been pushed toward writing the word risky with its preferences left untouched. The way the "
     "agent reads the size of the payoff might have changed.")
para("All three produce choice curves that look the same. Every steering figure in this literature is "
     "consistent with all three explanations at once.")
cue("The analogy", "A thermostat reading twenty degrees says nothing about whether the heating is "
    "running. It could be a warm day or a working boiler or a broken sensor. A second instrument is "
    "needed before those can be told apart.")
cue("Land this", "No steering method is being claimed here. The question is which steering claims are "
    "actually licensed by the evidence, and the answer requires an instrument that does not yet exist.")

# ================================================================ 2
heading("2. Prompting does not behave like a dial", 1)
cue("Open with", "The review asked for the prompting curves that had been left out. They exist, and "
    "they do not support the claim they were omitted from.")

heading("2.1 What was done and how", 2)
para("One thing should be said before anything else, because the paper as a whole is about steering "
     "and a listener will reasonably assume this figure shows some. It does not. Nothing here "
     "touches the model's internals at all. Every one of these nine conditions is a change to the "
     "words in the prompt, and the model itself is identical throughout. What varies is only what "
     "the agent is asked and what it is shown.")
para("All nine conditions of the prompting ladder were analysed on the local stack. Naming them is "
     "worth the time, because the flat result later depends on what each one actually contained.")
bullet("The first is the plain baseline. It states the two options and asks for a choice, with no "
       "further instruction of any kind.")
bullet("The second is the persona. It adds one sentence as a system prompt, which reads that the "
       "agent is inclined to take advantageous risky opportunities. The user prompt is unchanged "
       "from the baseline.")
bullet("The third is chain of thought. It adds an instruction to think step by step about the "
       "expected value of each option and about the agent's own attitude toward risk, and then to "
       "decide.")
bullet("The fourth is few shot. It places six worked examples in front of the question and adds no "
       "reasoning instruction. Each worked example is a complete lottery of the same kind, showing a "
       "risky reward against the sure fifty tokens, followed by the answer that was given for it. In "
       "the lottery version the six examples use risky rewards of one hundred and thirty two and "
       "thirty three and one hundred and sixty six and ninety nine and fifty one and sixty seven. The "
       "agent reads those six and then faces a lottery of its own.")
bullet("The remaining five combine few shot with chain of thought. They are identical to one another "
       "except in one respect, which is how many of the six worked examples end with the gamble being "
       "taken rather than the sure amount.")
para("Those five deserve spelling out, because the phrase two of six carries the whole design. In "
     "the first of them not one of the six examples takes the gamble, so every example the agent "
     "reads chose the sure fifty tokens. In the second, two of the six take the gamble and the other "
     "four take the sure amount. In the third it is three of six and in the fourth it is four of six. "
     "In the last, all six take the gamble, so every example the agent reads is a bold one.")
para("The reasoning behind the design is that an agent shown more bold examples should itself become "
     "bolder, and should do so in a graded way rather than all at once. The fraction of examples that "
     "take the gamble is therefore the quantity plotted along the horizontal axis of the right panel, "
     "and those five conditions are the dose response the work set out to demonstrate.")
para("The lottery arm covers all nine conditions across thirty five reward levels with forty "
     "agents at each point, which is twelve thousand six hundred individual choices. The "
     "ultimatum arm covers the same nine conditions across seventeen offer levels with forty "
     "agents at each point, which is a further six thousand one hundred and twenty. Every "
     "curve and every interval in this figure rests on those eighteen thousand seven hundred "
     "and twenty choices.")
para("The word agent needs a caution attached, because it promises more than it delivers here. "
     "The forty agents at each point are not forty different people with different backgrounds. "
     "They are the same prompt sent forty times, distinguished only by an identifier reading "
     "A one through A forty that is placed in the system message. Nothing else about them "
     "differs. In the persona conditions a single further sentence is added, and it is the same "
     "sentence for all forty.")
para("That also gives the phrase equally likely a concrete meaning. At each tested reward level "
     "the probability of gambling is simply the count of draws that chose the gamble divided by "
     "forty. Equally likely means twenty of the forty chose it. The switching point is the "
     "reward at which the curve passes that halfway mark, and because it usually falls between "
     "two tested levels it is read off by interpolation, so the count at the levels either side "
     "might be something like eighteen of forty below it and twenty three of forty above.")
para("Forty draws is not many, and it is worth knowing what that buys. The proportion can only "
     "move in steps of one fortieth, which is zero point zero two five, so the curve is a "
     "staircase rather than a smooth line. At the halfway mark the standard error on that "
     "proportion is about eight percentage points, which is roughly three agents either side of "
     "twenty. A ninety five percent band is about six agents either side, so anything from "
     "fourteen to twenty six of the forty is consistent with the agent being genuinely "
     "undecided. That is the main reason the switching point intervals in this figure are "
     "around eight tokens wide, and it is why a five and a half token spread across the middle "
     "of the dose response cannot be called a trend.")
para("What that means for the figure is that the spread across agents is sampling variation from "
     "a temperature of zero point seven rather than variation across a population. The intervals "
     "are therefore intervals on how stable the model is when asked the same question many "
     "times. They are not intervals on how much simulated people differ from one another, and "
     "they should not be described as though they were.")
para("Each condition was run without modification. The switching point was obtained from a logistic "
     "fit to the choice curve rather than by interpolation, and the confidence interval came from a "
     "cluster bootstrap, which means resampling whole groups of related prompts rather than single "
     "prompts, so that prompts sharing a template are not counted as separate evidence. The distinction matters and is returned to below, because the figure's own "
     "reference line uses interpolation while the reported table uses the logistic fit. The design variable is the "
     "demonstration mix, which is written as rho. It is the fraction of the six worked examples in "
     "the prompt whose answer is the bold one.")
para("One correction became visible during the analysis and is reflected in the axis. With six "
     "demonstrations the only achievable fractions are multiples of one sixth. The condition labelled "
     "as a quarter is in fact two of six and the condition labelled as three quarters is in fact four "
     "of six. The figure therefore plots the realised fraction rather than the intended label.")

figure(RISK / "figures" / "s1_7_ladder.png", 6.6,
       "Figure 1. Left panel: the full choice curve for every prompting condition. Right panel: the "
       "switching point plotted against the realised demonstration mix.")

heading("2.2 What the left panel shows", 2)
para("The horizontal axis is the risky reward in tokens and runs from about ten to about one hundred "
     "and eighty. The vertical axis is the probability that the gamble is chosen and runs from zero "
     "to one. Each plotted series is one prompting condition and each marker is one reward level.")
bullet("Blue with round markers is the plain baseline. It sits at zero until about one hundred tokens "
       "and then rises almost vertically to near certainty.")
bullet("Salmon with triangles is the risk seeking persona. It rises slightly earlier than the "
       "baseline, so the persona buys a little more willingness to gamble.")
bullet("Red with plus markers is chain of thought. This is the one that matters most. It never reaches "
       "certainty at all. It wanders between about zero point two and zero point five across the "
       "whole upper half of the grid.")
bullet("Dark yellow with crosses is few shot demonstration without chain of thought. It tracks the "
       "baseline closely and reaches certainty just after one hundred tokens.")
bullet("Pale yellow dashed with left pointing triangles is few shot combined with chain of thought "
       "where none of the six demonstrations gambles. It stays near zero across the entire grid.")
bullet("Dark yellow dashed with hexagons is the same condition where all six demonstrations gamble. "
       "It rises near one hundred tokens and then holds at certainty.")
bullet("The grey dashed line comes from a different serving stack and is labelled reference only and "
       "not compared. It is drawn faint deliberately, so "
       "that the reader can see where that stack sits, and nothing is differenced against it, because "
       "the two stacks differ for reasons unrelated to prompting.")
bullet("The vertical dotted line at fifty tokens marks the sure amount. To its left the gamble cannot "
       "beat the sure option even in the best case.")
bullet("There is no separate ceiling line in this panel. The only reference line drawn here is the "
       "vertical one at fifty tokens. What can look like a horizontal dotted line near the top is the "
       "dose one hundred series itself, which sits flat at certainty across most of the grid.")

heading("2.3 What the right panel shows", 2)
para("The horizontal axis is the realised fraction of bold demonstrations and its label names the "
     "three interior mixes explicitly as two and three and four of six. The vertical axis is the "
     "switching point in tokens. Every point carries its ninety five percent confidence interval as a "
     "vertical bar.")
bullet("Dark yellow with round markers is the lottery switching point. It sits at about one hundred "
       "tokens at every demonstration mix and its intervals overlap across the whole range.")
bullet("Purple with square markers is the ultimatum switching point. It begins near forty eight "
       "tokens and eases to about thirty seven and then drops sharply to about ten at the final point.")
bullet("The horizontal dotted line labelled lottery baseline one hundred and three is the same stack's "
       "baseline switching point. Any lottery point resting on that line has not been moved at all. "
       "One caveat belongs with it. That line is computed by interpolation and evaluates to one "
       "hundred and two point nine, while the reported baseline in the table is the logistic fit at "
       "one hundred and six point eight. The two differ because they are two estimators and not "
       "because the data differ. Before the figure is published one estimator should be chosen and "
       "used in both places.")

heading("2.4 What the panels establish", 2)
para("The lottery dose response is flat. From the first non zero mix to the full mix the switching "
     "point moves between ninety six and one hundred and one point six. That is a span of five and a "
     "half tokens inside intervals about eight tokens wide. Four interior points that cannot be told "
     "apart from one another do not constitute a dose response.")
para("The one condition that behaves differently is the mix in which nothing gambles, and it does not "
     "move the switching point. It abolishes the switching point entirely. Only ten percent gambling "
     "is reached at the very top of the grid and one half is never crossed.")
para("Chain of thought moves the agent in the opposite direction to the one assumed. The switching "
     "point rises from one hundred and six point eight to one hundred and seventy five point seven. "
     "The difference is minus sixty nine tokens with an interval from minus eighty seven to minus "
     "fifty two that excludes zero. A request to reason step by step about expected value produces "
     "more risk aversion rather than more deliberation. That interval is reported in the "
     "S1.7 report. The per condition switching points are registered individually and the difference "
     "interval should be registered alongside them before it is quoted anywhere.")
cue("The analogy", "Imagine teaching boldness through six worked examples. Two bold examples and "
    "three and four all produce identical behaviour. Only all six, or none at all, changes anything. "
    "That is a switch thrown at the extremes rather than a dial that can be turned.")
cue("Land this", "The prompting knob the paper assumed to be graded is not graded. That claim is "
    "carried by this figure alone and is enough on its own. The broader claim that behaviour cannot "
    "identify mechanism is built across the next two sections and should not be asserted here.")

# ================================================================ 3
heading("3. What the probe direction actually is", 1)
cue("Open with", "The review asked for the standard steering baselines. Building them revealed "
    "something unexpected about the paper's own probe.")

heading("3.1 What was done and how", 2)
para("This figure contains no steering either, and the reason differs between its two panels. Panel "
     "A compares two ways of recording an answer on the ordinary unmodified model, so nothing is "
     "added to the activations anywhere in it. Panel B compares candidate steering directions to one "
     "another as vectors, by measuring the angle between them, and never applies any of them to the "
     "model. It is a statement about what these directions are rather than about what they do.")
para("Two terms are needed before this makes sense. A direction is a single vector in the model's "
     "internal activation space, and steering means adding some multiple of it to the activations "
     "while the model runs. The probe is one such direction, obtained by training a small classifier "
     "on the model's activations. What a probe actually changes when it is used for steering is not "
     "known in advance, and finding that out is the point of all of this.")
para("Two separate checks were carried out. The first asks whether the measuring instrument can be "
     "trusted. The second asks what the probe direction is once it is placed beside the standard "
     "alternatives.")
para("For the instrument check the logit readout was compared against free generation at the same "
     "grid points. The readout infers the choice from the probability the model assigns to each "
     "answer token. Free generation lets the model write its answer and then reads the answer from "
     "the text.")
para("For the geometry check the standard contrastive directions were built from the probe's own "
     "activations so that the comparison cannot be confounded by different training data. Difference "
     "of means is the simplest of these recipes, and it is worth describing in full because the "
     "result of this section turns on it. The model is run on a large set of lottery prompts and "
     "its internal activations are recorded each time. Those recordings are then sorted into two "
     "piles according to what the agent actually chose. One pile holds every occasion on which it "
     "took the gamble and the other holds every occasion on which it took the sure amount. The "
     "average is taken within each pile, which gives one point standing for the typical internal "
     "state when gambling and another standing for the typical internal state when playing safe. "
     "Subtracting the second from the first leaves an arrow pointing from one to the other, and "
     "that arrow is the direction. Adding it to the activations pushes the model along the line "
     "that separates the two behaviours.")
para("The appeal of the recipe is that it requires no training at all. It is one average subtracted "
     "from another. If two groups of points sit in different places, the line joining their centres "
     "is the most obvious thing that tells them apart, and this is simply that line. It is the "
     "recipe the published method calls Contrastive Activation Addition. It is one of the standard "
     "ways the field builds a steering direction and one of the baselines the review asked to see. "
     "The "
     "second recipe takes the first principal component of the centred activations, meaning the "
     "single direction along which those activations vary the most, and that is the published "
     "method called Representation Engineering. A ridge probe for the logarithm of "
     "the payoff was built alongside them as a direction that encodes payoff size by construction.")
para("A fourth direction is compared against these and needs its own explanation, because it is not "
     "a recipe of the same kind. The readout gradient is worked out rather than fitted. It asks, at "
     "a given prompt, which small change to the model's internal activations would most raise the "
     "probability that the next word is risky rather than safe, and it takes that change as the "
     "direction. It is therefore the most direct lever on the written answer that exists, and it is "
     "the natural thing to compare a probe against. If a probe were simply a device for making the "
     "model say one word rather than the other, it ought to look like this direction.")
para("One idea makes the rest of this readable, and it is the one people find least intuitive. "
     "Similarity between two directions is measured by the cosine of the angle between them. A "
     "cosine of one means they point the same way, zero means they are at right angles, and minus "
     "one means they point in opposite directions.")
para("The awkward part is that what counts as a large cosine depends entirely on how many "
     "dimensions there are. On a flat page, where there are only two directions to choose from, "
     "two arrows picked at random are quite often roughly aligned, and the typical cosine between "
     "them is about zero point seven. In three dimensions it falls to about zero point five eight. "
     "In one hundred dimensions it is about zero point one. In the eight thousand one hundred and "
     "ninety two dimensions of this model it is about zero point zero one one. The more "
     "independent ways there are to point, the more certain it becomes that two arbitrary choices "
     "end up almost at right angles to each other.")
para("That typical value is what is meant by the null here. It is what two directions with nothing "
     "whatever to do with each other would score, and it is one divided by the square root of the "
     "number of dimensions. Drawing four thousand random pairs and measuring them directly gives "
     "an average of about zero point zero zero nine, which agrees with that formula.")
para("Every bar in the right panel is divided by the null before it is drawn. A bar of length one "
     "therefore means no more alignment than two unrelated directions would have, and it is the "
     "line everything has to beat before it means anything at all. The reason for reporting it "
     "this way is that raw cosines in a space this large are all small, so they are impossible to "
     "judge without knowing what small means here.")

figure(RISK / "figures" / "g4_summary.png", 6.6,
       "Figure 2. Panel A compares the two instruments against each other. Panel B places the choice "
       "probe among the standard steering directions.")

heading("3.2 What panel A shows", 2)
para("The vertical axis is the crossing point in tokens and runs from zero to three hundred. The "
     "crossing point is the switching point under another name. It is the reward at which the agent "
     "becomes equally likely to gamble or to take the sure amount, and it is called a crossing here "
     "because it is where the choice curve crosses one half. The point of this panel is that two "
     "different ways of recording the same choice put that crossing in two different places.")
para("The horizontal axis carries three groups. Each group is one way of reading a choice out of "
     "the text the model wrote, and the reason there are three is that the model rarely answers "
     "with a bare word. It usually reasons first, and that reasoning mentions both options along "
     "the way. A response might weigh up the risky option at length before settling on the safe "
     "one. Where in the text the reader looks therefore changes the answer that gets recorded.")
para("Legacy is the rule the original work used. It scans the whole response and takes the last "
     "occurrence of either word as the answer, so a response that considers the gamble and then "
     "declines it can be recorded as having taken it, depending on which word happens to appear "
     "last. Strict takes the first of the two words instead. The name refers to holding the "
     "model to its opening commitment rather than letting later discussion override it, and not "
     "to any extra requirement that the answer be clear.")
para("The words being searched for are the two option labels themselves, which in this task are "
     "safe and risky. First mention means the first time either word appears in what the model "
     "wrote, and last mention means the final time either appears. A real response makes the "
     "problem obvious, and the following is quoted from the stored generations rather than "
     "invented. It comes from the trial at a risky reward of sixty tokens.")
para("The model opened by announcing that it would work out the expected value of each option. It "
     "then wrote, as item one, safe option, fifty tokens for sure, expected value fifty tokens. "
     "Then, as item two, risky option, a fifty percent chance of sixty tokens and a fifty percent "
     "chance of nothing. And there the response stops.")
para("It stops because the generation limit was sixty four tokens, and the model had spent them "
     "restating the problem. No choice is made anywhere in it. Legacy takes the last label "
     "mentioned and records this as risky. Strict takes the first and records it as safe. Both "
     "have produced an answer from a response that contains none, and they have produced "
     "opposite answers, purely because the model happened to list the safe option first and the "
     "risky option second.")
para("A second response from the same set shows the other kind of behaviour. At a reward of "
     "twenty tokens one agent wrote a single word and nothing else. That word was safe. Here all "
     "three codings agree, because only one label is present and it is plainly the answer. Five hundred and seventy six of the eighteen hundred responses are bare answers "
     "of that kind, and the decision coding finds a stated choice in seven hundred and forty "
     "three of them altogether.")
para("So the two kinds of response divide the set. Either the model answers in one word, in "
     "which case every coding agrees, or it starts reasoning and gets cut off, in which case "
     "legacy and strict invent opposite answers and decision declines. Legacy and strict "
     "disagree on forty one percent of all trials, and not one response anywhere uses the "
     "final answer wording the prompt asked for.")
para("That response is not a specially chosen one, and it is worth saying so before anyone asks. "
     "Of the seven hundred and thirty seven responses where the two codings disagree, seven "
     "hundred and thirty five contain exactly two labels in the order safe then risky, and the "
     "remaining two contain the same two in the same order with one repetition. Ninety nine "
     "percent of them are the same numbered list, opening with the safe option as item one and "
     "the risky option as item two, cut off before any conclusion. The example is the ordinary "
     "case rather than an unusual one.")
para("One further count settles the mechanism, and it is more specific than it first appears. Of "
     "the seven hundred and thirty seven disagreements, every single one has strict reading "
     "safe and legacy reading risky. There is not one case in the other direction.")
para("The reason is that the model writes in two different shapes, and only one of them can "
     "produce a disagreement. Some responses open with a numbered list that gives the safe "
     "option as item one and the risky option as item two, and the limit cuts them off just "
     "after item two. Those are the ones that disagree, because the first label is safe and "
     "the last is risky. Other responses open instead by announcing that the expected value of "
     "the risky option will be worked out and compared against the safe option, and they "
     "return to the risky option as they calculate. In those the first and last label are both "
     "risky, so the two codings agree with each other even though the response still never "
     "decides anything. Four hundred and seventeen of the reasoning responses take that second "
     "shape.")
para("One check settles what these labels are. In not one of the twelve hundred and twenty four "
     "reasoning responses does the first label appear after any arithmetic. In every case where "
     "a calculation is present at all, the label comes first and the calculation follows. In "
     "sixty four percent of them the response is cut off before any arithmetic appears. The "
     "last label is almost never at the end either, falling in the closing characters in only "
     "one percent of cases, which means the text carries on past it into the calculation and "
     "then stops.")
para("So the order of events is always the same. The model names the two options while setting "
     "the problem up, then begins computing, then runs out of room. Both of the labels that "
     "legacy and strict rely on are produced before any reasoning has happened, as part of the "
     "restatement of the question. Neither is a conclusion, and no conclusion is ever reached.")
para("That is what makes the middle of the reward range the worst part of the figure. Where the "
     "model answers in one word, the label is a decision. Where it starts reasoning, the label "
     "is a framing word taken from the setup. Between roughly sixty five and one hundred "
     "tokens both kinds of response occur at the same reward, so the curve at those points is "
     "a blend of real choices and words that were never choices, in a proportion set by how "
     "many agents happened to skip the arithmetic.")
para("Which of the two openings a given trial gets is sampling noise and nothing more. About two "
     "thirds of responses take the numbered list and one third take the other form, and that "
     "ratio holds at every reward level with no trend. Looking across the forty agents, the "
     "spread in how often each one takes the first form has a standard deviation of zero point "
     "zero nine four, where pure coin flipping at the same rate would give zero point zero "
     "eight six. No agent has a leaning of its own. The generation temperature is seven "
     "tenths, and that is the whole of the explanation.")
para("So the claim to make is the narrow one. Disagreement is produced by the order in which a "
     "truncated list happens to name the options, and agreement between the two codings is no "
     "evidence that either has found a decision, because they agree most readily on responses "
     "that mention the risky option twice while deciding nothing at all.")

para("Decision is different in kind from the other two. It records an answer only when the "
     "response actually states a choice and declines to record anything at all when it does not. "
     "That distinction matters more than the gap between first and last mention, because legacy "
     "and strict will both assign a choice to a response that never made one. Whichever word "
     "they happen to find gets treated as the answer. For that reason the decision coding is the "
     "one the underlying analysis treats as the comparison of record, and it is the safest of "
     "the three to quote.")
para("The three are shown side by side so that the disagreement in this panel cannot be blamed on "
     "a badly chosen parser. Whichever of the three is used, the readout and the written answer "
     "still land in very different places.")
bullet("The purple bar in each group is where the logit readout places the crossing. It is the same "
       "height in all three groups at about two hundred and thirty four tokens, because the readout "
       "does not depend on how the text is parsed.")
bullet("The dark yellow bar in each group is where free generation places the crossing under that "
       "coding. It is about sixty three tokens under legacy and about one hundred and ten under "
       "strict and about sixty three under decision.")
bullet("The annotation above each pair is the distance between the two bars, and it reads thirty "
       "four steps and twenty five steps and thirty four steps. A step here means one rung of the "
       "reward ladder the agent was tested on. The risky reward was not varied continuously. It "
       "was offered at fixed values five tokens apart, so one step is five tokens.")
para("Where the figure of two hundred and thirty four comes from is worth a sentence, because it "
     "is the anchor for everything else in this panel. The risky reward was offered at forty "
     "five fixed levels running from twenty tokens up to two hundred and forty, five tokens "
     "apart. At each level the readout gives the probability that the model prefers the gamble, "
     "and that probability rises as the reward rises. The crossing is the reward at which it "
     "passes one half, found by drawing a straight line between the two tested levels that sit "
     "either side of it, which here are two hundred and thirty and two hundred and thirty five.")
para("One point of confusion is worth heading off, because the two figures use different reward "
     "ladders and nothing on either of them says so. The prompting figure runs its horizontal "
     "axis from about ten tokens to about one hundred and eighty, because that is the ladder "
     "the local stack was tested on. This panel uses the ladder the probe work was run on, "
     "which runs from twenty to two hundred and forty. Two hundred and thirty four is "
     "comfortably inside the second of those and would be far outside the first. Anyone "
     "carrying the number from one figure to the other will reach the wrong conclusion, and "
     "the ultimatum arm uses a third ladder again, running from ten to one hundred.")
para("If anyone asks why the ladders differ, the honest answer is that no reason is recorded "
     "anywhere. The three bodies of work were built separately and each fixed its own reward "
     "range, and the repository documents that they differ without documenting why. Every "
     "ladder does share the same five token spacing and the same sure amount of fifty tokens, "
     "so expected value parity sits at one hundred in all of them, which is the one thing that "
     "makes any comparison possible at all.")
para("The differing ranges are the smaller half of the problem. The stacks also disagree on "
     "behaviour. The baseline switching point is one hundred and two point nine on the local "
     "stack against one hundred and twenty seven point six on the hosted one, and the same "
     "persona instruction moves the local stack to ninety seven point three while moving the "
     "hosted stack to nineteen point eight. That is the same prompt producing an effect five "
     "times larger on one stack than the other. This is why the prompting figure draws the "
     "hosted baseline as a labelled reference line and differences nothing against it, and it "
     "is why numbers should not be carried between these figures.")
para("The arithmetic is exact. At two hundred and thirty the readout gives a probability of zero "
     "point two two, and at two hundred and thirty five it gives zero point five six. One half "
     "lies about eighty two percent of the way between those two, and eighty two percent of a "
     "five token step is four point one tokens, which put on top of two hundred and thirty "
     "gives two hundred and thirty four.")
para("What the shape of that curve looks like matters more than the number, and it should be "
     "described honestly rather than summarised as strong risk aversion. The readout gives a "
     "probability of zero, to two decimal places, at every reward from twenty tokens up to "
     "about one hundred and thirty. It then produces small and unsteady values through the "
     "middle of the range. Near the top it becomes erratic, reading zero point five at two "
     "hundred and fifteen, then zero point one at two hundred and twenty, then zero point "
     "three eight, then zero point two two, then zero point five six, and finally zero point "
     "one eight at the last level tested.")
para("So this is not a curve that rises and settles above one half. It crosses one half twice "
     "in the last three steps of the ladder and ends below it. The crossing being reported is "
     "the first of those two, found by interpolating between two neighbouring points whose "
     "probabilities differ by a third. The right way to describe the readout here is that it "
     "almost never prefers the gamble anywhere on the tested range and becomes unstable at the "
     "top, rather than that it measures an agent demanding two and a third times fair value. "
     "Reading it as a preference would be giving a number to something that does not have a "
     "stable value, and that is a stronger criticism of the readout than the one the panel "
     "was drawn to make.")
para("The arithmetic is worth doing once out loud, because it is the same in all three groups. "
     "The readout places the crossing at two hundred and thirty four tokens, and it places it "
     "there in all three groups, because the readout never looks at the text and so cannot care "
     "how the text is parsed. Under the strict coding the written answers place the crossing at "
     "one hundred and ten. The difference is one hundred and twenty four tokens, and since the "
     "ladder moves in steps of five, that is twenty five rungs. The same subtraction under "
     "legacy gives one hundred and seventy one tokens, which is thirty four rungs, and decision "
     "gives almost exactly the same as legacy.")
para("The claim this panel is making should be stated carefully, because it is narrower and "
     "sturdier than it first looks. The claim is not that any particular one of these three "
     "numbers is correct. It is that the disagreement between the readout and the written "
     "answers survives every reasonable way of reading the text. That is the entire reason three "
     "codings are shown rather than one. A single coding would invite the reply that the parser "
     "was simply chosen badly.")
para("Strict is the coding most favourable to the readout, and it is the number a sceptic would "
     "reach for, so it is worth meeting directly. Even under strict the two instruments sit "
     "twenty five rungs apart, against a standard set in advance of one rung. The most generous "
     "reading available still misses the agreement threshold by a factor of twenty five. Nothing "
     "in the argument depends on deciding which coding is best.")
para("Why strict lands at one hundred and ten while the other two land near sixty three follows from "
     "this. Strict takes the first label mentioned, and the numbered list names the safe option "
     "first, so strict records caution in exactly those cases where nothing was decided. Legacy "
     "takes the last and records the opposite on the same responses.")
para("Whatever the explanation turns out to be, it does not rescue the readout. The figure to "
     "quote is the thirty four rungs given by the decision coding, which is the one the "
     "underlying analysis treats as the comparison of record and the only one of the three that "
     "declines to invent an answer when the model did not give one. Quoting twenty five instead "
     "would be choosing the most flattering of three numbers, all of which fail the same test.")
para("Those numbers are what make the panel damaging rather than merely untidy. Under the legacy "
     "coding the readout places the crossing at two hundred and thirty four tokens and free "
     "generation places it at sixty three, a gap of one hundred and seventy one tokens, which is "
     "thirty four rungs of the ladder. The standard set in advance for calling the two "
     "instruments in agreement was that their crossings should fall within one rung of each "
     "other. They are thirty four apart under two of the three codings and twenty five apart "
     "under the third. The disagreement is not close to the tolerance. It is more than an order "
     "of magnitude outside it, and it is the whole width of the tested range.")

heading("3.3 What panel B shows", 2)
para("The horizontal axis is the cosine with the choice probe expressed in multiples of the null. "
     "The vertical axis lists six directions and each bar carries its own value as a label. The "
     "numbers shown are for layer fifty, and the layer forty eight figures sit within a few percent "
     "of them throughout, so nothing in the ordering depends on which layer is chosen.")
para("It is worth walking through where one of these numbers comes from, because every bar is built "
     "the same way. The cosine between the choice probe and the difference of means direction is "
     "zero point one nine two. Two unrelated directions in this space would score about zero point "
     "zero one one. Dividing the first by the second gives seventeen point four, which is the length "
     "of the longest bar. So the bar does not say the two directions are nearly the same. It says "
     "they are about seventeen times more aligned than two arbitrary directions would be, which is "
     "a statement about how far above chance the similarity sits rather than about how large it is.")
bullet("Difference of means, which is the direction the Contrastive Activation Addition method "
       "produces, is the longest "
       "bar at seventeen point four times the null. It is drawn in teal to mark it as the probe's "
       "nearest neighbour.")
bullet("First principal component, which is the direction the Representation Engineering method "
       "produces, sits at nine "
       "point eight times the null.")
bullet("Ridge on the logarithm of the payoff sits at eight point seven times the null.")
bullet("The reward probe, which is a second payoff related direction, sits at six point eight times "
       "the null.")
bullet("The readout gradient sits at only two point eight times the null and is drawn in grey. This "
       "is the lever on the written answer described above, so a low bar here says the probe is not "
       "simply a device for making the model say one word rather than the other.")
bullet("A random direction sits at zero point one times the null and confirms that the scale is "
       "calibrated correctly.")
bullet("The vertical dotted line at one marks the null itself. A bar reaching that line carries no "
       "more similarity than two arbitrary directions would.")
para("The block on the right states what each panel establishes. For panel A it states that sampled "
     "generation remains the primary measure, because the readout and free generation locate the "
     "switch in different places, which makes the readout a check on text rather than a substitute "
     "for it. For panel B it states that the choice probe is a contrastive direction, because it sits "
     "nearest to difference of means and far from the gradient of the answer logit, which is a "
     "different object entirely.")

heading("3.4 What the panels establish", 2)
para("Panel A says the cheap instrument and the expensive instrument disagree by thirty four grid "
     "steps. Any result resting on the readout alone requires the generated text to confirm it.")
para("Panel B says the probe's nearest neighbour among the standard directions is the contrastive "
     "baseline, and that it shares less with the lever that actually flips the "
     "answer. The wording here needs care. A cosine of about zero point one nine makes difference of "
     "means the closest direction by some distance, and it is not close in absolute terms. The "
     "defensible claim is that the probe is closest to difference of means. The claim that the probe "
     "is close to difference of means is not supported and should not be made.")
cue("The analogy", "This is a ranking and not a match. Several standard recipes for building a "
    "steering direction were compared against the probe, and the question was which one it most "
    "resembles. The contrastive recipe came first and the lever that drives the answer came near "
    "the bottom. That ordering is the finding. It does not mean the probe and the contrastive "
    "recipe are the same thing, because none of the similarities is large in absolute terms. It "
    "means that if the probe has to be described as one of the known recipes, the contrastive one "
    "is the closest description available.")
cue("Land this", "This is the second piece of evidence that mechanism cannot be read off behaviour. "
    "The direction being steered with is not the object it was assumed to be.")

# ================================================================ 4
heading("4. Planting changes whose nature is known in advance", 1)
cue("Open with", "If three explanations cannot be told apart, the remedy is to stop guessing and "
    "build them. Plant a change of known design and then check whether the method recognises it.")

heading("4.1 What was done and how", 2)
para("This section is also not about steering in the sense the paper uses the word, and the "
     "distinction is worth keeping clear. The adapters described below change the model by training "
     "a small set of extra weights, not by adding anything to the activations while it runs. The "
     "gradient anchor is a direction and could be used for steering, but in this section it is only "
     "computed and compared. Steering in the proper sense arrives in Section six.")
para("Two kinds of anchor were built on Llama 3.3 70B Instruct. The first is a single direction and "
     "the second is a set of trained adapters. Both are referred to again in Section six, where "
     "the first is called the readout anchor and one of the adapters is called the bias anchor.")
para("The first is the readout gradient anchor. It is the direction that most directly pushes the "
     "written answer from safe to risky. It was computed at layer forty eight and at layer fifty, and "
     "separately for each of the two possible option orders so that a position effect could be "
     "separated from an answer effect. The two orders agree at a cosine of about zero point seven "
     "three, which means the direction is mostly about the answer itself rather than about where the "
     "answer sits on the page. A smaller order dependent component does remain and is reported.")
para("The second kind of anchor uses adapters, so that word needs a meaning first. An adapter is a "
     "small set of extra weights trained on top of a frozen model so that the model behaves in some "
     "chosen way. Training one is cheap and it leaves the original model untouched. The technique is "
     "called low rank adaptation.")
para("This second anchor deserves the most time. Three synthetic decision makers "
     "were invented with rules chosen in advance. One is a reference agent. One is the same agent "
     "made slightly more willing to gamble. One is the same agent given a plain habit of picking one "
     "option regardless of the payoff. A small adapter was then trained for each so that the model "
     "chooses the way that invented agent would choose.")
para("The next point is the one most often misunderstood, so it is worth stating precisely. The anchor "
     "is not any single adapter. The anchor is the difference between the shifted adapter and the "
     "reference adapter, because that difference is a change whose size was set deliberately.")
para("Whether that worked is called cloning, and it is measured only on prompts the adapter never "
     "saw during training. An adapter counts as a faithful copy when its choices correlate with the "
     "target agent at at least zero point nine five and when its calibration slope lies between zero "
     "point nine and one point one. All three passed, at correlations of zero point nine nine one and zero "
     "point nine nine five and zero point nine nine three. That is the sense in which the adapters "
     "reproduce their target agents closely. A model was successfully taught to imitate a decision "
     "maker whose rules were already known.")

figure(TRACKB / "figures" / "B3_contrasts_plain.png", 6.3,
       "Figure 3. The two planted contrasts. Planted is the change that was built. Measured is what "
       "the method recovered. The interval is the ninety five percent confidence interval on that "
       "measurement.")

heading("4.2 What the table in the figure shows", 2)
para("The figure is a table carrying a title and four columns and two rows. Each element is worth "
     "naming explicitly.")
bullet("The title states the finding directly. The anchor is the contrast, and only one of them "
       "resolves.")
bullet("The column headed CONTRAST names which difference is being measured. The first row is the "
       "preference adapter minus the reference adapter. The second row is the bias adapter minus the "
       "reference adapter.")
bullet("The column headed PLANTED is the size of the change that was built into the model, expressed "
       "in the units of the choice log odds. The preference row carries zero point zero three zero "
       "two. The bias row carries zero point six.")
bullet("The column headed MEASURED is what the method recovered. The preference row carries zero "
       "point zero four seven four. The bias row carries zero point four nine six eight.")
bullet("The column headed ninety five percent interval is the uncertainty attached to each "
       "measurement. The preference interval runs from minus zero point zero two nine one to plus "
       "zero point one two three nine. The bias interval runs from plus zero point four one seven "
       "eight to plus zero point five seven five nine.")
para("The thing to notice is the sign of the lower end of each interval. The preference interval "
     "begins below zero, so at this stage the measurement could not distinguish the planted "
     "preference change from no change at all. The bias interval lies entirely above zero, so the "
     "planted bias is clearly detected. Reading the two rows together is what gives the figure its "
     "title.")
cue("The analogy", "A letter is being weighed on a bathroom scale. The scale is not broken and will "
    "happily report the weight of a person. It simply cannot resolve something as light as a letter, "
    "because the scale's own wobble is heavier than the letter is. The bias change is the person and "
    "the preference change is the letter.")

heading("4.3 A correction that belongs with this figure", 2)
para("These numbers came from two hundred and forty prompts and from an assumption that the two "
     "adapters carry independent imprecision. That assumption turned out to be wrong by design, "
     "because the protocol gives all three adapters the same data order and the same random seed, so "
     "their imprecisions are correlated at about zero point five eight. Measuring that correlation "
     "rather than assuming it away, and using all one thousand and sixteen available prompts, narrows "
     "the interval considerably and moves it clear of zero.")
para("If this figure is carried into the paper it should be regenerated from the corrected values. "
     "The shape of the problem shown here is right. The size of the problem shown here is no longer "
     "the final word.")
cue("Land this", "A change can be planted and a large one can be recovered. The small one sat at the "
    "detection limit of the method itself, which is precisely where a calibrated instrument should be "
    "expected to struggle.")

# ================================================================ 5
heading("5. The result that reverses the conclusion", 1)
cue("Open with", "The obvious question followed. Is the method wrong, or is the effect simply too "
    "small? It was settled by planting a bigger one.")

heading("5.1 What was done", 2)
para("One more term is needed first. The minimum detectable change is the smallest change the "
     "method is designed to be able to detect. It is a property of the method rather than of any "
     "particular result, and from here on it is the unit in which errors are reported. An error of "
     "one third of a minimum detectable change means the estimate landed a third of the way from the "
     "truth to the edge of what the method can resolve.")
para("A second preference anchor was built at three times the minimum detectable change instead of "
     "one times it. The shift parameter moves from zero point eight eight to one point one eight "
     "rather than to zero point nine eight. Everything else is identical. It was trained "
     "independently from a fresh initialisation rather than continued from any existing adapter, and "
     "cloning quality is unchanged at a correlation of zero point nine nine four.")
para("One fact about the order of events matters here, because it "
     "is what makes the change defensible. The decision to change the gate statistic was taken on "
     "structural grounds and was written down and committed before the three times result was read. "
     "It was not chosen after seeing which statistic gave the better answer.")
para("The statistic was also changed, and the reason is worth explaining because it is the heart of "
     "the matter. The planted change is a curvature change. Its effect on the choice varies with the "
     "payoff and changes sign across it. Averaging that effect is close to meaningless, because a "
     "perfectly faithful adapter could average to nearly zero. The gate therefore fits the model to "
     "each adapter and compares the fitted preference parameters instead.")

table(["Anchor", "Planted", "Recovered", "Error", "Attributed to preference", "Gate"],
      [["One times the MDC", "0.1000", "+0.0874", "0.13 MDC", "0.268 with belief ahead at 0.346", "FAIL"],
       ["Three times the MDC", "0.3000", "+0.2987", "0.01 MDC", "1.000 with action rejected", "PASS"]],
      "Table 1. The same pipeline and the same recipe. The only difference is the size of the planted "
      "change.")

heading("5.2 What Table 1 shows", 2)
para("The table has six columns and two rows and every cell carries part of the argument.")
bullet("The column headed Anchor names which of the two planted preference changes is being reported. "
       "The first row is the original anchor placed exactly at the minimum detectable change. The "
       "second row is the new anchor placed at three times that size.")
bullet("The column headed Planted is the size of the shift built into the synthetic agent, measured "
       "in the units of the preference parameter. Zero point one is one minimum detectable change and "
       "zero point three is three of them.")
bullet("The column headed Recovered is the shift the estimator actually found when it fitted the two "
       "adapters separately and took the difference.")
bullet("The column headed Error is the gap between planted and recovered, expressed in units of the "
       "minimum detectable change. A value of zero point one three means the estimate landed about an "
       "eighth of a detectable change away from the truth.")
bullet("The column headed Attributed to preference reports the second step of the analysis. Having "
       "measured that something changed, attribution is the separate question of what kind of change "
       "it was. Five competing explanations are fitted and each receives a share of the evidence "
       "between zero and one. This column is the share going to preference and the bar for passing "
       "is zero point eight. The first row also names the explanation that beat it, which is the "
       "belief explanation. That one means the agent has changed how it reads the stated odds rather "
       "than how much it dislikes risk, and it matters here because it sits closest to preference.")
bullet("The column headed Gate is the verdict of the decision rule fixed in the plan, which requires "
       "both an accurate recovery and a correct attribution. Nothing is tagged as pre-registered yet, "
       "so that phrase should be avoided.")
para("What the table shows is a clean separation between two kinds of failure. Recovery is excellent "
     "in both rows. Attribution collapses in the first row and is perfect in the second. Since the "
     "only thing that changed between the rows is the size of the planted effect, the attribution "
     "problem is caused by size and not by any confusion that is built into the method.")

heading("5.3 What the table establishes, and what it does not", 2)
para("Two claims must be kept apart here, because collapsing them is the most likely way to lose "
     "the argument to a single question.")
para("The claim that is established is magnitude recovery. The estimator recovers the size of the "
     "planted change accurately at both sizes, with errors of about an eighth and about a hundredth "
     "of a minimum detectable change. That is a genuine validation and it holds regardless of "
     "anything the attribution step does.")
para("The claim about attribution needs its own evidence, and that evidence exists. The obvious "
     "objection is that a weight of one point zero on preference might simply be what this "
     "classifier always says. The control that answers it is the bias adapter, which was built to be "
     "a pure push toward one answer. Run through the same fit against the same reference adapter, the "
     "bias contrast returns preference zero point zero zero zero, with its weight going to format at "
     "zero point five one and action at zero point four nine. The attribution step is therefore "
     "specific in this setting. It gives a known preference change full weight and it gives a known "
     "bias none at all.")
para("What the table does not establish is attribution on real model directions, and Section 6, on where the probe lands, shows "
     "that a different fit on that different problem is not specific at all. Those are two separate "
     "fits against two different baselines and they must not be quoted as though they were one "
     "result. The safe formulation is that magnitude recovery is validated, that attribution is "
     "specific against the planted anchors, and that attribution on arbitrary real directions is not "
     "yet specific.")
cue("The analogy", "A kitchen scale rated to one gram will not reliably resolve a single grain of "
    "rice. Place three grams on it and it reads three grams exactly. The scale was never broken. It "
    "had been tested at precisely its rated limit, and conclusions were being drawn about the scale "
    "rather than about the load.")
cue("Land this", "A planted preference change is recoverable and correctly attributable by this "
    "pipeline, and the size it needs to reach has now been measured rather than assumed.")

# ================================================================ 6
heading("6. Where the probe lands against the anchors", 1)
cue("Open with", "With anchors that work, the probe can finally be placed against something whose "
    "meaning is known.")
para("This is the first point in these notes where steering actually happens. Everything up to here "
     "has either changed the prompt or trained extra weights or measured angles between vectors. "
     "Here each direction is genuinely added to the model's activations while it runs, which is the "
     "operation the paper means by steering, and the whole question is what that operation does.")
para("Two of the anchors built in Section four are used here, and it is worth saying plainly which "
     "ones, because the names change slightly. The readout anchor is the gradient anchor, the "
     "direction that most directly pushes the written answer from safe to risky. The bias anchor "
     "is one of the three adapters, the one trained to imitate a decision maker with a plain habit "
     "of picking one option whatever the payoff. Those two are the poles that everything else is "
     "measured against.")
para("The preference adapter is deliberately absent, and a listener who has just heard two sections "
     "about it will notice. At the time this comparison was run the preference contrast had not "
     "resolved, so it could not serve as a pole. Using an anchor whose own measurement is "
     "unresolved would put an unknown quantity on both sides of the comparison. The plan for the "
     "work has the preference anchor added to this table in a second pass, once its contrast "
     "resolves, and that pass has not been run. This is the single largest gap in the comparison "
     "and it should be stated rather than waited for.")

heading("6.1 What was done", 2)
para("Every direction was given a dose chosen so that it produces the same behavioural effect as the "
     "bias anchor, which is a shift of the switching point by ninety one tokens from two hundred and "
     "ten down to one hundred and nineteen. The dose is simply how much of a direction gets added, and "
     "a larger dose means a larger push. It was solved on one set of prompts called the calibration "
     "split and the comparison was then run on a separate set called the selection split, so that no "
     "measurement is reported on the same prompts that were used to tune it.")
para("Matching on behaviour rather than on vector length matters. The doses that produce "
     "the same behaviour differ by a factor of about one hundred and fifty across directions. A "
     "comparison at equal vector length would have compared very different amounts of intervention "
     "and would have been meaningless.")

table(["Direction", "Distance to the bias anchor", "Distance to the readout anchor", "Placed with"],
      [["Choice probe at layer 48", "0.540", "0.679", "the bias anchor"],
       ["Choice probe at layer 50", "0.440", "0.778", "the bias anchor"],
       ["Difference of means at layer 48", "1.211", "0.045", "the readout anchor"],
       ["Reward probe at layer 48", "1.172", "0.043", "the readout anchor"]],
      "Table 2. Distances measured in the space of the model free variance decomposition. Smaller "
      "means closer.")

heading("6.2 What Table 2 shows", 2)
para("The table has four columns and four rows and reports where each direction sits between the two "
     "anchors.")
bullet("The column headed Direction names what was steered with. The first two rows are the paper's "
       "own choice probe at each of the two layers. The last two rows are control directions included "
       "so that the comparison has something to calibrate against.")
bullet("The column headed Distance to the bias anchor is how far that direction sits from the adapter "
       "built to be a pure push toward one answer. A small number means the direction behaves like a "
       "push toward an answer.")
bullet("The column headed Distance to the readout anchor is how far the direction sits from the "
       "gradient that most directly drives the answer logit. That anchor turns out to load almost "
       "entirely on format.")
bullet("The column headed Placed with records which of the two anchors the direction ends up nearer "
       "to, which is simply whichever of the two preceding numbers is smaller.")
para("What the table shows is that the two anchors are far apart from each other, which is what makes "
     "any placement between them meaningful in the first place. The choice probe sits closer to the "
     "bias anchor at both layers and by a clear margin. The two control directions sit close to the "
     "readout anchor instead, which shows the measure is capable of separating directions rather than "
     "placing everything in one bin.")
cue("The analogy", "Two reference weights are placed on a bench, one clearly heavy and one clearly "
    "light. An unknown object is then weighed against both. It is useful only because the two "
    "references are far enough apart to tell them apart in the first place.")

heading("6.3 Three qualifications that belong with this", 2)
para("Three things qualify what has just been said. They are stated here rather than left to be "
     "asked about, because stating them is what makes the rest of it credible.")
para("The first is the most serious and it must be stated precisely, because a loose version of it "
     "contradicts what was just said. In this comparison, which fits each steered direction against the "
     "unmodified model as its baseline, the classifier returns preference with full weight for almost "
     "every direction. That includes directions that plainly are not preference changes. A classifier "
     "behaving that way cannot be used to label the probe, so in this comparison the work is being "
     "done entirely by the model free layer. That is the set of checks that need no model of the "
     "agent at all. They split the change into the part that is a constant push and the part that "
     "depends on the wording and the part that depends on the payoff. A constant push indicates a "
     "bias and a dependence on payoff indicates a preference change.")
para("This is not the same fit as the one used in Section 5, and the difference is what resolves the "
     "apparent contradiction. That earlier test is the anchor gate, meaning the pass or fail check "
     "applied to a planted change, which asks both whether the recovered size is close to the size "
     "planted and whether the change is attributed to the right explanation. The anchor gate fits one "
     "adapter against another adapter, and there the "
     "attribution is specific, giving the planted bias preference zero point zero zero zero. The "
     "probe comparison fits a steered real model against the unmodified real model, and there it is "
     "not specific. Attribution has been demonstrated to work against planted anchors and has not "
     "been demonstrated to work against arbitrary directions on the real model. Anyone who has read "
     "both of these will ask about it, so it is answered here directly.")
para("The second concerns the controls. Three of the four random directions could not be dosed to the "
     "target at all. They saturate the model into always choosing the sure option before they ever "
     "reproduce the required behavioural shift. The one surviving random control reached only twenty "
     "of the ninety one tokens required. The comparison therefore carries a much weaker null than it "
     "was designed to have.")
para("The fix is already prescribed in the plan and is worth naming precisely. "
     "The controls that saturate are isotropic random directions, and amendment A8 calls for "
     "covariance matched random directions drawn with the empirical activation covariance at that "
     "layer and matched in norm. The stated reason in the plan is exactly the behaviour observed "
     "here, which is that isotropic directions do very little at the norms used for steering, so "
     "beating them proves little. Rerunning the controls under A8 is the next step.")
para("The third concerns stability. One control direction changes which anchor it resembles between "
     "layer forty eight and layer fifty. The placement is more sensitive to the choice of layer than "
     "the agreement between the probe's own two layers would suggest on its own.")
cue("Land this", "The probe looks more like a push toward an answer than like a preference change. "
    "This is offered as the direction for the next experiment rather than as a finding, because the "
    "classifier that would certify it has just failed its own calibration test.")

# ================================================================ 7
heading("7. How this enters the paper", 1)
para("This section is the operational one. Each piece of evidence is mapped to the place in the "
     "current draft that it repairs or replaces, and then the restructure that turns the collection "
     "into an oral is set out.")
para("The draft referred to throughout is the current working version at iclr2027 in the project "
     "root, which runs to thirty two pages including the appendix. Its structure is an introduction "
     "and a related work section whose second part covers opening the black box, then a methodology "
     "section whose three parts are the prompting setting and the sparse autoencoder setting and the "
     "probe setting, then a results section split into interpretability and controllability with "
     "preference and capability tasks under each, then a discussion.")
para("The most useful hook is in the abstract itself. It states that the sparse autoencoder and "
     "probe techniques often outperform basic prompt based methods, although the advantage narrows "
     "when compared with more advanced prompting strategies such as few shot and chain of thought. "
     "Figure 1 of these notes measures exactly those two strategies. The advantage does not merely "
     "narrow against them. The few shot dose response is flat and chain of thought moves behaviour in "
     "the opposite direction. That sentence in the abstract is the single place where the new "
     "evidence has the most leverage, and it can be corrected without restructuring the paper.")

heading("7.1 The prompting ladder repairs a claim the paper already makes", 2)
para("The draft defines the prompting ladder in the prompting setting subsection of the methodology "
     "and reports only part of it. A dose response over the demonstration mix is specified there and "
     "the symbol for it appears nowhere else in the paper. Five hosted conditions were run on the "
     "lottery and three were reported.")
para("Figure 3 in the draft is titled performance of generative agents on preference tasks and "
     "carries temperature and prompting and steering together in one place. Figure 4 carries the "
     "ultimatum results under probe steering. The ladder bears on both, because it measures the "
     "lottery and the ultimatum under the same nine conditions.")
para("Figure 1 of these notes closes that gap directly, but it cannot replace Figure 3 and the reason "
     "matters. Figure 3 is the hosted stack and carries the temperature and steering results "
     "alongside the prompting ones. The ladder ran on the local stack. Replacing one with the other would drop the SAE result and would put two "
     "stacks on a single axis, which is precisely the comparison the audit rules out and which "
     "decision D16 already settled. The ladder should be added as its own figure or as an appendix "
     "panel, and Figure 3 should be kept and given intervals. The caption should state the two findings without "
     "softening. The dose response is flat across its whole interior range. Chain of thought raises "
     "the switching point by sixty nine tokens with an interval that excludes zero.")
para("The accompanying text in Section 4 should be rewritten from a comparative claim into a measured "
     "negative result. The current phrasing asserts that advanced prompting conditions behave in a "
     "particular way without curves behind it. The replacement asserts that they were measured and "
     "that the graded response the design assumed is absent. A reviewer who asked for the curves gets "
     "them, and the paper gains a finding where it previously had an unsupported assertion.")
para("The axis correction should be stated in the caption rather than buried. With six demonstrations "
     "only multiples of one sixth are achievable, so two of the five labelled doses were never "
     "realised as labelled. Declaring this openly costs one sentence and removes an obvious line of "
     "attack.")

heading("7.2 The geometry answers the missing baselines and reframes Section 3.3", 2)
para("The review notes that Inference Time Intervention is not compared against, alongside "
     "Contrastive Activation Addition and Representation Engineering and Activation Addition. Panel B "
     "of Figure 2 supplies three of those four as a geometric comparison and should sit in Section "
     "2.2 or early in Section 4 as a short subsection titled what the probe direction is. Inference "
     "Time Intervention remains uncompared and should be named as a limitation rather than left "
     "silent.")
para("Panel B also bears on Section 3.3 and Appendix B.4, where the probe is described in three "
     "different ways across the paper. The geometry gives a single operational description that "
     "replaces all three. The probe is a contrastive direction that lies close to difference of means "
     "and that carries substantial overlap with payoff magnitude and that is nearly orthogonal to the "
     "gradient of the answer logit. That sentence is defensible and is more informative than any of "
     "the three descriptions it replaces.")
para("Panel A belongs in the measurement or limitations discussion for a different reason, and the "
     "two should not be conflated. The provenance problem with Figure 4 and Figure 6 is the G2 "
     "finding that the released probe code does not reproduce the original run. That still requires a "
     "provenance statement and a figure labelled as a reconstruction, but panel A is not the evidence "
     "for it. Panel A is about whether the readout tracks generated text, which is a separate "
     "question.")
para("Panel A carries a sharper consequence that these notes should not soften. Every anchor result "
     "and the entire probe comparison are measured with the logit readout, and panel A says the "
     "readout does not track free generation. One sentence is required in the talk. The anchor "
     "results are statements about the readout instrument until they are confirmed by sampled "
     "generation. The related observation is more uncomfortable still. G4 found that the layer forty "
     "eight probe moves nothing in sampled generation, and yet Table 2 doses that same direction to a "
     "ninety one token shift on the readout. Those two facts have to be reconciled before the layer "
     "forty eight row is relied on at all.")

heading("7.3 The planted anchors become the paper's new contribution", 2)
para("Figure 3 and Table 1 have no existing home in the draft. They should not be appended to the "
     "existing results. The natural placement is a "
     "new subsection at the head of the results section, before the interpretability and "
     "controllability parts, because the controllability claims are the ones that depend on the "
     "instrument this work validates. Placing it after those claims would read as an afterthought "
     "rather than as their foundation.")
para("The section should proceed in the order the work actually happened. State the identification "
     "problem. Introduce the planted anchors as the remedy. Report that the large planted bias is "
     "recovered and that the small planted preference change is not, at the detection limit. Then "
     "report that the same pipeline recovers and correctly attributes a change three times that size. "
     "Close by stating the measured sensitivity threshold as a property of the method.")
para("The ordering matters for how the result reads. Presenting only the passing case would look like "
     "a tuned demonstration. Presenting the failure first and then the pass reads as a calibration "
     "curve, which is what it is, and it gives the paper a quantity that no competing paper currently "
     "reports.")
para("The claim this section can carry is a bounded one. Magnitude "
     "recovery is validated. Attribution is specific against the planted anchors and is not yet "
     "specific against arbitrary real directions. The plan anticipates exactly this state of affairs "
     "and directs that the frames be redesigned when both anchors pass, so the honest heading for "
     "this work is a calibration result and not a solved identification problem.")
para("A scheduling constraint applies on top of the scientific one. By the rule governing this "
     "work, results from the anchor track enter the submission only with the two gates passed and an "
     "author having read the report. The first gate failed and the second is mixed. On that rule "
     "Sections 5 and 6 do not enter the near term PDF at all, and belong to the revision that "
     "follows it.")

heading("7.4 The probe comparison belongs in future work and not in results", 2)
para("The placement of the probe against the anchors is the most interesting result in these notes "
     "and also the least defensible one. It is exploratory. It sits on the selection split. Its "
     "classifier fails its own calibration check. Three of four random controls could not be dosed.")
para("Putting it in the results section would invite exactly the criticism the rest of the paper is "
     "built to avoid. Putting it in future work, with the distances reported and the three "
     "qualifications stated plainly, converts a weakness into evidence of judgement. The sentence to "
     "aim for is that the probe appears to behave more like an answer bias than like a preference "
     "change, that the apparatus needed to establish this now exists, and that the confirmatory "
     "version awaits a working null band.")

heading("7.5 What has to change beyond adding figures", 2)
para("Three edits matter more than any figure placement.")
para("The first is the abstract, and the timing here is a trap worth naming. Rewriting it to promise "
     "a diagnosis and an instrument would read as a different paper from the registered abstract, "
     "which a conference can treat as grounds for rejection at submission. That reframing is the "
     "story for the later revision or for a different venue. It is not a change to make to the "
     "imminent PDF. What the imminent PDF can do is add the measured curves and correct the claims "
     "that the data contradict.")
para("The second is the framing of the probe. Every sentence that treats the probe as a discovered "
     "representation of risk preference should be rewritten to treat it as a contrastive direction of "
     "unknown content that the paper then sets out to characterise. This is a demotion of the probe "
     "and a promotion of the method, and it is the change that makes the negative results read as "
     "contributions rather than as damage.")
para("The third is the provenance statement. The released probe code does not reproduce the original "
     "run and the paper should say so in its own voice rather than leaving it to be discovered. A "
     "paper that declares its own reproducibility gap and supplies the reconstruction is in a far "
     "stronger position than one that is caught with it.")
heading("7.6 What has to come out to make room", 2)
para("None of this is free. The submission already has to lose about one and a half pages to meet "
     "the nine page limit, and the additions proposed above would add a figure and a section on top "
     "of that. A plan that does not say what leaves is not a plan.")
para("The ladder figure is the one addition that pays for itself, because it answers a reviewer "
     "request directly and replaces prose that currently asserts what the curves disprove. That prose "
     "can go. The geometry comparison is small and fits as a single panel with two sentences. The "
     "anchor work is the expensive item and, by the scheduling rule above, is not eligible for the "
     "near term PDF in any case, which resolves the budget question for now. Any figure that survives "
     "only because it was in the previous version should be examined before anything new is added.")

# ================================================================ 8
heading("8. The narrative for an oral", 1)

heading("8.1 The reframing", 2)
para("The current framing offers a method for interpreting and steering agents. The stronger framing "
     "offers a diagnosis of a measurement problem that the subfield shares, together with the "
     "instrument that exposes it and the sensitivity threshold of that instrument.")
para("The central claim is that behavioural steering results in language model agents are not "
     "currently identifiable. Moving an agent toward the gamble is equally consistent with a "
     "preference change and with an answer bias and with a change in payoff reading. The paper then "
     "shows that these alternatives are separable in principle, supplies the apparatus that separates "
     "them, and reports the effect size at which separation begins to work.")

heading("8.2 Why this reads as strength rather than as a negative result", 2)
para("The argument has a property that reviewers reward. It is falsifiable, and several of its own tests came back negative. "
     "The planted bias is recovered. The planted preference change "
     "fails at one times the detection limit and passes cleanly at three times it. The controls that "
     "should have been neutral break the model instead. Each of those is a fact that a less careful "
     "paper would never have discovered about itself.")
para("The strength of the claim has to be set at what the evidence carries and no higher. What is "
     "validated is that the size of a planted change is recovered accurately, and that the "
     "attribution step distinguishes a planted preference change from a planted bias. What is not yet "
     "validated is that attribution is specific on arbitrary directions in the real model, where the "
     "same machinery currently labels almost everything a preference. To claim a solved "
     "identification problem would overstate it. To claim a calibrated recovery of magnitude, with "
     "attribution demonstrated against the planted anchors, is both "
     "defensible and still unusual in this literature.")
para("The field currently publishes steering results whose interpretation rests on exactly the kind "
     "of evidence shown here to be insufficient. A paper that supplies planted ground truth and "
     "reports what passes and what fails against it is offering a tool rather than a complaint, and "
     "that distinction is what separates an accepted paper from an oral.")

heading("8.3 The shape of the talk", 2)
bullet("Open on the identification problem. Three different internal changes produce the same "
       "behavioural curve.")
bullet("Give the prompting ladder as the first evidence that behaviour does not identify mechanism.")
bullet("Give the geometry as the second. Of the standard recipes, the direction being steered with most resembles the contrastive "
       "baseline and far from the lever that drives the answer.")
bullet("Introduce planted ground truth as the remedy. Build changes of known nature and test the "
       "method against them.")
bullet("Report honestly. The large bias is recovered. The small preference change fails at the "
       "detection limit and passes at three times it.")
bullet("Close on the standard that follows. Any steering claim should arrive with a planted anchor "
       "that the same pipeline can recover.")

heading("8.4 The closing line", 2)
para("The field is not being asked to stop steering. It is being asked to report, alongside every "
     "steering result, what happened when the same pipeline was pointed at a change whose answer was "
     "already known.", bold=True)

heading("8.5 The questions this invites, and the answers", 2)
bullet("Why should the adapters be believed to imitate the invented agents. The answer is the "
       "correlation of zero point nine nine and the calibration slope inside nine tenths to eleven "
       "tenths, measured on prompts the adapter never saw during training.")
bullet("Is this not simply a negative result. The answer is Section 5. The instrument passes at three "
       "times its detection limit, so a threshold has been measured rather than a failure reported.")
bullet("Why is the probe comparison not presented as a finding. The answer is the first "
       "qualification. The classifier that would certify it labels a known bias as a preference, so "
       "it is not leaned on.")
bullet("What is still missing. Two things rather than one. The first is a working null band, because "
       "the isotropic random controls destroy the model before reaching the required dose, and the "
       "plan already prescribes covariance matched directions under amendment A8. The second is "
       "attribution specificity on real model directions, which is demonstrated against the planted "
       "anchors and is not yet demonstrated against arbitrary directions.")
bullet("Does a larger model fix the sensitivity problem. The same pattern appeared on the eight "
       "billion parameter model, so scale alone does not fix it. What fixes it is a planted effect "
       "above the detection limit.")
bullet("Are these results about the model or about the readout. About the readout, until confirmed "
       "by sampled generation. Panel A shows the readout and free generation disagree by thirty four "
       "grid steps, and every anchor number quoted here is a readout measurement. This should be "
       "conceded at once rather than defended.")

para("Every number in these notes is produced by a script that reads raw logs and is registered "
     "together with that script and with the inputs it read and with the commit at which it was "
     "computed. Where a quantity could not be computed it is named as not available together with "
     "the reason.", size=9, color=MUTED, after=4)

# ================================================================ contents
body = doc.element.body
anchor_p = doc.paragraphs[toc_placeholder_index - 1]._p
for title, name, lvl in TOC:
    p = link_para(title, name, indent=0.0 if lvl == 1 else 0.28)
    anchor_p.addnext(p._p)
    anchor_p = p._p

doc.save(str(OUT))
print("wrote", OUT, "with", len(TOC), "navigable headings")
