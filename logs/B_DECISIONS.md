# B_DECISIONS.md

Track B decisions and their reasons. The shared `logs/DECISIONS.md` belongs to the Friday session and
is not edited from this worktree (author instruction, 22 Sept); entries that would have gone there are
recorded here and numbered `BD<n>` so the two sequences can never collide on a merge.

**BD1. The "60" in the amendment's 400 GPU-hour cap was Track B's budget.** The Friday session's D38
recorded that the cap "replaces the earlier 40 and 60" while only 40 had ever been communicated there.
The 60 was communicated to *this* session, as Track B's own allowance, alongside `--nice=1000` and a
one-job-at-a-time restriction, with the Friday session holding GPU priority. Neither session could see
the other's figure, which is why the sum looked unattributed. Confirmed by the authors on 22 Sept: the
400 is **shared across both sessions**, not 400 each, and is evaluated on `sacct` totals. Track B's
one-job-at-a-time restriction and its `--nice=1000` default are superseded by amendment items 2 and 3;
`--nice=10000` now marks work deferred past the cutoff, not Track B work as such.

**BD2. B3.2's LoRA anchors are blocked on `peft`, and the 4-bit fallback is unverified, not broken.**
Confirmed from this worktree: `peft` is absent (`torch` 2.5.1+cu121, `transformers` 4.50.3,
`accelerate` 1.10.0 present), so no LoRA anchor can be trained until it is installed. This matches the
Friday session's D40. The intended fallback for the 70B — 4-bit base weights if bf16 on 2 GPUs does not
fit — needs `bitsandbytes`, installed at 0.43.2 but printing "compiled without GPU support" on import.
**That warning is not evidence of a bad build**: it was observed on a login node with no GPU at all
(`nvidia-smi` absent, `torch.cuda.is_available()` false), where the message is expected. Whether 4-bit
works is an open question to settle on a GPU node before the fallback is relied on. B3.2 is not
schedulable until `peft` is installed and that import check has run. B1 and B2 are unaffected: both are
CPU-only and need neither library.

**BD3. Track B's write scope, job prefix and artefact location.** Author instruction, 22 Sept. This
worktree writes only under `cv_bench/tasks/`, `cv_bench/estimator/`, `cv_bench/anchors/`, `results/B/`,
`reports/B_*` and these two logs. `CLAUDE.md`, `FRIDAY_PLAN.md`, `ICLR_PLAN.md`, `GATE_S0_RESPONSE.md`
and the shared logs are read-only here and arrive by merging `iclr-extension`, never by editing. An
earlier commit in this worktree (`1876057`) appended two entries to the shared `logs/DECISIONS.md`
before this rule existed; that file has been restored byte-for-byte to its `iclr-extension` content and
the entries now live here as BD1 and BD2. Slurm job names start with `cvb_`, so the shared 400
GPU-hour cap can be evaluated on `sacct` totals for that prefix without either session needing to see
the other's registry — which is the gap the Friday session's `SCHEDULE.md` §6 left open. Large
artefacts go to `/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB/`, beside the Friday session's
`g2_lambda0/` outputs, and never to the pool filesystem, which stands at 99.4% of quota.

**BD4. Every prompt goes through the chat template, and the generators cannot emit a raw prompt by
accident.** Author instruction, 22 Sept, on the evidence in `reports/G2_legacy_format.md`: the legacy
raw-string format yields no answer on **88.3%** of trials (989 of 1,120), which is why the committed
legacy path cannot reproduce the published 0%-unparseable data. Track B therefore never uses the raw
format. This is enforced rather than documented: `cv_bench/tasks/core.py` renders every prompt through
the tokenizer's `apply_chat_template`, and the one function that renders without it,
`render_raw_unsafe`, raises unless it is passed `acknowledge_no_chat_template=True`, which nothing in
Track B passes. It exists only so that a future audit can reproduce the legacy format deliberately and
label it, in the way G2's `legacy` arm does. `readout.TrialSpec` already defaults to
`use_chat_template=True`, so the shared readout agrees with this by default.

**BD5. Experimental conditions are replicated across splits; only reward levels are divided.**
`ICLR_PLAN.md` B1 assigns splits "by reward-level index mod 4 within each cell". Applied literally to
every family, that rule silently destroys two parts of the design, both caught by the B1 tests rather
than by reading:
- **The mini-ultimatum lost a condition.** Its four alternatives — (5,5), (2,8), (10,0) and *no
  alternative* — are conditions, not reward levels. Under mod-4 each landed in exactly one split, and
  the no-alternative condition landed in `test`, so it was generated **zero times** and the contrast
  the design exists to measure was absent from the dataset. Conditions are now replicated in full in
  every split.
- **The transfer battery was cut to a quarter.** Holt-Laury's switching point needs all ten decisions;
  splitting by item index left **three of ten** in `disc` and no switching point to find. Each
  instrument is now emitted whole within each requested split. The battery is still barred from `sel`
  and `cal` (A11), enforced by `TransferMisuse`.
The rule is therefore read as applying to *reward levels within a cell* — the sure-gain and sure-loss
x grids, the mixed ratio, the paired spread, the responder and dictator offers — and not to design
conditions or to the rungs of a standard instrument. Splitting a condition across splits also confounds
condition with split, which would bias any comparison between them.

**BD6. The low end of the plan's reward grid is statewise dominated, and the cells are kept.** The
grid runs from 0.3x to 5x the risk-neutral point s/p, so whenever p >= 0.3 the lowest levels put the
gamble's best outcome below the sure amount: at p = 0.5, s = 20 the grid starts at x = 12, and a 50%
chance of $12 cannot beat $20 for sure. 104 of the 726 risk trials are dominated this way. They are
kept, because a dominated level is a legitimate extreme reward level that pins the floor of the choice
curve, but every one is flagged (`Trial.dominant`) so that the dominated-choice rate counts them and
the B2 estimator can weight or drop them deliberately. In a gain frame the sure option dominates; in a
loss frame the gamble does, since it risks losing at most x <= s. Dominance outside this low-end region,
or in the paired and mixed families, is a bug and is asserted against.

**BD7. The transfer battery is locked in the runner, not just documented.** Author amendment, 22 Sept,
extending BD5. The battery was already barred from `sel` and `cal` (`TransferMisuse`); it is now also
**evaluation-only**. `role` is a *required* argument of every transfer generator, with no default, so a
caller cannot materialise the battery without saying who is about to look at it. Only `unmodified` and
`anchor` are admitted until the predictions B9 derives from the choice-based fit are committed at
`results/B/b9_transfer_predictions.json`; every other role raises `TransferLocked`. Every access,
granted or refused, is appended to `logs/B_TRANSFER_ACCESS.log`. The check requires the predictions to
be **committed in HEAD**, not merely present in the working tree, because a file that can still be
edited after the battery is seen does not constrain anything — which is the whole point of deriving
predictions "before looking".

**BD8. `peft` was already installed by the Friday session; Track B installs nothing.** Amendment item 6
asked to check first. `peft==0.13.2` is present and pinned in `env/requirements-lock.txt`, installed
22 Sept under the S2.1-fix amendment and recorded there as D45. BD2 is therefore closed: B3.2 is no
longer blocked on the dependency. The 70B LoRA will train in **bf16 on 4 GPUs** per the amendment, with
4-bit used only if four GPUs cannot be obtained and recorded as a deviation. `bitsandbytes` remains
compiled without GPU support, which the lock file also notes, so the 4-bit fallback would need that
fixed first — one more reason the bf16 path is the one to take.

**BD9. The dominated-trial policy for B2, recorded before any model data is fitted.** Author amendment
item 4. Default: the flagged dominated trials (BD6) feed **D1 only** — the dominance-violation rate —
and are **excluded from the parametric likelihood**. Sensitivity analysis: include them with a free
lapse parameter in the choice rule. The recovery study decides which recovers parameters better, and
this entry fixes the comparison *before* any model data exists, so the choice cannot be made by
looking at which answer suits the paper. Both policies are implemented in
`cv_bench/estimator/fit.py` as `dominated_policy in {"exclude", "lapse"}`.

**BD10. Lambda is unidentified outside mixed frames, predicted analytically before fitting.** Under the
contextual-utility normalisation the plan mandates, the loss-aversion parameter cancels on any trial
whose outcomes all share a sign: every value scales by lambda, the utility range scales by lambda, and
the normalised difference is unchanged. Measured on the B1 grid, the largest change in z from moving
lambda by its full minimum detectable change (0.30) is **exactly 0.000000 on all 245 sure-gain and all
245 sure-loss trials**, 0.105 on the 36 mixed trials and 0.044 on the 68 paired trials. So lambda is
identified on 104 of 726 risk trials and weakly at that. The prediction recorded here, before the
recovery study runs, is that **lambda's RMSE will fail Gate B2's "at most half the minimum detectable
change" (0.15)** while alpha and gamma pass. Under Gate B2 the response to a failure is to change the
grid and never the thresholds, so the remedy would be more mixed-frame trials, not a looser bound.
This is written down now so that the grid change, if it happens, is visibly a response to a
pre-stated structural fact rather than to an unwelcome number.

**BD11. Template effects are drawn once and shared between conditions, not redrawn.** Found while
testing the estimator, and it changed the answer. The recovery study's template-level noise is the
plan's "SD of z across templates": it is a property of the *instruction template*, so a real experiment
that runs the baseline and the intervention on the same prompts sees the same offset in both, and it
cancels in the comparison. The first implementation redrew it per condition. The difference between two
independent draws then entered every trial as a **constant shift** — which is exactly the signature of
an action bias — so a genuine preference shift at the minimum detectable change was being attributed to
action. The symptom was seed dependence that should not have existed: on one seed `pref_alpha` gave a
preference share of 0.996, on another an action share of 0.89. With the draw shared, the true model
wins in both. Only the numerical-noise component is redrawn per condition, which is correct: it stands
for batch-composition non-determinism, which genuinely differs between runs.

**BD12. "The action model is rejected" is operationalised as a cluster-bootstrap probability.** The
decision rule requires preference share >= 0.8 **and** the action model rejected. The plan does not say
how to reject it, so Track B reads it as: the preference model beats the action model on held-out
reward levels in at least 95% of paired cluster-bootstrap draws, clustered on reward level x template
as the plan specifies for that comparison, with the Vuong statistic reported beside it. The 0.95 is a
threshold and therefore an **AUTHOR DECISION** frozen at B6; it is flagged here rather than quietly
chosen, and `reports/B_B2.md` reports the rule's behaviour if it were dropped to 0.90.

**BD13. Label sets are chosen per family and domain, not applied to everything.** A bug, caught while
sampling prompts for the fp32 job and visible the moment a prompt was printed. `expand_formats`
defaulted to *every* label set in `LABEL_SETS`, so after the social pairs were added it dressed lottery
trials in Reject/Accept and Yes/No:

    Reject: $20 for sure
    Accept: a 10% chance of $60 and otherwise nothing

Three-quarters of the risk grid carried a label pair that does not describe the choice, and the
label-bias term — which contrasts "legacy" against everything else — was being computed against that.
`DOMAIN_LABEL_SETS` existed but was never wired in. Now `label_sets_for` picks by family first and
domain second: risk and transfer take legacy/neutral, social takes accept-reject/neutral, and the
accept-bias control takes accept-reject/yes-no, since its items are yes/no questions with a correct
answer. The expanded grid falls from 29,408 rows to **14,704**, which is the correct size; the earlier
B1 dataset and the first two B2 recovery submissions were built on the wrong grid and are superseded,
not reported. A test now asserts that no risk prompt can contain "Reject:" or "Accept:".

**BD14. Three estimator corrections, each found by the recovery study failing for the wrong reason.**
The first run of the study failed Gate B2 in all 18 configurations with *every* agent, preference
shifts included, classified as not preference-like. A rule that rejects everything has perfect
specificity for free and is not a rule, so the failure was diagnosed rather than reported:

- **The model had no template term.** B1 gives each split two instruction templates, and the plan asks
  B2 to simulate template-level variation of 0.5 to 2 logits. With no per-template intercept that
  variation is unmodelled misfit, and the comparison between nested models is decided by which one best
  absorbs it rather than by the effect under study. Adding intercepts, estimated on the baseline
  condition and held fixed across the intervention models, raised the preference share for a true alpha
  shift from 0.265 to 0.591. The intercepts are not separately identified — templates are nested within
  splits, so a template effect is confounded with that split's reward levels — and only differences
  matter; the first is pinned at zero.
- **The fit used binary choices when the instrument returns z.** The plan's own diagnostics are written
  on z and dz, and the logit readout returns z directly; fitting one Bernoulli draw per row discards
  most of the measurement. With an observation mode that fits z under Gaussian numerical noise, alpha's
  RMSE fell from 0.055 to **0.0054** and gamma's to **0.0032**, against a Gate B2 limit of 0.05, and the
  preference share for a true shift went to 1.000 with the action model rejected in every draw. Both
  modes are kept: `choice` is what sampled free-text generation gives, `logit` what the readout gives.
- **D5's transfer ratio divided two squashed probability differences.** A change in choice probability
  is a few points wide, so the ratio of two of them swung outside the pre-registered band on noise alone
  and failed a genuine preference shift about half the time. It is now taken on mean dz, like the
  plan's other diagnostics, and a zero effect in both formats is scored as perfect transfer rather than
  as a ratio of 0/0.

None of this touched a threshold. Plan v4's numbers are held in one place in `decision.py` and asserted
by a test.

**BD15. What Gate B2 still fails on, and the arithmetic of the remedy.** Two failures survive, both
measured rather than argued, and both with the remedy the gate prescribes — change the grid, never the
thresholds.

- **Lambda, as predicted in BD10.** RMSE around 0.25 against a limit of 0.15, because lambda cancels
  exactly outside mixed frames and only 36 of 726 risk trials are mixed. The remedy is a denser
  mixed-frame grid, not a wider bound.
- **D5's transfer band is beyond the grid's power.** At the minimum detectable change the mean shift is
  **+0.0109 logits**, while the numerical-noise floor on a format subset's mean is **0.0023** — a
  signal-to-noise of 4.7 on each subset, so their *ratio* carries about 24% error against a band of
  +/-25%. Holding the band at 0.8-1.25 therefore needs roughly **nine times** the rows per subset, or
  about nine independent reads per prompt to average the numerical noise down. That is a grid decision
  and a budget decision for the authors: nine reads of the current grid is a real cost, and the
  alternative — widening the band — is an AUTHOR DECISION frozen at B6 and is not Track B's to make.

**BD16. B2-cal: the agents are calibrated to the model before any power number is believed.** Author
item 1. The B2 agents were scaled without a model, so every power number the recovery study reported
is a statement about an assumed choice function rather than about this one. The Friday session's
diagnostics put the unsteered z near **-9.7** at one prompt with a crossing near **n = 242**, which is
far steeper than the agents' TAU0 = 0.25 implies; if that holds, an alpha shift of 0.10 is worth
tenths of a logit near indifference rather than the **0.0109** the uncalibrated agents gave, and both
Gate B2 failures may simply dissolve. `cv_bench/estimator/b2_cal.py` reads the unmodified 70B
unbatched on the calibration split and returns theta0, the temperature, the template-level noise, the
numerical-noise floor **measured in that same run**, and a test of whether the slope of z against
log x is constant across sure amounts. The 18-configuration study is then rerun at the fitted scale
and noise, reporting sensitivity per criterion and jointly. **No conclusion from the current study is
carried forward until this lands.**

**BD17. B2-cal runs on legacy labels only, and carries the readout-versus-generation check.** Author
item 7. The Friday session found that under neutral A/B labels the unsteered readout ignores the
payoff, so the neutral half would calibrate against a readout that is not measuring the choice. The
stem is `Answer:`, which their D47 measured at valid mass **1.0000** on both games with the legacy
labels. The readout-versus-free-generation comparison is part of the same job and the same report:
greedy decoding, first stated option wins, and an output that states neither is counted rather than
dropped. `iclr-extension` is merged again when the label work is committed.

**BD18. BD12's 0.95 bootstrap threshold is approved, with Vuong beside it.** Author item 4. Both are
reported together and both are frozen in `PREREG.md`. This closes BD12's open flag.

**BD19. The D5 band stays at 0.8-1.25.** Author item 5. BD15's arithmetic said the band needs about
nine times the rows at the uncalibrated scale; the band does not move to accommodate that. Power is
revisited only after BD16, because the effect size that arithmetic divides by is exactly the thing
B2-cal is about to replace. If it is still short at the calibrated scale, the remedy is more rows or
repeated reads.

**BD20. A failed Gate B2 stops evaluation, not construction.** Author item 6. B3.1 and B3.2 are built
in parallel with the B2 rework, but **no anchor is scored with the decision rule until Gate B2
passes**. B3.1 computes and saves the gradient direction at layers 48 and 50; the gradient is taken
with respect to the output of `model.model.layers[L]`, because that is exactly the tensor
`steer.SteeringHook` adds to — a gradient taken anywhere else would not be the direction a dose
actually moves. B3.2 waits on theta0 and the temperature from B2-cal, dry-runs on the 8B, and trains
the 70B in bf16 on 4 GPUs with the cloning check. `b0_numerics` is re-run against the real gradient
anchor once it exists, replacing the labelled random stand-in.

**BD21. Every long job now checkpoints and resumes, and the resume is tested by interrupting it.**
Amendment item 4 required it and the first implementation only wrote heartbeats. Slurm jobs already
survive a dropped connection — they run on a compute node with no tie to the submitting shell — but
they do not survive preemption, and `ou_bcs_low` is the low-priority partition where preemption is
expected. `cv_bench/estimator/checkpoint.py` adds an append-only on-disk array that a loop resumes
from, flushed every chunk and written atomically through a temporary file and a rename, so a job
killed mid-flush leaves the previous good checkpoint rather than a truncated one. A checkpoint carries
a fingerprint of the item list it belongs to and is refused if the prompts, the shape or the run
differ, because silently resuming into another run's partial results is worse than starting over.
`b2_cal`, `gradient` and `numerics_fp32` resume within a pass; `numerics_fp32` also skips a dtype
stage that already finished, so a requeue after fp32 does not pay 346 seconds to load it again; and a
`recovery` array task whose output file exists returns immediately. Eight tests in
`cv_bench/tests/test_checkpoint.py` cover resuming mid-pass, losing at most one chunk, refusing a
foreign or corrupt checkpoint, and a heartbeat that cannot take the job down.
