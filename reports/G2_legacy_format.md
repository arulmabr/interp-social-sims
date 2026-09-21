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

---

# Addendum, 22 Sept — the three checks the authors asked for

## A.1 No caller retries, falls back to logits, or filters rows

**The psychometric sweeps that produced the published curves do neither.** A single
`model.generate(...)` call per trial, parsed once, and the row is written whatever came back
(`Probes/tasks/preference.py:48-58`, and `:115-125` for the ultimatum):

```python
parsed = prompts.parse_lottery_choice(result.text)
return {
    ...
    "response": "Risky" if parsed == 1 else ("Safe" if parsed == 0 else result.text.strip()),
    "parsed_choice": int(parsed) if parsed is not None else -1,
}
```

No loop, no retry, no second attempt, no logit fallback. An unparseable generation is written as
`parsed_choice = -1` with its raw text preserved. **That branch is never taken in the published
data.**

There is exactly one drop in the whole package, and it is in **probe training**, not in the sweeps
(`Probes/experiments/_common.py:99-101`):

```python
choice = parse_fn(gen.text)
if choice is None:
    continue  # unparseable -> no ground-truth label, drop the trial
```

Two downstream filters exist and are **not** row filters: `Probes/calibration.py:90`
(`if v in (0, 1)`) and `preference.py::aggregate_by_param` both ignore `-1` when computing a
switching point or a cell fraction. They operate on rows that are already stored, so they cannot
explain `per_agent_rows` containing no `-1` at all.

The retries in `Probes/judge.py:298-317` are HTTP retries for the LLM judge and touch nothing here.

## A.2 Git history: the code that ran is not in it

`git fetch --all --tags` brought nothing new; the only remote is
`github.com/arulmabr/interp-social-sims`, and `origin/main` is at the same commit as local `main`.
32 commits across all refs.

**`-S` search over every commit on every branch:**

| string | commits | where |
|---|---:|---|
| `apply_chat_template` | 5 | 3 are mine (21 Sept). The 2 legacy ones are `53c449e` and `59ca0f0`, and in both the hits are only in **`SAE/scripts/`** and **`Revised Prompting/scripts/`** |
| `add_generation_prompt` | 4 | same pattern |
| `<\|begin_of_text\|>` | 1 | `59ca0f0`, in `SAE/` only |
| `<\|start_header_id\|>`, `<\|im_start\|>` | 0 | — |

**No commit, on any branch, ever put a chat template anywhere in `Probes/`.** The SAE and vLLM
stacks used one throughout; the probe stack never did.

**Earlier versions of the probe files: there are none.**

| file | commits touching it | first appearance |
|---|---:|---|
| `Probes/models.py` | **1** | `59ca0f0`, +176 lines |
| `Probes/config.py` | **1** | `59ca0f0`, +207 lines |
| `Probes/tasks/prompts.py` | **1** | `59ca0f0`, +92 lines |
| `Probes/tasks/preference.py` | **1** | `59ca0f0`, +220 lines |

`git log --follow` finds no predecessor path — these are first appearances, not renames. Each file
has been modified **zero** times since. So there is no earlier version whose prompt construction,
`max_new_tokens` or sampling could have differed: the pipeline entered git in exactly its current
form and stayed there.

**Against the dates in the run records**, this is the heart of it. `59ca0f0` is the repository's
**root commit**, dated **2026-05-25**. The runs it supposedly produced are dated earlier:
`SAE/data/raw/games/.../results_20251008_225522` (8 Oct 2025) and
`product_innovation_20251102_202650` (2 Nov 2025). The multi-judge rescoring carries epoch
timestamps from 26 May 2026, the day after the root commit.

**The experiments predate the repository.** Git cannot show what changed, because the working code
was committed months after it ran — if the committed copy is even the same copy.

## A.3 What the run records store, and what it can prove

Fields in `figure_7_psychometric_curves_llama.per_agent_rows`: `agent_id`, `game`,
`lambda_calibrated`, `model`, `parsed_choice`, `probe_layer`, `prompt`, `response`,
`risky_reward_tokens`, `target_switching_point_tokens`.

- **Prompt text: stored.** All **21,040 of 21,040** stored prompts match what the committed
  `Probes/tasks/prompts.py` produces, character for character. So `prompts.py` is unchanged.
- **Token counts: not stored.** (`risky_reward_tokens` is the game's payoff in "tokens", not a
  tokenizer count.)
- **Generation length: not stored.**

**The stored prompt cannot settle the question, and it is worth being exact about why.**
`run_lottery_trial` stores the string it *passes to* `generate`; `Wrapped.generate` then tokenises
whatever it is given. A chat template applied inside `generate` — or a different `generate` — would
leave the stored field identical. The match confirms the prompt *function* is unchanged and is silent
on what was tokenised.

## Where that leaves it

Three independent checks, and none of them explains the contradiction:

- no retry, no fallback, no row filter in the path that wrote the rows;
- no earlier version of the probe code anywhere in git, and no chat template in `Probes/` at any
  commit;
- the stored prompts match the committed code exactly, and cannot discriminate.

The committed pipeline yields no answer on 88% of trials; the published data has none missing. The
difference lies in something that never reached this repository, and the repository's history begins
seven months after the experiments. **Only an author, a surviving working directory, or a run script
can close this.**
