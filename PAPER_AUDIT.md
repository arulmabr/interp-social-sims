# PAPER_AUDIT.md

Audit of `55998_Interpreting_and_Steerin*.pdf` (32 pp., built 2026-09-19), checked against the figures themselves, `feedback.txt`, and the extension plan. Line numbers are the ICLR margin line numbers in the PDF. Values marked "≈" were read off the plots and must be replaced with the logged numbers.

Status tags: **[VERIFIED]** I checked it against the PDF. **[REVIEWER-WRONG]** the automated review in `feedback.txt` is mistaken; do not "fix". **[NEEDS-REPO]** can only be settled from code or logs.

---

## 1. Things that get the paper desk-rejected before anyone reads it

1. **Page limit. [VERIFIED]** ICLR 2027 allows 9 pages of main text at submission (10 only in the discussion phase and camera-ready), strictly enforced. The main text currently ends at l. 557 on page 11, about 10.3 pages. Figures 1 and 2 occupy a full page between them; Table 1 and the Limitations section sit on pages 10 and 11. Roughly 1.4 pages must go before anything is added.
2. **AI-use statement.** ICLR 2027 requires a dedicated AI-use section (outside the page limit) and the same information in the submission form. Tasks with *required* disclosure include designing or giving feedback on methodology or experiments, proposing or refining hypotheses, implementing methods, generating synthetic datasets, and interpreting results. The current "Acknowledgments" paragraph (ll. 560–563) covers coding assistance only. If the probe training text in Fig. 2 was LLM-generated, if `feedback.txt` came from an AI reviewer, and if this plan is adopted, all three belong in the statement. The policy treats a falsehood or misrepresentation produced by an LLM as an ethics violation by the authors.
3. **References.** ICLR 2026 desk-rejected papers with unverifiable references, so every entry needs to resolve.
   - "Davis & Bingham, 2007" (l. 044, ll. 617–618) omits the second author. The paper is Davis, Eisenhardt and Bingham, *Academy of Management Review* 32(2), 480–499.
   - Angelopoulos, Lee and Misra (l. 577): venue is garbled ("B Tests (April 2, 2024), 2024"). It is also cited at ll. 130–132 as an SAE steering paper, which it is not; it is about aligning LLM outputs with A/B test results through prompting.
   - Alain and Bengio appears twice (2016 preprint and 2017 workshop) and is cited under both years.
   - Nanda 2023, "Attribution patching" (ll. 664–665) is listed as a Transformer Circuits report. It is a post on the author's own site.
   - Chen et al. 2025, "A financial brain scan of the LLM": the bibliography lists four authors, the extension plan's reference list gives five (adds Pourmohammadi). Check arXiv 2508.21285 and use what is there.
   - Chang et al. title has a hyphenation artefact ("ho-mophily").
   - Give API model identifiers and access dates for all five judges. (The automated review's claim that GPT-5 is an unreleased model is wrong; the citation can stay.)
4. **Anonymity of the supplement.** The code lives under a path containing a username. Any zip or anonymous repository must be free of absolute paths, usernames, API keys, notebook outputs with paths, and git history.
5. **Reviewer registration and quotas.** Every submission needs at least one author registered to review three papers, if any author is qualified (a main-track paper accepted at ICLR, NeurIPS, ICML, ACL, EMNLP, CVPR, AAAI, KDD or similar by the abstract deadline); a submission with no registered reviewer is desk-rejected. If no author qualifies, the paper is exempt, but each such author may appear on only one submission. Authors cannot be added or removed now; order can change until Sept 25. This is for the authors to check on OpenReview, not something in the repo.

---

## 2. Places where the text and the paper's own figures disagree

1. **λ polarity. [VERIFIED]** ll. 397–398 say higher positive λ increases risk seeking and lowers the switching point. Fig. 10a shows required λ rising monotonically from ≈0.3 at a target of 30 to ≈5.7 at 240, and Fig. 11a/App. B.7 show safe choices scoring higher on the probe. Positive λ therefore pushes toward the safe option. The same ambiguity affects the ultimatum panels and Fig. 2's "altruism probe".
2. **Where is λ = 0? [VERIFIED as a contradiction; cause NEEDS-REPO]** Fig. 10a is close to linear; extrapolating to λ = 0 gives a lottery switching point of roughly 15–25, and Fig. 10b gives an ultimatum threshold near 25. The text says the unsteered model switches at ≈125 (l. 395), and Fig. 3B puts the unsteered ultimatum threshold at ≈38. Either the unsteered model on the local probe stack behaves very differently from the unsteered model on the Goodfire/EDSL stack, or λ is not zero-centred, or a sign was dropped. Until this is settled, no comparison between the probe results (Figs. 4, 6, 9–18) and the prompting/SAE results (Figs. 3, 5) is safe. Every dose-response figure needs the λ = 0 point on it.
3. **Fig. 6, "consistently below the diagonal". [VERIFIED]** Mean achieved scores are ≈4.05, 5.35, 6.6, 7.55 at targets 3, 5, 7, 9. The curve is above the diagonal at 3 and 5 and below it at 7 and 9; the slope is ≈0.58. This is range compression around the unsteered mean, as the review says.
4. **Fig. 6, the target scale. [VERIFIED]** The probe was trained on GPT-5 labels, yet GPT-5's own achieved scores sit 0.5 to 3 points below target everywhere (≈2.5 at target 3, ≈6.0 at target 9). The five-judge mean tracks the diagonal only because lenient judges (DeepSeek, Kimi) offset harsh ones. Per-judge z-scoring or a held-out-judge design is needed before "target" means anything.
5. **Judge agreement on condition ordering. [VERIFIED; not in the automated review]** App. A.3.5 (ll. 1120–1122) says the ordering of conditions was consistent across all five judges. Fig. 5 shows otherwise. Brick: GPT-5 (≈4.65 vs 5.0), Claude (≈4.8 vs 5.15) and Kimi (≈5.0 vs 6.0) rate SAE steering *below* baseline, while Gemini (≈6.3) and DeepSeek (≈7.0) rate it far above. Stapler: GPT-5 (≈6.4 vs 5.85) and DeepSeek (≈7.15 vs 6.85) prefer prompting to steering. "SAE steering attains the highest score in both tasks" (l. 416) rests on averaging judges who disagree about the sign. The 0.77 mean Spearman is probably carried by the high-temperature condition, which every judge scores near 2.
6. **High temperature. [VERIFIED]** Brick creativity falls from ≈5.2 to ≈2.1 and the top SAE features are "messy formatting, multilingual fragments". That is degenerate text, not a test of Campbell's blind-variation idea. The appendix gives the temperature only as "e.g., 0.9 or 1.0" (l. 1130), and sampling settings for the other conditions are never stated (App. A.6 says only that they were held constant).
7. **Fig. 3A and the 50-token pivot. [REVIEWER-WRONG]** The review says the SAE-steering curve stays at 0% until 100 tokens. It confused the curves. The steering curve (teal, dotted) is ≈5% at 55, ≈60% at 60 and ≈98% at 65; the curve that stays flat until 120 is the baseline. ll. 373–375 are correct as written.
8. **Fig. 3B. [VERIFIED]** The SAE-steering curve for the ultimatum game (≈88% acceptance at 35, 100% at 40, against a baseline of ≈30% at 35 and ≈62% at 40) is never described in the text.
9. **Fig. 16. [VERIFIED; provenance NEEDS-REPO]** The caption describes one line per judge plus a bold mean. The plot shows a single "Brick" line with error bars and λ annotations (1.20, 2.40, 4.20, 6.00 for targets 3, 5, 7, 9). Its values (≈3.95, 5.3, 6.55, 7.65) are nearly identical to the Llama-70B means in Fig. 6A. Confirm it is Qwen data scored under the five-judge protocol. Note also that λ = 1.2 yields ≈3.95, below the unsteered 5.18 reported in Fig. 5, which is the capability-side version of item 2.
10. **App. B.11 cross-references and the Fig. 15 caption. [VERIFIED]** As listed in `feedback.txt`.

---

## 3. What the existing figures already show, and the text does not say

These need no new compute and are the seed of the extension plan's thesis.

1. **The persona prompt produces dominated choices. [VERIFIED]** In Fig. 3A every prompted agent picks the risky option at n = 25, a 50% chance of 25 tokens over a guaranteed 50. The risky option's best outcome is worse than the sure amount, so no attitude to risk explains the choice. The persona says "likes to take risks" and the option is labelled "Risky Option"; label matching is the obvious rival reading.
2. **Probe steering does the same. [VERIFIED]** The leftmost curves in Fig. 4a reach 60–90% risky choices at n = 35–45, all dominated. The curves are close to parallel horizontal translations of one another.
3. **The ultimatum probe reaches thresholds no fairness preference produces. [VERIFIED]** Fig. 10b calibrates targets up to 100, which means rejecting offers of 90 out of 100. Under Fehr–Schmidt preferences with β < 1 a responder never rejects an offer above half the pie. Rejections of offers ≥ 50 are the ultimatum game's catch trials, the counterpart of dominated gambles.
4. **Interventions carrying the same name disagree about what acceptance means. [VERIFIED]** The "altruistic and selfless" persona drops the threshold to ≈12 and the SAE feature with the identical label moves it only slightly (≈38 to ≈33). Fig. 2 illustrates steering toward *lower* altruism with the response "I don't accept this offer". The paper thus equates acceptance with altruism, which inverts the standard reading: a payoff maximiser accepts any positive offer, and rejecting a low offer is costly enforcement of a fairness norm. The closest prior work on altruism features (Zhang et al., arXiv 2604.19260) uses the Dictator Game, which is the instrument for altruism.
5. **The unsteered responder is harsher than people. [VERIFIED]** It rejects 30/100 every time. ll. 402–404 ("slightly more altruistically than perfectly rational humans") is wrong twice: a rational responder accepts anything positive, and most human responders accept 30%.

---

## 4. Method descriptions that contradict each other or cannot be right

1. **What the preference probes were trained on. [NEEDS-REPO]** §3.3 reports 82% accuracy "on held-out preference trials"; Fig. 2 shows training on synthetic low- and high-altruism statements; App. B.4 describes median-splitting the target metric "across calibration runs". These are three different datasets.
2. **Capability probes. [NEEDS-REPO]** App. B.2 says activations come from the final prompt token. Every creativity prompt is identical, so that position cannot separate high from low creativity, let alone reach ≈92%. Training set, labels, pooling position and sample sizes are missing.
3. **The steering hook. [NEEDS-REPO]** App. B.5.2 applies the vector to "the last 20% of tokens" with a 0.5→1.0 ramp. During cached decoding `seq_len` is 1, so the code as printed applies a constant 0.5 to every generated token, and the "last 20%" logic only ever touches the prompt. §3.3 and Fig. 2 give plain h + λŵ. `v_scaled` is never defined.
4. **Fig. 1's equation** replaces the hidden state with the SAE reconstruction; the Goodfire "nudge" mode and any sane implementation add a decoder direction to the residual stream.
5. **Forty "agents" are forty samples.** Traits contain only `subject_id` (the `age` loop variable is unused, ll. 803–809), so the agents are i.i.d. draws from one prompt at one temperature. "Percentage of agents" is a Monte Carlo estimate of a single choice probability with a binomial error of up to ±15 points, which is what the zig-zag in the Fig. 3A baseline (75, 65, 60, 97, 72, 100) is. No figure has an interval and no comparison has a test.
6. **Unmatched comparisons.** SAE steering is at layer 50 through a hosted API with no position masking; probe steering is at layer 48 on a local stack with the ramp; prompting runs through EDSL. The three-way comparison in Table 1 and §5 is confounded by stack, layer and position policy.
7. **Promised results that are absent.** §3.1 defines CoT, few-shot, few-shot CoT and a ρ dose-response, and the abstract reports a conclusion about them ("this advantage narrows"). No figure, table or appendix contains those results or the prompts.
8. **Superseded rubric in the appendix.** A.3.4 prints the old prompt with "you can be generous"; A.3.5 says that line was removed.
9. **Terminology.** l. 368 calls risk-neutral indifference (n = 100) an "equilibrium". Table 1 lists SAE training cost as a limitation although the authors trained nothing, while probes needed data generation, sweeps and fitting.
10. **Lottery SAE settings.** A.1.3 gives two overlapping presets ("0.5 to 0.7", "0.4 to 0.6"), placeholder UUIDs, and does not say which produced Fig. 3A.

---

## 5. Missing context a reviewer in this area will look for

- Activation steering is attributed to the probing literature. The relevant line is ActAdd (Turner et al.), Representation Engineering (Zou et al.), Inference-Time Intervention (Li et al.) and Contrastive Activation Addition (Rimsky/Panickssery et al.). A difference-of-means baseline is the minimum; it costs nothing once activations are cached.
- Direct precedents: Zhu, Yan and Griffiths (arXiv 2505.11615; CogSci 2026) steer risk preferences with aligned representations; Zhang et al. (arXiv 2604.19260) find and steer altruism SAE features in the Dictator Game; Ma (arXiv 2504.11671), Chen et al. (arXiv 2508.21285) and "Persona Vectors in Games" (arXiv 2603.21398) steer social or financial behaviour. Against these, "steering moves lottery and ultimatum choices" is consolidation. What none of them asks is *which construct moved*, and that is the opening for this paper.
- AxBench (Wu et al., ICML 2025) on prompting and finetuning beating SAEs at equal budget; Tan et al. (NeurIPS 2024) on the unreliability of steering vectors; Arditi et al. (NeurIPS 2024) for ablation/addition as necessity and sufficiency tests.
- The "social simulation" framing promises more than single-turn, single-agent vignettes deliver. Say the paper studies the micro-foundations that a simulation would be built from.

---

## 6. Points in `feedback.txt` that are valid and only need editing

The altruism/ultimatum conflation, the Angelopoulos misattribution, the causal over-reading of top-activating SAE features in §4.1 (the "unethical request" and "writing instruments" features), the unreported calibration from target score to λ, the two cross-object protocols described as one (App. B.8 vs. Fig. 9), the broad claim in §5 that contradicts §4.2.1, the Table 1 recommendation that contradicts the Limitations section, and every item under "Minor Corrections and Typos". I checked a sample of the typo list against the PDF and found no errors in it.
