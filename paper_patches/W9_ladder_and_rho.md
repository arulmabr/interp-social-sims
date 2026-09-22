# W9: the prompting ladder and the rho dose-response

**Status.** Draft for the authors (rule 12). Every number carries its `MANIFEST.csv` id.
**Nothing here is a new experiment.** All rows already existed in
`cleaned/behavioral_games_combined.csv` before this audit; `cv_bench/s1_ladder.py` fits
curves to them. Figure: `figures/s1_7_ladder.{pdf,png}`.

## Why this patch exists

Section 3.1 defines a five-rung prompting ladder (persona, chain-of-thought, few-shot,
their composition, and a rho sweep over the demonstrations). Section 3.1 then states:

> "For the lottery and ultimatum games we additionally trace a prompting dose-response:
> we vary the fraction rho in {0.0, 0.25, 0.5, 0.75, 1.0} of the N demonstrations that
> take the target action."

`rho` appears nowhere else in the submission. Figure 3 reports `baseline`,
`prompting` (the persona rung), `steering` and high temperature. The four remaining
rungs were run and are unreported: 2,080 rows each for `cot`, `fewshot` and each of the
five `fewshot_cot_dose*` conditions, 14,560 rows in total for the preference tasks, plus
200 to 400 rows per condition for the capability tasks.

## Correction required in Section 3.1, independent of whether the figure is added

Section 3.1 states N=6 demonstrations. With six exemplars the reachable fractions are
multiples of 1/6. **rho = 0.25 and rho = 0.75 cannot be realised.** The conditions named
`dose025` and `dose075` in fact use 2 of 6 and 4 of 6 demonstrations:

| condition | realised fraction | id |
|---|---|---|
| `fewshot_cot_dose000` | 0.0 (0 of 6) | `S1.7.exemplars.lottery.fewshot_cot_dose000.fraction_positive` |
| `fewshot_cot_dose025` | **0.3333** (2 of 6) | `S1.7.exemplars.lottery.fewshot_cot_dose025.fraction_positive` |
| `fewshot_cot_dose050` | 0.5 (3 of 6) | `S1.7.exemplars.lottery.fewshot_cot_dose050.fraction_positive` |
| `fewshot_cot_dose075` | **0.6667** (4 of 6) | `S1.7.exemplars.lottery.fewshot_cot_dose075.fraction_positive` |
| `fewshot_cot_dose100` | 1.0 (6 of 6) | `S1.7.exemplars.lottery.fewshot_cot_dose100.fraction_positive` |

Suggested replacement for the sentence above:

> For the lottery and ultimatum games we additionally trace a prompting dose-response:
> we vary the fraction of the N = 6 demonstrations that take the target action over the
> reachable values {0, 2/6, 3/6, 4/6, 1}, with the remainder taking the opposite action,
> and use reasoning-bearing demonstrations throughout.

## The result

Logistic switching points, local vLLM stack, cluster-bootstrap 95% intervals.

**Lottery.** Flat across the whole range; every interval overlaps every other.

| rho | switching point | 95% CI | id |
|---|---:|---|---|
| 0.0 | not identified on the grid | | `S1.7.vllm.lottery.fewshot_cot_dose000.switch` |
| 0.333 | 101.6 | [98.3, 105.8] | `S1.7.vllm.lottery.fewshot_cot_dose025.switch` |
| 0.5 | 96.0 | [87.9, 101.0] | `S1.7.vllm.lottery.fewshot_cot_dose050.switch` |
| 0.667 | 99.1 | [93.6, 102.0] | `S1.7.vllm.lottery.fewshot_cot_dose075.switch` |
| 1.0 | 100.0 | [92.9, 104.0] | `S1.7.vllm.lottery.fewshot_cot_dose100.switch` |

**Ultimatum.** Flat from 2/6 to 4/6, then a 27-token drop at 6 of 6.

| rho | threshold | id |
|---|---:|---|
| 0.0 | 48.1 | `S1.7.vllm.ultimatum.fewshot_cot_dose000.switch` |
| 0.333 | 38.7 | `S1.7.vllm.ultimatum.fewshot_cot_dose025.switch` |
| 0.5 | 37.1 | `S1.7.vllm.ultimatum.fewshot_cot_dose050.switch` |
| 0.667 | 37.9 | `S1.7.vllm.ultimatum.fewshot_cot_dose075.switch` |
| 1.0 | **10.5** | `S1.7.vllm.ultimatum.fewshot_cot_dose100.switch` |

## The other rungs

| condition | lottery switching point | 95% CI | id |
|---|---:|---|---|
| `baseline_rp` | 106.8 | [99.8, 116.3] | `S1.7.vllm.lottery.baseline_rp.switch` |
| `persona` | 94.3 | [85.2, 101.2] | `S1.7.vllm.lottery.persona.switch` |
| `cot` | **175.7** | [160.1, 191.8] | `S1.7.vllm.lottery.cot.switch` |
| `fewshot` | 100.6 | [95.6, 105.2] | `S1.7.vllm.lottery.fewshot.switch` |

On the ultimatum game only `fewshot` identifies a threshold (12.6,
`S1.7.vllm.ultimatum.fewshot.switch`); `baseline_rp`, `persona` and `cot` never cross 0.5
on that grid, which is reported as "not identified" rather than extrapolated.

## Draft text (appendix)

> **Prompting dose-response.** Varying the fraction of demonstrations that take the target
> action does not produce a graded shift in either game. On the lottery the switching point
> stays within [96.0, 101.6] across the reachable range, with overlapping bootstrap intervals
> at every level. On the ultimatum game the acceptance threshold sits near 38 for fractions of
> 2/6, 3/6 and 4/6 and falls to 10.5 only when all six demonstrations accept. The effect is a
> threshold at unanimity rather than a dose. Chain-of-thought moves the lottery switching
> point in the opposite direction from every other rung, from 106.8 unsteered to 175.7,
> making the agent markedly more risk averse when asked to reason before answering.

## Caveats the authors must keep in any version of this

1. **Stack.** These conditions ran on the local vLLM stack (Llama-3.3-70B-Instruct, bfloat16,
   tensor-parallel 2, temperature 0.7, top-p 1.0), not the hosted Goodfire stack behind
   Figures 3 and 5. The two stacks' unsteered lottery switching points differ: 132.9
   (`S1.3.hosted.lottery.baseline.switch`) against 106.8 (`S1.7.vllm.lottery.baseline_rp.switch`).
   The figure therefore plots Stack A's baseline as a labelled reference line only and
   differences nothing across stacks. Any main-text sentence must say which stack.
2. **Two estimators.** `MANIFEST` registers the logistic fit. The legacy linear interpolation
   gives 140.0 for `cot` where the logistic gives 175.7, because the curve is shallow and
   non-monotone there. Report one estimator and name it.
3. The rho = 0 lottery cell never crosses 0.5, so that panel has four usable points, not five.
