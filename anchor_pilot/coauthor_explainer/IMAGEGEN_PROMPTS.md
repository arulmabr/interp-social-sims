# Image-generation prompts

Mode: built-in image_gen tool. New images generated from text; overview refined through two image_gen edits. Final outputs were visually inspected. These are conceptual illustrations, not measurements or new experiments.

## Experiment overview — initial generation

Use case: scientific-educational.
Create a polished, visually rich scientific editorial infographic for research coauthors, landscape 3:2, high resolution with very legible typography. It must look like a beautifully illustrated research explainer, not a screenshot of boxes or a generic corporate flowchart. Off-white paper, navy ink, restrained teal, blue, purple and amber; fine vector-like linework, soft dimensional illustrations, generous whitespace.

Title exactly: "Does steering change risk preferences?"
Subtitle: "Or does it mainly change which answer the model selects?"

Organize in three clearly numbered horizontal sections.

1: "Two independent reference interventions"
Show two parallel and distinct mechanisms entering a stylized language-model layer stack:
LEFT blue: "Action anchor: raw gradient" with an arrow nudging a risky-versus-safe answer dial. Caption: "Directly pushes the answer readout."
RIGHT purple: "Intended preference anchor: LoRA" with small weight-adapter modules attached to the model, taught by three small knobs captioned "Curvature", "Probability weighting", "Loss aversion". Caption: "Learns choices from a known artificial policy."
Small clear line under both: "Neither anchor is built with an SAE."
Expansions, readable: "LoRA = Low-Rank Adaptation" and "SAE = Sparse Autoencoder".

2: "Compare two ways to steer the same model"
Illustrate a large residual-state arrow for "Dense direction" and a bundle of exactly ten colored small feature arrows combining into one for "10-feature SAE direction". The two final arrows must have equal length, communicating a matched displacement, not equal effectiveness.
Caption: "Same layer, positions and steering norm."
Both feed into three illustrated test cards labeled "New reward values", "Reworded prompts", "Swapped A/B labels". On the A/B card, use obvious crossed arrows between A and B; do not show invented probability data.

3: "What the pilot supports"
Three succinct result statements with restrained amber markers, not celebratory green:
"LoRA: recovery failed after rewording."
"Dense and SAE: no complete preference-check passes."
Verdict ribbon: "Current recipe not validated. Broader SAE question remains open."
Footer: "Conceptual illustration • Prepared with Codex"

Accuracy constraints: Keep the two anchors independent of the SAE dictionary. Do not show SAE creating the LoRA adapter or raw gradient. Do not imply LoRA is a validated preference reference. No brain/person/robot anthropomorphism. No invented plots, numerical results, axis ticks or significance stars. No statement that all SAE steering is answer bias. Use the exact concise text above, with clear hierarchy and readable labels; avoid additional filler.

## Experiment overview — label corrections

Edit this scientific infographic with only these corrections, preserving its beautiful layout, palette, illustrations and all other wording:
1. Remove the tiny decorative word lists in BOTH upper corners entirely (the upper right has a typo). Leave clean whitespace.
2. On the blue gradient tile, replace the mathematical symbol with a large simple lowercase "g". This is the risky-minus-safe logit gradient, not a training loss.
3. Change the line "Linear combination of ten SAEs features." to exactly "Linear combination of ten SAE features."
4. In section 2, make the final blue dense arrow and the final purple SAE arrow have the same physical drawn length, approximately 220 pixels, and identical width and thickness. Center the blue arrow in its panel. The purple arrow should remain to the right of the bundle, with enough room. Both existing "(matched length)" labels must now be visually true.
5. Show exactly TEN thin colored arrows in the small feature bundle (ten horizontal rows).
Do not change any findings, labels, expansions, disclaimer, title or conclusion. Keep high resolution and legibility.

## Experiment overview — final schematic clarification

Make one targeted text correction to this otherwise final image: replace BOTH occurrences of "(matched length)" below the large blue and purple arrows with "(schematic, not to scale)". The blue and purple arrows in this conceptual illustration have different drawn lengths; the new labels must clearly identify them as schematic. Keep the sentence "Same layer, positions and steering norm." exactly unchanged because that is the actual experimental design. Preserve absolutely everything else, including all findings, titles, the ten-feature bundle, the palette, typography, footer and layout. Do not add or change any other text.

## CPT explainer — generation

Use case: scientific-educational.
Create a beautiful, legible landscape 3:2 scientific editorial infographic explaining Cumulative Prospect Theory to AI research coauthors who do not know decision theory. Warm white paper, navy serif display title with clean supporting type, rich restrained teal/blue/purple accents, finely drawn dimensional educational illustrations, soft shadows, spacious professional magazine layout. This is a conceptual illustration, not a chart of experimental measurements.

Exact large title: "What is Cumulative Prospect Theory?"
Exact subtitle: "CPT is a mathematical model of choices under risk."

Top illustration: two elegant gamble cards side by side. Left exact text: "Option A" and "40 tokens for sure". Right exact text: "Option B" and "50% chance of 100 tokens" and "50% chance of 0 tokens". Illustrate token stacks and a balanced two-outcome branching tree; keep the branches visually equal. Caption exactly: "The same gamble can appeal differently depending on how outcomes and probabilities are valued."

Middle: three richly illustrated equal columns, each with a clear numbered heading and one simple conceptual icon:
1. "Outcome curvature" — a smooth diminishing-returns curve without numeric axes, caption: "How subjective value changes as gains or losses grow."
2. "Probability weighting" — a dial and probability icon, caption: "How decision weights differ from stated probabilities."
3. "Loss aversion" — balanced plus/minus token stacks, loss side visually heavier, caption: "How strongly losses count relative to gains."

Bottom: a visually clear pipeline across the width:
"Choose known CPT parameters" → "Generate artificial choices" → "Train a LoRA adapter" → "Test on new prompts"
Small readable expansion: "LoRA = Low-Rank Adaptation"

Then a prominent caution panel with exact text:
"A trained adapter is only an intended preference reference."
"Parameter recovery must hold on unseen rewards, reworded prompts and swapped answer labels."

Footer: "Illustrative example, not measured data • Prepared with Codex"

Constraints: Do not claim all people have the same preferences. Do not mark Option A or Option B as correct. Do not invent parameter values, data points, experimental findings or numeric axes. Do not call CPT the model's true internal psychology. No human brain, anthropomorphic robot or gratuitous business decoration. Do not add text beyond the specified text. Typography must be precise, clean and large enough to read in a Slack attachment.
