# DECISIONS.md

Decisions made while working, and why. Anything marked AUTHOR DECISION is recorded here as *proposed*,
not settled.

---

## 2026-09-21 — S0

**D1. Branch `iclr-extension` cut from `main` at `0aeba62`.** CLAUDE.md rule 10. Nothing committed
during S0; the working tree holds only new files under `cv_bench/`, `reports/`, `logs/`, `results/S/`
and `MANIFEST.csv`.

**D2. Every number in the S0 reports is produced by one script, `cv_bench/s0_recon.py`.** Rule 1 says
no number without a file behind it. Rather than quoting values computed in a shell session that
evaporates, the script recomputes all 234 of them from the repository's own files and writes
`MANIFEST.csv` and `results/S/s0_numbers.json`. `rm MANIFEST.csv && python -m cv_bench.s0_recon`
reproduces both byte-for-byte.

**D3. The script uses neither pandas nor scikit-learn.** This machine has pandas 1.5.3 and scikit-learn
1.2.2; `Probes/requirements.txt` requires scikit-learn ≥ 1.4, and the user slice is capped at 10 GB of
memory. Streaming `csv` plus numpy keeps S0 runnable in the environment that actually exists and avoids
a silent version mismatch. Noted in `REPO_MAP.md` §7 so it is fixed properly before any probe rerun.

**D4. Extrapolated quantities are labelled as extrapolations everywhere they appear.** The λ=0
switching points (~27 lottery, ~24 ultimatum) and the λ=0 creativity score (~3.96) are OLS intercepts
outside the observed λ range. They are informative and they are not measurements; they must not reach
the paper. S2.3 measures them. Rule 1.

**D5. No Goodfire API call was attempted.** No `GOODFIRE_API_KEY` is set, and the repository's own
documentation records the hosted Ember service as retired with its nudge normalisation unrecoverable.
The purpose behind the Q10 instruction — securing the feature labels and UUIDs against an external
dependency — is met instead by recovering all eight from the logged `model.controller` records into
`results/S/goodfire_labels.json`.

**D6. The paper-figure ↔ rendered-PNG mapping is presented as inferred, with uncertain rows marked.**
There is no LaTeX source or figure manifest in the repository, so the mapping is reconstructed from
`PAPER_AUDIT.md` and `cleaned/README.md`. Guessing silently would put unverified figure numbers into
patches that the authors would then have to unpick. Raised at the gate instead.

**D7. Nothing in the four legacy directories was moved, renamed, edited or deleted** — including the
two `*.preintegration.bak` files, the twelve untracked-looking-but-tracked `SAE/runs/` folders, and the
layer-50 data that never reached `cleaned/`. Rule 2. An `archive/` location is *proposed* in
`EXCLUDED_ARMS.md` §1 and not created.

**D8. Discrepancies I could not settle are reported as open, not resolved in either direction.** Three:
the Fig. 11/18 tracking provenance (Q3), the "5.57 vs 5.18" / "6.25 vs 5.23" inline pairs, and the
high-temperature brick score the audit reads as ≈2.1. In each case the repository is consistent with
more than one story, and saying which is right would be inventing a fact.

**D9. `S0.I` (dominated choices under probe steering) computed during S0 although it belongs to S1.1.**
It is the fact the extension's thesis rests on, it costs one pass over data already loaded, and the
gate summary is much less useful without it. S1.1 still does it properly, per condition, with Wilson
intervals.

**D10. S1 continues while the gate is open, and nothing else starts.** The gate's own text permits S1
(no GPU, no decisions) and forbids everything else. S1.4(c) is dropped as infeasible — it presumes
cached activations, and none exist anywhere in the repository.

### Proposed, for the authors to settle (AUTHOR DECISION)

- **P1.** Develop on Llama-3.1-8B-Instruct first (amendment A10). It is the only relevant model already
  on disk, and neither HOME (~37 GB free) nor POOL (~5.7 GB free) can hold a bf16 70B checkout.
- **P2.** Run ICLR GPU work on `ou_bcs_low` only, and touch none of my other running jobs.
- **P3.** Report the prompting ladder on its own axes with the stack stated, rather than overlaying it
  on Figs. 3 and 5. Overlaying would reproduce the cross-stack confound the audit flags in §4.6.

---

## 2026-09-21 — S1, under GATE_S0_RESPONSE §3 P2–P5 and P10

**D11. Intervals are bootstrapped over reward levels, not trials.** At a fixed reward level the 40
"agents" are i.i.d. draws from one prompt at one temperature, so they say how noisy that cell is, not
how uncertain the curve's location is. Both intervals are in
`results/S/s1/s1_3_switching_points.csv`; the reward-level one is primary everywhere, and it is the
wider of the two for every hosted curve. This is the plan's own rule for Track B (§0.1), applied to S1
because the same argument holds.

**D12. A switching point is reported only where the measured curve crosses 0.5 inside the grid.**
Several curves never do — `barely_prompting` on the hosted lottery, the vLLM ultimatum baseline and its
persona, the ρ = 0 lottery condition. A two-parameter logistic will still return a number for these, and
the number is an extrapolation past the data with an interval hundreds of tokens wide. Those rows carry
`crosses_half_on_grid = False` and blank estimates rather than a fitted fantasy.

**D13. Probe-stack pairwise differences are adjacent doses only.** The "conditions" on that stack are
calibrated targets, so all 45 pairs of a 10-target sweep would mostly compare a dose with a dose four
steps away. Adjacent pairs answer the question that matters — whether the dose-response is monotone —
at a twentieth of the compute.

**D14. The repo's canonical condition-to-colour map is kept; three of its six hexes are snapped.**
`cleaned/regenerate_all_figures.py` fixes which family gets which hue, and the paper depends on that
across every figure, so the hue *assignments* are preserved exactly. Three hexes fail the computable
palette checks — navy at OKLCH L 0.32 is outside the 0.43–0.77 band, and orange, teal and goldenrod
fall below 3:1 against the surface — so each was moved to the nearest step of the same hue that passes.
The snapped set passes all five checks. Conditions that share a family colour are separated by marker
shape and a direct label, never by inventing a hue. Details in `cv_bench/s1_figures.py`.

**D15. Analysis code pins BLAS to one thread.** The S1 bootstraps solve millions of 2×2 systems; on
this login node OpenBLAS spread each across every core it could see, measured at 394% CPU for a
single-threaded workload, on a machine shared with other users' jobs. `cv_bench/__init__.py` sets the
thread variables before numpy is imported. Override with `CV_BENCH_THREADS` if something genuinely
parallel is ever added.

**D16. S1.7 is reported on Stack B's own axes.** The plan asks for the ladder overlaid on the Fig. 3
and Fig. 5 panels. Those panels are Stack A. The same persona text moves Stack A's switching point by
−113 tokens and Stack B's by −12.5, so an overlay would read as a difference between prompting
strategies when it is mostly a difference between stacks. The figure draws Stack A's baseline as a
separately labelled reference line and differences nothing against it. Recorded as a deviation from the
plan's wording, with the reason, rather than done silently.

---

## 2026-09-21 — G1, the download

**D17. The model is fetched with a second account's token, and that is recorded rather than hidden.**
The environment's `HF_TOKEN` belongs to `gunahn`, which holds meta-llama access for Llama-3.1-70B and
3.1-8B but **not** for 3.3-70B — a 403 that exactly explains the 239 KB stub already on the share. An
author supplied a token for a second account, `sk1609`, whose access to
`meta-llama/Llama-3.3-70B-Instruct` and to the Goodfire SAE was verified before anything was fetched.
Both tokens are read-only for this work; nothing is ever pushed to the hub. The reproducibility
statement should say the weights came from the official `meta-llama` repository at the revision
recorded in `results/S/g1_download_verification.json`, not which account fetched them.

**D18. `original/` is not downloaded.** The model repo is 282 GB because it ships the weights twice:
30 sharded safetensors (141.1 GB), which `transformers` loads, and a consolidated `original/*.pth`
copy of the same parameters (141.1 GB). Only the safetensors, the index, the config and the tokenizer
are fetched — 141.1 GB — plus the SAE at 4.3 GB. Total 145.4 GB, which is what the gate approved.

**D19. The SAE is pinned to the revision the legacy runs used**,
`128ee921ecd1b8b3a87d776cbcc357c0855da134`, recovered by V3 from the `sae_path` field of the logged
open-SAE runs. New SAE work therefore matches the logged runs exactly. The model itself has no such
pin — no stack recorded one — so G1 records the revision it fetched and the paper should say the
legacy revision is unknown.

**D20. The token file is excluded from git locally, not by editing `.gitignore`.**
`hf_token.txt` sits in the working tree. `.gitignore` is a tracked file belonging to the legacy
repository, so instead `hf_token.txt` and `*token*.txt` were added to `.git/info/exclude`, which is
local and untracked. The file is in no commit on any branch. It should still be moved out of the
repository: X1's deny-list scan is a backstop, not a reason to leave a credential in a working tree.

---

## 2026-09-22 — author amendments 1–5 to `FRIDAY_PLAN.md`

Appended verbatim to `FRIDAY_PLAN.md` under "Amendments". Effect on the work:

**D21. V4 moves ahead of the remaining verification tasks, and G2 is queued on G1's verification.**
G1 verified at 36/36 files, 30 shards, 141.12 GB, revision `6f6073b42301`, no missing or wrong-sized
file, sha256 matching the hub on the two sampled shards, and the SAE loading under
`weights_only=True`. V1 and V2 are CPU-only and run while the GPU job waits in the queue.

**D22. The Qwen arm is downloaded, and it is `Qwen/Qwen2-7B-Instruct`.** That is the id V3 recovered
from `Probes/config.py:34`, and it is *not* the `Qwen2.5-7B-Instruct` already on the share, which is a
different model. Roughly 15 GB into the same cache on the lab share.

**D23. V5 gates every excess result.** No "excess over the staircase" number enters a patch until the
raw responses behind it have been audited for parse failures. This is the right order: the excess is a
difference between an observed rate and a rate implied by a fit, and a parser that codes a malformed
generation as a choice would inflate the observed rate without touching the fit — which is exactly the
shape of a spurious positive excess. Where malformed outputs were coded as choices, both the original
and the clean-only excess are reported.

**D24. The X1 deny-list gains `gunahn`, `sk1609` and `hf_[A-Za-z0-9]{20,}`.** The first two are
account names that now appear in `logs/` and in run provenance; the third catches any Hugging Face
token that reaches a file. The supplement build fails on a match rather than scrubbing silently.

**D25. The token moves to `~/.hf_token`.** `cv_bench/g1_download.py` reads that path first and falls
back to the in-repo file and then to `HF_TOKEN`, so nothing breaks while the move happens.
**At the time of writing `~/.hf_token` does not exist and `hf_token.txt` is still in the working
tree** — flagged to the authors rather than worked around.

---

## 2026-09-22 — author amendments 6–10

**D26. G2 is submitted as two jobs, and the Qwen arm is its own 1-GPU allocation.**
`g2_qwen` (job 23379474, 1 GPU, 4 h) and `g2_llama` (job 23379475, 2 GPUs, 12 h), both on
`ou_bcs_low` with `--account=mit_general --qos=normal --requeue`. Splitting them lets the 7B start
without waiting for a 2-GPU slot, and it keeps a preemption on one from costing the other.

**D27. Three arms, and the third is labelled a departure.** `legacy` reproduces the legacy pipeline
with the hook off — raw prompt strings, temperature 0.7, top-p 0.95, `max_new_tokens=12`, 40 agents,
the legacy grids and the legacy per-agent seeding. `chat` changes exactly one thing, the chat template.
`chat64` additionally raises `max_new_tokens` to 64; it is recorded in every row as
`legacy_settings=false` so it can never be mistaken for a legacy number. The legacy path is *imported*
(`Probes.models.Wrapped`, `Probes.tasks.prompts`, `Probes.config`), never edited, and the run asserts
that no steering hook is installed.

**D28. Every raw generation is saved and coded twice.** `legacy_code` is the last-match rule that
produced every published probe curve; `strict_code` takes the first stated option and keeps
`no_answer` and `unclear` as categories rather than forcing a choice. The divergence is not
hypothetical: `"Safe. The risky option is worse."` codes **Risky** under the legacy rule and **safe**
under the strict one. Rows are written after every reward level so a preempted job resumes.

**D29. The GPU order becomes G2, G4, G3, G5.** G4 moves ahead of G3 because it now carries the
audit that gates the excess results, which is on the critical path for what the paper may claim; G3's
label-neutral test is valuable but claims nothing that is currently blocked.

**D30. The "survives regardless" line in `reports/V5_parse_audit.md` is withdrawn.** It asserted that
the layer-48 versus layer-50 dissociation could not be a parser artefact, on the grounds that a
mis-coding would have to act differently between layers. That symmetry argument does not hold: the two
layers are different interventions, steering can change verbosity as well as choices, and a direction
that makes the model append a rationale would move the last-match coding without moving a decision.
The finding is now stated as a difference in **coded outputs**, with the question of whether it is a
difference in **choices** deferred to G4. A section was also added recording that the hosted-stack
curves in S1 and in Figure 3 come from EDSL's recorded answer, not from a regex over the text.

---

## 2026-09-22 — Track B in parallel; shared modules landed

**D31. The four governing documents are now tracked.** `CLAUDE.md`, `ICLR_PLAN.md`,
`PAPER_AUDIT.md` and `GATE_S0_RESPONSE.md` were deliberately left untracked through S0 and S1 as the
authors' own inputs; `FRIDAY_PLAN.md` was already tracked. Git worktrees share `.git` but not the
working tree, so an untracked rules file is invisible in the Track B worktree. Committed at `5b4e01f`.
Still untracked on purpose: the 18 MB submitted PDF, `feedback.txt`, the plan `.docx`, and
`hf_token.txt` (which is also in `.git/info/exclude`, and `.git/info/exclude` *is* shared across
worktrees, so the exclusion holds there too).

**D32. Track B runs in parallel on `iclr-trackB`, and nothing from it enters the Sept 25 PDF.**
The amendment says it supersedes "Not in this week's plan" in `FRIDAY_PLAN.md`. **That phrase is not in
that file, or in any other document in the repository.** The nearest thing is
`GATE_S0_RESPONSE.md:130` — "Until the deadline `FRIDAY_PLAN.md` replaces this list. It applies again
afterwards, for Track B" — which defers Track B until after the deadline, and that is the line taken as
superseded. Flagged rather than assumed. My priorities are unchanged: G2 running, then V1/V2 on CPU,
then G4 and G3.

**D33. `cv_bench/readout.py` and `cv_bench/steer.py` are committed early, with tests.** They did not
exist before this amendment; S2.1 and S2.2 were queued inside G3 and G4. They are now a shared
dependency of two sessions, so they land on their own at `82daf32` with a passing suite rather than
arriving inside a large GPU commit.

Two design choices the other session should know about:

* **`scale` is in units of the median residual-stream norm at the intervention layer**, measured over
  calibration prompts with the first token excluded. The legacy λ was in raw units, which is why it is
  not comparable across layers or models. `Intervention.norm_unit` carries the measured value and
  `delta_norm` is what actually gets added.
* **`positions` is explicit**, one of `last`, `all_prompt`, `all`, `legacy_ramp`. The first three say
  what they mean at every forward pass, prefill or cached decode. `legacy_ramp` reproduces
  `Probes/models.py` exactly — including that it modifies **no generated token**, because its index
  arithmetic yields zero positions when `seq_len == 1`. The recording test asserts that, so the
  `STACK_AUDIT.md` §3 finding cannot silently regress.

**D34. The test suite runs on CPU against Qwen2.5-0.5B-Instruct from the lab share.** Real forward
passes, not mocks, because the two things that actually break here — left padding silently corrupting
rotary positions, and a position policy meaning something different during cached decoding — are
invisible to a mock. Measured on that model: batched and unbatched logit differences agree to
**0.00e+00**, median residual norm at layer 8 is 14.06, and valid mass is **0.32**, far below the
plan's 0.98 bar. The last number is expected on a 0.5B model with this stem and is reported, not
asserted; `Readout.check_valid_mass` enforces the bar before any 70B result is used, and if the stem
fails there it gets revised, as S2.1 instructs.

---

## 2026-09-22 — scheduling by estimate, to a cutoff of Thu 24 Sept 06:00 UTC

Appended to `FRIDAY_PLAN.md` and, for rules 6 and 7, to `CLAUDE.md`.

**D35. The cutoff replaces the results freeze.** Wed 23 Sept 23:00 PDT = **Thu 24 Sept 06:00 UTC**,
about **68 hours** from this entry. Only work finished, verified and committed before it may enter the
Sept 25 PDF.

**D36. Scheduling is by measured estimate, and the measurements come from the live runs.** G2 is
already producing exactly the numbers a benchmark would: Llama-3.3-70B at 2 GPUs loads in **4.5 min**
and generates at **1.25 generations/s** at the legacy settings; Qwen2-7B at 1 GPU loads in 0.5 min and
generates at **6.90/s**, completing all of G2 in 9.2 minutes. Those are real allocations under real
contention, so they are used in preference to a synthetic benchmark. A separate 8-minute benchmark
(job 23379816) measures the **forward-pass** path, which G3 and G4 depend on and which G2 does not
exercise.

**D37. The budget binds before Slurm does.** Read, not guessed: QOS `ou_bcs_low` caps a user at
`gres/gpu=64` (32 a100 + 32 h100) with 256 submitted jobs, but this account's association permits only
QOS **`normal`** on that partition, which carries no GPU cap; the association cap is
`MaxSubmit=500`, and `MaxArraySize` is 25,000. So Slurm would allow tens of GPUs. **400 GPU-hours over
68 hours is ~5.9 GPUs sustained**, and at 2 GPUs per 70B replica that is about **three concurrent
replicas**. The schedule is therefore budget-shaped, not limit-shaped, and asking for 32 GPUs would
exhaust the cap in half a day.

**D38. Two items in the amendment do not exist in the repository, and are not invented.**
- **G4b and G6** are named as remaining tasks. `FRIDAY_PLAN.md` defines only **G1–G5**. They are absent
  from `reports/SCHEDULE.md` with that stated, rather than guessed at.
- The cap is described as "replacing the earlier 40 and 60". The only budget communicated to this
  session was **40** GPU-hours (`GATE_S0_RESPONSE.md` §1.2). No 60 was ever recorded here.

**D39. Gate B2 and Gate B3 become automatic checks; every other gate still stops.** This is a genuine
change to rule 6 and is recorded as such. It is bounded: the criteria for B2 and B3 are numeric and
written out in `ICLR_PLAN.md`, so "evaluate exactly as written" is well defined. The test split
remains locked behind a human unlock and the `prereg-v1` tag, rule 4 still forbids any rerun motivated
by an unhelpful result, and rule 1 still forbids any number without a file.

**D40. `peft` is not installed**, so the LoRA anchors of B3.2 cannot run as things stand. The
benchmark records `lora_seconds_per_step = null` rather than estimating it. Installing `peft` is a
small change but it is a dependency addition, so it is reported rather than made silently.

---

## 2026-09-22 — S2.1-fix: the stem, the batch gap, and the environment

The amendment's diagnosis of the stem is correct and is worth writing down, because it explains a
number that had no explanation an hour ago.

**D41. `"My choice: "` ends in a space, and that is why the valid mass was 0.371.** These tokenizers
attach a leading space to the following word. After a trailing space, the spelling `" Safe"` is
unreachable and the model must emit the rarer bare `"Safe"` — so most of the probability sits on
tokens the readout was not counting. Every candidate stem now ends **without** a space, and
`Readout.label_token_ids` counts four spellings per label (`Safe`, ` Safe`, `safe`, ` safe`, plus the
upper-case form) instead of two.

**D42. The calibration split is defined off the legacy grid, and this is a choice worth defending.**
`ICLR_PLAN.md` B1 splits by reward-level index within a grid that does not exist yet, and the legacy
grid is the one every published curve uses, so selecting on it would contaminate exactly the cells the
paper reports. The calibration prompts are therefore reward values **congruent to 2 or 3 mod 5**,
where the legacy grid uses multiples of 5: 50 per game, off every published curve and off any future
split defined on the legacy grid. Recorded here because the stem is selected on them and then frozen.

**D43. Selection rule, exactly as instructed.** Per label set, the stem with the highest mean valid
mass; ties broken by the calibration slope of the readout probability against the sampled choice
frequency (20 samples per prompt). `mean ≥ 0.98` passes. `mean` in 0.95–0.98 with `min ≥ 0.80` and
slope in 0.8–1.2 passes **as a recorded deviation**. Below that the job stops and reports the top ten
tokens carrying the remaining mass. Jobs `cvb_s21_stem` (23380336).

**D44. Every number that can reach the paper is read unbatched until the batch gap is settled.**
That costs little — 6.35 readouts/s unbatched against 11.6/s at batch 16 — and it removes the
question from the critical path. Two diagnostics are running: `cvb_s21_fp32` (23380334) checks
Llama-3.1-8B in **fp32**, where batched and unbatched must agree to ≤ 1e-4 if the machinery is
correct; `cvb_s21_batch` (23380335) compares unbatched, equal-length batches with no padding, and
left-padded batches on the 70B in bf16, and regresses the discrepancy on **pad length** and on **batch
position**. A discrepancy that grows with pad length is a masking bug to fix, not a tolerance to
loosen. The noise floor — the SD of z for one prompt across six batch compositions — is measured in
the same job, and any effect smaller than five times it will be flagged.

**D45. `peft` installed, pinned, and locked.** `peft==0.13.2`, into the user environment, with
`env/requirements-lock.txt` recording every version this work depends on. One thing the lock file
notes and the schedule must respect: **`bitsandbytes` 0.43.2 is present but was compiled without GPU
support**, so 4-bit is not available here. B3.2 should train its LoRA in bf16; if that does not fit,
a GPU-enabled build is needed first, and that is a request, not something to work around.

---

## 2026-09-22 — S2.1-fix results, and two corrections from the Track B session

**D46. The monitor's NaN check was dropping real failures; fixed, with a test.** `scan_log` reported a
standalone `nan` only when the log also contained the word "loss", so a NaN in any log that is not a
training log — a readout sweep, a calibration pass, an attribution run — was silently ignored. The
standalone-word boundary was always the filter that mattered; the extra condition only narrowed it.
Removed, the pattern tightened to `(?<![A-Za-z0-9_])(?:nan|NaN|NAN)(?![A-Za-z0-9_])`, and
`cv_bench/tests/test_monitor.py` added: 17 tests, including the exact regression (a log with a
standalone `nan` and no "loss" anywhere) and the false positives the boundary must reject —
*finance*, *tenant*, *banana*, *nanometre*, *covariance*, *Kernighan*. Reported by the Track B
session.

**D47. The stem is settled, and the trailing space was only half the story.**
Mean valid mass on 50 calibration prompts per game, unbatched, unsteered:

| label set | stem | lottery | ultimatum |
|---|---|---:|---:|
| legacy | `My choice:` | 0.646 | 0.259 |
| legacy | `I choose the` | 0.910 | **0.000** |
| legacy | **`Answer:`** | **1.0000** | **1.0000** |
| neutral | `My choice: Option` | 1.0000 | 1.0000 |
| neutral | `Answer: Option` | 1.0000 | 0.9996 |
| neutral | **`Option`** | **1.0000** | **1.0000** |

Removing the trailing space lifted `My choice:` from 0.371 to 0.646 on the lottery — real, and not
enough. The rest is that `My choice:` invites a sentence, while `Answer:` invites a token. And
`I choose the` collapses to **zero** on the ultimatum, because "I choose the Accept" is not English:
a stem has to fit its labels grammatically, which is not a consideration the plan anticipated.

Top tokens after `Answer:` are ` Safe`, `Safe`, ` '`, ` Risk`, `.Safe`, ` SAFE`, ` Saf`, ` safe` —
the leading-space spelling is reachable again, which is exactly what the trailing space had blocked.

**Both winners pass the 0.98 bar outright**, so no recorded deviation is needed for selection. For the
neutral set three stems tie at ~1.0000, so the tie-break is the calibration slope, which is why D48
matters for selection and not only for validation.

**D48. The constant column: the calibration set did not span the switching region.** The stem job
ended `legacy: slope=0.000 r=nan`. The constant column is the **sampled choice frequency**: the
calibration values ran 22–143, and the unsteered model answers Safe across all of them, so y was 0
everywhere and a regression of y on x is undefined. The readout probability is not the problem — a
slope is a statement about how sampled behaviour tracks the readout, and it has no content where
behaviour does not vary. `phase_slope` now locates the crossing by a geometric readout sweep from 20
to 1200, takes the band where the readout sits between 0.05 and 0.95, widens it 20%, and draws 50
values from it — still congruent to 2 or 3 mod 5, so still off the legacy grid. Job 23380708.
Caught by the Track B session from the log; amendment item 4's "no constant columns" check is what
should have caught it here, and the monitor only applies that check to `.jsonl` outputs, not to a
job's own summary.

**D49. The batch discrepancy is bf16 numerics, not a masking bug — the padding test says so.**
The first two batch runs could not answer the question: every calibration prompt tokenises to exactly
112 tokens, so pad length was 0 for all 16 and the "left-padded" condition was a second equal-length
run. With filler prepended so lengths run 112 → 832 and pad reaches 720 tokens:

- slope of |discrepancy| per pad token: **−5.3e-05**, r = **−0.089** — no growth, and if anything a
  slight decline;
- max |diff| 0.500, mean 0.172, i.e. the same magnitude at pad 0 as at pad 720;
- fp32 on Llama-3.1-8B, same code: **3.2e-05**, inside the 1e-4 bar.

So the masking, the `position_ids` and the attention mask are correct, and the 0.125–0.50 spread on
the 70B is bf16 accumulation. **A tolerance is not being loosened to accommodate a bug.**

**D50. The noise floor is not stable across runs, and that is reported rather than averaged.**
The SD of z for one prompt across six batch compositions measured **0.094** in the first 70B run and
**0.000** in the second, from identical code on the same model. The plausible cause is kernel
selection: batch shape decides which cuBLAS kernel and reduction order run, and that is not fixed
across allocations. Consequences: the floor has to be measured **in the run that uses it**, not quoted
from another; and a single measurement of it is not a property of the model. Until `phase_slope`
returns, the operative figure for the five-times rule is the larger of the two, **0.094**, giving a
threshold of **0.47 in z** — deliberately the conservative choice.

**D51. The legacy stem is frozen at `Answer:` for the legacy label set; the neutral set is not
frozen and goes back for rework.**
Chosen on the unsteered model and on calibration prompts only (n % 5 in (2,3), off the legacy grid),
before any steered readout, on valid mass first and the calibration slope second:

| label set | stem | valid mass, lottery | valid mass, ultimatum | slope | r |
|---|---|---|---|---|---|
| legacy | `My choice:` | 0.646 | 0.259 | — | — |
| legacy | `I choose the` | 0.910 | 0.000 | — | — |
| **legacy** | **`Answer:`** | **1.0000** | **1.0000** | 1.091 / 1.003 | 0.982 / 1.000 |
| neutral A/B | `Option` | 1.0000 | 1.0000 | — / 0.317 | — / 0.860 |

`I choose the` collapses on the ultimatum because "I choose the Accept" is not English. The neutral
A/B set reaches full valid mass and still fails: on the lottery the sampled choice is **constant**
across the whole calibration range, and on the ultimatum the slope is 0.317. A label set the model
answers without reading the payoff measures a label prior, so it is not frozen. Rework in
`cv_bench/neutral.py` (FRIDAY amendment item 4).

**D52. The two slope numbers above do not establish that the readout measures free generation, and
are not cited as if they did.**
`s21_fix.phase_slope` generates its 20 samples per prompt from `rd.render(spec)` — the same string
the readout scores, ending in the same stem. Both columns therefore come from a prompt that forces
an immediate label token, so the slope shows internal consistency under a forced answer and cannot
distinguish that from a label prior. The non-circular comparison is against G2's free generation
(`cv_bench/instr.py`, FRIDAY amendment item 2), and it decides which of G4's two measurements is
primary.

**D53. G4's dose grid, fixed in advance and before any steered run.**
Doses are in units of **M**, the median residual-stream norm at the steered layer, first token
excluded, measured on calibration prompts. Two anchors, 11 points, deduplicated:

- **legacy-anchored** — λ ∈ {0, 0.3, 0.5, 1.0, 2.0, 3.0, 4.5, 6.0}, the endpoints and interior of
  `Probes/config.py::CALIBRATION["coarse_grid"]`, the raw-unit grid every published λ was searched
  on (observed |λ| run 0.31 → 5.27). Dose = λ / M.
- **norm-anchored** — dose ∈ {0.25, 0.50, 1.00} of M.

The second anchor exists because the first may be tiny: if M is of order 100, every published λ is
under 6% of the residual-stream norm, and a null there would mean only that the dose was small. With
both anchors, "no effect at the doses the paper used" and "no effect at any dose" are separable.
The grid contains 0 and is identical for both variants, both layers and both games. It is **not**
calibrated to any target (CLAUDE.md rule 4): no dose is chosen, moved or added because of what a
result looks like.

**D54. G4's two variants, and what differs between them.**

| | `as_written` | `reconstruction` |
|---|---|---|
| prompt | raw string, no chat template | chat template |
| new tokens | 12 (`DECODING_DEFAULTS`) | the cap the instrument check selects |
| steering positions | `legacy_ramp` — last 20% of **prompt** tokens, ramp 0.5→1.0, and zero generated tokens | `all` — prompt and generated, which is what `STEERING["apply_during_generation"]=True` claims |
| direction | added in raw space although fitted in standardised space, as the legacy code does | mapped back to raw space first |
| probe labelling | the legacy last-match parser | a stated decision only |

Both are run at every dose, both layers, both games. Neither is a sensitivity analysis of the other.

**D55. Every generation in G4 is coded three ways and all three are kept.**
`legacy` (last mention), `strict` (first mention) and `decision` (a choice only when the response
says what it chose). The third exists because of a measurement, not a preference: on G2's Llama
chat64 lottery arm the first two disagree on **737 of 1800** trials, every disagreement in the same
direction, and in all of them the response is still enumerating the prompt's own two options when
the cap lands. The legacy rule then reads "Risky" off option 2 and the strict rule reads "Safe" off
option 1; neither has seen a decision. 68.0% of that arm's responses never state one.

**D56. G4 carries the extension plan's control directions, at a dose and level subset.**
`mech_interp_paper_ICLR_extension_plan.docx` requires every steering effect to be compared with a
random direction of the same norm at the same layer and position, and with a direction trained to
encode the reward stated in the prompt. G4 as first specified swept the choice probe alone, which
can show that an intervention moved behaviour but not that what moved was preference-like. Four
directions now run in every cell:

| direction | what it is | doses | levels |
|---|---|---|---|
| `probe` | the rebuilt choice probe | all 11 | 23 lottery / 19 ultimatum |
| `reward` | a probe on the same activations labelled by whether the prompt's payoff is above the grid median | 4 | 8 / 10 |
| `rand0`, `rand1` | unit vectors, seeded by (layer, game, draw), fixed across cells | 4 | 8 / 10 |

The controls only have to establish a band, so they run coarser: 678 sampled cells against 462,
a 1.47x cost rather than 3x. The **readout** arm is cheap enough (6.5 forward passes per second)
that all four directions get all 11 doses and the full grid — 2,816 cells for 0.12 h.
The control doses are chosen by rule, not by hand: zero, the largest legacy lambda, and the two
largest norm-anchored doses. `cos(choice probe, reward probe)` is recorded at training time, which
is the extension plan's hypothesis 1 measured directly.

**D57. G4's wall clock is measured, not assumed, and batching does not help at the long cap.**
One real cell, timed on the model (`g4/bench_cell.json`):

| variant | cap | 1 sequence | 40 sequences | per-replica projection |
|---|---|---|---|---|
| `as_written` | 12 | 0.145 s | 3.40 s | 0.65 h |
| `reconstruction` | 256 | 0.357 s | 34.6 s | 6.5 h |

The 40-way batch is **slower per sequence** than one at a time, and the reason matters: a single
sequence stops at EOS after about ten tokens, while a batch of 40 runs until the last of them
stops, so one straggler drags all 40 to the full cap. Batching is kept because the alternative is
worse for the readout arm and because the cost is affordable, but no speed-up is claimed for it,
and the token cap — not the batch size — is the lever that decides G4's runtime.

**D58. The two anchors are Track B's, and are not built on this side.**
Correcting an offer I made in this session: the answer-readout gradient and the synthetic-utility
LoRA are **B3.1** and **B3.2** in `ICLR_PLAN.md`, under amendment **A5**, and they belong to Track B.
They need no specification from the authors — B3.1 fixes the gradient's definition and B3.2 fixes
the LoRA's rank, target modules, three-adapter design, loss, training split and cloning check
(correlation ≥ 0.95, calibration slope 0.9–1.1). Nothing on this side builds either.

**D59. G4b consumes Track B's gradient direction; a locally computed one is a duplicate, not a
replacement.**
`cv_bench/g4b.py` loads B3.1's direction from `trackB/` on the lab share **only when its hash is
committed** on `iclr-trackB`, so the direction in a geometry table is tied to a commit. A file on
the share whose hash is not committed is not yet the anchor of record and is skipped with a note.

If it is absent when G4 is committed, `--fallback` computes one to B3.1's definition — the gradient
of z, the logit difference, with respect to the residual stream at the intervention layer, final
prompt token, averaged over calibration prompts, in both the single-format and format-averaged
versions — and **every row carrying it is labelled `duplicate_to_reconcile`**. One difference is
recorded in the artefact rather than glossed: B3.1 averages over Track B's calibration-split *core*
prompts, which B1/B2 define and which do not exist on this side, so the fallback averages over this
session's off-grid calibration values and says so in the same field. Two independently computed
anchors are two numbers until someone reconciles them.

As of this entry Track B is at B2 with Gate B2 failing in all 18 configurations, so no B3 artefact
exists yet.

**D60. `readout.score` refuses a label pair it cannot tell apart.**
Reported by the Track B session on 22 Sept: with labels `"Option A"` / `"Option B"` under a bare
stem `"Answer:"`, both labels' first-token id sets are the same — the scored token is `Option` —
so `logit_diff` is a difference of two identical quantities and is **identically zero**, for every
prompt, silently. It reads as "the intervention did nothing" when the truth is "nothing was
measured", and any gradient taken through it is zero as well.

`Readout.assert_labels_distinguishable` now runs inside both `score` and `score_batch` and raises,
naming the shared token, the stem, and the remedy (move the scored position onto the differing part:
stem `"Answer: Option"` with labels `"A"` and `"B"`). Blank labels are rejected too, since they
tokenise to whitespace. Seven tests cover it; the check is copied from Track B's
`cv_bench/anchors/gradient.py`, which guards its gradient anchor the same way.

**Every label pair this repository uses was checked against the Llama-3.3-70B tokenizer and none
collides:** `Safe`/`Risky`, `Reject`/`Accept`, `A`/`B`, `Certain`/`Chance`, `Refuse`/`Take`. The
neutral finding in **D51** is therefore unaffected — those stems end in `"Option"` and the scored
token is `" A"` or `" B"`, which are distinct ids. The lottery constancy and the 0.317 ultimatum
slope stand as a **behavioural label prior**, not an artefact of the readout.

**D61. G4b reads Track B's `legacy_one_format` gradient, and reports its `both_orders` version too.**
Per the authors, 22 Sept: load `legacy_one_format` at layers 48 and 50 from `trackB/` on the lab
share once its hash is committed, and report cosines against `both_orders` as well. The cosine
between the two versions is itself a number worth having — it says how much of the anchor is a
property of the surface format rather than of the readout. `legacy_one_format` is the version the
geometry table treats as *the* gradient; `both_orders` enters as its own row. The hash gate, the
fallback and the `duplicate_to_reconcile` labelling of **D59** are unchanged and apply to both.

**D62. Rule 16 is in force; what it changes and what it does not.**
Appended to `CLAUDE.md` at the authors' instruction of 22 Sept. Four hard stops keep an approval
step — a pre-registered threshold or metric, an anchor's training objective after its dry run has
passed, the GPU budget (400 here to the cutoff, 1,000 for Track B through 5 Nov, both on the shared
`cvb_` prefix), and paid API spend above the standing $50. Everything else proceeds under "keep every
threshold and lock intact, choose the option cheapest to reverse, record it with the alternatives".

Two consequences worth stating rather than discovering later.

**The recording obligation is not a formality.** Rule 16 trades an approval step for a written one.
An entry naming the alternatives has to exist *when the choice is made*; a decision reconstructed
afterwards has none of the property that makes autonomy safe, which is that a reader can see what was
not chosen. This file is where that happens, and the rule says as much.

**The test-split change is the consequential one.** Rule 3 required an affirmative unlock in session.
It now requires only that the `prereg-v1` tag exist and that 24 hours pass without a veto — silence
becomes consent. That is a real loosening of the project's strongest lock, and it is the authors' call
to make. What is in our gift is keeping the window meaningful: the window opens only once the tag is
present, its opening and expiry are posted here at the moment it opens, and nothing on the test split
is touched before the full 24 hours have elapsed. An unannounced window would satisfy the letter of
the rule and defeat its purpose.

**Numbering.** Neither checkout has rules 13–15; this file holds 1–12. The authors' number 16 is kept
as given so their reference resolves, rather than renumbered to 13.

**D63. A framing selection was written from zero free-generation levels; it is quarantined, not used.**
Taken under rule 16 and recorded with the alternatives.

`cvb_neutral2` was cancelled during a queue reshuffle and never ran, so `neutral/free_llama.jsonl`
does not exist. `cvb_choose` ran anyway on its `afterany` dependency, found no free generations, and
wrote `framing_choice.json` reporting `{"framing": "counterbalanced", "passed": false}` with
`n_free_levels = 0` in every cell. G3 reads that file and would have used the framing as though a
selection had been made.

**Chosen:** rename the file to `framing_choice_EMPTY_n0.json`, resubmit `cvb_neutral2`, and re-chain
G3 on **`afterok`** rather than `afterany`, so a cancelled or failed neutral pass no longer releases
the job that depends on its output.

**Alternatives not taken.** (a) Delete the file — rejected: it is evidence of how the gap arose, and
deleting is not reversible. (b) Leave it and let G3 record "default, no selection" — rejected: the
file *claims* a selection, and `chosen_framing()` reports a selection as made when the file parses.
(c) Make `choose_framing` refuse to write when `n_free_levels == 0` — worth doing and additive rather
than corrective, but it does not address the file already on disk, so it follows rather than replaces
this step.

**The dependency lesson generalises.** `afterany` was the right choice for a step that should run
whatever the upstream outcome; it is the wrong choice for a step that consumes the upstream's output.
Every chain of the second kind is now `afterok`.

**D64. Two systematic faults, found because a job finished too fast to be real.**
Taken under rule 16, recorded with the alternatives.

`cvb_g5` reported **COMPLETED in 3:11** and `cvb_g4b` **FAILED in 1:09**. Neither had loaded a model.

**Fault 1 — a GPU request that does not fit the model.** `--gres=gpu:2` asks for two GPUs of any
type. On this cluster L40S is by far the most plentiful, and two of them give 80.1 GiB usable against
the 141.1 GB the 70B needs, so accelerate placed 36 layers on **disk**. Usable capacity by request:

| request | usable | fits |
|---|---|---|
| a100:2 / h100:2 | 142.6 GiB | yes |
| h200:2 | 251.5 GiB | yes |
| l40s:2 | 80.1 GiB | **no** |
| l40s:4 | 160.2 GiB | yes |

Every 70B job now requests `a100:2` explicitly, in the sbatch files and in the monitor's resubmission
arguments. *Alternatives not taken:* `--gres=gpu:4` generic always fits but consumes the whole
4-GPU preemptable cap for a job needing two; `l40s:4` fits and is the most plentiful type but runs
roughly 2.4x slower because pipeline placement leaves one card active at a time. Both remain
available if a100 queues badly, and that is why they are written down here.

**This fault was caught by the guard added earlier today,** which refuses a CPU or disk placement
instead of silently running a forward pass that takes hours. Without it, both jobs would have looked
healthy while producing nothing.

**Fault 2 — the sbatch scripts masked their own failures.** Each ended

    srun python3 -u -m cv_bench.<mod> ...
    echo "$(date -u +%FT%TZ) exit=$?"

The `echo` succeeds, and *its* status becomes the script's status, so a job whose python raised
reported **COMPLETED** to `sacct`. That is why `cvb_g5` looked fine: the monitor saw COMPLETED, and
only the missing completion marker would eventually have caught it. Every script now captures `rc`
and exits with it; all 16 verified, all syntax-checked.

Fault 2 is the more serious of the two. Fault 1 announced itself; fault 2 made a crash indistinguishable
from success in the one place both the monitor and the watcher look first.

**D65. The memory probe now waits for a busy device instead of dying on it.**
Taken under rule 16, recorded with the alternatives.

`cvb_g5` failed a third time, differently:

    RuntimeError: CUDA error: CUDA-capable device(s) is/are busy or unavailable

raised from `torch.cuda.mem_get_info` inside `load()`. Asking a device its capacity initialises CUDA
on it, and on a shared node that raises while a previous job is still tearing down. The irony is that
`wait_for_gpus` exists for exactly this transient — but the probe that *computes the budget* ran
**before** the wait, so the job died instead of waiting a few seconds.

**Chosen:** retry the probe itself, 12 attempts at 20 s, and only on the two transient messages
("busy or unavailable", "initialization"); any other `RuntimeError` still propagates immediately.
After ~4 minutes it raises with a message saying this is a node condition, and exits non-zero so the
job is resubmitted rather than silently producing nothing.

**Alternatives not taken.** (a) Catch all `RuntimeError` and retry — rejected: it would swallow real
CUDA faults and turn a broken build into a four-minute hang. (b) Skip the probe and hard-code a
budget per GPU type — rejected: that is what caused D64's disk offload, a fixed number outliving the
hardware it was written for. (c) Let the monitor's retry handle it — it would have, eventually, but a
transient lasting seconds should not cost a queue cycle and a model reload.

**Three failures, three distinct causes, one job.** `cvb_g5` failed on a request too small for the
model (D64), on a script that reported the crash as success (D64), and now on a probe that could not
tolerate a busy device. Each was hidden by the one before it.

**D66. Only the last `srun` was propagating; now every one does.**
D64 made each script capture `rc` after its final command. `cvb_neutral2` runs two phases and
`cvb_g4b` and `cvb_s32` run theirs in a loop, so a failure in any but the last was still invisible:
neutral2's `free` phase crashed on the busy-device transient, its `choose` phase then correctly
refused to write a selection from no data (D63), and the job reported **COMPLETED in 24 seconds**.
Two guards worked and the job still looked successful.

Every `srun` now carries `|| exit $?`, including the indented ones inside `for` loops. Verified by
counting: 13 scripts, every `srun` line propagating, all syntax-checked.

**The pattern across D63-D66 is worth naming.** Four separate mechanisms each turned a failure into a
silence: a dependency that fired on cancellation, a selection written from zero rows, an `echo` that
overwrote a crash's exit status, and a loop that discarded all but its final iteration's. None was a
wrong *result*; each was a missing *signal*. The guards that caught them — the placement assertion,
the empty-selection refusal, the completion markers — all worked. What failed was the reporting path
between the guard and me.

**D67. A running monitor holds a stale table, and now says so.**
A job named `cvb_neutral` was submitted hours after that task had been renamed to `cvb_neutral2`.
Cause: the monitor process imported its `EXPECTED` table at start and had been running since before
the rename. Editing `monitor.py` does not change a live process.

The monitor now prints its own file's modification time and the task names it is watching at
startup, so a stale process is identifiable from its log rather than from a mystery job in the queue.
The operational rule that follows: **restart the monitor whenever `monitor.py` changes**, which this
session had not been doing consistently.

Separately, four duplicate submissions (`cvb_s32`, `cvb_s35`, `cvb_g5b` twice each) were **mine** --
I resubmitted a batch without cancelling the previous one. The monitor was not at fault there; it
treats a PENDING job as live and does not double-submit. All duplicates cancelled, one job per name
verified.

**D68. node2119 is excluded: five failures, one node.**
Taken under rule 16, recorded with the alternatives.

`cvb_g5` failed four times. The fourth failure named a different CUDA fault from the third --
"unspecified launch failure" rather than "busy or unavailable" -- which is why the D65 retry, written
narrowly for the transient, did not catch it. Correlating every failure log against the node it ran
on:

| node | failures | cause |
|---|---|---|
| **node2119** | **5** (g3, g4b, g5 x2, neutral2) | CUDA errors, two different kinds |
| node3512, node4105, node4106 | 1 each | the L40S capacity fault of D64, now fixed |
| node2101, node3209, node4204, node4501 | 0 | jobs succeeded |

Every failure after D64's fix was on one node. "Unspecified launch failure" is a device-level fault,
not a transient, so retrying on the same node would burn four minutes and fail again.

**Chosen:** `--exclude=node2119` in every sbatch script and in the monitor's resubmission arguments.
Nothing is killed and nobody else's work is touched; the scheduler simply places my jobs elsewhere.
`scontrol update ExcNodeList` does not apply to a job that has already started, so the pending queue
was rebuilt from the updated scripts -- at the cost of the queue age those jobs had accumulated,
which is the cheaper loss against a node that destroys them on contact.

**Alternatives not taken.** (a) Broaden D65's retry to catch any CUDA error -- rejected: it would
turn a hardware fault into a four-minute hang before the same failure, and would mask a genuinely
broken build. (b) Do nothing and let the monitor retry -- rejected: retries land on the same node
often enough that five of them already have. (c) Report the node to the cluster operators -- not
mine to do from here, but the evidence is in this entry if an author wants to.

**What this cost.** Four failed attempts at `cvb_g5`, each dying within a minute, so under ten GPU
minutes in total. The expensive part was not compute; it was that the first two failures reported
COMPLETED (D64, D66) and so were not visible as failures at all.

**D69. Credentials moved out of the working tree; X1 implemented.**
`working_apis/` (a directory of nine key files) and `hf_token.txt` sat in the repository root.
Both were untracked and appear in no commit on any branch — verified with `git log --all` on the
paths and by listing the trees of the sampled history. They are now at `~/secrets/working_apis`
and `~/secrets/hf_token`, directory mode 700 and files 600, and their names are in
`.git/info/exclude`.

`cv_bench/g1_download.py` read `ROOT / "hf_token.txt"` as a fallback. That fallback is **removed
rather than re-pointed**: a loader that reads a credential from the working tree is how one gets
committed. It now reads `~/secrets/hf_token` or `HF_TOKEN`, and logs the path it used, never the
value. Five legacy scripts under `SAE/` and `Revised Prompting/` also reference the old paths; they
are in the read-only directories (rule 2) and are not edited. They are not run by this session, and
the path they name no longer exists, so they fail closed.

**X1 is now implemented** (`cv_bench/x1_supplement.py`), having previously been only a specification.
It builds from an allow-list and fails on a deny-list. Added per the authors: the filenames
`working_apis` and `hf_token`, and the patterns `sk-[A-Za-z0-9_-]{20,}` and `AIza[0-9A-Za-z_-]{35}`,
alongside the existing `hf_[A-Za-z0-9]{20,}`, the identifier terms, and AWS-key and private-key
shapes. A credential match is reported as file, line and rule with the text **withheld** — a scanner
that echoes the secret it found writes it into the build log.

**First run of X1 on the allow-listed supplement: 0 credential matches, 1,160 anonymity matches.**
387 `guna23`, 386 `gabrieli`, 373 `orcd`, almost all from the hard-coded lab-share default
`/orcd/data/gabrieli/001/guna23/hf_cache` that every module carries. The supplement cannot be built
until those defaults are parameterised. That is W1/X1 work, recorded here and not done tonight,
because results come first until the cutoff.

**D70. Three of the five judges are reachable; two have no key.**
Verified with one minimal request each, reporting only a status and a reason class:

    gpt-5              ok      http 200
    claude-sonnet-4-6  ok      http 200
    gemini-2.5-pro     ok      http 200
    deepseek-v4-pro    fails   no key file
    kimi-k2.6          fails   no key file

Per the authors' instruction the judge phase runs with the three and records the gap. The
consequence for the paper is worth stating: **the published five-judge mean cannot be reconstructed
here**, only a three-judge one, and V2 already showed the five-judge passes carry no API response
ids. Any G5b judge figure is a three-judge figure and will say so.

`cv_bench/g5b.py --phase judge` imports the rubric and its length-control suffix from
`Probes/judge.py` rather than retyping them, so the wording is the paper's own. Keys are read at the
moment of use, held in local variables, and never printed; a provider error is reported as a class
(`http 401`, `no json in reply`) and its body is never echoed.

**D71. The gradient anchor needs roughly twice the model's memory.**
`cvb_g4b` failed on node2102 with a genuine `torch.OutOfMemoryError`: 128 MiB requested, 90 MiB free,
the model holding 79.15 of the card's 79.25 GiB. The gradient of z with respect to a layer-48
activation retains the forward graph from that layer to the logits, so the backward pass needs
headroom the 70B leaves none of on 2 x A100-80GB. This is a property of the computation, not a
transient — and it is distinct from the three earlier `g4b` failures, which were node2119's CUDA
faults.

**Chosen:** 2 x H200 (139.7 GiB each) on the amf pool, leaving about 70 GiB per card free.
*Alternatives not taken:* `a100:4`, which also fits and spreads the model to ~35 GiB per card, but
consumes the whole 4-GPU preemptable cap for a 20-minute job; gradient checkpointing, which would
change the computation to fit the hardware rather than the other way round.

**D72. The failure watcher was watching a list that never grew.**
`cvb_g4b` failed inside a 30-minute watch window and the watcher reported nothing. The cause was not
a filter or a query: **`cvb_g4b` was not in the watched list at all**, along with `cvb_g4q`,
`cvb_g5b`, `cvb_s32`, `cvb_s35` and `cvb_instr`. The list was hard-coded when the watcher was written
and five of those tasks did not exist yet.

This is the same failure as **D67**, where the in-cluster monitor ran a table it had imported before a
task was renamed. Both times a static list silently stopped describing the work. The fix is the same
in kind: the watcher now derives its list from `cv_bench.mine --names` at the top of **every** cycle,
so it cannot drift, and because `mine.py` refuses anything matching `^cvb_b\d` it cannot drift onto
Track B's jobs either. Verified: 21 task names watched, all five previously-missing ones present,
zero Track B names.

**The pattern, stated once.** Three times tonight a guard was defeated not by being wrong but by
describing yesterday's world: the monitor's imported table (D67), the watcher's hard-coded list
(D72), and my own belief that an edit had applied when it had silently failed to match. A check that
enumerates what it protects has to derive that enumeration, not restate it.

**D73. Every job that runs a backward pass needs the same headroom; I fixed one and missed the other.**
`cvb_g6` failed with `torch.OutOfMemoryError` in `z.backward()` -- 448 MiB requested, 42 MiB free --
which is D71's failure exactly. G6 computes attribution as activation x (decoder . grad of z), so it
backpropagates from the logits like the gradient anchor does.

When D71 fixed `cvb_g4b` I treated it as a property of that job rather than of the operation. The
generalisation was one grep away: `grep -ln "\.backward()" cv_bench/*.py` names `g4b`, `g6` and
`bench_throughput`. G6 is now on 2 x H200 alongside g4b. `bench_throughput` is a timing harness that
does not load the 70B for backward work and is unaffected.

**Rule of thumb, recorded so the next such job is submitted correctly the first time:** a 70B forward
pass fits in 2 x 80 GiB; a 70B *backward* pass does not. Anything calling `.backward()` on this model
asks for `h200:2` or `a100:4`.

**D74. The readout and the generation were scoring different prompts, so the selection joined on almost nothing.**
`cvb_neutral2` completed and `cvb_g3` ran behind it, so the chain worked mechanically. The selection
it produced does not.

When D-2026-09-21-10 changed `phase_free` to span each framing's switching point, `phase_mass` was
left scoring the calibration values. The two sets barely intersect: **37 shared keys out of 344**.
`choose_framing` joins the readout probability to the sampled frequency on
`(framing, game, value, flip)`, so its slope was computed from accidental overlaps --
`n_free_levels` of 0, 2, 3, 10 and 20 where every cell should have 10.

    mass levels (content/lottery):  22, 23, 27, 28, 32, 33 ...
    free levels (content/lottery):  22, 33, 48, 62, 77, 88 ...

**Chosen:** a new `--phase massfree` scores the readout at exactly the levels free generation
visited -- 80 forward passes, about a minute -- and `choose_framing` prefers that file when it
exists. `framing_choice.json` is renamed to `framing_choice_PARTIAL_JOIN.json`, not deleted, and G3
is requeued behind the corrected selection.

*Alternatives not taken:* record the readout probability inside each free-generation record, which is
the cleanest design but needs the 640-sample pass regenerating (~35 min against ~1 min); or widen
`phase_mass` to cover both sets, which scores hundreds of prompts nobody needs.

**G3's completed run is not wasted but is not final.** Its 384 rows used
`framing = counterbalanced`, chosen from the partial join, and its log says "selected by
cv_bench/neutral.py" -- which was true of the file and false of the evidence. The legacy-label half
of that run (128 rows) is unaffected by the framing and stands; the neutral half is superseded by
the rerun.

**Third instance of one shape.** D63 was a selection written from zero rows; this is a selection
written from a join of almost none. Both parsed cleanly and both were consumed downstream as though
they meant something. `choose_framing` now refuses an empty input (D63) -- it should also report the
join size, which it now does through `n_free_levels` being visible in the file it writes.

**D75. One model load per allocation, not one per layer.**
`cvb_g4b` computed the L48 lottery gradient successfully -- both versions are on disk -- and then
failed with

    RuntimeError: GPUs still busy after 900s: free = 6.8 GiB, 6.9 GiB; need 118.8 GiB each

The sbatch ran `for L in 48 50; do srun ... --layer $L; done`, so each layer was a separate `srun`
that loaded the 141 GB model from scratch. The second could not start because the first had not
finished releasing its memory. `wait_for_gpus` waited the full 900 seconds and then refused, which is
exactly what it is for -- the guard behaved correctly and the design was wrong.

**Chosen:** one `srun`, one model load, an internal loop over every (layer, game) pair, and a skip for
any gradient already on disk. The L48 lottery result is therefore kept rather than recomputed.

*Alternatives not taken:* a sleep between sruns, which guesses at a teardown time that depends on the
node; `--exclusive`, which reserves hardware this job does not need for the 20 minutes it actually
computes.

**Four of tonight's failures now share one description:** a job that was correct in what it computed
and wrong in how it asked for its resources -- the L40S capacity fault, the two backward-pass OOMs,
and this teardown race. None was a bug in the science; all four were me mis-specifying the
environment a correct computation needed.

**D76. All 720 judge calls succeeded and every one was recorded as failed.**
Two independent bugs in `_call_judge`, both mine.

**Parsing.** The scores were searched for in `json.dumps(payload)` — the response envelope
re-serialised — where every quote inside the assistant's text is backslash-escaped. The pattern
`"fluency"` therefore matched nothing and 480 good replies from gpt-5 and claude-sonnet-4-6 were
recorded as `no json in reply`. The fix pulls the assistant's text out of each provider's envelope
first (`choices[0].message.content`, `content[*].text`, `candidates[0].content.parts[*].text`) and
parses that.

**Endpoint.** `gemini-2.0-flash` is not served on this key; all 240 Gemini calls returned `http 404`.
The models endpoint lists `gemini-2.5-flash`, which is used instead.

Verified with one live call per judge before rerunning — all three now return four integer fields.
The 720 failed rows and their completion marker are moved to `*_ALLFAILED.*` rather than deleted, so
the failure is on the record and the rerun does not skip them.

**What this nearly cost.** The marker had been written, so by every automated check this project has
— completion marker present, expected rows on disk, job exited 0 — G5b's judging was finished. Only
reading `parse_status` showed that 100% of it was empty. A marker says a job ran to the end; it says
nothing about whether what it wrote means anything.

**D77. G5b is scored by two judges, not three; the gap is reported, not hidden.**
Authors' decision, 22 Sept, on the measured cost of the alternative.

| judge | scored | note |
|---|---|---|
| `gpt-5` | **240 / 240** | complete |
| `claude-sonnet-4-6` | **240 / 240** | complete |
| `gemini-2.5-pro` | 23 / 240 | rate limited; `http 429` on 216 of its first 240 calls |
| `deepseek-v4-pro` | 0 | no credential in `~/secrets/working_apis` |
| `kimi-k2.6` | 0 | no credential |

Retrying Gemini with 4/8/16/32/64 s backoff reached **0.5 rows per minute** — measured over a
110-second window, not estimated — putting the remaining 215 calls at about **6.5 hours**. The limit
is a hard quota rather than a transient, so the backoff worked as designed and made no difference to
the throughput. The authors chose to stop and report two judges.

**What this means for any G5b figure.** It is a **two-judge** figure and will say so. The published
five-judge mean was already unreproducible on this side for want of two credentials (D70), and V2
established that the paper's own five-judge passes carry **no API response ids**. So the comparison
available here is narrower than the paper's in a way no amount of compute fixes.

Means on the 480 complete rows: `gpt-5` 7.651, `claude-sonnet-4-6` 6.316. The 23 Gemini rows are
kept and labelled partial; they are **not** pooled into a mean with the other two, because a
23-of-240 subsample of one judge is not that judge's score.

Judge-independent measures (`results/S/s1/g5b_measures.csv`, S1.6's four text measures on all 240
generations) are complete and unaffected — they need no API at all, which is why the phases were
split.

## D78 — Figure 11 is an inverse calibration, not a dose-response (22 Sept)

Asked whether the paper's layer-48 steerability contradicts panel A. It does not, and
the two cannot be compared directly, because they are different measurements.

`Probes/raw_data/probe_results_final.json`, key `figure_11_dose_response_lottery_ultimatum_llama`,
holds 30 records of the form (target switching point, `lambda_required`), produced by
`coarse_grid_then_bracketed_binary_search` over a declared bracket `lambda_range: [-6.0, 0.0]`.
That is the inverse of G4: it fixes the outcome and searches for the dose, where G4 fixes the
dose and measures the outcome. A bracketed search returns a number whether or not the target
was reached; no residual, convergence flag or failure case is recorded alongside it.

Two features of the returned values are consistent with the bracket rather than with a
measured response, and are recorded as observations, not as a verdict:
  - lottery is linear in the target (R^2 = 0.981, 22 points) and its last value is -5.9987,
    0.0013 from the declared bracket edge -6.0;
  - 7 of its 21 steps reverse direction, which a smooth calibration would not do.
  - ultimatum (R^2 = 0.989, 8 points) stops at -5.0661, short of the edge, so the pattern is
    not uniform across games.

The decisive test — steering with the paper's own direction at layer 48 — cannot be run.
No probe weight vector exists in the repo: `probe_results_final.json` carries figure data and
21,040 per-agent rows only, and `Probes/runs/` carries judge-scoring artefacts only. This is
the same provenance gap recorded in `reports/PROBE_PROVENANCE.md`, now blocking the one
experiment that would settle the discrepancy.

Options not taken: (a) treat the flat L48 panel as refuting the paper — rejected, a rebuilt
direction cannot refute a claim about a direction that was not kept; (b) refit a direction and
call it theirs — rejected under rule 1. Chosen: report it as a failure to reproduce with the
qualifier stated in the figure, which is cheapest to reverse if the direction is later found.

Figure change: panel A's note in `cv_bench/g4_figure.py` now carries the qualifier its own
title already had ("with a probe we rebuilt: its own direction was never saved"). No data
changed; `figures/g4_summary.{pdf,png}` rebuilt.

## D79 — D78 corrected: the paper's layer-48 steering is verified in its own data (22 Sept)

D78 read `figure_11_dose_response_lottery_ultimatum_llama` as possibly an artefact of its own
search bracket. That was wrong, and the error came from reading only the inverse-calibration
records and not the psychometric curves beside them.

`figure_7_psychometric_curves_llama` holds the forward evidence: per target switching point,
the full curve over the task parameter, n_agents = 40 at every point, with `n_choosing_risky`
and `raw_fraction_risky` (verified: raw == k/n at all 450 rows). Interpolating the 0.5 crossing
from their raw counts and comparing to the target:

  lottery   L48  10 targets 30..200   mean |error| 2.1 tokens, max 4.5
  ultimatum L48   4 targets 30..60    mean |error| 1.1 tokens, max 2.5
  lottery   L50  10 targets 30..200   mean |error| 2.6 tokens, max 5.0
  ultimatum L50   4 targets 30..60    mean |error| 1.8 tokens, max 3.8

So the paper's claim on p8 -- "we successfully shift this switching point across a wide range
from approximately 30 to 200 tokens, with achieved values closely matching targets" -- is
supported by the data it released. The effect is forward-verified, not merely a search return.

What survives from D78, reduced in scope:
  - `lambda_required` = -5.9987 against the declared bracket edge -6.0 is real, but it sits at
    target 240, outside the 30-200 range the text claims. It is a remark about figure_11's tail,
    not about the headline result.
  - The non-monotone steps in `lambda_required` remain, and are unremarkable given that the
    achieved crossings land within ~2 tokens regardless.

Two observations that are new and are NOT challenges to the above:
  - A complete parallel layer-50 set exists in the released data (`*_layer50`, 7 keys) and is
    not reported in the paper, which states layer 48 throughout and says the layer was chosen
    on held-out probe performance. An unreported arm, noted for rule 5 symmetry; the two layers
    perform almost identically.
  - `plotted_fraction_risky` differs from `raw_fraction_risky` on 124 of 450 rows, by up to
    0.0705, mean +0.0007. It is not add-alpha or Jeffreys smoothing (tested, 1-2 matches of 450).
    Some display-level smoothing is applied that the paper does not describe. Every number above
    is computed from the raw counts, so this does not affect them.

Consequence for G4: panel A now stands as a direct contradiction of a verified claim, not as a
methodological caveat about it. The explanation must lie in the difference between the paper's
setup and the rebuild, and the decisive discriminator -- their probe direction -- is still not
in the repo. `reports/G4_DECISION.md` and `reports/REVIEW_CROSSREF.md` to be updated.

## D80 — G4 figure restricted to layer 50, all external attribution removed (22 Sept)

At the authors' instruction the figure now reports layer 50 only and names no external work.

Changes in `cv_bench/g4_figure.py`:
  - panel A plots layer 50 alone; title "rebuilt probe, layer 50: moves, then reverses";
    single-series legend dropped.
  - panel B drops the two layer-48 bars, leaving as-written L50, rebuilt L50, rebuilt Qwen17.
  - panel E restricted to layer 50 (it previously averaged 48 and 50 silently). Values move
    slightly: diff-of-means 17.2 -> 17.4, first PCA 9.5 -> 9.8, ridge 9.5 -> 8.7, reward
    5.8 -> 6.8, readout gradient 2.7 -> 2.8, random 0.2 -> 0.1.
  - panels C and D are unchanged: neither is layer-specific.
  - every reference to the published work removed from titles, notes and docstrings.
  - panel B's y-axis now names the coding it uses. The bar is computed under decision-phrase
    coding; the same quantity under legacy coding is 0.122 rather than 0.005, so an unlabelled
    axis overstated the gap roughly 25-fold at that bar. No data changed, only the label.

Recorded because it is a reporting decision, not a result: the layer-48 arm still ran, is still
in `results/S/s1/g4_curves.csv`, and is still reported in `reports/G4_DECISION.md` and
`reports/EXCLUDED_ARMS.md` under rule 5. Nothing was deleted or regenerated.

Cost of the choice, noted for the authors rather than as an objection: layer 48 carried the
flat arm, and it also served as panel A's control -- it showed the hook, the direction and the
coding all work, so a flat curve was a measurement rather than a dead pipeline. With one layer
plotted the remaining curve has nothing to be read against. Options not taken: keep both layers
(rejected, the authors asked for one); keep layer 48 as an unlabelled grey control line
(rejected, it would still be a second layer on the panel). Reversible by reverting this commit.

## D81 — G4 figure reduced to three measurement panels (22 Sept)

At the authors' instruction the dose-response panel and the variant-coding panel are removed.
The figure is now 2x2: coding agreement against the token cap (A), readout against free
generation (B), direction geometry at layer 50 (C), and the notes block.

  - `panel_a` and `panel_b` deleted from `cv_bench/g4_figure.py`; both remain in git history
    at a3710c0 and can be restored by reverting this commit.
  - surviving panels relabelled A, B, C; layout 2x2 at 9.8x7.2 in.
  - suptitle "G4: coding, instrument and direction geometry".
  - the notes block is rewritten as findings rather than verdicts. Every entry previously
    began "No", which reads as a rebuttal; the panels are measurements of how the instruments
    behave, not a rebuttal of anything, and the column of "No"s misrepresented that.

Consequence, recorded for the authors rather than as an objection: the figure no longer carries
a steering result. What remains is entirely about how the measurements behave -- the parser, the
readout and the direction's geometry. That is a coherent figure and every panel is well
evidenced, but the G4 dose-response is now reported only in `results/S/s1/g4_curves.csv` and
`reports/G4_DECISION.md`, not in any figure. Nothing was deleted or regenerated; rule 5 holds
through the report and the CSV.

Options not taken: keep the dose-response as a fourth panel (rejected, the authors asked for its
removal); split it into a separate figure (not asked for, and available on request).

## D82 — W9 to W12 drafted: the four additive S1 patches (22 Sept)

The authors chose the paper-patch route over expanding `friday_session.txt`. Four entries
written to `paper_patches/`, eight rows appended to `paper_patches/CLAIMS.csv`.

  W9  the prompting ladder and the rho dose-response  (s1_7)
  W10 an effect size and an interval for the persona result  (s1_8, hosted rows)
  W11 catch trials for the ultimatum responder  (s1_2)
  W12 uncertainty on every switching point  (s1_3)

All four are re-analyses of `cleaned/` logs. No new compute, no GPU, nothing regenerated, and
rule 2 is untouched: the legacy directories were read, never written.

**Selection rule the authors set:** worth including, absent from the submission, and not
contradicting it. That filter admits these four and excludes s1_4 (the probe ceiling: 82%
against the 0.95-0.99 reachable from the stimulus alone, and a by-row split that makes
Section 3.3's "held-out preference trials" inaccurate) and s1_5 (per-judge orderings, already
`PAPER_AUDIT` section 2.5). Both are recorded here as deferred, not resolved. s1_4 remains the
finding with the most evidence behind it and the one a reviewer reading
`Probes/experiments/_common.py` is most likely to reach independently.

**Two things inside the four that are not purely additive, flagged rather than buried:**
  - W11 reports the probe stacks' hyper-fair rejection rates (0.232 at Llama L48 target 60,
    0.400 at Qwen L17 target 60) alongside the hosted 0.000. Reporting only the clean hosted
    result would have been selective under rule 5. The excess-over-staircase column shows the
    rejections follow from a calibrated threshold that has moved above half, which bounds what
    high-target calibration can claim.
  - W12's method sentence states that the 40 "agents" are i.i.d. samples of one prompt
    (`agent.agent_instruction` empty in every logged row). That is a framing correction to
    Section 3. It is included because rule 1 does not allow reporting an interval whose
    definition depends on a population the logs show does not exist.

**A number corrected in passing.** Earlier in session I quoted CoT's lottery switching point as
140.0 from the interpolation column. `MANIFEST` registers the logistic fit, 175.7 with CI
[160.1, 191.8]. W9 uses the registered value and names both estimators, since the curve is
shallow and non-monotone there and the two disagree by 36 tokens.

Checks run: all 34 `S1.*` ids cited across the four files resolve in `MANIFEST.csv`; CLAIMS.csv
parses at 54 rows with no malformed fields; no em dashes in any of the four.

Options not taken: write the S1 findings into `friday_session.txt` as a section 3.9 (the
authors chose the patches instead, and it remains available); apply the patches to the paper
source (there is no `paper_src/` in the repo, so this is blocked, not declined).

## D83 — W9 to W12 folded into friday_session.txt; the separate files removed (22 Sept)

At the authors' instruction everything lives in one .txt. The four patch files written under
D82 are deleted and their content is now section 7 of `friday_session.txt`, which grows from
248 to 556 lines. `paper_patches/` holds `CLAIMS.csv` (54 rows, unchanged by this) and
`appendix_prompts.md` (pre-existing).

Nothing was lost in the move. Section 7 carries all four patches in full, plus the deferred
items (S1.4, S1.5, S1.6, S1.1) with the reason each is out. `CLAIMS.csv`'s `patch` column
still names W9 to W12, which now resolve to section 7 rather than to files; section 6's
inventory line says so.

Checks: every explicit MANIFEST id in section 7 resolves; no em dashes; no line over 80
columns in the new section (the four over-length lines at 95, 157, 161 and 222 predate this
and are left alone).

Recoverable: the four files are in git history at 8717d38.

## D84 — W10 recharacterised: it corrects published values, it does not corroborate them (22 Sept)

The authors asked whether s1_7 and s1_8 really neither contradict nor duplicate the
submission. Checking rather than asserting, the answer for s1_8 is no, and D82's "corroborated"
verdict was wrong.

Against the four values in Section 4.2.1:

      published        measured               inside the interval
      around 125       132.9 [131.3, 134.5]   no, though "around" is hedged
      only 20 tokens    20.0 [19.8, 20.2]     yes, exact
      exceeds 30        37.9 [36.9, 38.9]     no
      only 10 tokens    12.8 [11.5, 13.9]     no

One of four. The direction and rough magnitude of both persona effects hold; three of the four
stated numbers do not. What the patch actually does is settle PAPER_AUDIT section 2.2's
text-versus-figure disagreement on the ultimatum baseline: 37.9 agrees with Fig. 3B (~38) and
not with the text's 30.

It is also redundant as a figure. The hosted rows measure the experiment Figure 3 already
shows; the new content is the intervals, the test, the corrected values and the two unreported
arms. W10 now says so and recommends the numbers go in the text rather than as a panel.

W9 survives the same check, with one caveat added rather than removed: its baseline is 106.8
against the hosted 132.9, so printing the panel puts PAPER_AUDIT section 2.2's 26-token
cross-stack gap in front of a reviewer. The patch does not create that problem but it does make
it visible, and the authors should decide that deliberately. A second, smaller point added:
"prompting dose-response" in Section 3.1 presupposes a response the lottery does not show.

Also added to W9, from a question in session and previously unlogged: the exemplar sets are
asymmetric. The lottery dose100 prompt carries 1 of 6 dominated-choice demonstrations and the
ultimatum dose000 prompt carries 3 of 6 catch-trial demonstrations
(S1.7.exemplars.*.fraction_positive notes). Moving along rho changes both which action the
examples take and how many irrational examples appear, which is a plausible partial explanation
for the ultimatum drop at rho = 1.0.

Changed: friday_session.txt section 7 (W10 "Why" block, W9 caveats 1, 1b and 4);
paper_patches/CLAIMS.csv rows GAP-persona-ci and GAP-ladder. No figure or data changed.

## D85 — stack labels named directly instead of A/B/C (22 Sept)

At the authors' instruction the figures name the serving setups rather than lettering them.

    hosted          -> "Goodfire hosted API"        (ticks: "Goodfire")
    vllm            -> "local vLLM, bf16"           (ticks: "local vLLM")
    probe-llama-l48 -> "local probe, Llama layer 48"
    probe-llama-l50 -> "local probe, Llama layer 50"
    probe-qwen-l17  -> "local probe, Qwen layer 17"

Changed in `cv_bench/s1_figures.py` (STACK_TITLE, plus a new SHORT_STACK for axis ticks where
the full name will not fit) and `cv_bench/s1_data.py`. s1_8 built its y-tick labels from the raw
stack key and now routes them through SHORT_STACK. s1_7's title, panel title and reference-line
label follow: "run on the local vLLM stack only", "local vLLM: the ladder on its own axes",
"Goodfire baseline (reference only, not compared)".

The lettering is also gone from the paper-facing prose so the vocabulary matches the figures:
`friday_session.txt` section 7, `paper_patches/appendix_prompts.md`, and the `cv_bench/s1_ladder.py`
string that generates that appendix, edited together to stay in sync without re-running the
script (which would have appended duplicate MANIFEST rows). "Stack C" survives only in two
source comments and one docstring, which render nowhere.

One layout fix this forced. s1_7's legend had `frameon=False`, and the longer "Goodfire
baseline" label put the grey reference curve straight through the text. The legend now has an
opaque SURFACE background at zorder 6. No data changed; all eleven figures regenerated.

## D86 — s1_2 annotation layout rebuilt to remove five text collisions (22 Sept)

Reported by the authors. Layout only; no value, interval or marker position changed.

Collisions and what each one was:
  1. the "(threshold not identified)" labels were annotated at (2, y) with y the condition's
     own rate, so baseline_rp (0.0278), persona (0.003) and cot (0.000) were written within
     0.03 of each other and struck through one another. They are now collected and printed
     once as a single corner block, "no threshold on this grid: baseline_rp, cot, persona",
     while each still draws its own dashed reference line.
  2. every marker label used the same (7, 4) offset, so fs+cot 025 (y=0.031) and fs+cot 075
     (y=0.014) landed on top of each other. The offset now drops to -11 when a label already
     sits within 0.02 in y and 12 in x.
  3. "offers at or above half the pie" sat at (51, 0.28), right of the rule, which on the
     probe panel is exactly where target60 and its interval are. It moved left of the rule and
     down to y=0.205.
  4. "offer grid ends at N" sat at the bottom right, where the fs+cot labels land. It moved to
     the top right.
  5. after 4, it collided with the rule label along the top row, which is what 3's move to
     mid height resolves.

Every small annotation now carries an opaque SURFACE bbox at zorder 5, because these panels
have full-width dashed reference lines at 0.000, 0.003 and 0.0278 that ran through the text
whatever the placement.

Only s1_2 was rebuilt. The other figures were checked visually after the label rename (D85) and
the grid removal (D85's predecessor) and are clear.

## D87 — s1_2 reports layer 50; "bf16" dropped from the stack label (22 Sept)

Both at the authors' instruction.

1. The precision suffix is gone from the vLLM label: "local vLLM, bf16" becomes "local vLLM"
   in `STACK_TITLE` and `cv_bench/s1_data.py`. It is a shared label, so s1_1, s1_3 and s1_4
   change with s1_2 and were regenerated. The precision itself is unchanged and still recorded
   in `reports/STACK_AUDIT.md` and in the run manifest.

2. s1_2's third panel switches from `probe-llama-l48` to `probe-llama-l50`. Both were already
   computed and are already in `results/S/s1/s1_2_catch_ultimatum.csv` and in MANIFEST; this
   selects which one the figure shows and recomputes nothing.

   The panel now reads higher at every target, which the authors should know before using it:

                      L48                     L50
       target 30     0.000 [0.000, 0.0087]   0.0614 [0.0425, 0.0878]
       target 40     0.0205 [0.0108, 0.0384] 0.0727 [0.0520, 0.1009]
       target 50     0.0932 [0.0694, 0.1240] 0.1432 [0.1135, 0.1790]
       target 60     0.2318 [0.1948, 0.2735] 0.2682 [0.2289, 0.3115]

   Layer 50 rejects hyper-fair offers at every calibration target including 30, where layer 48
   rejects none. Section 7's W11 quotes the layer-48 numbers in its draft text and table; those
   are still correct as written but no longer match the figure. Flagged to the authors rather
   than silently rewritten, since which layer the paper reports is theirs to decide.

Two layout consequences, both handled: the y limit rises to 0.37 because the layer-50 target60
interval reaches 0.3115 and was colliding with the corner note, and the rule label moves from
y=0.205 to 0.235 to stay clear. Condition labels drop to zorder 3.5, above the dashed reference
lines so their boxes still mask them but below the markers so a box never covers its own point,
which it was doing to target40.

## D88 — panel A's note corrected: the mechanism is the option list, not truncation (22 Sept)

The authors asked whether panel A is an effect of responses being truncated. Measured rather
than assumed, on the two caps that bracket the dip, both from `g2_lambda0/llama_chat*_lottery.jsonl`:

    cap    n      looks cut off   mentions both labels   legacy-strict agreement
     12   1800        0.680              0.000                  1.0000
     64   1800        0.641              0.559                  0.5906

Truncation is marginally HIGHER at 12 tokens and agreement there is perfect. Truncation
therefore does not explain the dip. What changes is whether the severed text got far enough to
name both options: at 12 tokens the reply is cut before the second option, so the two rules read
the same single label by construction; at 64 it has echoed "1. Safe Option ... 2. Risky Option"
and been cut before choosing, so first-mention and last-mention differ on 56% of trials.

Being cut off is necessary (a completed reply states a choice and all three rules find it) and
not sufficient. The note said the opposite:

  was: "Agreement collapses where responses are cut mid-sentence and returns once they can
        finish, so the token budget drives it, not real ambiguity."
  now: "A mid-range budget lets the reply list both options before it stops, so first and last
        mention diverge. Shorter and longer budgets each leave one answer."

The claim line changes from "is a truncation effect" to "is a budget artefact". The panel's
conclusion is unchanged and still correct: it is an artefact of the decoding budget, not real
ambiguity about what the model chose. Only the stated mechanism was wrong. No data, no point
and no axis changed; `figures/g4_summary.{pdf,png}` rebuilt. The word "truncation" now appears
nowhere in `cv_bench/g4_figure.py`.

STILL OPEN, and it blocks this panel from going in the paper. Its three points are hard-typed
in `panel_c`:

    pts = [(12, 0.982, "27,120"), (64, 0.591, "1,800"), (256, 0.999, "920")]

They are not read from a file and are not in `MANIFEST.csv`, which is a rule 1 violation. The
64-token point reconciles exactly against the source (0.5906, n=1,800). The 12-token point does
not: the figure says 0.982 on n=27,120 while `llama_chat_lottery.jsonl` gives 1.0000 on n=576
both-coded, so the figure's value comes from some larger aggregation not yet identified. Offered
to the authors: recompute all three from files and register them. Not done yet.

## D89 — the coding-agreement panel removed from g4_summary (22 Sept)

Removed at the authors' instruction, and it should have been withdrawn on the evidence anyway.
`g4_summary` is now two panels and the notes block: the readout against free generation (A) and
direction geometry at layer 50 (B). Suptitle "G4: instrument and direction geometry".

Why it could not stay, recorded because this is a retraction of my own claim and not a style
change:

  1. The three points are not a controlled comparison. They come from three different runs with
     n = 27,120, 1,800 and 920, not from one prompt set swept across three budgets, while the
     x axis is labelled "max new tokens" as though the budget were the only thing varying. The
     12-token point's source was never located.
  2. The points were hard-typed in `panel_c` and absent from `MANIFEST.csv`, which is a rule 1
     violation. Only the 64-token value was ever reconciled against a file (0.5906 on n=1,800,
     from `g2_lambda0/llama_chat64_lottery.jsonl`).
  3. Two different mechanisms were asserted for it in the notes block, in D88 and before it,
     and neither was measured on the panel's own data. The first (responses cut mid-sentence)
     is contradicted by the 12-token arm, where truncation is higher and agreement is perfect.
     The second (the reply lists both options before stopping) was stated without a check; a
     later look at a 256-token slice showed a similar both-mention rate with very different
     agreement, though that slice was itself mismatched and so settles nothing either way.

What survives and is not in doubt: on `g2_lambda0/llama_chat64_lottery.jsonl`, 737 of 1,800
trials are coded differently by the last-match and first-match rules, an agreement of 0.5906.
That measurement is sound and stays available; what could not be supported was the curve built
around it and the causal reading attached to it.

To rebuild it properly: one fixed prompt set and format, generate at 12 / 64 / 128 / 256 varying
nothing else, then compute agreement and a first-versus-last breakdown on identical trials.
`instr_cap.csv` already has that design at 64/128/256 with n=140 and needs the 12-token arm and
a larger n. Offered; not run.

`panel_c` is deleted from `cv_bench/g4_figure.py` and recoverable at f2eafec. No report,
patch or section of `friday_session.txt` referenced the panel, so nothing else needed changing.

## D90 — the Goodfire reference line removed from s1_7 (23 Sept)

From the 22 Sept sync (`shrey/meeting.txt`), verbatim: "we might just want to discard the
Goodfire baseline", answered "Goodfire. Yeah, sure. Yeah."

Two things that phrasing does not settle, recorded so the basis for this change is not
overstated. The request is hedged ("might just want to"), and the referent is ambiguous: the
plots were on a screen share and the same passage points in turn at "these 2", at something
"corresponding to the Figure 3 here", at one that is "for both lottery and ultimatum", and at
the statistical-test plot. s1_7 was chosen because it is the only figure carrying an explicitly
labelled Goodfire baseline reference line, but "discard the Goodfire baseline" could equally
mean dropping the hosted panel from s1_1, s1_2 or s1_3, or the hosted rows from s1_8. That
inference is mine and has not been confirmed.

The dashed grey line and its legend entry are gone from
`s1_7_ladder`'s left panel, which is now single-stack. Title becomes "S1.7  The prompting
ladder, local vLLM stack".

The opaque legend background added yesterday is reverted to `frameon=False`: it existed only
because that dashed line ran through the label text, and with the line gone the upper-left
region is clear.

Consequence, and it cuts both ways. The line was the only place the 26-token cross-stack gap
(132.9 Goodfire against 106.8 vLLM) was visible in any figure, and D82's W9 listed that
exposure as a caveat of publishing the panel. Removing it removes the exposure but not the
problem: PAPER_AUDIT section 2.2 still holds that until the gap is settled, no comparison
between the probe results and the prompting or SAE results is safe. Section 7's W9 caveat 1 is
rewritten to say the line is gone and that any sentence citing these numbers must still name
the stack, because a reader can no longer see it on the panel.

Still outstanding from the same meeting and not done here: the readout figure rework (drop the
"steps" annotations, four columns, spell out legacy/strict/decision underneath, add intervals
across agents), the font check against the paper, and the anchors README with the three-step
write-up. Also unresolved: the meeting kept layer 48 in the main text with layer 50 in the
appendix, while this session was instructed on 22 Sept to switch s1_2 to layer 50. Raised with
the authors; s1_2 is left on layer 50 until they choose.

## D91 — s1_7 gains the ultimatum ladder (23 Sept)

The left panel was lottery only while the rho panel already carried both games, so a reader of
the left panel would have taken the whole figure for lottery. It is now 1x3: lottery ladder,
ultimatum ladder, rho dose-response. Suptitle "S1.7  The prompting ladder on both games, local
vLLM stack".

No new compute. All six ladder conditions already exist for ultimatum in
`cleaned/behavioral_games_combined.csv`, 17 offer levels each, and `load_behavioural` already
returned them; only the lottery ones were being plotted. Added a 0.5 rule to both ladder panels
so the crossing is readable, and kept one legend, since both panels show the same six
conditions.

What the new panel shows, and it corroborates a finding already in `friday_session.txt`
section 3.8 rather than adding a new one. On the local stack the responder accepts almost
everything unless given few-shot demonstrations:

    persona        P(accept) 1.00 at an offer of 10, 0.97 at 90
    baseline_rp    0.78 -> 0.85
    cot            0.57 -> 1.00
    fewshot        0.30 -> 1.00
    fewshot_cot_dose000  0.00 -> 0.72
    fewshot_cot_dose100  0.45 -> 1.00

The first three never fall below 0.5, which is why `S1.7.vllm.ultimatum.{baseline_rp,persona,
cot}.switch` are registered as not identified. The panel makes that visible instead of leaving
it as an empty cell in a table.

Note for whoever places this: at 16.6 inches wide it is built for an appendix page and will
need scaling to a text column. If that is too wide, the alternative is a 2x2 with the rho panel
spanning the bottom; not done, since the authors asked for the ultimatum version rather than a
relayout.

## D92 — the few-shot family is separable by colour and dash, not marker alone (23 Sept)

Reported by the authors: three lines in s1_7's ladder panels were the same yellow. They were.
`FAMILY` gave every few-shot condition the single base gold #BD8A00, and the only difference
between them was a small marker glyph, which does not read at panel size or in print.

The family hue is kept, because the docstring's convention is that a reader tells the family
from the colour across figures. Two channels added inside it:

  GOLD_RAMP  000 #7A5A00, 025 #9C7300, 050 #BD8A00, 075 #D3A63A, 100 #E0BE6B
             graded dark to light by dose; plain `fewshot` stays on the base gold
  DASH_OF    a distinct dash pattern per member, applied in the ladder panels

Colour, dash and marker now all differ, so the three lines separate at size, in greyscale and
in print. s1_2's middle panel benefits from the same ramp: fs+cot 000, 025 and 075 were three
identical gold points and are now dark, mid and light.

One caveat on the ramp: #E0BE6B at the light end has low contrast against the #FCFCFB surface,
around 1.7:1, below the usual 3:1 floor for graphical objects. It is legible here because the
dash pattern and marker carry it, but if the palest member ever has to stand on colour alone it
should be darkened.

Knock-on fix in s1_2's probe panel. Switching that panel to layer 50 (D87) moved target30 and
target40 close together, 0.061 against 0.073 at thresholds 31.8 and 36.3, and target30's label
ran through target40's marker. The label placement now looks ahead at every marker in the panel,
not only at labels already written, and flips to the left when another point sits where the text
would go.

## D93 — the ultimatum version of g4_summary: one panel possible, the other not (23 Sept)

Asked to plot the ultimatum version of both panels. Only one can be built from existing data,
and for two different reasons, so the figure now carries a third panel that says why.

Panel A, the readout against free generation. Not extendable, and this is a behavioural fact
rather than a data gap. Measured from `instr/freegen_llama.jsonl` and
`instr/readout_grid_llama.jsonl`, on ultimatum at every offer from 10 to 100:

      free generation  P(accept) = 1.000 at all 7 levels
      logit readout    p_positive = 1.000 at all 19 levels (0.991 at 85)

Neither curve approaches 0.5, so neither has a crossing and the comparison panel A makes is
undefined. This is why `instr_agreement.csv`'s six ultimatum rows all carry empty crossings and
were being silently dropped by the panel's filter. Note the two instruments AGREE perfectly on
ultimatum, which sounds like a positive result and is not: they agree because both are
saturated. The panel's finding, that the readout does not track free generation, is a lottery
result and the figure now says so.

Panel B, direction geometry. Not extendable either, but here it is a genuine gap:
`results/S/s1/g4b_geometry.csv` has 36 rows, all lottery. No ultimatum probe or direction set
was ever fitted. Adding it is GPU work, a probe fit plus the five comparison directions at
layer 50, not a filter change.

Built instead: panel C, both ultimatum curves across offers with the 0.5 line, which documents
the saturation directly. The figure is now 2x2 and the suptitle names the scope, "lottery, with
the ultimatum check". A fourth notes entry states that A and B are lottery only.

Outstanding under rule 1: panel C computes its values inline from the two raw jsonl files and
they are not in `MANIFEST.csv`, unlike panel A's, which come from the registered
`instr_agreement.csv`. They should be registered before this figure goes anywhere near the
paper. Not done here.

## D94 — panel C removed again (23 Sept)

Removed at the authors' instruction, one commit after it was added. The figure is back to two
panels and the notes block, suptitle "G4: instrument and direction geometry (lottery)", which
keeps the scope statement the panel was carrying. `panel_u` is deleted and recoverable at
39db54b.

The measurement behind it stands and is recorded in D93: on ultimatum, free generation gives
P(accept) = 1.000 at all seven offer levels and the readout gives p_positive = 1.000 at all
nineteen, so neither instrument has a crossing and panel A's comparison is undefined for that
game. That is now stated only in the title's "(lottery)" and in this log, not on the face of the
figure.

## D95 — the notes block removed from g4_summary (23 Sept)

Removed at the authors' instruction. The figure is two panels at 9.6x4.4 inches, down from
12.6x4.4, since the third grid column was the notes block. Recoverable at ee331e3.

What goes with it, so the authors know what a reader loses. The block carried the only
statement on the figure of what each panel is for, and in particular the qualifier on panel A:
that the readout is a check on sampled text rather than a substitute for it. Without it panel
A's title, "the readout does not track free generation", stands alone and a reader has to infer
the consequence. If this figure goes in the paper, that belongs in the caption.

The "(lottery)" scope marker stays in the suptitle. It is now the only thing on the figure
saying the panels are single-game, since both the ultimatum panel (D94) and the notes entry
that said so (D93) are gone.

## D96 — G4 has no Llama ultimatum arm, and why (23 Sept)

Surfaced by a question from the authors, not by any report, which is the process gap worth
fixing here: the fact was recorded only inside a JSON.

`g4/probe_reconstruction_L48.json` and `_L50.json` both carry, for ultimatum:

    trained=False   classes=[1]   n_kept=152   n_dropped=0   n_levels=19

All 152 probe-training trials are labelled accept. A logistic probe needs two classes and a
difference of means needs two groups, so no choice direction exists, and the sweep rows record
`"skipped": "direction unavailable"` rather than running. Nothing was fabricated; nothing was
reported either.

Checked and ruled out as causes:
  - not a coding bug. Three scripts agree the text says accept: instr free generation gives
    P(accept) = 1.000 over 420 generations at 7 levels, the logit readout gives p_positive =
    1.000 at all 19 levels, and section 3.8 already records 760 of 760 accepts at two
    temperatures.
  - not a prompt bug. `cv_bench/instr.py::prompt_for` states both options and both payoffs
    symmetrically and names the two answers.
  - not a pipeline bug. The skip is logged per row.

It is real, and it is format-dependent. The same weights at an offer of 10 accept at 1.000 under
the reconstruction format, 0.775 under vLLM baseline_rp, and 0.000 on the hosted stack. On the
lottery the stacks differ by a 26-token threshold; on ultimatum they differ by the whole
behaviour. Accepting 10 tokens is individually rational, so the model is acting as a payoff
maximiser rather than as the human-like responder the work is trying to simulate.

Consequences already established elsewhere and now joined up: g4_summary panel A cannot be
extended to ultimatum (D93, both instruments saturate at 1.000), and panel B cannot either,
because its y axis is the cosine with a choice probe that does not exist. Qwen L17 is
unaffected, `classes=[0, 1]`, and does yield a full ultimatum geometry.

Not done: adding this to `reports/EXCLUDED_ARMS.md`, where under rule 5 an arm that could not
run belongs. Offered to the authors.

## D97 — the ultimatum geometry joins g4_summary as panel C (23 Sept)

At the authors' instruction. `g4_summary` is three panels at 14.2x4.4 inches: the readout
against free generation, the lottery geometry, and now the ultimatum geometry from the G4u run
in the Track B tree. Suptitle drops "(lottery)" since the figure is no longer single-game.

The bar design is panel B's exactly, as asked: same 0.62 height, same colour rule (teal at or
above 10x, navy at or above 3x, grey below), same `{v:.1f}x` labels, same dotted rule at the
analytic null. Data is read from the shared run root, `g4u/g4u_geometry.csv`, so nothing is
duplicated across trees.

Added on top of the matched design: a black tick per bar at that direction's own permutation
null, 95th percentile over 200 refits with the offer labels shuffled. That is an overlay, not a
change to the bars.

THE CONFLICT THIS CREATES, and it is a direct consequence of matching the design. Panel B's
colour rule is by magnitude. On ultimatum it paints diff-of-means at 34.9x and the ridge at
32.3x teal, the strongest colour, and both sit INSIDE their permutation null, so their height
means nothing. First PCA, the only direction that clears its null, is teal too at 21.8x. Colour
therefore carries no information about which bar survives, and the tallest and most saturated
bar on the panel is one that fails its test. Only the tick position separates them.

Options not taken: colour by whether the bar clears its null, or hollow the failing bars as the
Track B figure did before the match. Either fixes the reading and both break the visual
consistency the authors asked for. Left as instructed and flagged.

Second asymmetry, which no design choice can fix: panel B's reference is the choice probe and
panel C's is a probe fitted to the offer, because the ultimatum probe has one class. The two
panels answer related but different questions and should not be read as a like-for-like
comparison between games.

## D98 — panel C coloured by the test, and why panel B has no ticks (23 Sept)

Both at the authors' instruction, one a fix and one an answer.

Colour. Panel C no longer uses panel B's magnitude ramp. Teal means the bar clears its own
permutation null, grey means it does not, and the value label greys out with the bar. The ramp
was painting diff-of-means at 34.9x and the ridge at 32.3x in the strongest colour while both
sit inside their null, and first PCA, the only direction that clears, in the same colour at
21.8x. Colour now carries the finding rather than the height. A three-entry legend names the
tick and both colours. Bar geometry, label format and the dotted analytic-null rule are still
panel B's exactly; only the fill rule changed.

Why panel B has no ticks, which is not a design choice. The permutation null needs the
activations, and only the ultimatum ones were kept: `g4u/ultimatum_activations.npz` exists and
there is no lottery equivalent anywhere under the run root. G4b saved direction vectors and
gradients, not the matrix they were fitted from, so the lottery null cannot be computed from
what is on disk. Leaving one panel ticked and the other bare invites a reader to assume panel B
passed a test it has not taken, so its title now says so: "no permutation null run; see C".

This is the open item, and it is the same question panel C answers for the other game. Panel B
has 45 levels in 8,192 dimensions and five directions all fitted from that one matrix, so its
`multiples_of_null` axis rests on the same assumption that the ultimatum data just failed. The
fix is a short collection job on the lottery prompts, both layers in one model load, of the same
shape as the ultimatum one that cost 7m54s on two GPUs, so on the order of half a GPU-hour
against 58.1 of 400 used. Not started: it is new compute two days from the deadline and the
authors have been deciding each step, so it is theirs to call.

## D99 — the lottery choice probe does not reproduce on a rerun (23 Sept)

The lottery permutation null was authorised and run as `cvb_g4null` (23611883). It did not
produce a null. The verify guard stopped it first, which is what the guard was for.

    [g4null] verify lottery L50: cosine with G4's direction_raw = 0.39387039
    [g4null] refit does not reproduce G4's direction; the null is not written

What was rerun. `cv_bench/g4null.py::collect` repeats G4's own `phase_train` loop for lottery at
layer 50: the same `render`, the same variant config, the same `torch.manual_seed(int(v))` per
level, the same PROBE_SAMPLES draws at temperature 0.7 and top-p 0.95, the same
`decision_code` coding. It then refits with `_fit`, which reproduces phase_train's estimator
exactly.

Where the two runs differ:

    kept / dropped      mine 354 / 6      G4 351 / 9
    base rate           mine 0.63277      G4 0.62963
    scaler scale median mine 0.019862     G4 0.019852
    distinct activation vectors: 45 of 354 rows

The activations are the same object: 45 distinct vectors, one per reward level, and the scaler
agrees to the fifth decimal. Generation is what differs. Despite the per-level seed, sampling a
70B across two GPUs is not bit-reproducible across runs, so a handful of trials code
differently.

How much that matters, measured on the saved arrays by flipping k labels at random and
refitting:

    k= 1   mean cosine with the original probe 0.931
    k= 3                                       0.824
    k= 5                                       0.755
    k=10                                       0.630
    k=20                                       0.486   (min 0.395)

Flipping ONE trial in 354 moves the direction to 0.93. The observed 0.394 corresponds to about
twenty trials coding differently between the two runs.

**The finding.** G4's lottery choice probe is not a stable object. Rerun the same code, same
seeds, same model, same prompts, and the direction comes back at cosine 0.394 to the one
reported. Two arbitrary directions in the 44-dimensional span of these activations sit near
0.12, so 0.394 is above chance and nowhere near reproducible.

This outranks the question that prompted the job. `g4b_geometry.csv` measures every direction's
cosine against this probe, and G4's own record gives cos_choice_diffmean = 0.269,
cos_choice_pca1 = 0.215, cos_choice_ridge = 0.137. All three are smaller than the probe's own
run-to-run movement. Panel B's bars are therefore not interpretable as stated, for a reason that
has nothing to do with the null scale: the reference direction is noise-dominated at the scale
of the effects being reported.

Not done, and now the open question for the authors. A null for panel B can still be computed on
the re-collected arrays, but it would describe my run rather than the reported one, so it would
not license panel B's numbers. The more useful measurement is the one this accidentally started:
refit the probe n times with fresh sampling and report the spread of the direction. That is the
stability check the probe never had, it needs no new code beyond a loop around `collect`, and at
roughly 0.6 GPU-hours per repeat it is affordable inside the remaining budget.

Spend: about 18 minutes wall on two A100s, roughly 0.6 GPU-hours. Nothing pre-registered
changed and no existing file was written; `g4null/` holds only new outputs.

## D100 — the lottery permutation null: the same verdict as ultimatum (23 Sept)

Computed on the arrays saved by the g4null collection, CPU only, 200 permutations of the choice
labels with every direction refitted each time.

    direction        observed   null p95   verdict
    diff-of-means       19.3x      45.0x    inside
    first PCA           13.3x       2.5x    CLEARS
    ridge, log n        12.0x      21.6x    inside
    reward probe        11.4x      22.9x    inside
    random direction 0   2.9x       2.0x    clears, and see below
    readout gradient     1.7x       2.2x    inside
    random direction 1   0.8x       2.0x    inside

The same shape as the ultimatum result: every direction fitted alongside the probe sits inside
its own null except the first principal component, which clears by a wide margin in both games.

**The verdict does not depend on which fit is used.** The observed values above come from the
re-collected arrays, which give diff-of-means 19.3x where `g4b_geometry.csv` reports 17.4x
(D99: the probe does not reproduce between runs). Both are far below the 45.0x null, so panel
B's tallest bar fails its test whichever of the two fits you take. The instability in D99 makes
the bar heights uninterpretable; this makes the ranking uninterpretable as well, and it does so
robustly.

**One false positive, reported rather than tidied away.** `rand0` sits at 2.9x against a 2.0x
null and formally clears. It is a random direction with no relationship to anything. At a 95th
percentile threshold across seven comparisons a false positive is the expected outcome, not a
surprise, and it is the reason first PCA's margin matters: 13.3x against 2.5x is a different
kind of result from 2.9x against 2.0x. Anyone reading this table should read the margin, not the
verdict column.

What this settles, across both games: the claim panel B carries in its title, that the choice
probe is a contrastive direction because it sits nearest difference-of-means, is not supported.
Difference-of-means is the largest bar in both games and is inside its null in both. The one
direction that survives is the first principal component, which is a statement about the
dominant variance in the activations rather than about contrast.

Not done: panel B still shows the reported bars with no ticks. Making it match panel C means
recomputing it from these arrays, which changes every bar (D99). Left for the authors.

## D101 — the null is drawn on the lottery panel too (23 Sept)

Panel B now carries the permutation null, so the two geometry panels match. Both are titled
"only first PCA clears its null", which is what both games show.

The bars are unchanged. They are still `g4b_geometry.csv`'s reported values, so the panel still
matches the reports and the manifest. What is added is each direction's null as a tick, and a
colour rule that is honest about D99's instability:

    teal    the bar clears its null under BOTH the reported fit and the g4null refit
    grey    it is inside the null under both
    hatched the two fits disagree, so the bar is too close to call

That third case exists because the probe does not reproduce between runs. Checked per bar:

    direction     reported   refit   null p95   verdict
    diff-of-means     17.4    19.3       45.0   inside, both fits
    first PCA          9.8    13.3        2.5   CLEARS, both fits
    ridge, log n       8.7    12.0       21.6   inside, both fits
    reward probe       6.8    11.4       22.9   inside, both fits
    readout gradient   2.8     1.7        2.2   FLIPS
    random direction   0.1     2.9        2.0   FLIPS

The four substantive directions agree under both fits, which is why the panel can be drawn at
all without recomputing the bars. Only the two sitting on top of the null flip, and those are
hatched rather than coloured either way.

Why the bars were not recomputed from the refit, which was the alternative: it would change
every value (diff-of-means 17.4 to 19.3, reward probe 6.8 to 11.4), break agreement with
`g4b_geometry.csv`, `MANIFEST.csv` and the reports, and change nothing about the conclusion,
since all four verdicts are identical either way. Cheapest to reverse was to leave the bars and
add the test.

The headline now holds in both games and under both fits: difference of means is the tallest bar
in each panel and inside its null in each. The title claim that the probe is a contrastive
direction is not supported. The first principal component is the only direction that clears,
which is a statement about dominant variance rather than about contrast.

## D102 — the null is taken off both geometry panels (23 Sept)

At the authors' instruction, matching the earlier plain-bar treatment. Panels B and C are now
solid bars coloured by magnitude (teal at or above 10x the analytic null, navy at or above 3x,
grey below), no dotted rule at 1.0, no permutation-null ticks, no legend, no hatching.

What comes off the figure with them, so this is a deliberate choice and not a quiet loss:

  - each direction's permutation null, which is what said the bars mean what they appear to
  - that difference of means, the tallest bar in BOTH panels, is inside its null in both:
    17.4x against 45.0x on lottery, 34.9x against 56.6x on ultimatum
  - that first PCA is the only direction clearing its null in either game
  - the hatching that marked the two lottery bars whose verdict flips between fits (D99)

The colour rule now reads against the test. On lottery, diff-of-means at 17.4x is teal, the
strongest colour, and fails its null; first PCA at 9.8x is navy and passes. On ultimatum all
three top bars are teal and only one passes. Height and colour both rank the bars in close to
the reverse of what the null supports.

Titles were NOT reverted with the styling. The original read "the probe is not the readout
direction", and that claim is what the null contradicts, so restating it on a panel that no
longer shows the null would assert something the data does not support. Both panels now carry
neutral descriptive titles naming the reference direction instead.

Nothing is lost from the record. `g4null/g4null_lottery.csv` and `g4u/g4u_geometry.csv` hold
every null value, and D99, D100 and D101 hold the findings and the reasoning. Reverting this
commit restores the ticks.

## D103 — the figure title drops the internal task id (23 Sept)

"G4: instrument and direction geometry" becomes "The steering probe: how it is read out, and
which directions it is closest to". G4 is a task id from ICLR_PLAN.md and means nothing to a
reader of the paper; the new title says what the three panels do without it.

The id is not lost: the file is still `figures/g4_summary.{pdf,png}`, the generating script is
still `figures/make_g4_summary.py`, and every value is still registered under its G4 or G4b
MANIFEST id, so the figure remains traceable to the task that produced it.

Remaining jargon a reader still meets on the panels, left because each is defined by its own
axis label or is standard: "choice probe" and "offer probe" (named in the x labels), "logit
readout" and "free generation" (panel A's legend), "diff-of-means", "first PCA", "ridge, log n",
"readout gradient". The three coding names on panel A's x axis, legacy, strict and decision,
are the one place where a caption is still needed: nothing on the figure says they are three
rules for reading a choice out of generated text.

## D104 — s1_7 plotting changes from the 23 Sept review (24 Sept)

Three cosmetic changes requested on the ladder figure, all applied and rendered.

  1. The legend shows "baseline" where it showed "baseline_rp". Display only, via a SHOWN map
     in `s1_7_ladder`. The condition name in `cleaned/behavioral_games_combined.csv`, in
     `MANIFEST.csv` and in every report is unchanged, so `S1.7.vllm.lottery.baseline_rp.switch`
     and the rest still resolve.
  2. Panel titles are "Lottery Game" and "Ultimatum Game". The phrase "the ladder" is gone from
     both, and with it the stack name that used to sit in the lottery title. The suptitle still
     carries "local vLLM stack", which is now the only place on the figure that says which
     stack the curves come from. Worth keeping if the panels are ever cropped apart.
  3. The parenthetical "(2, 3 and 4 of 6)" is removed from panel 3's x label. That text was the
     only thing on the figure recording that the realised fractions are sixths rather than the
     quarters the condition names imply, so the N=6 point now lives only in the caption text of
     section 7's W9 and in `reports/S1_7.md`. Flagged rather than reinstated, since the authors
     asked for it to come off.

No data, fit or value changed. Figure regenerated.
