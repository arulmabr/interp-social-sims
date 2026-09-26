# B_DEVIATIONS.md

Track B deviations. The shared `logs/DEVIATIONS.md` belongs to the Friday session and is not edited
from this worktree; anything Track B departs from is recorded here instead.

Format: what was planned, what was done, why, and the before and after. A deviation is a *technical*
change only — `CLAUDE.md` rule 4 still forbids changing seeds, prompts, doses, thresholds, exclusions
or metrics because a result looks unhelpful.

*No deviations recorded yet.*

**Gate B2's text changes, twice, before any model data was fitted.** Both are author decisions of
22 Sept, recorded here because they alter the criteria `ICLR_PLAN.md` states for a gate, and both were
made while the only data in existence was synthetic. `CLAUDE.md` rule 4 is not in play: no result was
rerun, and no threshold was relaxed to accommodate an outcome.

**1. Lambda becomes a secondary parameter with its own gate.**
- *Planned:* Gate B2 passes when "parameter RMSE is at most half of each minimum detectable change",
  which covers alpha, gamma and lambda together, lambda's bar being 0.15.
- *Now:* Gate B2 is evaluated on **alpha and gamma only**. The RMSE bars and the 95% classification
  rule are unchanged for both. Lambda **keeps its 0.15 bar** and moves to its own gate, tested once a
  denser mixed-frame grid passes on synthetic agents; the smallest such grid is to be found by
  simulation.
- *Why:* the paper's tasks are in the gain domain and the first preference anchor of B3.2 shifts
  alpha, so lambda is not on the critical path for anything the Sept 25 paper claims. It is also not
  identified on the current grid at all: under the mandated contextual-utility normalisation lambda
  cancels exactly wherever outcomes share a sign, giving a largest change in z of **0.000000** across
  all 245 sure-gain and all 245 sure-loss trials (BD10, recorded before fitting). Holding the whole
  gate hostage to a parameter the grid cannot see would block alpha and gamma, which it can.
- *Before / after:* Gate B2 failed on lambda RMSE 0.416 against 0.15 in all 18 configurations. Under
  the amended text those configurations are judged on alpha (0.0091) and gamma (0.0044) against 0.05.
  Lambda's own gate remains unmet and unreported as passed.

**2. The misspecified agents become bases, not interventions.**
- *Planned:* mean-variance utility and the arbitrary monotone curve sat beside action, belief, noise
  and format as agent types, and Gate B2 required the decision rule to handle them "on the model-free
  layer" — a phrase the plan did not define.
- *Now:* they are **base agents**. Base in {CPT, mean-variance, monotone} is crossed with intervention
  in {preference shift within that family, action bias, belief distortion, noise, format}. On the two
  misspecified bases the **model-free layer** must classify the interventions correctly at **>= 95%**.
  The parametric layer is permitted to be wrong there, and how often it contradicts the model-free
  verdict with a share above 0.8 is reported rather than gated. **D1 is scored as a change from that
  base agent's own baseline**, not from the CPT baseline.
- *Why:* a mean-variance agent is not an intervention that looks odd; it is a different model of the
  subject, on which the same five interventions can be applied. Asking whether it "looks like a
  preference shift" was the wrong question. The right one is whether the diagnostics still work when
  the parametric model is wrong about the subject — which is what the two agents were put in the plan
  for. Track B had flagged the ambiguity rather than settling it (BD14), and this settles it.
- *Before / after:* under the old reading the two agents were scored by whether they looked clean, and
  mean-variance failed because it genuinely violates stochastic dominance, so D1 flagged it correctly
  and the gate counted that as a failure. Under the amended text that same behaviour is scored against
  the mean-variance baseline, where it is not an anomaly at all.

**B1 rebuilt with the social framing defect unfixed.** Author reply "audit ok", 22 Sept, after
`reports/B_PROMPT_AUDIT.md` flagged it (BD31).
- *Planned:* the social families state their game, as `Probes/tasks/prompts.py` does for the ultimatum.
- *Done:* they render as bare payoff pairs — `Reject: nothing` / `Accept: 90 tokens for sure` — with no
  proposer, no pie and no "both of you get 0".
- *Why it is acceptable here:* nothing in the current chain reads them. B2-cal, B3.1, B3.2 and the B2
  recovery study are risk-domain only. The defect is confined to the social families and to any future
  result that uses them.
- *Standing caveat:* **no social number from this build may be reported as a social preference.** With
  the framing absent, rejecting a low offer is an arithmetic error rather than inequity aversion, and
  the mini-ultimatum's alternatives never reach the model. Free-text cells carry the same caveat: they
  are scored by the first-token readout, not by sequence log-probability, so they are a second
  multiple-choice arm.

**B3.2 70B LoRA: 2 GPUs instead of the instructed 4, and a shortened walltime.** 22 Sept, technical
(scheduling capacity), no author involvement in the numbers.
- *Instructed:* train the 70B LoRA anchor in bf16 on **4 GPUs**, one job, no partition races.
- *Done:* submitted on **2x A100-80GB** (`--gres=gpu:a100:2 --mem=48G`), first at `--time=10:00:00`,
  then `--time=04:00:00` after the longer request proved unbackfillable.
- *Why:* the QOS cap leaves 2 GPUs free once Friday's `cvb_g5b` holds 2, and the measurement says 2 is
  enough: on node2102 the bf16 weights (141 GB) loaded into 160 GB of HBM with no OOM --
  `loaded in 323s; 207.1M trainable LoRA params; 4bit=False`. Waiting for a 4-GPU window costs more
  than the run. **No fallback to 4-bit was taken**; the anchor is bf16 as specified.
- *Effect on the numbers:* none expected. Per-device batch and `--accum 8` are unchanged, so the
  optimiser sees the same effective batch; only wall-clock differs.
- *Cheapest to reverse:* resubmit at `--gres=gpu:a100:4` if a window opens before the cutoff.

**B3.2 70B LoRA: first attempt lost to preemption after ~11 minutes.** 22 Sept, technical.
- Job 23460192 on `mit_preemptable`/node2102 reached `reference step 25/500 loss 0.5992`, then
  `JOB 23460192 ON node2102 CANCELLED AT 2026-09-22T02:39:11 DUE TO PREEMPTION` (in the job's `.err`).
- The checkpoint survived and was verified before resubmission: **resumes from step 25, 3360 adapter
  tensors**. Nothing was retrained from scratch and no seed, prompt, dose, threshold or metric changed
  -- this is CLAUDE.md rule 4's technical-reason case only.
- Step rate, measured from the job's own file timestamps rather than estimated: the `.out` file was
  created 02:31:02, `loaded in 323s` puts the first training step at 02:36:25, and the
  `reference step 25/500` line was written at 02:38:07 -- **102 s for 25 steps = 4.08 s/step**. A cold
  reload costs 323-372 s, i.e. ~80 steps' worth, so an 11-minute mean uptime makes `mit_preemptable`
  net-negative for this job. Hence the move off it. (An earlier note in this file put the rate at
  ~13 s/step; that was arithmetic off total elapsed, which wrongly assumed preemption landed on step 25
  rather than 64 s past it. 4.08 s/step is the measured figure and supersedes it.)
- *Resolution:* no preemption was needed. Job 23460913 was placed by the scheduler on `ou_bcs_normal`
  node3910, which had 2 idle a100s, and started at 2026-09-22T02:52 resuming from step 25. The four
  `ou_bcs_low` array tasks that `sbatch --test-only` had listed as preemptable were left running.

**B3.3 pass 1: the first dose solve matched 2 of 12 directions and its read is void.** 22 Sept,
technical (my bug), jobs 23502634 / 23502635.
- *Planned:* every direction dosed to the bias adapter's legacy switching-point shift (-91.14 tokens,
  from 210.08 unmodified to 118.94), so the comparison is at matched behaviour.
- *What happened:* `switching_points` returns nothing when P(risky) never crosses 0.5 on the ramp, and
  the solver collapsed that to NaN and treated NaN as "dose too weak", so it walked the scale UP.
  A ramp with no crossing saturates for **opposite** reasons -- always-gamble or always-sure -- and on
  a too-strong dose the correct move is down. `readout_anchor_L50` went 2.0 -> 3.94 and never looked
  below 2.0. **Only 2 of 12 directions matched to within 3%.**
- *Consequence:* the read stage ran anyway, at the fallback scale for 10 of 12 directions, so
  `b33_probe_vs_anchors/z_selection.npz` is **not a matched-behaviour comparison and is not analysed**.
  It is kept, unanalysed, as the record.
- *Fix:* `measure()` now reports which way the ramp saturated; the solver probes the SIGN first (some
  directions move the switching point the wrong way and need sign -1, which the old solver could not
  express at all), then walks a ladder to bracket, then bisects with saturation pulling the bracket
  down rather than up. Regression test in `cv_bench/tests/test_steer.py`.
- *Re-run in a NEW directory* `b33_probe_vs_anchors_v2`. Only `ckpt_dose_unmodified` and
  `ckpt_dose_bias` are carried over, because they are dose-independent. The `sel_*` checkpoints are
  deliberately NOT carried over: their tags and item list are unchanged, so a resumed read would have
  silently returned the old z at the old wrong doses -- the BD37 failure mode.
- *No threshold, prompt, seed or metric changed.*

**GATE B3's statistic changes from the mean of dz to the estimator itself.** Author decision, 22 Sept,
recorded BEFORE any Pass 1 probe-comparison result was read (their item 5).
- *Planned:* `ICLR_PLAN.md:186` is evaluated on the anchor contrast, and Track B implemented that
  contrast as the **mean of dz** between the shifted and reference adapters.
- *Amended to:* fit the parametric model to each adapter's z and require **(a)** the fitted alpha
  difference to be within one MDC of the planted shift, and **(b)** the contrast to be classified
  preference-like under the decision rule -- preference share >= 0.8 and the action model rejected at
  0.95 on the cluster bootstrap (BD12). The slope of measured-on-planted contrast with its intercept,
  and the mean dz, are reported beside it and decide nothing.
- *Why, in the authors' words:* the planted change is a **curvature** shift. Alpha moves, so its effect
  on z varies with the payoff and changes sign across it; the mean of dz therefore does not measure it,
  and **a faithful adapter could show mean dz near zero**. The statistic was wrong for the quantity,
  independently of what it returned.
- *Not outcome-driven, and the ordering proves it:* the decision was taken on the structural argument
  and committed before Pass 1 was read. The mean-dz numbers it supersedes are kept in `MANIFEST_B.csv`
  under `B3.2.70b.*.contrast.preference.estimate` and in BD50, not deleted.
- *Scope:* the same statistic applies to **every contrast from here on, including the probe's**.

**The anchor is the independently trained full-row pair; the paired adapter becomes a negative control.**
Author decision, 22 Sept.
- The paired preference adapter carries a constant offset of **-0.045 in z** relative to the reference
  (BD50), which is an **action component acquired during retraining**. That makes it impure as a
  preference-like anchor however well it clones (r 0.9968, slope 0.9947).
- It is retained as a **documented failure mode and negative control**: an adapter that clones better
  than any other in this project and is nonetheless the wrong thing to anchor on.
- The standing anchor is `b3_lora_70b_fullrows`, independently trained, n = 1016.

**A second preference anchor at 3x the MDC.** Author decision, 22 Sept.
- Trained independently with the same recipe, so the anchor set **brackets a range** instead of sitting
  at the detection limit. **The MDC itself is unchanged** -- this adds an anchor, it does not move a
  threshold.
- Scheduled after Pass 1 of the probe comparison.

**Under-recovery is a property of the adapters, not an error term.** Author decision, 22 Sept.
- The adapters recover ~0.62 of the planted shift (slope 0.620 independent, 0.774 paired; BD50).
- Therefore the anchor's known value is the **achieved alpha difference measured on the selection
  split**, not the planted target. Downstream comparisons use the achieved value.

**B10.5 creativity weight-push anchor: rerun for memory, nothing else changed.**
- *What happened:* job 23973498 failed after 1m35s with a CUDA out-of-memory error during the
  first backward pass. The 70B weights occupy about 35 GB of each 44 GB card, and the backward
  pass over two full responses at once needs more than the remainder.
- *Fix:* gradient checkpointing enabled, so activations are recomputed instead of stored, and
  the response length cap lowered from 320 tokens to 192. Allocator set to expandable segments.
- *Unchanged:* the agent definition, the two constants and the rules that set them (BD59), the
  pair set, the seed, the step count, the learning rate and the loss. The measured unmodified
  readout is carried over: mean +0.0059, spread 0.2425, from which w0 +0.00412, detectable
  change 0.00150 and push 0.0428 were derived before the failure.
- *Not outcome driven:* no result had been produced when the job died.
