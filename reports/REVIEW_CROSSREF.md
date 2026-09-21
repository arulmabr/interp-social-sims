# The review, the measurements, and what the Sept 25 PDF says

`feedback.txt` is a full review of the submitted PDF. This maps every substantive
point to the measurement that bears on it **and to the sentence the paper will
carry**. The third part is the one that matters operationally: a reviewer
weakness with no written response in the paper is the failure this document
exists to prevent. Every row has one, including the five whose honest response is
"not done, named as a limitation, ongoing work".

Machine-readable form: `paper_patches/CLAIMS.csv`, 46 rows, rebuilt by
`python -m cv_bench.claims`.

| | rows |
|---|---|
| answered with **data** — a measurement finished before the cutoff | 17 |
| answered with **text** — a correction, a removal, or a statement of fact | 24 |
| answered as a **limitation** — not done, named, with the reason | 5 |

| verdict | rows |
|---|---|
| not reproducible from the committed code | 12 |
| contradicted by the repository's own data | 12 |
| confirmed — the concern is right, and we measured how far | 14 |
| open — real, measurement not yet in hand | 4 |
| deferred to the extension plan | 2 |
| editorial | 2 |

## Reviewer weaknesses answered with data

**Missing representation-steering baselines (CAA, RepE, ActAdd).** G4b runs them.
Difference-of-means is the CAA / ActAdd form; the first principal component of
the centred activations is the RepE / LAT form. Both are fitted from the *probe's
own activations*, so the comparison is not confounded by training data, and both
are steered at the same doses on the same grid. A ridge probe for log n runs
beside them as a payoff code by construction. Descriptive reporting only.
**ITI is the exception** and is a limitation, below.

**The prompting ladder is missing from the results.** S1.7 answers it with the
curves the paper omits. They do not support the claim they were omitted from: the
ρ sweep is flat across its whole range (96.0 to 101.6) and chain of thought moves
the switching point **the wrong way**, 175.7 against a baseline of 106.8. Two of
the five dose labels are also wrong — six exemplars can only realise sixths, so
`dose025` is 0.333 and `dose075` is 0.667.

**Judge-independent creativity measures.** S1.6 computes four of them on the same
responses. They do not rescue the judges: category spread correlates 0.72 with
the judges pooled and 0.06 / 0.14 within task — the same pooling artefact that
produces the headline agreement figure.

**No causal test behind the SAE attributions.** G6 ablates each named feature
against 100 activation-matched random features and reports its attribution rank
among all 65,536. Section 4.1's readings become tested statements or are
withdrawn.

**Agent-level inferential statistics.** A crossed mixed model with random
intercepts for judge and response is already fitted (S1.5).

**Judge verifiability.** V2 reports the evaluator identifiers actually present.
The four single-judge passes are **gpt-5 alone**, 80 rows each, every row
carrying an `api_response_id`. The three five-judge passes carry **none**.

## Where the repository's data goes further than the review

**The 0.77 agreement is cited as a strength; it is a pooling artefact.** It
reproduces exactly (0.7695) only across both tasks and all conditions. Within
task: 0.458 brick, 0.353 stapler. Within the prompting condition: 0.135 and
0.020. Dropping high temperature *raises* the pooled value, so temperature is not
what carries it.

**The judge ordering claim is false.** On brick, four of five judges rate SAE
steering below baseline (Claude 4.83→4.39, Gemini 4.74→4.49, GPT-5 4.83→4.68,
Kimi 5.09→4.76; DeepSeek flat). Table 1's recommendation rests on this.

**Length is not controlled in the direction stated.** Within the dataset the
capability figures use, length explains up to 59% of a judge's variance with a
**negative** slope; the repo's pooled file reports positive slopes and up to 43%.

**The λ polarity contradiction is deeper than a sign slip.** Every λ in the
repository is negative, in both games at both layers, and no λ = 0 row exists.
There is no positive-λ arm to describe.

**The two SAE doses are one dose** — byte-identical curves, 0 risky choices
different in 1400. **Prompting and SAE steering are not independent arms** — the
creativity prompting system prompt is the three steered features' labels
verbatim. **A quarter of the creativity composite is a constant** — every
response produces exactly 10 ideas because the prompt caps the list at 10.

**The steering hook steers no generated token.** At `seq_len == 1`, every cached
decoding step, its own index arithmetic yields zero positions.

**The probe cannot encode what §3.3 says it encodes.** 45 prompts differing in
one integer, 8 repeats each, 45 distinct vectors; CV splits rows, not prompts.
The capability probe has two distinct training prompts. A rule that knows n
perfectly scores 0.95–0.99 on this design, above the reported 82%.

## The finding the review could not have made

The review assumes the figures came from the committed code. The committed probe
path gives **no answer on 88.3%** of Llama lottery trials while the published data
has **0 unparseable rows in 21,040**; no retry, fallback or filter exists;
`apply_chat_template` appears in no commit of `Probes/`; and the four probe files
have one commit each, dated 2026-05-25, while the runs are dated October and
November 2025. Twelve figures are marked `not_reproducible`.

**V1 closes the Figure 5 question.** Searching 1,175 cells — every scoring pass,
prompt version, condition, task, score column and judge subset — found 21 single
value matches to the PDF's readings. **21.0 is exactly the number chance predicts
at that search width.** Requiring a *pair* to be coherent, both halves from the
same pass, task, column and judge subset, differing only in condition: **none
matches**. No scoring pass in this release produces Figure 5's numbers.

## Answered as limitations — named in the paper, not quietly absent

| point | what the PDF says |
|---|---|
| **ITI** | §4 reports the difference-of-means and first-PCA baselines at equal dose. The limitations state that ITI, which intervenes per attention head rather than on the residual stream, is not among them, and is ongoing work. |
| **Human-normed AUT / SemDis** | The four judge-independent measures are reported. The limitations state that no semantic-distance benchmark or human-normed distribution was used, and that validating against one is ongoing work. |
| **Multi-turn and multi-agent settings** | The framing is narrowed to single-turn individual vignettes. The limitations state that multi-agent and multi-turn settings, where activation drift could accumulate, are not tested here. |
| **Personality batteries / collateral distortion** | The limitations state that collateral effects on unsteered traits were not measured, that the collateral frontier is ongoing work, and that **no claim of specificity is made without it**. |
| **Proposer role, mini-ultimatum** | The construct is renamed to what the responder role measures — fairness enforcement, not altruism — and the limitations state that separating it from an accept bias needs the proposer role and a mini-ultimatum variant. |

## Still open

- Whether Fig. 3(A)'s curve matches the text's "pivot at 50 tokens".
- Whether the layer 48 / layer 50 dissociation is a difference in **choices**
  rather than wording — waiting on G4's coding agreement.
- The two provenance rows that only an author can close: how the original probe
  runs were made, and which scoring pass produced Figure 5.
