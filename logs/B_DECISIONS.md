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

**BD22. The monotone base agent was indifferent on every trial, and it is one of the two agents the
plan relies on to test misspecification.** Found while matching the crossed zoo on effect size: three
of the five monotone cells could not reach the target effect at any parameter value in their search
range. The cause is a unit mismatch in the contextual-utility normalisation. The range was computed in
**amount units for every family except CPT**, but the monotone family's utility is a tanh bounded in
[-1, 1]; dividing a tanh-scale utility difference by a range in dollars crushed z by about two orders
of magnitude. Measured on 200 sure-gain trials, the monotone base had **z sd 0.0073 and a P(risky)
spread of 0.0105** — indifferent everywhere, so no intervention applied to it could be detected and
the agent tested nothing at all. The range is now measured in each family's own units
(`_to_utility_scale`): CPT's value function, mean-variance's amounts, monotone's tanh. The monotone
base now has **z sd 1.3389 and a P(risky) spread of 0.8716**, against CPT's 1.2663 and 0.7937. The
scalar and packed paths still agree to 0.00e+00 for all three bases. A test now asserts that no base
agent is flat, because a degenerate base passes every specificity check for free and would have made
the misspecification test look like it was working.

**BD23. The effect-size matching was the slowest thing in the study and did not need to be.**
`behavioural_effect` still used the readable scalar path at about 520 ms a call; the bisection calls it
roughly 1,600 times, so building the crossed zoo alone would have taken about 850 seconds inside every
one of the 18 array tasks. It now takes the packed path with the trials packed once, and the zoo builds
in **1 second**. No result changes: the two paths are asserted equal.

**BD24. The mean-variance base is mean minus b x standard deviation, not minus b x variance.** The
textbook mean-*variance* form is not scale-invariant: variance grows as the square of the stake while
the mean grows linearly, so at a constant penalty the same agent is nearly risk-neutral at $20 and
extreme at $500. Across B1's 25x stake range that gave z running to **-90.32 with an SD of 10.27**
against CPT's 1.69, and mean P(risky) 0.29 rather than about a half. Penalising the standard deviation
keeps both terms linear in the stake and makes `mv_b` dimensionless. At `mv_b = 0.35` the base now has
**z SD 1.744, range [-4.02, 3.67], P(risky) spread 0.958**, beside CPT's 1.691 / [-3.67, 3.67] / 0.950
and monotone's 1.847 / [-3.84, 3.84] / 0.958. All three bases are now plausible subjects on one scale,
and all 17 crossed cells match the target effect of 0.0176.

**BD25. On a mean-SD base a preference change is observationally an action bias, and this is
structural.** Gate B2's one remaining classification failure, and it survived the rescaling of BD24, so
it is not a scaling artefact. Measured on the sure-gain grid, shifting the mean-SD risk penalty gives a
dz with **mean -0.2611 and SD 0.0753**, a ratio of **0.29**: it varies with p (from -0.17 at p = 0.1 to
-0.32 at p = 0.5, tracking sqrt(p(1-p))) but hardly at all with the reward level (-0.19 to -0.27 across
three decades of x). A CPT alpha shift on the same grid has a ratio of **0.99** and changes sign across
x, from -0.037 at x about 10 to +0.096 at x about 100. The reason is exact: after the contextual
normalisation the mean-SD risk term is the gamble's standard deviation divided by the outcome range,
which for a two-outcome gamble is sqrt(p(1-p)) and carries no dependence on the reward level at all. A
shift in it is therefore close to a constant shift in z, which is the model-free signature of an action
bias. **The model-free separation of preference from action is model-dependent**: it works when the
subject reshapes the choice curve, as a CPT agent does, and fails when the subject's risk attitude
enters as a level-independent offset. That is exactly the question the two misspecified bases were put
in the plan to answer, and the answer is negative and worth reporting rather than tuning away. It is
reported, not fixed: the fix would be to add a regressor built from the mean-SD form, which is to tell
the model-free layer the answer.

**BD26. No mixed-frame grid in the swept family identifies lambda.** Author item 2 asked for the
smallest denser mixed-frame grid that passes. There is none in this family. Lambda's RMSE **plateaus at
about 0.26** against its 0.15 bar and does not fall with density: 576 mixed rows give 0.3216, 2,304
give 0.2654, 3,072 give 0.2629, and 4,608 rows over eight loss levels still give 0.2663 — an eightfold
increase in mixed trials for no improvement. That is the signature of an identification limit, not a
sample-size one, so buying more mixed trials buys nothing. The sweep now also fits lambda with alpha
and gamma held at the baseline fit, to separate "lambda is invisible" from "lambda is confounded with
the curvature it is estimated beside"; if the held arm passes where the joint arm fails, the remedy is
to pin alpha on the gain frame — which is what the plan already does for out-of-frame prediction —
rather than to enlarge the grid.

**BD27. The readout gradient at layers 48 and 50 is mostly a position direction, not a preference
direction.** B3.1 on Llama-3.3-70B, calibration-split core prompts, legacy labels, gradient taken with
respect to the output of `model.model.layers[L]` — the tensor `SteeringHook` adds to. The two option
orders give **strongly anti-aligned** gradients:

| layer | \|g1\| | \|g2\| | \|g1+g2\| | \|g1-g2\| | cos(g1,g2) | diff/sum |
|---|---|---|---|---|---|---|
| 48 | 13.74 | 8.82 | **8.32** | **21.54** | **-0.8140** | 2.59 |
| 50 | 13.00 | 8.40 | **7.73** | **20.48** | **-0.8232** | 2.65 |

Within a single order the per-prompt gradients are highly coherent (0.927-0.941), so each of g1 and g2
is a real direction rather than an average of noise. But swapping which option is presented first very
nearly reverses it. Decomposed as the amendment asks: the **order-invariant part g1 + g2 has norm 8.3
at layer 48, while the position part g1 - g2 has norm 21.5** — the position component is about **2.6
times larger** than the part that survives a change of presentation order.

This is the concern A6 raises, measured: "features chosen by their effect on the risky-minus-safe logit
are aligned with the readout gradient, which the plan itself defines as action-like". On this model the
readout gradient is not merely *somewhat* action-like, it is **predominantly** a position signal.

Two consequences, neither of them Track B's to settle alone:

- **For Track B**, the B3.1 anchor is `legacy_sum` (g1 + g2), which is the right choice and also a much
  weaker direction than the raw gradient. `legacy_diff` joins the controls as a position-bias direction
  by construction, and it is the larger of the two.
- **For the Friday session's G4b**, the instruction was to load `legacy_one_format`. That version is
  order-0 only, so by construction it carries the position component — steering along it would move
  position bias at least as much as preference. The per-order files and the sum are saved beside it so
  the choice can be made deliberately; this is flagged rather than decided here.

Saved under `$TRACKB_SHARE/trackB/b3_gradient/` with sha256 per file in `b3_gradient.json`, plus a
`how_to_load` block naming the tensor the gradient is taken against.

**BD28. Option order was relabelling the options, not reordering them. BD27 is withdrawn.** Found by
running the sanity check that should have preceded BD27: are the readout's two labels the same in both
option orders? They were not. `body_text` paired each label with a *position* rather than with its
lottery, so every order-1 legacy prompt read

    Safe Option: a 25% chance of $37 and otherwise nothing
    Risky Option: $20 for sure

— the gamble announced as "Safe Option" and the sure amount as "Risky Option". That is a relabelling,
not an order manipulation. z itself stayed content-anchored, so nothing was inverted, but half of every
legacy comparison was asking a different question.

**This invalidates BD27's conclusion.** cos(g1, g2) = -0.814 was reported as evidence that the readout
gradient is "predominantly a position direction". The far simpler explanation is the bug: under order 0
the word "Risky Option" names the gamble, under order 1 the word "Safe Option" does, so a model with any
prior toward the token "Safe" has its z-raising direction flipped by the relabelling. The measurement
cannot separate that from a real position effect, so **the claim is withdrawn, not merely qualified.**
Whether the gradient is position-dominated is now an open question, to be re-measured on corrected
prompts.

The fix binds each label to its lottery and lets the order reorder the two lines. `safe_label` and
`risky_label` no longer depend on `option_order`. Two tests lock it: the label-lottery pairing must be
identical across orders, and the two orders must differ only in the order of the lines.

**What the bug touched, and what has to be redone.** Only label sets whose labels carry meaning are
affected; "Option A"/"Option B" are arbitrary, so the neutral set was always fine.
- `B1` dataset — rebuild (half the legacy rows carried contradictory prompts).
- `B2` recovery study — rerun; the label-bias and position-bias terms were confounded with each other.
- `B2-cal` — rerun; the theta0 fit, the template-noise estimate and the slope table all used 872 rows of
  which half were order-1 legacy.
- `B3.1` gradient — rerun; this is where the bug produced a headline finding that was not real.
- `B3.2` LoRA — the 8B dry run was cancelled mid-flight; it was training on the contradictory prompts.
None of this was caught earlier because every test compared the code against itself: the label
properties agreed with `body_text` because both applied the same wrong rule. The check that found it
compared the *rendered prompt* against what the readout claimed to be scoring.

**BD29. The prompts diverged from the plan and the paper for no reason, and one of the divergences
caused a bug I then "discovered".** Asked whether the prompts matched the paper, and they did not.
`ICLR_PLAN.md:153` specifies the label sets as legacy **"Safe/Risky"** and neutral **"A/B"**;
`Probes/tasks/prompts.py` uses `'Safe'`/`'Risky'` and denominates everything in **tokens**. This file
had `"Safe Option"/"Risky Option"` and `"Option A"/"Option B"` in dollars. None of that was a decision;
it was written without checking the spec and never recorded as a deviation.

The neutral divergence is the one that cost time. `Option A` and `Option B` share their first token, so
z was log p(Option) - log p(Option) = 0 on every neutral trial. The plan's `A` and `B` tokenise
distinctly ([32, 362] and [33, 426]). I found the zero gradients, reported them as a finding about the
readout, and built a per-label-set stem to work around them — **the fix was to use the labels the plan
already specified.** The stem workaround is removed; the `assert_labels_distinguishable` guard stays,
because it would have caught this on the first run had it existed.

Corrections, all now in code and under test:

| item | was | now | source |
|---|---|---|---|
| legacy labels | `Safe Option`/`Risky Option` | `Safe`/`Risky` | `ICLR_PLAN.md:153` |
| neutral labels | `Option A`/`Option B` | `A`/`B` | `ICLR_PLAN.md:153` |
| currency | `$` | `tokens` | `Probes/tasks/prompts.py` |
| legacy cell | 10..240, 47 levels | **20..240, 45 levels** | `Probes/config.py:91` |

**A discrepancy for the authors:** `ICLR_PLAN.md` B1 says the legacy cell is "10...240 in steps of 5",
but the published grid is `reward_grid_tokens=list(range(20, 245, 5))` — 20..240, 45 columns. The code
now follows the paper. The plan's figure appears to be wrong, and my earlier claim in
`reports/B_B1.md` that the legacy cell "lines up with the published runs" was false in two ways at once:
wrong range and wrong wording.

**BD30. Prompts are now audited as text, not as code.** Author item 1. Both prompt bugs survived a
full test suite because every test compared the implementation against itself: `risky_label` agreed
with `body_text` because both applied the same wrong rule, and no test ever read a rendered prompt.
`reports/B_PROMPT_AUDIT.md` now renders two prompts verbatim for every (family x label set x option
order x response format x template) cell, after the chat template, with the stem and the exact token
ids scored for each label. A test asserts **from the rendered text alone** that the safe label's line
states a certainty and the risky label's line states a chance, and another asserts no label pair shares
a first token. B1 is not rebuilt until an author replies "audit ok".

**BD31. The audit found two things no test could have: the social games have no game text, and free
text is scored like multiple choice.** Both are properties of what the prompt *says*, which is exactly
the class of defect that a suite comparing the code against itself cannot reach, and exactly why item 1
asked for rendered text.

- **The social families render as bare payoff pairs.** A responder trial reads `Reject: nothing` /
  `Accept: 90 tokens for sure`. The published prompt states a proposer, a 100-token pie, and that
  rejection gives *both* parties zero. None of that survives. The cause is that the social games were
  represented as degenerate lotteries so they could reuse the risk domain's machinery; sharing the
  split logic and the format logic is right, sharing `body_text` is not. `responder`, `proposer`,
  `dictator` and `mini_ultimatum` are all affected. Without the framing, rejecting a low offer is not
  a preference, it is an arithmetic error, and the mini-ultimatum's alternatives — the entire point of
  that family — never appear in the prompt.
- **Free text is a second multiple-choice arm.** `ICLR_PLAN.md:153` says free text is "scored by
  sequence log-probability"; both formats currently use the `Answer:` stem and the same first-token
  readout, differing only in instruction wording. So the response-format factor in D5 and in the B2
  format term is not the factor the plan defines, and "the effect survives the response format" is
  currently unsupported.

Neither is patched. Both change what the instrument measures, so they go to the authors with the audit
rather than being fixed inside the gate.

**BD32. The three legacy stacks disagree with each other, which corrects BD29.** Checked `Probes/`,
`SAE/` and `Revised Prompting/` after being asked whether the prompts match what was done before.
There is no single "what was done": the three stacks that produced the paper's figures used different
wordings and different grids.

| stack | lottery prompt | answer tokens | reward grid |
|---|---|---|---|
| `Probes` | `SAFE VS. RISKY CHOICE GAME`, numbered list | `'Safe'`/`'Risky'` | 20..240 step 5 (45) |
| `SAE` | prose, "Option safe gives 50 tokens for sure…" | `safe`/`risky` lower case | 10..180 step 5 (35) |
| `Revised Prompting` | as SAE, plus CoT variants | `safe`/`risky` | 10..180 step 5 (35) |

Common to all three: safe = **50 tokens**, p = **0.5**, denominated in **tokens**, EV crossover at 100.
So the currency correction in BD29 was right for all three stacks.

**BD29 was too confident about the grid.** It asserted that the published grid "is" 20..240 and that
`ICLR_PLAN.md`'s 10..240 was simply wrong. In fact 20..240 is the *probe* stack's grid; the SAE stack —
which produced the layer-50 SAE steering results, the paper's headline method — used **10..180**. The
plan's 10..240 is the union of the two: the 10 from SAE, the 240 from Probes. It is not a grid anyone
ran, but neither is it a simple error, and **which grid the bridging cell should reproduce depends on
which figure it is meant to bridge to.** That is an author decision, not a code fix, and the build
currently uses 20..240 by my choice rather than by instruction.

The ultimatum comparison is less ambiguous and worse for Track B: **all three** legacy stacks state the
proposer, the pie and that rejection gives both parties zero. Track B states none of them (BD31).

**BD33. A checkpoint keyed on trial ids would have silently reused stale reads after the prompt
rewrite.** Caught before rerunning B2-cal. A `trial_id` hashes the trial's content and format — domain,
family, parameters, label *set name*, order, template — but not the words the model is shown. Renaming
the legacy labels from "Safe Option"/"Risky Option" to "Safe"/"Risky" and the currency from dollars to
tokens changed **every prompt** while leaving **every trial id identical**. The resume logic would have
matched its key, declared 872 of 872 rows already done, and returned the previous run's z values for
prompts that no longer exist — a silent, total contamination of the refit, with no error anywhere.
`items_key` now folds a hash of the rendered prompt text into the key, so a change of wording
invalidates the checkpoint. A test asserts exactly that. The same fix applies to the gradient and
numerics jobs.

**BD34. External check 2(a): the G2 arm named in the instruction cannot serve as the reference; chat64
can.** Author item 2(a) asks that the rebuilt legacy cell reproduce "G2's chat-arm unsteered curve"
within one grid step at the crossing. Measured on the Friday session's data:

| arm | max_new_tokens | answered | crossing | levels with <20/40 answering |
|---|---|---|---|---|
| legacy | 12 | 234/1800 = **13.0%** | — | — |
| chat | 12 | 576/1800 = **32.0%** | 68.4 | **13 of 25** |
| **chat64** | 64 | **1800/1800 = 100%** | **110.0** | **0 of 45** |

The chat arm answers on a third of trials, and its answer rate collapses above n = 60 — at n = 65 only
**2 of 40** agents answer. Its apparent crossing at 68.4 is an artefact of those two rows, not a
measurement. The chat64 arm answers every trial and crosses at **n = 110**. So the reference for 2(a)
is taken as **chat64, crossing n = 110**, and the substitution is flagged rather than made silently:
`reports/G2_legacy_format.md` labels chat64 a departure because it raises `max_new_tokens` from 12, but
it is the only arm whose curve is supported by data at every level. The 12-token budget, not the chat
template, is what truncates the answers.

**BD35. Autonomy amendment, 22 Sept — in force before and after the cutoff.** Recorded because it
changes how every later entry in this log comes to exist.
- Open choices in the plan are **decided here, not escalated**: take the option that keeps every
  pre-registered threshold and lock intact and is cheapest to reverse, record it with the alternatives
  considered, and proceed. A later overrule is a rerun, not a reason to wait now.
- Prompt rebuilds no longer wait for "audit ok". They proceed when three automatic checks pass:
  (a) the rendered-text tests; (b) the legacy cell's user turn equals `Probes/tasks/prompts.py`
  character for character; (c) every social prompt contains the proposer, the pie, the offer and the
  consequence of rejecting, checked as strings. `reports/B_PROMPT_AUDIT.md` is still regenerated.
- Gates B2 and B3 stay automatic after the cutoff. Budget rises to 1,000 GPU-hours through 5 Nov, with
  the running total in `STATUS.md`.
- Test split: once `PREREG.md` is committed and tagged `prereg-v1`, `logs/UNLOCK_REQUEST.md` records
  the tag SHA and time and the runner unlocks 24 hours later **unless `logs/VETO` exists**. Nothing
  else about the lock changes; it is still refused until that file appears.
- Only four things still need an author: changing a pre-registered threshold or metric; changing an
  anchor's training objective **after its dry run passed**; exceeding the budget; and a spec conflict,
  which is reported and then worked around on every branch it does not block.

**BD36. The three checks forced two prompt changes I had been holding open, and both are now done.**
Check (b) required the legacy cell to be the paper's text, and check (c) required the social games to
state themselves. Neither was a judgement call any more, so both were implemented rather than asked
about.
- **The legacy cell now renders `Probes/tasks/prompts.py::lottery_prompt` verbatim** — the numbered
  `SAFE VS. RISKY CHOICE GAME` list, "Guaranteed 50 tokens", "Respond with either 'Safe' or 'Risky'".
  Only the canonical bridging cell does this (sure-gain, p=0.5, s=50, legacy labels, canonical order,
  multiple choice); everything else keeps the generator's wording, because everything else is a new
  instrument by design. **This also settles the open grid question by construction**: the paper text
  is the probe stack's, so the bridging cell is the probe stack's 20..240, and the SAE stack's 10..180
  is a different bridge that would need its own cell. Alternatives considered: make the whole risk
  domain paper-faithful (rejected — it would delete the p and s variation the plan requires), or keep
  my wording and compare curves loosely (rejected — check (b) forbids it, and it is the weaker claim).
- **The social families now state the game.** `responder`, `proposer`, `dictator` and
  `mini_ultimatum` each carry a scenario naming the proposer, the pie, the offer and that rejection
  gives both parties zero. The option lines are suppressed where a scenario exists, because the
  payoffs are already in it and "Accept: nothing" at an offer of zero is absurd; the paper's ultimatum
  states the game and asks the question, and so does this.
- Two consequences that fell out of writing it: the generic question was wrong for three families —
  a proposer is not asked to "accept" and a true/false claim is not accepted — so each family now has
  its own question and its own label vocabulary; and the accept-bias control **split into two
  families**, `accept_bias_control` (true/false statements, yes/no) and `offer_bias_control`
  (accept/reject offers), which is what B1 asks for when it says "unrelated accept/reject **and**
  yes/no items" rather than one kind wearing the other's clothing.

**BD37. The gradient rerun returned the withdrawn run's vectors in 32 seconds.** The skip-if-done check
tested only that `grad_*.npy` and its metadata existed. After the prompt rewrite the filenames were
unchanged and the words were not, so the job "completed" instantly and reported the very vectors BD27
was withdrawn for — sha256 `e23ea580...`, identical to the old run. This is BD33's bug recurring in a
second place: an identity check that does not cover the thing that actually changed. The metadata now
carries the `items_key` fingerprint over trial ids **and rendered prompt text**, and a version is
recomputed unless that matches. The stale outputs were deleted and the job resubmitted.

**BD38. B2-cal on corrected prompts: what changed, and what gamma is now doing.** All first-run numbers
were withdrawn; these replace them. 864 rows, legacy labels, `Answer:` stem, unbatched, 4:52 on 4 GPUs.

| quantity | first run (withdrawn) | corrected prompts |
|---|---|---|
| valid mass | 0.9641 | **0.9945** |
| z mean | -0.947 | **-3.199** |
| z range | [-10.3, +12.2] | [-17.1, +6.1] |
| template noise SD | 0.5816 | **2.1338** |
| numerical noise SD | 0.0 | **1.1e-16** (bit-identical) |
| readout vs free generation | 0.36 (bug: no chat template) | **0.59** |

Three consequences:
- **The recovery study's noise assumptions were wrong by 4x.** Template noise is 2.13, at the very top
  of the 0.5/1/2 range simulated, while the "primary" configuration used 0.5. The rerun centres on the
  measured value. Numerical noise is zero to machine precision, confirming item 3.
- **gamma is railed.** The fit returned exactly 1.600, its optimiser bound. That is a statement about
  the bound, not the model. Bounds widened to gamma 4.0 and alpha 2.5 — optimiser bounds, not
  pre-registered thresholds, so no gate criterion moves — and if it rails again gamma is unidentified
  on this grid and will be reported as such rather than quoted.
- **The readout agrees with free generation on 59 of 100 held-out prompts**, with zero unparseable.
  Barely above chance, measured with the chat template on both sides. This is Track B's half of the
  comparison item 6 asks for and it goes beside the Friday session's when theirs lands.

The within-cell slope is again positive and the pooled table again is not: mean within-cell slope
**+2.74**, all four p=0.5 stakes positive (2.77, 5.97, 2.91, 2.35), joint within-cell log x **+3.00**
against a pooled log p of +5.12. Two of 40 cells have a negative slope, both in the saturated floor.
So the withdrawal of "undermines the contextual-utility assumption" stands on the corrected prompts
too. CPT's residual RMSE is **3.87** against a z SD of 3.96 — the parametric model explains almost
none of the variance, which is the same story gamma railing tells.

**BD39. theta0 on corrected prompts, refitted under bounds that do not bind: alpha 0.701, gamma 1.685,
tau 0.119.** With gamma capped at 1.60 the fit returned exactly 1.600; widened to 4.0 it settles at
**1.6849** and **no parameter is on a bound**, so this is an estimate rather than a description of my
optimiser. The earlier 1.600 is superseded.

Set against plan v4's theta0 = (alpha 0.88, gamma 0.61, lambda 2.25):

| parameter | plan v4 | fitted on this model |
|---|---|---|
| alpha | 0.88 | **0.701** — more curvature |
| gamma | 0.61 (inverse-S) | **1.685 (S-shaped)** — the opposite direction |
| tau | — | 0.1186 |

**Gamma's sign is reversed relative to the plan's assumption.** Plan v4 assumes inverse-S weighting,
which overweights small probabilities — the standard human finding. This model's weighting is
S-shaped: it *under*weights small probabilities. That is consistent with everything else measured
here — the CPT residuals are most negative at p = 0.1 (about -4.5 across every stake in the first run),
and the model is far more averse to low-probability gambles than an inverse-S agent would be.

**But the parametric model fits badly regardless.** CPT's residual RMSE is **3.869** against an
observed z SD of **3.957**: the fitted model explains essentially none of the variance in z. So gamma
1.685 is the best CPT can do on this data, not evidence that this model is a CPT agent with S-shaped
weighting. Both facts are reported together; quoting the parameter without the residual would be
misleading. The B3.2 adapters are trained to a *specified* agent rather than to this fit, so the poor
fit does not contaminate the anchors — it constrains what a comparison against the unmodified model
can claim.

The within-cell slope on corrected prompts is again positive: mean **+2.74**, all four p = 0.5 stakes
positive (2.77, 5.97, 2.91, 2.35), joint within-cell log x **+3.00** against a pooled log p of +5.12.
Two of 40 cells run negative, both in the saturated floor. The withdrawal of "undermines the
contextual-utility assumption" therefore stands on the corrected prompts as well.

**BD40. B3.1 on corrected prompts: the gradient is predominantly ORDER-INVARIANT. BD27 was exactly
backwards.** Re-run on the rebuilt grid with no prior claim attached, 4:01 on 4 GPUs, layers 48 and 50,
calibration-split core prompts, legacy labels, gradient w.r.t. the output of `model.model.layers[L]`.

| | withdrawn run (buggy prompts) | corrected prompts |
|---|---|---|
| cos(g1, g2) at L48 | **-0.8140** | **+0.7274** |
| cos(g1, g2) at L50 | **-0.8232** | **+0.7386** |
| \|g1\| , \|g2\| at L48 | 13.74 , 8.82 | 13.19 , 11.20 |
| \|g1+g2\| (order-invariant) | 8.32 | **22.68** |
| \|g1-g2\| (position) | 21.54 | **9.19** |
| position / order-invariant | **2.59** | **0.41** |

The conclusion reverses completely. BD27 reported that the position component was **2.6 times larger**
than the part surviving a change of presentation order, and read that as A6's warning confirmed — the
readout gradient being "not merely somewhat action-like but predominantly a position signal". On
corrected prompts the order-invariant component is **2.4 times larger than the position component**,
and the two orders are strongly *positively* aligned.

The whole of the original effect was the relabelling bug: under the old code the word naming the gamble
swapped between orders, so the direction that raises z swapped with it. Withdrawing the claim outright
rather than qualifying it was the right call — a qualified version would have survived as "the gradient
is somewhat position-contaminated", which is also false.

What stands: within a single order the per-prompt gradients are coherent at **0.88-0.93**, so each of
g1 and g2 is a real direction; the magnitudes are now close (13.19 against 11.20, against 13.74 against
8.82 before), which is itself evidence the relabelling had been distorting one order more than the
other. **Track B's B3.1 anchor is `legacy_sum`**, and on this evidence it is a strong direction rather
than the weak residual BD27 implied. `legacy_diff` remains the position control and is now the smaller
of the two, as a control should be.

For the Friday session's G4b: the directions are on the share with sha256 each and a `how_to_load`
block. Their `cvb_g4b` run failed in `fallback_gradient` — it was building its own direction, which
item 3 exists to avoid — with a placement error (`36 module(s) landed on disk rather than a GPU`).
These files are the ones to load; `legacy_one_format` is the version item 3 named for them.
