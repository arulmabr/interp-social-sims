# G2_legacy_format.md — the legacy code path does not produce answers

**This is the most consequential thing G2 has found, and it arrived in its first arm.**
Raised immediately rather than at the end of the run.

Data: `/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g2_lambda0/*.jsonl`.
Runner: `cv_bench/g2_lambda0.py` (jobs 23379474, 23379475).

---

## 1. What was measured

G2's `legacy` arm reproduces the legacy pipeline exactly: it *imports*
`Probes.models.Wrapped`, which tokenises the raw prompt string —
`self.tokenizer(prompt, return_tensors="pt")` — with **no chat template**
(`Probes/models.py` contains zero uses of `apply_chat_template`). Sampling, grids, N and
per-agent seeding are the legacy ones. The steering hook is not installed.

Strict coding, which never forces a choice:

| arm | file | n | **no answer / unclear** | safe or reject | risky or accept |
|---|---|---:|---:|---:|---:|
| **legacy** | `llama_legacy_lottery` | 1,120 | **989 (88.3%)** | 121 | 10 |
| **legacy** | `qwen_legacy_lottery` | 840 | **753 (89.6%)** | 32 | 55 |
| **legacy** | `qwen_legacy_ultimatum` | 360 | **214 (59.4%)** | 12 | 134 |
| chat | `qwen_chat_lottery` | 840 | 58 (6.9%) | 231 | 551 |
| chat | `qwen_chat_ultimatum` | 360 | **0 (0.0%)** | 100 | 260 |
| chat64 | `qwen_chat64_lottery` | 840 | 58 (6.9%) | 231 | 551 |
| chat64 | `qwen_chat64_ultimatum` | 360 | 1 (0.3%) | 100 | 259 |

46.5% of the Llama legacy generations are **literally empty**. Most of the rest are the model
continuing the prompt as a document rather than answering it:

```
' \n\n(Note: Please keep in mind the expected value of both'
' \n\n(Remember, the goal is to maximize your expected'
" \n\n(Note: Please respond with the exact word, either '"
```

This is what an instruction-tuned model does when handed a bare string with no assistant turn to
complete. Applying the chat template and changing nothing else takes the no-answer rate from
**89.6% to 6.9%** on the same prompts, the same grid and the same sampling.

## 2. Why this matters

The published probe data contains **no unparseable trial at all**.
`figure_7_psychometric_curves_llama` has 21,040 per-agent rows and `parsed_choice` takes only the
values 0 and 1 — never −1. The same holds for the layer-50 and Qwen figure keys
(`MANIFEST.csv:V5.probe_unparseable_share.*` = 0.0).

A pipeline that yields no answer on 88% of trials cannot produce a dataset with 0% unparseable rows.

**So the committed legacy code path is not what produced Figures 4, 6 and 9–18.** Something differed
between the code in this repository and the runs that made the paper's probe figures. The most likely
candidate, given the size of the effect, is that the real runs applied a chat template or some other
assistant framing that `Probes/models.py` does not.

This is a stronger statement than the earlier findings. `PROBE_PROVENANCE.md` established that no
probe artefact was saved; `V5_parse_audit.md` established that the raw generations were overwritten.
This establishes that **the code that remains cannot regenerate the data that remains**.

## 3. What it changes

**For the paper.** Any claim that the probe results are reproducible from this repository is not
supportable. Under rule 1 of `FRIDAY_PLAN.md` — the paper follows the repo — the probe figures either
get regenerated on a stack that does work (which is a different stack, reported as such) or they are
described as produced by a pipeline that is no longer recoverable. This needs an author decision and
it is on the critical path for W3 and W4.

**For G4.** G4 rebuilds the choice probe "by the legacy recipe". The legacy recipe labels each
activation by the model's own sampled choice, and under the legacy format 88% of trials have no
choice to label. `build_preference_probe` drops unparseable trials, so a faithful legacy rebuild would
train on roughly 12% of its intended data — 43 of 360 lottery rows. **I have not silently redesigned
it.** The options, for the authors:

1. run the legacy recipe as written, report that it trains on ~12% of trials, and treat that as the
   finding;
2. run it with the chat template, label it a reconstruction on a new stack, and report both the
   yield and the fact that the legacy format could not supply one;
3. both, which is roughly twice the GPU time and is affordable.

My recommendation is **3**: the comparison is the result. `reports/SCHEDULE.md` costs it that way.

**For V5.** V5 asked whether the legacy coding could be audited. The answer is now sharper than
"the raw text was discarded": under the legacy format there is mostly nothing to code. The
layer-48 versus layer-50 difference in coded outputs remains a difference in coded outputs, and the
question of what produced those codings is now open in a way it was not this morning.

## 4. What is not claimed

- Not that the published numbers are wrong. They may be perfectly good numbers from a working
  pipeline whose code did not reach the repository.
- Not that the chat template *is* what the original runs used. It is the candidate that fits the
  evidence; only the authors or a surviving run script can settle it.
- Not that Qwen and Llama behave identically. The Llama legacy arm is still running; its chat arm has
  not been measured yet, and this report will be updated when it is.

## 5. For the authors

One question settles a lot: **is there a run script, notebook or shell history from the original probe
runs that shows how the prompt was built?** `GATE_S0_RESPONSE.md` §1.3 already asks where those runs
executed. If the answer includes a working directory, its copy of `models.py` is the thing to look at.
