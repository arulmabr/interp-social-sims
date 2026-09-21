# V5_parse_audit.md — do the excess results rest on clean responses?

Task V5, added by the author amendments of 22 Sept. It gates every "excess over the staircase" number
before it may enter a patch. Values as `MANIFEST.csv:V5.*`.

**Verdict: the excess results are not invalidated, but one assumption behind them cannot be checked
from this repository, and G2 can settle it at no extra cost.**

---

## 1. What the amendment asked, and what the data allows

> "For every curve with positive excess, open the raw responses. Report the share that parse cleanly,
> the share that are malformed or off-task, and how the legacy parser coded the malformed ones. If
> malformed outputs were coded as a choice, recompute the excess on clean responses only and report
> both."

Every curve with positive excess is on the probe stack (Stack C). For that stack the first half is
answerable and the second half is not, for a reason worth stating plainly.

**Share that parse cleanly: 100%.** Across 51,920 probe-stack trials — 21,040 at layer 48, 21,040 at
layer 50, 9,840 on Qwen — `parsed_choice` is never `-1`
(`V5.probe_unparseable_share.*` = 0.0 for all three). Every row carries one of exactly four response
strings: `Risky`, `Safe`, `Accept`, `Reject`.

**Share that are malformed or off-task: not recoverable.** `Probes/tasks/preference.py` writes

```python
"response": "Risky" if parsed == 1 else ("Safe" if parsed == 0 else result.text.strip()),
```

so the generation is **replaced by the canonical label whenever it parses**. The raw text survives only
for trials that failed to parse, and there are none. `V5.probe_raw_generation_retained` = false.

So "100% parse cleanly" is not evidence that the generations were clean. It is a consequence of the
parser accepting any text containing `Risky` or `Safe` anywhere, and of the writer discarding the
evidence afterwards. The recomputation on clean responses only cannot be performed for Stack C,
because by construction there is nothing the repository marks as unclean.

## 2. How much this matters, measured where the raw text does survive

Stacks A and B keep the generation (`generated_tokens.*`) beside the recorded answer
(`answer.*`), so the legacy parser can be run against them and compared with the answer the run
actually recorded. The legacy rule is the **last** match of `\b(Risky|Safe)\b`, case-insensitive.

| stack | game | n | legacy regex would code a **different** answer | rows mentioning both labels |
|---|---|---:|---:|---:|
| hosted Goodfire | lottery | 7,000 | **55.2%** | 85.5% |
| hosted Goodfire | ultimatum | 2,040 | **33.9%** | 89.6% |
| local vLLM | lottery | 12,600 | 0.03% | 100% |
| local vLLM | ultimatum | 6,120 | 0.03% | 96.2% |

This is not an error in the hosted data — the hosted stack used EDSL's multiple-choice validation, not
this regex. It is a measurement of **how fragile the legacy rule is on text that carries a rationale**.
The hosted prompt asks for a comment after the answer; the comment mentions the other option most of
the time; the last-match rule then reads the comment instead of the answer, and gets it wrong in
between a third and a half of trials.

The vLLM stack shows the opposite because its prompt forces `Final answer: safe|risky` at the very end.
When the label is last by construction, last-match is safe.

## 3. What follows for the probe stack

The probe stack sits between the two. It generates at most **12 tokens** with no comment requested, so
its generations are probably just the label — in which case the coding is sound and the excess results
stand as computed. But "probably" is doing work there, and it cannot be replaced by evidence:

- the raw text was discarded at write time (§1);
- the prompt ends `Respond with either 'Safe' or 'Risky' as your final answer`, which invites the
  bare label but does not force it;
- twelve tokens is room for `Safe. The risky option is worse` — which the last-match rule codes as
  **Risky**.

**So the honest statement for any patch is:** the positive excesses — **nine** of the ten layer-50
lottery targets, layer 48 at targets 49 and 68, and layer 50 ultimatum target 30 — are computed from choices coded by a rule
that, on the one stack where it can be checked against retained text, disagrees with the recorded answer
on 34–55% of trials whenever a rationale is present. No such check is possible on the probe stack.

## 4. What settles it, and it is nearly free

**G2 regenerates on the same checkpoint with the legacy code path.** It should:

1. **retain the raw generation** for every trial, parsed or not, in a column the legacy pipeline
   does not have;
2. record the legacy regex's coding **and** a strict coding (the label must be the final token, or the
   generation must be exactly one label) and report the disagreement rate;
3. report the excess under both codings.

If the two codings agree on the probe stack's short generations, the S1 excess results are confirmed
and the paper can cite them. If they disagree materially, the excess results are withdrawn and the
disagreement is itself the finding. Either outcome is reportable, and it costs one extra column.

Until G2 returns, **no excess number goes into a patch** — which is exactly what the amendment
instructs.

### A scope correction to the amendment's own list

The amendment names "all ten L50 lottery targets". It is now **nine**. Layer-50 lottery target 30 was
withdrawn while implementing P13: its logistic fit returns a switching point of **−12.96** against an
interpolated crossing of 32.9, because that curve is non-monotone in the tail. A fit outside the
observed grid cannot imply a staircase rate, so the excess for that curve is not computed
(`fit_inside_grid = False`). Its raw responses are still audited above along with the rest.

## 5. One thing that is safe to say now

The *direction* of the layer-48 versus layer-50 dissociation does not depend on the parser. Both
layers were coded by the same rule, on the same grid, at matched λ and matched switching points. A
parser that mis-codes some fraction of generations would have to do so **differently between the two
layers** to manufacture the difference, and there is no mechanism for that. The dissociation is
therefore more robust than the absolute excess values are.
