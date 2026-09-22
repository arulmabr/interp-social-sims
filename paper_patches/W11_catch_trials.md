# W11: catch trials for the ultimatum responder

**Status.** Draft for the authors (rule 12). Re-analysis of existing logs; no new compute.
Figure: `figures/s1_2_catch.{pdf,png}`. Script: `cv_bench/s1_behaviour.py`.
Report: `reports/S1_2.md`.

## Why this patch exists

The submission contains no behavioural validity check. A reviewer asking "how do you know the
agent is playing the game rather than pattern-matching the prompt?" has nothing to read. The
ultimatum grids already contain the standard check and it was never analysed.

**The catch trial.** Offers of at least half the pie. A responder who rejects 60 out of 100
gives up a certain 60 in order to impose a loss of 40 on someone who treated them generously.
Under Fehr-Schmidt inequity aversion with beta < 1 a responder never rejects an offer above
half, and no standard fairness preference produces it. It is the ultimatum counterpart of a
dominated gamble. Every grid carries them: 9 levels x 40 agents = 360 trials per hosted
condition, 11 x 40 = 440 per probe condition.

Rates are reported beside `excess_over_staircase`, which subtracts the rejection rate that a
step function at that curve's own fitted threshold already implies. A curve whose threshold
has been pushed above 50 will reject some fair offers without any extra irrationality; the
excess column separates the two.

## The result on the hosted stack, which is the stack behind Figures 3 and 5

| condition | threshold | P(reject given offer >= 50) | Wilson 95% | excess | id |
|---|---:|---:|---|---:|---|
| `baseline` | 38.1 | **0.000** | [0.000, 0.0106] | 0.000 | `S1.2.hosted.baseline.pReject_hyperfair` |
| `prompting` | 13.3 | **0.000** | [0.000, 0.0106] | 0.000 | `S1.2.hosted.prompting.pReject_hyperfair` |
| `steering` | 32.9 | **0.000** | [0.000, 0.0106] | 0.000 | `S1.2.hosted.steering.pReject_hyperfair` |

Zero hyper-fair rejections in 1,080 trials across all three published conditions.

## The result on the probe stacks, which must be reported with it

Rule 5. These rates are substantial and rise with the steering target.

| stack | target | P(reject given offer >= 50) | Wilson 95% | excess over staircase |
|---|---:|---:|---|---:|
| probe Llama L48 | 30 | 0.000 | [0.000, 0.0087] | 0.000 |
| probe Llama L48 | 40 | 0.021 | [0.011, 0.038] | 0.021 |
| probe Llama L48 | 50 | 0.093 | [0.069, 0.124] | 0.002 |
| probe Llama L48 | 60 | **0.232** | [0.195, 0.274] | **-0.041** |
| probe Llama L50 | 60 | **0.268** | [0.229, 0.312] | -0.005 |
| probe Qwen L17 | 60 | **0.400** | [0.335, 0.469] | 0.000 |

ids follow the pattern `S1.2.probe-llama-l48.target60.pReject_hyperfair` and
`...excess_over_staircase`.

**The honest reading.** At the highest targets the excess is near zero or negative, so the
rejections are what a step at the fitted threshold already implies: steering has moved the
threshold itself above half (59.6 at L48 target 60, 65.0 at Qwen target 60). This is not extra
noise on top of a sensible policy. It is that calibrating the responder to a target of 60
places it outside the space of policies any standard fairness preference can generate. That is
a real limit on what "calibrated control" means here, and it should be stated rather than left
for a reviewer to derive.

## Draft text (appendix, with one main-text sentence)

Main text, after the ultimatum baseline is introduced:

> The ultimatum grids include hyper-fair catch trials, offers of at least half the pie, which
> no standard fairness preference rejects. Across the baseline, prompting and steering
> conditions the agents reject none of 1,080 such offers (Appendix, Table W11).

Appendix:

> **Catch trials.** Offers of at least half the pie are rejected at 0.000 (Wilson 95%
> [0.000, 0.0106], n = 360 per condition) in every hosted condition, so the responder is not
> rejecting indiscriminately. On the probe stacks the rate rises with the calibration target,
> reaching 0.232 at a target of 60 on Llama layer 48 and 0.400 on Qwen layer 17. At those
> targets the fitted threshold has itself moved above half (59.6 and 65.0), so the rejections
> are consistent with a step at the calibrated threshold rather than with added noise; the
> excess over that step is -0.041 and 0.000 respectively. Calibrating the responder above an
> even split therefore produces behaviour outside the range of standard inequity-averse
> policies, which bounds the interpretation of high-target calibration.

## Caveat

`P(accept | offer <= 10)` is computed in `results/S/s1/s1_2_catch_ultimatum.csv` and in
`reports/S1_2.md` but is not registered in `MANIFEST.csv`. If the authors want it in the paper
it must be registered first, per rule 1. The vLLM `baseline_rp` value of 0.775 is the one worth
looking at before deciding.
