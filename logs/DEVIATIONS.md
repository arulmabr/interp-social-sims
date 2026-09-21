# DEVIATIONS.md

Departures from `ICLR_PLAN.md` as written, and corrections to work already delivered. Every entry gives
the before and the after. Reruns are recorded here only when they happened for a technical reason
(CLAUDE.md rule 4); none has yet.

---

## D-2026-09-21-00 — P2–P5 and P10 of `GATE_S0_RESPONSE.md` put in force early

**Instruction.** The authors directed that `GATE_S0_RESPONSE.md` §3 **P2, P3, P4, P5 and P10** apply to
S1 now. The rest of that file — including P1, P6–P9, P11, §2, §4, §5, §6 and §7 — is **not in force**
and has not been applied. In particular:

- `ICLR_PLAN.md`, `PAPER_AUDIT.md` and `CLAUDE.md` are **unedited**. §7 step 1 was not carried out.
- No new task S2.0 (P1) and no Track B work (§2) has been started.
- The §4 corrections to `PAPER_AUDIT.md` are **not** applied, with one exception forced by P10: §4.2
  states that the PDF's Fig. 5A high-temperature brick bars read ≈2.1 against the repo's 4.91. P10
  requires S1.5 to carry both, so `reports/S1_5.md` reports the repo values and lists the PDF values in
  a separate column marked "PDF, source unknown". That is P10 operating, not §4 being adopted.
- `GATE_S0_RESPONSE.md` is unsigned: §1 is blank and the CONFIRMED BY line is empty. Nothing in it is
  treated as an author decision.

**Effect on S1.** P3 adds a task, **S1.8**, which is not in `ICLR_PLAN.md`. P2, P4, P5 and P10 constrain
S1.1, S1.4, S1.5 respectively. All are reflected in `reports/S1_*.md`.

**Logged as AI feedback on methodology** in `logs/AI_USE_LOG.md`, per that file's own header.

---

## D-2026-09-21-01 — S0 preview of S1.1 overstated its conclusion; corrected

**Where.** `reports/PHASE0_SUMMARY.md` §4, and the same claim as relayed in the Gate S0 terminal
summary.

**Before.**

> That refines PAPER_AUDIT §3.1–3.2 in a way that matters for the thesis: **dominated choices are
> produced by the persona prompt and by probe steering at its strongest doses, but not by the SAE
> features at either published dose.** The three families are not interchangeable on this diagnostic,
> which is a point in favour of the benchmark being able to tell them apart.

**After.** The rates are retained; the conclusion is withdrawn and replaced by the floor argument P2
supplies. The replacement text is quoted in `reports/PHASE0_SUMMARY.md` §4 inside a marked block.

**Reason (GATE_S0_RESPONSE §3 P2).** Eight of the legacy grid's reward levels lie below 50, so
P(risky | n < 50) is an arithmetic consequence of the achieved switching point rather than independent
evidence: a switch at 30 leaves about 4 of 8 levels above it, one at 19.8 about 6 of 8, one at ≈59 none.
The three numbers I compared (probe 0.483, persona 0.690, SAE 0.000) are the three switching points
(30, 19.8, 59.1) restated — and they come from **two different stacks at unequal doses**, with no
unsteered rate on the probe stack to compare against. The comparison was invalid on both counts.

**Data unchanged.** No number was recomputed and no rerun occurred; `MANIFEST.csv:S0.I.*` and
`S0.A.lottery.pRisky_dominated.hosted.*` are byte-identical. This is a correction of interpretation.

**Carried into S1.1.** `reports/S1_1.md` gives every rate beside its own switching point and its own
stack's unsteered rate, makes no cross-stack or unequal-dose comparison, and states the floor argument
instead.

---

## D-2026-09-21-02 — S1.4(c) not run: no cached activations exist

**Plan text.** S1.4(c): "If activations are cached: fit a ridge probe for log n, report its cosine with
the choice probe, and the choice probe's accuracy after projecting that direction out."

**Status: not available.** The condition is not met. No `.npy`, `.npz`, `.pt`, `.pth`, `.safetensors`
or `.pkl` exists anywhere in the repository (`S0` search, `REPO_MAP.md` §3), so there are no cached
activations and no saved probe to take a cosine with. Reported as "not available" with the reason, per
CLAUDE.md rule 1. It becomes feasible after S2, which is where P8 requires artefacts to start being
saved.

---

## D-2026-09-21-03 — S1.4(a) not available as specified; nearest available substitute reported

**Plan text.** S1.4(a): "Correlation of the logged baseline probe score with n and with log n."

**Status: not available.** There is no logged baseline probe score. The only probe scores in the
repository are `mean_probe_activation` in `figure_12`/`figure_18`, which are (i) aggregated over the
whole reward grid rather than per-n, (ii) recorded only under steering, with no λ = 0 row anywhere
(`S0.D.lambda.n_zero_rows` = 0), and (iii) of contested provenance (`PROVENANCE.md` §4, Q3).

**Substituted.** `reports/S1_4.md` reports what the same data can support — the dependence of the
tracked score on λ and on the target, with both readings of its provenance stated — and marks the
correlation with n as blocked on S2.0. Nothing is presented as the quantity the plan asked for.

---

## D-2026-09-21-04 — S0 mis-stated the hyper-fair catch trials; corrected

**Where.** `reports/PHASE0_SUMMARY.md` §4.

**Before.** "…because the offer grid stops at **90** and the crossing never goes that high — so the
paper has **no hyper-fair catch trials at all**, and PAPER_AUDIT §3.3's observation is about the probe
stack's *calibration targets* (up to 100) rather than about realised rejections."

**After.** The sentence is withdrawn and replaced by a marked block pointing at `reports/S1_2.md`.

**Reason.** Two errors, both found by running S1.2 properly.

1. The trials exist. Offers of 50–90 are on the hosted grid (9 levels × 40 agents = **360 trials per
   condition**) and offers of 50–100 on the probe grid (11 levels × 40 = **440**). What the hosted
   stack lacks is hyper-fair *rejections*, not hyper-fair trials. Conflating the two was sloppy.
2. Realised hyper-fair rejections do occur, on the probe stack, and they are large. P(reject |
   offer ≥ 50) rises with the calibrated target to **0.232** [0.195, 0.274] on Llama layer 48,
   **0.268** [0.229, 0.312] on layer 50 and **0.400** [0.335, 0.469] on Qwen, all at target 60.
   PAPER_AUDIT §3.3 was therefore right about the realised behaviour, not merely about the
   calibration targets, and my S0 remark diminished a finding that the logs support.

**Data unchanged.** `S0.A.ultimatum.pReject_hyperfair.hosted.*` = 0 is correct and stands; the error
was in what I inferred from it.

---

## D-2026-09-21-05 — `GATE_S0_RESPONSE.md` signed; `FRIDAY_PLAN.md` supersedes §7

**Instruction.** An author signed `GATE_S0_RESPONSE.md` on 21 Sept 2026 (`CONFIRMED BY: shreyas`) and
added `FRIDAY_PLAN.md`, which replaces §7 of that file until the deadline. The decisions taken are:
submit to ICLR on **25 Sept**, produce results on **`meta-llama/Llama-3.3-70B-Instruct`**, use
`/orcd/data/gabrieli/001/guna23` for storage, and pre-approve the ≈145 GB download plus **40 GPU-hours**
across G2–G5.

**What is now in force.** All of `GATE_S0_RESPONSE.md` except §7, plus `FRIDAY_PLAN.md`. This
supersedes D-2026-09-21-00, under which only P2–P5 and P10 applied. In particular P1 (task S2.0), P6–P9,
P11 and §4–§6 are now live, and `CLAUDE.md` still outranks all of it.

**Not yet done, and tracked:** the §4 corrections to `PAPER_AUDIT.md`, the §5 additions to `CLAUDE.md`
(rules 13–15), and P7's revision of A10. They are queued behind the Friday ordering, which puts
verification first.

**Sequence.** The authors directed: V3 first, report before the download; then finish the P12/P13
revision (V0); then continue down `FRIDAY_PLAN.md`.

---

## D-2026-09-21-06 — V3 run before the download; stop condition not triggered

**Why.** `FRIDAY_PLAN.md` V3 makes the download conditional: if the legacy probe runs name
`Llama-3.1-70B-Instruct`, stop, because the paper would then misstate the model for every probe
experiment and G2 would belong on the 3.1 checkpoint already on the share.

**Result: not triggered** (`MANIFEST.csv:V3.stop_condition.legacy_probe_names_3_1_70B` = false).
All four stacks name `meta-llama/Llama-3.3-70B-Instruct`; `Llama-3.1-70B-Instruct` appears in no file
and at no commit on any branch. The repository's only `Llama-3.1` strings are an SAE **filename**
helper for the 8B open SAE, which was never run. Full table in `reports/V3_model_ids.md`.

**Also settled from the logs, as §1 asked:** the Qwen arm is **`Qwen/Qwen2-7B-Instruct`**
(`Probes/config.py:34`), which matches the paper. `Qwen2.5-7B-Instruct` on the share is a different
model and is not substituted.

**Recorded as a limitation, not a deviation:** the probe run records carry `ModelConfig.name`, a
display string, not `hf_id`, so for Stack C the checkpoint is attested by one line of configuration
rather than by the logs. Stacks A, B and D record the id itself.
