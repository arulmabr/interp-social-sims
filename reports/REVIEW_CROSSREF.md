# The review, against what we measured

`feedback.txt` is a full review of the submitted PDF. This maps each of its
substantive points to the report that answers it, and says plainly where the
review is right, where the repository's own data goes further than the review
does, and where we still have nothing.

The machine-readable form is `paper_patches/CLAIMS.csv` (43 rows), rebuilt by
`python -m cv_bench.claims`. Counts: 12 not reproducible, 12 contradicted by the
repository's own data, 11 confirmed, 4 open, 2 deferred to the extension plan,
2 editorial.

## Where the review is right and we can say by how much

**The ladder is missing from the results.** The review notes that §3.1 defines a
multi-tier prompting ladder and the Abstract claims internal steering's advantage
narrows against it, while Figures 3–5 carry no curve for any of it. The ladder is
complete in the repository — nine conditions, 35 rewards, 40 agents — and it does
not support the claim. The ρ sweep is **flat** across its whole range (96.0 to
101.6) and chain of thought moves the switching point **the wrong way**, 175.7
against a baseline of 106.8. Two of the five dose labels are also wrong: six
exemplars can only realise sixths, so `dose025` is 0.333 and `dose075` is 0.667.

**The λ polarity contradiction.** The review spots that §4.2.1 says positive λ
increases risk-seeking while Fig. 10(a) shows positive λ raising the switching
point. The cause is deeper than a sign slip: **every λ in the repository is
negative**, in both games and at both layers, and no λ = 0 row exists anywhere.
There is no positive-λ arm to describe.

**Fig. 6's diagonal.** The review is right that low targets overshoot. The
pattern is regression toward the baseline mean, which overshoots low targets and
undershoots high ones by construction.

**No causal test behind the SAE attributions.** Correct, and it is why G6
(ablation and attribution) exists. Not yet run.

**Single-turn vignettes under a social-simulation framing.** Correct: no
multi-agent or multi-turn run exists anywhere in the repository.

**Missing steering baselines (CAA, RepE, ITI, ActAdd).** Correct, and none is run
anywhere. The extension plan's hypothesis 4 adds a contrastive persona direction;
that is the nearest thing scheduled.

## Where the repository's data goes further than the review

**The 0.77 agreement is cited as a strength; it is a pooling artefact.** It
reproduces exactly (0.7695) only across both tasks and all conditions. Within
task it is 0.458 (brick) and 0.353 (stapler); within the prompting condition,
0.135 and 0.020. Dropping high temperature *raises* the pooled value, so
temperature is not what carries it — pooling across tasks is.

**The judge ordering claim is false.** App. A.3.5 says the ordering was
consistent across all five judges. On brick, four of five rate SAE steering
**below** baseline (Claude 4.83→4.39, Gemini 4.74→4.49, GPT-5 4.83→4.68, Kimi
5.09→4.76; DeepSeek flat), five-judge mean 5.00→4.77. Table 1's recommendation
rests on this.

**Length is not controlled in the direction stated.** Within the dataset the
capability figures use, length explains up to **59%** of a judge's variance with
a **negative** slope. The repository's own pooled file reports positive slopes
and up to 43%.

**The two SAE "doses" are one dose.** 0.7/0.5 and 0.6/0.4 produce byte-identical
choice curves: a gap of 0 risky choices in 1400.

**Prompting and SAE steering are not independent arms.** The creativity
"prompting" system prompt is the three steered SAE features' labels verbatim.

**A quarter of the creativity composite is a constant.** Every response produces
exactly 10 ideas, because the prompt caps the list at 10.

**The steering hook steers no generated token.** The review asks about the hook's
execution mechanics (§B.5.2). At `seq_len == 1` — every cached decoding step —
the hook's own index arithmetic yields zero positions and returns the activation
untouched. It edits the last 20% of the *prompt* and nothing else, despite
`apply_during_generation=True`.

**The probe cannot encode what §3.3 says it encodes.** 45 lottery prompts
differing in one integer, each repeated 8 times, activation read at the final
prompt token: 45 distinct vectors, not 360. CV splits rows, not prompts, so every
vector is on both sides of every fold. The capability probe has **two** distinct
training prompts. A rule that knows n perfectly scores 0.95–0.99 on this design,
above the reported 82%.

## The finding the review could not have made

The review assumes the figures were produced by the committed code. They were
not, and cannot have been. The committed probe path gives **no answer on 88.3%**
of Llama lottery trials while the published data has **0 unparseable rows in
21,040**; no retry, fallback or filter exists; `apply_chat_template` appears in
no commit of `Probes/`; and the four probe files have exactly one commit each,
dated 2026-05-25, while the runs are dated October and November 2025. Twelve
figures are marked `not_reproducible` in CLAIMS.csv on this basis.

## Still open

- Which dataset produced Fig. 5 and its four numbers (V1). The PDF and the repo
  differ by 2.8–3.6 points in the same direction for every judge.
- Whether Fig. 3(A)'s curve matches the text's "pivot at 50 tokens" (V1).
- The five judge identities (V2).
- Whether the layer 48 / layer 50 dissociation is a difference in **choices**
  rather than in wording. This waits on G4, because the legacy coding overwrites
  the generation with its own label and cannot be audited.

## Deferred to the extension plan, not to a Sept 25 patch

The altruism / inequity-aversion conflation (hypothesis 5, which needs the
proposer role and a mini-ultimatum variant) and the causal SAE work (hypothesis 4
and G6). Both are real; neither is a wording fix.
