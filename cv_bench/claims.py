"""paper_patches/CLAIMS.csv -- every claim we can check, and what checking found.

Three sources are merged into one table so that nothing is answered twice and
nothing is answered nowhere:

  audit     PAPER_AUDIT.md and our own S0/S1/V/G reports
  reviewer  feedback.txt, the review of the submitted PDF
  plan      mech_interp_paper_ICLR_extension_plan.docx, where a point is already
            scheduled as future work rather than a patch

`verdict` is what the evidence supports, not what would be convenient:

  contradicted      the paper states X; the repository's own data shows not-X
  confirmed         the concern is right and we have measured how far
  not_reproducible  the figure cannot be rebuilt from the committed code
  open              real, and we do not yet have the measurement
  deferred          answered by the extension plan, not by a Sept 25 patch
  editorial         wording, citation or typo

Rebuild with:  python -m cv_bench.claims
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "paper_patches/CLAIMS.csv"

FIELDS = ["id", "source", "location", "claim_or_concern", "our_measurement",
          "verdict", "answered_with", "pdf_response", "evidence",
          "reproducible_from_committed_code", "patch"]

# `answered_with` is how the Sept 25 PDF answers the point:
#   data        a measurement in this repository, finished before the cutoff
#   text        a correction, a removal or a statement of fact, no new run
#   limitation  named in the limitations as not done, with the reason
# `pdf_response` is the sentence the PDF is to carry. Every row has one: a
# reviewer weakness with no written response in the paper is the failure mode
# this column exists to prevent.

# Figures whose provenance G2/A.1-A.3 settled: the committed probe path gives no
# answer on 88.3% of Llama lottery trials, the published data has 0 unparseable
# rows in 21,040, and the four probe files have one commit each, dated seven
# months after the runs.
NOT_REPRODUCIBLE = [4, 6] + list(range(9, 19))

R: List[Dict[str, str]] = []


def add(**kw):
    kw.setdefault("reproducible_from_committed_code", "n/a")
    kw.setdefault("patch", "")
    kw.setdefault("answered_with", "text")
    kw.setdefault("pdf_response", "")
    R.append(kw)


# --- provenance: the finding that governs the rest --------------------------
for fig in NOT_REPRODUCIBLE:
    add(id=f"PROV-fig{fig}", source="audit", location=f"Figure {fig}",
        claim_or_concern=f"Figure {fig} is presented as output of the committed probe pipeline",
        our_measurement=("the committed path gives no answer on 88.3% of Llama lottery "
                         "trials and 89.6% of Qwen's, while the published data has 0 "
                         "unparseable rows in 21,040; no retry, fallback or filter exists; "
                         "apply_chat_template appears in no commit of Probes/; the four "
                         "probe files have one commit each (59ca0f0, 2026-05-25) and the "
                         "runs are dated Oct-Nov 2025"),
        verdict="not_reproducible", answered_with="text",
        pdf_response=("The figure is rebuilt from the reconstruction and labelled as such, "
                      "or removed. The PDF states that the released probe code does not "
                      "reproduce the original run."),
        evidence="reports/G2_legacy_format.md; reports/G2_RESULTS.md",
        reproducible_from_committed_code="no",
        patch="W1 provenance statement")

# --- claims the repository's own data contradicts ---------------------------
add(id="C-judges-order", source="both", location="App. A.3.5; l. 416",
    claim_or_concern=("'the ordering of conditions was consistent across all five judges'; "
                      "'SAE steering attains the highest score in both tasks'"),
    our_measurement=("on brick, 4 of 5 judges rate SAE steering BELOW baseline "
                     "(Claude 4.83->4.39, Gemini 4.74->4.49, GPT-5 4.83->4.68, "
                     "Kimi 5.09->4.76; DeepSeek flat); five-judge mean 5.00->4.77"),
    verdict="contradicted", evidence="reports/S1_5.md", patch="W3 results text",
    answered_with='text',
    pdf_response="App. A.3.5's consistency claim is withdrawn and replaced by the per-judge table: on brick, four of five judges rate SAE steering below baseline. The l.416 superiority claim is removed.")

add(id="C-spearman", source="both", location="l. 0.77 inter-judge agreement",
    claim_or_concern=("the review cites the 0.77 mean pairwise Spearman as a strength "
                      "of the evaluation protocol"),
    our_measurement=("0.7695 reproduces only when pooled over both tasks and all "
                     "conditions; within task it is 0.458 (brick) and 0.353 (stapler), "
                     "and within the prompting condition 0.135 and 0.020. Dropping high "
                     "temperature raises the pooled value (0.634 -> 0.650), so temperature "
                     "is not what carries it -- pooling across tasks is"),
    verdict="contradicted", evidence="reports/S1_5.md; reports/S1_6.md",
    patch="W3 results text",
    answered_with='data',
    pdf_response='The 0.77 is reported as a pooled figure and accompanied by the within-task and within-condition values (0.458, 0.353, 0.135, 0.020), with a sentence saying the pooled number is carried by between-task variation.')

add(id="C-lambda-sign", source="both", location="Sec. 4.2.1 vs Fig. 10(a), App. B.7",
    claim_or_concern=("text says positive lambda increases risk-seeking; the figure shows "
                      "positive lambda raising the switching point (more risk aversion)"),
    our_measurement=("every lambda in the repository is negative, across both layers and "
                     "both games (lottery -0.31 to -5.27, ultimatum -0.46 to -2.31), and no "
                     "lambda = 0 row exists anywhere"),
    verdict="contradicted", evidence="reports/PHASE0_SUMMARY.md; S0.D.lambda.n_zero_rows = 0",
    patch="W2 methods text",
    answered_with='text',
    pdf_response='Sec. 4.2.1 is corrected to the sign the runs used. The PDF states that every lambda in the released data is negative and that no lambda = 0 condition exists.')

add(id="C-ladder-missing", source="both", location="Sec. 3.1, Abstract vs Sec. 4, Figs. 3-5",
    claim_or_concern=("the ladder (CoT, few-shot, combined, dose-response) is defined and "
                      "claimed in the abstract but no curve for it appears in the results"),
    our_measurement=("the ladder is complete in the repository: 9 conditions x 35 rewards x "
                     "40 agents. It does not support the claim. The rho sweep is flat "
                     "(96.0-101.6 across the whole dose range) and chain of thought moves the "
                     "switching point the WRONG way, 175.7 against a baseline of 106.8"),
    verdict="confirmed", evidence="reports/S1_7.md", patch="W4 ladder section",
    answered_with='data',
    pdf_response="The ladder's curves are reported (S1.7): the rho sweep is flat at 96.0-101.6 and chain of thought raises the switching point to 175.7 against a baseline of 106.8. The abstract's 'advantage narrows' claim is rewritten to match.")

add(id="C-rho-labels", source="audit", location="dose-response condition names",
    claim_or_concern="conditions are named dose025 and dose075",
    our_measurement=("six exemplars can only realise sixths, so the realised values are "
                     "0.333 and 0.667"),
    verdict="contradicted", evidence="reports/S1_7.md", patch="W4 ladder section",
    answered_with='text',
    pdf_response='The dose labels are corrected to their realised values, 0.333 and 0.667, with a note that six exemplars can only realise sixths.')

add(id="C-fewshot-dominated", source="audit", location="App. A.1 few-shot exemplars",
    claim_or_concern="the few-shot prompt demonstrates the task",
    our_measurement=("it demonstrates a DOMINATED choice: answer risky at n = 33 against a "
                     "sure 50"),
    verdict="confirmed", evidence="reports/S1_7.md; paper_patches/appendix_prompts.md",
    patch="W4 ladder section",
    answered_with='text',
    pdf_response='App. A.1 states that the few-shot exemplar demonstrates a dominated choice (risky at n = 33 against a sure 50).')

add(id="C-fig6-diagonal", source="reviewer", location="Sec. 4.2.2, Fig. 6",
    claim_or_concern=("text says achieved capability scores consistently fall below the "
                      "diagonal; low targets visibly overshoot it"),
    our_measurement=("the pattern is regression toward the baseline mean, which overshoots "
                     "at low targets and undershoots at high ones by construction"),
    verdict="confirmed", evidence="reports/S1_5.md", patch="W3 results text",
    answered_with='text',
    pdf_response='Sec. 4.2.2 is corrected: low targets overshoot and high ones undershoot, which is regression toward the baseline mean.')

add(id="C-fig3a-50", source="reviewer", location="Sec. 4.2.1, Fig. 3(A)",
    claim_or_concern=("text says SAE-steered agents pivot to risky choices at 50 tokens; the "
                      "curve is flat at 0% until 100"),
    our_measurement="not yet recomputed against the figure's own source file",
    verdict="open", evidence="pending V1", patch="W3 results text",
    answered_with='text',
    pdf_response="Either corrected against the figure's source file or the sentence is removed; V1 found no scoring pass that reproduces the figure's values.")

# --- method claims that do not match the code -------------------------------
add(id="M-probe-training", source="both", location="Sec. 3.3, Fig. 2, App. B.4",
    claim_or_concern=("the probe is described three different ways, and as trained on "
                      "held-out prompts"),
    our_measurement=("the preference probe trains on 45 lottery prompts (19 ultimatum) that "
                     "differ in ONE integer, each repeated 8 times, with the activation read "
                     "at the final prompt token -- 45 distinct vectors, not 360. CV splits "
                     "rows, not prompts, so every vector appears on both sides of every fold. "
                     "The capability probe trains on TWO distinct prompts"),
    verdict="contradicted", evidence="reports/PROBE_PROVENANCE.md", patch="W2 methods text",
    answered_with='data',
    pdf_response='Sec. 3.3 is rewritten to the code: 45 prompts differing in one integer, 8 repeats each, activation at the final prompt token, and CV over rows rather than prompts. The three inconsistent descriptions are replaced by one.')

add(id="M-probe-ceiling", source="audit", location="Sec. 3.3, 82% held-out accuracy",
    claim_or_concern="82% held-out accuracy is presented as evidence the probe reads preference",
    our_measurement=("the ceiling for a rule that knows n perfectly is 0.95-0.99 on this "
                     "design, so 82% is below what a pure payoff code achieves"),
    verdict="contradicted", evidence="reports/S1_4.md", patch="W2 methods text",
    answered_with='data',
    pdf_response='The PDF states that a rule knowing n perfectly scores 0.95-0.99 on this design, so 82% is below the payoff-code ceiling and is not evidence of a preference code.')

add(id="M-hook", source="both", location="App. B.5.2; Fig. 1; config STEERING",
    claim_or_concern=("the steering hook is described as applying during autoregressive "
                      "generation (apply_during_generation=True)"),
    our_measurement=("at seq_len == 1, every cached decoding step, the hook's own index "
                     "arithmetic yields zero positions and returns the output untouched. It "
                     "steers the last 20% of the PROMPT and zero generated tokens. Also "
                     "v_scaled equals the unit vector, so no norm matching happens, and the "
                     "probe scores in standardised space while it steers in raw space"),
    verdict="contradicted",
    evidence="reports/STACK_AUDIT.md sec.3; cv_bench/tests/test_readout_steer.py",
    patch="W2 methods text",
    answered_with='data',
    pdf_response='App. B.5.2 is corrected: the released hook edits the last 20% of prompt positions and no generated position, and the reported runs are those.')

add(id="M-capability-probe", source="reviewer", location="Sec. 3.3, App. B.4",
    claim_or_concern="capability probe training data and token extraction are underspecified",
    our_measurement=("two distinct prompts (task, and persona-prefixed task); the ~92% "
                     "accuracy is a statement about how often the persona produced an "
                     "above-median-scoring response"),
    verdict="confirmed", evidence="reports/PROBE_PROVENANCE.md", patch="W2 methods text",
    answered_with='data',
    pdf_response="App. B.4 states the capability probe's two distinct training prompts and that its accuracy measures persona detection.")

add(id="M-sae-lottery-uuids", source="reviewer", location="App. A.1.3",
    claim_or_concern="UUIDs missing from the lottery controller configuration",
    our_measurement="all 8 Goodfire feature UUIDs recovered from the logged EDSL controllers",
    verdict="confirmed", evidence="reports/PROVENANCE.md", patch="W5 appendix",
    answered_with='data',
    pdf_response='App. A.1.3 carries all eight feature UUIDs with their index_in_sae, recovered from the logged controllers.')

add(id="M-sae-probe-confound", source="reviewer", location="Sec. 3.2/3.3",
    claim_or_concern="operational confounders between the SAE and probe steering modalities",
    our_measurement=("they differ in stack, dtype, temperature, layer, position policy and "
                     "dose units simultaneously; four distinct inference stacks are in use "
                     "across the paper's figures"),
    verdict="confirmed", evidence="reports/STACK_AUDIT.md", patch="W2 methods text",
    answered_with='data',
    pdf_response='A stack table is added: the SAE and probe arms differ in service, dtype, temperature, layer and position policy at once, so the comparison is between pipelines, not between methods.')

add(id="M-prompting-not-independent", source="audit", location="App. A.3.2 creativity conditions",
    claim_or_concern="prompting and SAE steering are compared as independent arms",
    our_measurement=("the creativity 'prompting' system prompt is the three steered SAE "
                     "features' labels verbatim"),
    verdict="contradicted", evidence="reports/EXCLUDED_ARMS.md", patch="W3 results text",
    answered_with='text',
    pdf_response="The PDF states that the creativity prompting system prompt is the three steered SAE features' labels verbatim, so the two arms are not independent.")

add(id="M-fluency-constant", source="audit", location="App. A.3.4 composite creativity score",
    claim_or_concern="fluency is one of four scored components",
    our_measurement=("every response produces exactly 10 ideas because the prompt caps the "
                     "list at 10; a quarter of the composite is noise around a constant"),
    verdict="contradicted", evidence="reports/S1_6.md", patch="W3 results text",
    answered_with='text',
    pdf_response="The PDF states that fluency is fixed at 10 by the prompt's own cap and reports the composite without it, or reports it as a constant.")

add(id="M-length", source="both", location="App. A.3.5 length control",
    claim_or_concern=("scores are described as length-controlled; the repo's pooled file "
                      "reports positive slopes and up to 43% of variance"),
    our_measurement=("within the dataset the capability figures use, length explains up to "
                     "59% of a judge's variance with a NEGATIVE slope -- longer scores lower"),
    verdict="contradicted", evidence="reports/S1_5.md", patch="W3 results text",
    answered_with='data',
    pdf_response="The length regression is reported on the dataset the figures use: up to 59% of a judge's variance with a negative slope.")

add(id="M-no-agent-stats", source="reviewer", location="Sec. 4.2.2",
    claim_or_concern="no inferential test across agents for the capability scores",
    our_measurement=("a crossed mixed model with random intercepts for judge and response is "
                     "fitted in S1.5 and is available for the patch"),
    verdict="confirmed", evidence="reports/S1_5.md", patch="W3 results text",
    answered_with='data',
    pdf_response='A crossed mixed model with random intercepts for judge and response is reported for the capability scores.')

# --- effect sizes the paper does not put in context -------------------------
add(id="E-sae-ultimatum", source="audit", location="Sec. 4.2.1 ultimatum SAE result",
    claim_or_concern="the SAE altruism feature shifts the acceptance threshold",
    our_measurement=("3.45 tokens against its own baseline (stratified permutation p < 0.001, "
                     "within-level 95% CI [2.38, 4.57]) = 0.69 of ONE grid step, while the "
                     "persona on the same stack shifts 25.09 tokens = 5.02 grid steps"),
    verdict="confirmed", evidence="reports/S1_3.md; reports/PHASE1_FINDINGS.md",
    patch="W3 results text",
    answered_with='data',
    pdf_response="The effect is reported in grid steps: 3.45 tokens = 0.69 of one step, beside the persona's 25.09 tokens = 5.02 steps.")

add(id="E-sae-dose", source="audit", location="App. A.1.3 two SAE doses",
    claim_or_concern="two SAE doses (0.7/0.5 and 0.6/0.4) are run as distinct conditions",
    our_measurement="they produce byte-identical choice curves: dose gap = 0 risky choices in 1400",
    verdict="contradicted", evidence="reports/EXCLUDED_ARMS.md", patch="W3 results text",
    answered_with='text',
    pdf_response='The PDF states that the two SAE doses produce byte-identical choice curves and reports them as one condition.')

add(id="E-layer-dissociation", source="audit", location="App. B.11 layer comparison",
    claim_or_concern="layers 48 and 50 are presented as a replication of each other",
    our_measurement=("at matched lambda and matched switching point, layer 50 produces "
                     "hyper-fair rejections at target 30 (excess +0.061, CI [0.041, 0.084]) "
                     "where layer 48 produces exactly 0.000; layer 50 shows positive excess "
                     "at 9 of 10 lottery targets, layer 48 at 2 of 10. Whether this is a "
                     "difference in CHOICES waits on G4, because the legacy coding cannot be "
                     "audited"),
    verdict="open", evidence="reports/S1_3.md; reports/V5_parse_audit.md; pending G4",
    patch="W3 results text",
    answered_with='data',
    pdf_response="Reported with G4's coding agreement attached, so the reader can see whether the layer difference is in choices or in wording.")

add(id="E-persona-unreported", source="audit", location="not in the paper",
    claim_or_concern="the strongest single persona effect in the repository is unreported",
    our_measurement=("barely_prompting refuses a gamble worth 90 against a sure 50, 1400 "
                     "times out of 1400"),
    verdict="confirmed", evidence="reports/S1_8.md", patch="W3 results text",
    answered_with='data',
    pdf_response='The barely_prompting result is reported: a gamble worth 90 against a sure 50 refused 1400 times out of 1400.')

add(id="E-fig5-dataset", source="audit", location="Fig. 5; 5.57 / 5.18 / 6.25 / 5.23",
    claim_or_concern="Figure 5's numbers come from the repository's scoring pass",
    our_measurement=("the PDF and the repo differ by 2.8-3.6 points in the SAME direction for "
                     "every judge, so the built paper used a scoring pass this repository "
                     "does not contain; both sets are carried side by side and neither is "
                     "preferred"),
    verdict="open", evidence="results/S/s1/s1_5_pdf_vs_repo.csv; pending V1",
    reproducible_from_committed_code="no", patch="W1 provenance statement",
    answered_with='data',
    pdf_response="The PDF reports the repository's scoring pass and states that the earlier figure's values could not be reproduced from any scoring pass in the release: 21 single-value matches were found across 1,175 cells, exactly the 21.0 expected by chance, and no pair matched coherently.")

# --- framing and literature -------------------------------------------------
add(id="F-altruism", source="both", location="Sec. 1 ll. 018-020, 063-065; Sec. 3 ll. 135-139",
    claim_or_concern=("the ultimatum responder role is described as measuring altruism; "
                      "accepting low offers is called 'altruistic and selfless'"),
    our_measurement=("rejecting a low offer is costly fairness enforcement, not selfishness; "
                     "the extension plan's hypothesis 5 separates inequity aversion from an "
                     "accept bias using the proposer role and a mini-ultimatum variant"),
    verdict="deferred", evidence="feedback.txt; extension plan H5", patch="W2 methods text",
    answered_with='limitation',
    pdf_response='The construct is renamed to what the responder role measures - fairness enforcement / inequity aversion - and the limitations state that separating it from an accept bias needs the proposer role and a mini-ultimatum variant, which are ongoing work.')

add(id="F-steering-lit", source="reviewer", location="Sec. 1 ll. 058-061; Sec. 2.2 ll. 108-116",
    claim_or_concern=("activation-addition steering is attributed to diagnostic probing work "
                      "(Alain & Bengio, Hewitt & Manning, Belinkov); CAA, RepE, ITI and "
                      "ActAdd are absent"),
    our_measurement="no baseline from that literature is run anywhere in the repository",
    verdict="confirmed", evidence="feedback.txt; extension plan H4", patch="W8 related work",
    answered_with='data',
    pdf_response='Sec. 2.2 is rewritten to place probe steering within the activation addition literature, and G4b reports difference-of-means (CAA / ActAdd form) and first-PCA (RepE / LAT form) directions from the same activations, steered at the same doses. ITI is named in the limitations as not run.')

add(id="F-sae-mischaracterised", source="reviewer", location="Sec. 2.2",
    claim_or_concern="factual mischaracterisation of prior SAE literature",
    our_measurement="not checked; a citation question, not a data question",
    verdict="editorial", evidence="feedback.txt", patch="W8 related work",
    answered_with='text',
    pdf_response='The characterisation is corrected or the citation removed; AUTHOR TO VERIFY.')

add(id="F-causal-sae", source="both", location="Sec. 4.1",
    claim_or_concern=("SAE latent interpretations are attributed causally from co-occurrence "
                      "of top-activating latents, with no ablation or patching"),
    our_measurement="G6 (ablation and attribution) is defined and not yet run",
    verdict="deferred", evidence="FRIDAY_PLAN.md G6", patch="W3 results text",
    answered_with='data',
    pdf_response="G6 reports ablation of each named feature against 100 activation-matched random features and its attribution rank among all 65,536, so Sec. 4.1's readings are stated as tested or withdrawn.")

add(id="F-social-sim-scope", source="reviewer", location="Sec. 1, Sec. 5",
    claim_or_concern=("the framing is multi-agent social simulation; every experiment is a "
                      "single-turn individual vignette"),
    our_measurement="confirmed by the repository: no multi-agent or multi-turn run exists",
    verdict="confirmed", evidence="reports/REPO_MAP.md", patch="W6 limitations",
    answered_with='limitation',
    pdf_response='The framing is narrowed to single-turn individual vignettes, and the limitations state that multi-agent and multi-turn settings, where activation drift could accumulate, are not tested here and are ongoing work.')

add(id="F-table1", source="reviewer", location="Table 1 vs stated limitations",
    claim_or_concern="Table 1 recommends SAE steering in terms its own limitations contradict",
    our_measurement="see C-judges-order: SAE steering is below baseline on brick for 4 of 5 judges",
    verdict="contradicted", evidence="reports/S1_5.md", patch="W6 limitations",
    answered_with='text',
    pdf_response="Table 1's SAE recommendation is revised to match the per-judge result.")

add(id="F-judge-citations", source="reviewer", location="Sec. 4.2.2 judge citations",
    claim_or_concern="verifiability and archival validity of the judge model citations",
    our_measurement="the five judge identities are task V2, not yet run",
    verdict="open", evidence="pending V2", patch="W5 appendix",
    answered_with='data',
    pdf_response='App. A.3.5 reports the evaluator identifiers actually present per scoring pass, and states that the five-judge passes carry no API response ids while the single-judge passes carry one per row.')

add(id="F-semdis", source="reviewer", location="Sec. 4.2.2; App. A.3.4",
    claim_or_concern=("creative capability is judged entirely by prompted LLM judges, with no "
                      "objective, judge-independent semantic-distance benchmark (SemDis) or "
                      "human-normed AUT distribution"),
    our_measurement=("S1.6 computes four judge-independent text measures on the same responses. "
                     "They do not rescue the judges: category spread correlates 0.72 with the "
                     "judges pooled and 0.06 / 0.14 within task. No SemDis or human-normed "
                     "comparison exists in the repository"),
    verdict="confirmed", answered_with="limitation",
    pdf_response=("The four judge-independent measures are reported beside the judge scores "
                  "(S1.6), and the limitations state that no semantic-distance benchmark or "
                  "human-normed AUT distribution was used, and that validating against one is "
                  "ongoing work."),
    evidence="reports/S1_6.md", patch="W3 results text; W6 limitations")

add(id="F-collateral", source="reviewer", location="Sec. 4.2; Sec. 5",
    claim_or_concern=("no standardised psychometric battery is administered to check for "
                      "unintended collateral distortion of unsteered traits"),
    our_measurement="no such battery exists anywhere in the repository",
    verdict="confirmed", answered_with="limitation",
    pdf_response=("The limitations state that collateral effects on unsteered traits were not "
                  "measured, that the collateral frontier - the other task, arithmetic, "
                  "instruction following and KL on neutral prompts - is ongoing work, and that "
                  "no claim of specificity is made without it."),
    evidence="reports/REPO_MAP.md", patch="W6 limitations")

add(id="F-iti", source="reviewer", location="Sec. 2.2; Sec. 4",
    claim_or_concern=("Inference-Time Intervention is not compared against, alongside CAA, RepE "
                      "and ActAdd"),
    our_measurement=("G4b supplies the difference-of-means (CAA / ActAdd form) and first-PCA "
                     "(RepE / LAT form) directions from the probe's own activations, steered at "
                     "the same doses. ITI selects attention heads by probe accuracy and shifts "
                     "along head activations; nothing in the repository does that and it is not "
                     "built"),
    verdict="confirmed", answered_with="limitation",
    pdf_response=("Sec. 4 reports the difference-of-means and first-PCA baselines at equal dose "
                  "(G4b). The limitations state that ITI, which intervenes per attention head "
                  "rather than on the residual stream, is not among the baselines and is "
                  "ongoing work."),
    evidence="reports/G4b (pending); FRIDAY_PLAN.md G4b", patch="W8 related work; W6 limitations")

add(id="T-typos", source="reviewer", location="ll. 036, 070, 089, 117, 128, 202, 211, 312, 354, 400, 413, 418, 467, 470, 1394",
    claim_or_concern=("15 wording, grammar, notation and typographical corrections listed "
                      "across the review's five 'Minor Corrections and Typos' blocks"),
    our_measurement="transcribed verbatim into the W7 ledger; no measurement required",
    verdict="editorial", evidence="feedback.txt", patch="W7 feedback ledger",
    answered_with='text',
    pdf_response='All 15 corrections applied; ledger in paper_patches/FEEDBACK_LEDGER.csv.')


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS)
        w.writeheader()
        for r in R:
            w.writerow({k: r.get(k, "") for k in FIELDS})
    import collections
    c = collections.Counter(r["verdict"] for r in R)
    s = collections.Counter(r["source"] for r in R)
    print(f"wrote {OUT} ({len(R)} rows)")
    print("  verdicts:", dict(c))
    print("  sources: ", dict(s))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
