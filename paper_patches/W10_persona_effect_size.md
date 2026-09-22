# W10: an effect size and an interval for the persona result

**Status.** Draft for the authors (rule 12). Re-analysis of existing logs; no new compute.
Figure: `figures/s1_8_persona.{pdf,png}`. Script: `cv_bench/s1_behaviour.py`.

## Why this patch exists

Section 4.2.1 reports the persona result as two bare numbers:

> "generative agents exhibit human-like risk aversion, shifting their preference only once
> the risky reward exceeds 100 tokens, around 125. In the prompting scenario ... they start
> pivoting to risky option when the reward is only 20 tokens."

and for the ultimatum game, a baseline "start to take the offer when it exceeds 30" against
a prompted "even when the offer is only 10 tokens". No interval, no n, no test. This patch
supplies all three from the same logs, and the measured values corroborate the published ones.

## The measurement

Logistic switching points on the hosted stack, with two bootstrap schemes. The primary
interval holds the reward levels fixed and resamples responses within level; the sensitivity
interval resamples levels as well.

| | switching point | primary 95% CI | levels resampled | n | id |
|---|---:|---|---|---:|---|
| lottery, `baseline` | 132.9 | [131.3, 134.5] | [127.8, 139.5] | 1400 | `S1.3.hosted.lottery.baseline.switch` |
| lottery, `slightly_prompting` | 20.0 | [19.8, 20.2] | [17.5, 25.0] | 1400 | `S1.3.hosted.lottery.slightly_prompting.switch` |
| ultimatum, `baseline` | 37.9 | [36.9, 38.9] | [35.0, 39.9] | 680 | `S1.3.hosted.ultimatum.baseline.switch` |
| ultimatum, `prompting` | 12.8 | [11.5, 13.9] | [10.5, 14.9] | 680 | `S1.3.hosted.ultimatum.prompting.switch` |

Shifts, computed within stack so nothing is differenced across serving setups:

| | shift (tokens) | grid steps | stratified permutation p | id |
|---|---:|---:|---:|---|
| lottery, `slightly_prompting` | **-112.9** | -22.6 | 0.0005 | `S1.8.hosted.lottery.slightly_prompting.shift` |
| ultimatum, `prompting` | **-25.1** | -5.0 | 0.0005 | `S1.8.hosted.ultimatum.prompting.shift` |

## Draft text (replacing the bare numbers in 4.2.1)

> Unsteered, the agents switch to the risky option at 132.9 tokens (95% CI [131.3, 134.5],
> n = 1400). A persona that "slightly likes to take risks" moves that switching point to 20.0
> ([19.8, 20.2]), a shift of 112.9 tokens, or 22.6 levels of the reward grid (stratified
> permutation p = 0.0005). In the ultimatum game the acceptance threshold moves from 37.9
> ([36.9, 38.9]) to 12.8 ([11.5, 13.9]), a shift of 25.1 tokens (p = 0.0005, n = 680).

## Two arms that ran and are not reported

Rule 5. Both are on the hosted stack and belong in the record even if not in the figure.

- `barely_prompting` (lottery, 1400 rows) never crosses 0.5 on its grid, so no switching point
  is identified: `S1.8.hosted.lottery.barely_prompting.shift` is recorded as not available
  rather than extrapolated. This is informative about persona dose: the weaker trait wording
  produces no identifiable threshold at all, while the stronger one moves it 113 tokens.
- `lite_steering` (lottery, 2080 rows) gives a switching point of 71.7
  (`S1.3.hosted.lottery.lite_steering.switch`), between baseline and the reported `steering` arm.

## What is deliberately excluded

The local vLLM persona row is in the figure but should not carry a claim. It shows a shift of
-12.5 tokens (`S1.8.vllm.lottery.persona.shift`, -2.5 grid steps) against the hosted -112.9.
Three things differ between the two stacks at once: the persona text ("slightly likes to take
risks" against "You are inclined to take advantageous risky opportunities"), the option labels
(`['Safe Option', 'Risky Option']` against `"Final answer: safe"` / `"Final answer: risky"`),
and the temperature (0.5 against 0.7). The comparison is confounded and the figure's subtitle
says so. Do not write a stack-dependence claim from it.

The vLLM ultimatum persona cell never crosses 0.5 and is reported as not identified
(`S1.8.vllm.ultimatum.persona.shift`).
