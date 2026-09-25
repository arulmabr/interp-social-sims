# Every change to the paper that is text only

Drafted for the authors under rule 12. There is no LaTeX in this repository, so
none of this is applied. Each entry gives the location, the sentence as it
stands in the 21 Sept PDF, and the sentence to replace it with.

Ordered by what happens if it is skipped. Tier 1 risks the submission. Tier 2 is
the paper disagreeing with its own data. Tier 3 answers the review. Tier 4 is the
limitations paragraph.

Every number below is in `MANIFEST.csv`. Nothing here needs a GPU.

---

## Tier 1. Skipping these risks the submission

### 1.1 The AI-use statement (required, outside the page limit)

ICLR 2027 requires a dedicated section. The present Acknowledgments paragraph
covers coding assistance only. Required disclosure covers designing or giving
feedback on methodology, proposing or refining hypotheses, implementing methods,
generating synthetic datasets and interpreting results. `logs/AI_USE_LOG.md` has
the record to write it from. The policy treats a misrepresentation produced by a
language model as an ethics violation by the authors, so this is not optional.

### 1.2 Page limit

Main text currently ends on page 11, about 10.3 pages against a 9-page limit.
Roughly 1.4 pages must come out before anything goes in. Figures 1 and 2 occupy a
full page between them.

### 1.3 References that do not resolve

  - "Davis & Bingham, 2007" omits the second author. It is Davis, Eisenhardt and
    Bingham, Academy of Management Review 32(2), 480-499.
  - Angelopoulos, Lee and Misra: the venue is garbled as "B Tests (April 2,
    2024), 2024".
  - Alain and Bengio appears as both 2016 and 2017 and is cited under both.
  - Nanda 2023 "Attribution patching" is listed as a Transformer Circuits report.
    It is a post on the author's own site.
  - Chen et al. 2025: the bibliography lists four authors, the extension plan
    five. Check arXiv 2508.21285.
  - Chang et al. has a hyphenation artefact, "ho-mophily".
  - The five judges need API model identifiers and access dates.

### 1.4 A citation that does not support its claim

**p3.** Currently:

> Previous attempts have utilized SAEs to demonstrate the steerability of
> generative agents in financial activities or marketing messaging design (Chen
> et al., 2025; Angelopoulos et al., 2024).

Angelopoulos, Lee and Misra align model outputs with A/B test effects through
prompt construction. They do not train, inspect or intervene on representations
with sparse autoencoders. Replace with:

> Previous attempts have utilized SAEs to demonstrate the steerability of
> generative agents in financial activities (Chen et al., 2025). Related work
> aligns generative model outputs with experimental treatment effects through
> prompt construction rather than representation-level intervention
> (Angelopoulos et al., 2024).

---

## Tier 2. The paper disagrees with its own data

### 2.1 The steering-strength convention is never stated

**p8.** Currently:

> Higher positive λ values increase risk-seeking behavior (lower switching
> points), while negative values enhance risk aversion.

Every calibrated λ in `probe_results_final.json` is negative, running from
-0.3186 at a target of 30 to -5.1531 at 200 on the lottery. More negative λ
raises the switching point. Figure 10 plots the magnitude, so the figure appears
to show λ rising while the values are falling. State the convention once:

> All calibrated λ values are negative in our experiments. More negative λ
> increases risk aversion and raises the switching point, from λ = -0.32 at a
> target of 30 tokens to λ = -5.15 at 200. Figure 10 plots the magnitude |λ|.

### 2.2 The unsteered switching points

**p8.** Currently:

> The baseline agent exhibits risk aversion with a switching point around 125
> tokens.

Fitted from the released per-level counts the value is 132.9 with a 95 percent
interval of [131.3, 134.5] at n = 1400. Replace "around 125 tokens" with:

> a switching point of 132.9 tokens (95% CI [131.3, 134.5], n = 1400).

**p8.** Currently:

> they start to take the offer when it exceeds 30

The fitted threshold is 37.9 [36.9, 38.9] at n = 680, and Figure 3B shows about
38. The text disagrees with the paper's own figure. Replace with:

> they start to take the offer once it exceeds 37.9 tokens (95% CI [36.9, 38.9],
> n = 680).

The prompted values move likewise: lottery 20.0 [19.8, 20.2] against "only 20",
and ultimatum 12.8 [11.5, 13.9] against "only 10 tokens".

### 2.3 Two of the five rho levels cannot exist

**p4.** Currently:

> we vary the fraction ρ ∈{0.0, 0.25, 0.5, 0.75, 1.0} of the N demonstrations
> that take the target action

p3 states N = 6. With six demonstrations only multiples of one sixth are
reachable, so 0.25 and 0.75 cannot be realised; the conditions named dose025 and
dose075 use 2 of 6 and 4 of 6. Replace with:

> we vary the fraction of the N = 6 demonstrations that take the target action
> over the reachable values {0, 2/6, 3/6, 4/6, 1}

### 2.4 "Held-out" describes something the code does not do

**p4.** Currently:

> The probe achieved 82% classification accuracy on held-out preference trials

`Probes/experiments/_common.py` splits with StratifiedKFold over rows. Each of
the 45 lottery prompts contributes eight identical activation vectors, so every
vector appears in both the training and validation folds of the same split.
There is no prompt-level held-out set. Replace with:

> The probe achieved 82% classification accuracy under stratified cross
> validation over trials. Because each prompt contributes several trials with
> the same activation, this is not a prompt-level held-out estimate.

The same word appears at p4 in "achieved the highest held-out performance" for
the layer sweep and needs the same treatment.

### 2.5 The judges do not agree about the ordering

**p21.** Currently:

> The relative ordering of conditions was consistent across all five judges,
> indicating that the creativity comparisons reported in the main text are not an
> artifact

Figure 5 shows otherwise. On the brick task GPT-5, Claude and Kimi all rate SAE
steering below baseline while Gemini and DeepSeek rate it well above. On the
stapler task GPT-5 and DeepSeek prefer prompting to steering. Replace with:

> Agreement among the five judges was high on the pooled correlation, with a
> mean pairwise Spearman of 0.77, but the judges do not agree about the ordering
> of conditions. On the brick task three of the five rate SAE steering below
> baseline while two rate it above, so the mean ordering reported in the main
> text depends on averaging judges who disagree about the sign.

---

## Tier 3. Reviewer weaknesses answered in text

### 3.1 The steering hook's position policy

The review works out that under KV caching `seq_len // 5` evaluates to 0, so the
ramp collapses to a constant 0.5 on generated tokens, and that "the last 20% of
tokens" is not computable during open-ended generation unless the hook is
restricted to prefill. Both are correct. Add to the probe appendix:

> The positional ramp is computed from the sequence length of the current
> forward pass. During prefill this is the prompt length, so the ramp covers the
> final 20% of prompt positions. During cached decoding the pass carries a single
> token, so the ramp does not apply to generated positions. Steering is therefore
> applied to prompt positions only.

### 3.2 What the ultimatum responder measures

The review objects that willingness to accept low offers is not altruism, and
that rejecting a low offer is costly enforcement of a fairness norm rather than
selfishness. This is right. Replace "altruism" with the construct actually
manipulated wherever it describes the ultimatum responder:

> In the responder role we manipulate willingness to accept unequal offers,
> which corresponds to inequity aversion in the Fehr-Schmidt sense rather than to
> altruism. We use the term acceptance threshold throughout.

### 3.3 SAE features are correlational

The review notes that top-activating features are observational and that refusal
and safety latents fire on gambling and payout language in instruction-tuned
models. Add to Section 4.1:

> Top-activating features identify correlational hypotheses about which concepts
> are active, not established causal mechanisms. Confirming that a feature
> mediates behaviour requires targeted ablation or clamping, which we do not
> perform here.

### 3.4 Fluency is a constant

The creativity prompt states that the list must not contain more than 10 items,
and every response in every condition returns exactly 10. Fluency is therefore a
constant that carries a quarter of the composite creativity score. Add:

> The alternative-uses prompt caps the response at ten items and every response
> reaches that cap, so the fluency dimension is constant across conditions. It is
> reported separately rather than folded into the composite score.

### 3.5 High temperature is degenerate, not a control

Brick creativity falls from about 5.2 to about 2.1 under high temperature and the
top features are messy formatting and multilingual fragments. Add:

> The high-temperature condition produces degenerate text rather than a
> controlled increase in variation, so it is reported as a sampling artefact
> rather than as a test of blind variation.

Also state the sampling settings for every condition. The appendix currently
gives temperature only as "e.g., 0.9 or 1.0".

---

## Tier 4. The limitations paragraph

Five reviewer points have no experiment behind them and are answered by naming
them. Two cannot be fixed by any experiment.

> **Limitations.** Our ultimatum manipulation moves the acceptance threshold,
> which is inequity aversion rather than altruism, and we have renamed it
> accordingly. Every experiment is a single-turn individual vignette, so the
> framing of multi-agent social simulation describes the intended application and
> not the present design. Creative capability is scored entirely by prompted
> language-model judges; we report four judge-independent text measures alongside
> them, but no human ratings. We administer no psychometric battery, so we cannot
> rule out unintended collateral change from steering. Finally we compare against
> difference-of-means, first principal component and ridge baselines but not
> against Inference-Time Intervention.

---

## What is deliberately not here

Changes that need a number we do not have, or a figure rebuild, or a rerun. They
are in `paper_patches/CLAIMS.csv` under the data and figure rows.
