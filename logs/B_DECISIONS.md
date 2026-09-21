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
