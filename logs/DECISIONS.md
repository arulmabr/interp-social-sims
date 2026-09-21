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

**D41. The "60" in the amendment's cap is Track B's budget, and D38's second flag is closed.** D38
recorded that the cap "replaces the earlier 40 and 60" while only 40 had ever been communicated to the
Friday session. The 60 was communicated to the **Track B session** instead, as its own allowance of 60
GPU-hours, alongside `--nice=1000` and a one-job-at-a-time restriction, with the Friday session holding
GPU priority. Neither session could see the other's figure, which is why the sum looked unattributed.
The amendment's single 400 GPU-hour cap now replaces **both** budgets, and with it Track B's
one-job-at-a-time restriction and its `--nice=1000` default, which are superseded by amendment items 2
and 3: `--nice=10000` now marks work deferred past the cutoff, not Track B work as such. The 400 is a
**shared** pool across both sessions, not 400 each; Track B draws from the same cap and the accounting
in `reports/SCHEDULE.md` is therefore joint. Track B still writes only under `cv_bench/tasks/`,
`cv_bench/estimator/`, `cv_bench/anchors/`, `results/B/` and `reports/B_*`, and takes shared modules by
merging `iclr-extension` rather than rewriting them.

**D42. B3.2's LoRA anchors are blocked on `peft`, and the 4-bit fallback is unverified, not broken.**
Confirmed independently from the Track B worktree: `peft` is absent (`torch` 2.5.1+cu121,
`transformers` 4.50.3, `accelerate` 1.10.0 are present), so D40 holds and no LoRA anchor can be trained
until it is installed. The intended fallback for the 70B — 4-bit base weights if bf16 on 2 GPUs does not
fit — needs `bitsandbytes`, which is installed at 0.43.2 but prints "compiled without GPU support" on
import. **That warning is not evidence of a bad build**: it was observed on a login node that has no GPU
at all (`nvidia-smi` absent, `torch.cuda.is_available()` false), where the message is expected. Whether
4-bit actually works is therefore an open question to settle on a GPU node before the fallback is relied
on, and it is recorded as unverified rather than failed. Both the primary path and its fallback are
blocked or unconfirmed, so B3.2 is not schedulable until `peft` is installed and a GPU-node import check
has run; that check costs one short interactive allocation and is not a reason to spend the budget.
