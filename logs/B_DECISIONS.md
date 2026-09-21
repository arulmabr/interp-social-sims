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
