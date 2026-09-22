# W12: uncertainty on every switching point

**Status.** Draft for the authors (rule 12). Re-analysis of existing logs; no new compute.
Figures: `figures/s1_3_switching_lottery.{pdf,png}`, `figures/s1_3_switching_ultimatum.{pdf,png}`.
Script: `cv_bench/s1_behaviour.py`. Report: `reports/S1_3.md`.
Data: `results/S/s1/s1_3_switching_points.csv` (68 curves),
`results/S/s1/s1_3_pairwise_differences.csv` (121 within-stack contrasts).

## Why this patch exists

Every switching point and acceptance threshold in the submission is a bare point estimate.
No figure or table carries an interval, and no difference carries a test. This is the single
cheapest change to the paper's defensibility: the numbers already exist, 68 curves are already
fitted, and 121 within-stack contrasts are already computed.

## Method, and why there are two intervals

Each curve gets a two-parameter logistic, P(positive) = sigmoid(b0 + b1 x / 100), fitted by
IRLS on the per-level binomial counts. The switching point is -b0/b1. The legacy linear
interpolation (`Probes/calibration.py::switching_point_from_rows`) is reported beside it and
the two agree to a few tokens on well-behaved curves.

**The 40 "agents" are i.i.d. samples of one prompt at one temperature.** They differ only in a
`subject_id` string, and `agent.agent_instruction` is empty in every logged row. The spread
across those 40 draws is therefore the sampling noise of a single choice probability, not
evidence about where the curve sits. Two intervals are reported for that reason:

- **primary**, levels held fixed and responses resampled within level. This is the interval for
  "where is the threshold of this prompt set at this temperature".
- **sensitivity**, levels resampled as well. This is wider and answers "how much does the
  estimate depend on which reward levels were chosen".

Both are 2,000 draws.

## Worked examples

| curve | switching point | primary 95% | levels resampled | n | id |
|---|---:|---|---|---:|---|
| hosted lottery `baseline` | 132.9 | [131.3, 134.5] | [127.8, 139.5] | 1400 | `S1.3.hosted.lottery.baseline.switch` |
| hosted lottery `slightly_prompting` | 20.0 | [19.8, 20.2] | [17.5, 25.0] | 1400 | `S1.3.hosted.lottery.slightly_prompting.switch` |
| hosted lottery `lite_steering` | 71.7 | see MANIFEST note | | 1400 | `S1.3.hosted.lottery.lite_steering.switch` |
| hosted ultimatum `baseline` | 37.9 | [36.9, 38.9] | [35.0, 39.9] | 680 | `S1.3.hosted.ultimatum.baseline.switch` |
| hosted ultimatum `prompting` | 12.8 | [11.5, 13.9] | [10.5, 14.9] | 680 | `S1.3.hosted.ultimatum.prompting.switch` |
| vLLM lottery `baseline_rp` | 106.8 | [105.4, 108.1] | [99.7, 116.0] | 1400 | `S1.7.vllm.lottery.baseline_rp.switch` |

All 68 are in `MANIFEST.csv` under `S1.3.*.switch` with both intervals in the note field.

## Draft text (methods)

> **Switching points and their uncertainty.** Each psychometric curve is fitted with a
> two-parameter logistic on the per-level binomial counts, and the switching point is the
> reward at which the fitted probability reaches 0.5. We report two bootstrap intervals over
> 2,000 draws. The primary interval holds the stimulus levels fixed and resamples responses
> within each level; the sensitivity interval additionally resamples levels. The 40 agents at
> each level differ only by an identifier string and carry no distinct instruction, so the
> spread across them is the sampling noise of one choice probability rather than variation
> across individuals, and we do not treat them as a population.

## What this makes possible, and what it costs

**Enables.** Any claim of the form "condition A switches later than condition B" can be stated
with a within-stack contrast from `s1_3_pairwise_differences.csv` instead of by eye. It also
makes negative results reportable: the rho sweep in W9 is flat precisely because its intervals
overlap, and without intervals that panel says nothing.

**Costs.** The sentence above changes how the word "agents" reads in Section 3. The submission
describes 40 agents per condition; this states that they are 40 samples of one prompt. That is
a correction to the framing, not to any number, and the authors may prefer to phrase it
differently. It is included here because rule 1 does not permit reporting an interval whose
definition depends on a population that the logs show does not exist.
