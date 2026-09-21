# G2 — the unsteered choice curve, per arm and per coding

FRIDAY amendment (22 Sept), item 1. `reports/G2_legacy_format.md` reported one number
from this run, the no-answer rate, because that number settled whether the committed
code path could have produced the published data. This is the rest of it: for every
model, arm and coding, the no-answer rate, the switching point and ultimatum threshold
with within-level 95% intervals, and the two catch-trial rates, beside the hosted and
vLLM baselines.

Source: `results/S/s1/g2_summary.csv`, built by `cv_bench/g2_summary.py` from the
raw generations in `g2_lambda0/*.jsonl`. λ = 0 throughout — no steering, no
intervention hook installed.

The three arms are the ones the amendment fixed: **legacy** is the committed code
path exactly (raw prompt string, no chat template, 12 new tokens); **chat** adds the
chat template and nothing else; **chat64** adds the chat template and raises the cap
to 64 new tokens, which the amendment labelled a departure. The two codings are
**legacy** (`Probes/tasks/prompts.py`, the last mention of either label) and **strict**
(the first option the response states; `no_answer` and `unclear` are outcomes, never
forced).

`fit` marks whether the logistic switching point lands inside the observed grid. A
fit outside the grid is an extrapolation and is not a switching point; where it is
marked `out`, the interpolated crossing of 0.5 on the observed rates is the number
to read, and where that is `—` the curve never crosses 0.5 anywhere on the grid.

## Llama-3.3-70B-Instruct, lottery

| arm | coding | no answer | n coded | switch (95% CI) | fit | crossing | P(risky \| n<50) |
|---|---|---|---|---|---|---|---|
| legacy | legacy | **0.870** | 234 | 604.3 [−2682, 4280] | out | 35.0 | 0.087 [0.024, 0.268] |
| legacy | strict | **0.873** | 229 | 608.5 [−2708, 4438] | out | — | 0.045 [0.008, 0.218] |
| chat | legacy | 0.680 | 576 | 93.0 [89.2, 96.7] | in | 68.4 | 0.000 |
| chat | strict | 0.680 | 576 | 93.0 [89.2, 96.7] | in | 68.4 | 0.000 |
| chat64 | legacy | 0.000 | 1800 | **74.6** [72.7, 76.6] | in | 62.6 | 0.000 |
| chat64 | strict | 0.000 | 1800 | **222.7** [207.2, 242.5] | in | 110.0 | 0.000 |
| *hosted baseline (A)* | as published | 0.000 | 1400 | 132.9 [131.3, 134.5] | in | 127.6 | 0.000 |
| *vLLM baseline (B)* | as published | 0.000 | 1400 | 106.8 [105.4, 108.1] | in | 102.9 | 0.000 |

## Llama-3.3-70B-Instruct, ultimatum

| arm | coding | no answer | n coded | threshold (95% CI) | fit | crossing | P(reject \| offer≥50) |
|---|---|---|---|---|---|---|---|
| legacy | legacy | **0.951** | 37 | 111.4 [−448, 522] | out | 30.0 | 0.481 [0.307, 0.660] |
| legacy | strict | **0.966** | 26 | 216.6 [−591, 1514] | out | 40.0 | 0.176 [0.062, 0.410] |
| chat | legacy | 0.000 | 760 | — | — | — | 0.000 |
| chat | strict | 0.000 | 760 | — | — | — | 0.000 |
| chat64 | legacy | 0.000 | 760 | — | — | — | 0.000 |
| chat64 | strict | 0.000 | 760 | — | — | — | 0.000 |
| *hosted baseline (A)* | as published | 0.000 | 680 | 37.9 [36.9, 38.9] | in | 38.1 | 0.000 |
| *vLLM baseline (B)* | as published | 0.000 | 680 | −71.0 [−401, −17] | out | — | 0.028 [0.015, 0.050] |

Under the chat template Llama **accepts every offer from 10 to 100**, 760 of 760, at
both caps and under both codings. There is no threshold to report, not a wide one.
The hosted baseline's 37.9 is therefore not a property of the model that survives a
change of prompt format.

## Qwen2-7B-Instruct

| game | arm | coding | no answer | n coded | switch (95% CI) | fit | crossing | catch rate |
|---|---|---|---|---|---|---|---|---|
| lottery | legacy | legacy | **0.894** | 89 | 149.0 [−659, 980] | out | 23.2 | 0.636 [0.430, 0.803] |
| lottery | legacy | strict | **0.896** | 87 | 141.9 [−456, 849] | out | 23.2 | 0.636 [0.430, 0.803] |
| lottery | chat | both | 0.069 | 782 | 47.8 [45.7, 49.8] | in | 51.3 | 0.151 [0.110, 0.204] |
| lottery | chat64 | legacy | 0.069 | 782 | 44.6 [42.3, 46.8] | in | 50.6 | 0.213 [0.165, 0.271] |
| lottery | chat64 | strict | 0.069 | 782 | 47.8 [45.7, 49.8] | in | 51.3 | 0.151 [0.110, 0.204] |
| ultimatum | legacy | legacy | 0.575 | 153 | 1104.5 [−3060, 3236] | out | — | 0.138 [0.083, 0.222] |
| ultimatum | legacy | strict | 0.594 | 146 | 1815.8 [−2442, 3264] | out | — | 0.090 [0.046, 0.167] |
| ultimatum | chat | both | 0.000 | 360 | 29.9 [27.6, 32.1] | in | 31.1 | 0.010 [0.003, 0.036] |
| ultimatum | chat64 | strict | 0.003 | 359 | 30.0 [27.7, 32.3] | in | 31.3 | 0.010 [0.003, 0.036] |

## What the table says

**1. No arm of the committed code path reproduces a published curve.** The legacy arm
codes 13% of Llama's lottery trials and 5% of its ultimatum trials, and on what it does
code the logistic lands hundreds of tokens outside the grid. Its dominated-choice rate
is 0.087 where every published Llama curve reports 0.000, and its hyper-fair rejection
rate is 0.481 on 27 coded catch trials. These are not a version of the published numbers; they
are what a 13% sample of a 45-level grid looks like.

**2. The chat template alone does not rescue Llama.** It rescues Qwen — 89.4% no answer
falls to 6.9% — but Llama still fails to answer 68.0% of lottery trials in 12 tokens,
because it opens with "To solve this, let's calculate the expected value" and the cap
lands mid-sentence.

**3. The chat64 arm's 0.0% no-answer rate is an artefact, and the number to distrust.**
Raising the cap to 64 tokens does not make Llama state a decision more often. It makes
the response long enough to mention both labels while restating the options, which is
enough for both codings to assign a choice. Measured directly:

| | states a decision | codings assign a choice |
|---|---|---|
| Llama, chat, lottery | 32.0% | 32.0% |
| Llama, chat64, lottery | **32.0%** | **100%** |

The decision rate is identical. The extra 52 tokens bought coverage, not answers.

**4. The two codings disagree on 40.9% of that arm, always the same way.** On 737 of
1800 chat64 lottery trials the legacy rule says risky and the strict rule says safe.
Every one of the 737 is a truncated reasoning trace of the form

> To make a decision, let's evaluate the expected value of each option:
> 1. Safe Option: You get 50 tokens for sure. The expected value is 50 tokens.
> 2. Risky Option: There's a 50% chance of getting 65 tokens and a 50% chance of 0

The legacy rule takes the **last** label mention, which is option 2, *Risky*. The strict
rule takes the **first**, which is option 1, *Safe*. Neither has seen a choice: both are
reading the order in which the prompt lists its own options. The consequence for the
switching point is not small — **74.6 under the legacy coding, 222.7 under the strict
one**, a gap of 148 tokens, or about 30 grid steps, on identical generations.

This is the coding-agreement number the standing gate refers to. It says no excess
number and no probe-stack curve described as a shift in choices can rest on the legacy
coding of a truncated response. G4 therefore carries a third coding that refuses to code
a response which never states a choice, alongside both of these (`logs/DECISIONS.md`
D55), and its token cap is chosen by measurement rather than inherited
(`cv_bench/instr.py`).

**5. Qwen's codings agree (0.972–1.000) because Qwen answers with a bare label.** 89.6%
of its chat-arm lottery responses are the single word *Safe* or *Risky*. Where there is
one mention, first and last are the same mention. The disagreement above is specific to
responses long enough to reason and too short to conclude.

**6. Qwen makes dominated choices at a rate no published curve reports.** 15.1% under
the strict coding, 63.6% on the legacy arm's 22 coded dominated-level trials. Every
published Qwen lottery curve reports 0.000.
