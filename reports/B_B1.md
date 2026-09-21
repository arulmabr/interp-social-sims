# B_B1.md — Track B B1: trial generators, formats and splits

**Status: complete.** Code in `cv_bench/tasks/`, values in `MANIFEST_B.csv`, 37 B1 tests passing
(46 across the repo). Built by Slurm job `cvb_b1_build` (23380488), CPU only, 4 seconds — no GPU-hours
against the shared 400-hour cap.

`$TRACKB_SHARE` below is the project directory on the lab share; the dataset is
`$TRACKB_SHARE/trackB/b1_trials/20260921T101538Z_7f63fba/`.

## 1. What was built

**919 content trials, 29,408 rows** after expanding each by option order (2) x label set (2) x
response format (2: multiple choice, free text) x instruction template (2 per split).

| domain | content trials | families |
|---|---|---|
| risk | 726 | sure-gain 245, sure-loss 245, paired 68, mixed 36, catch 132 |
| social | 168 | responder 48, proposer 48, dictator 48, mini-ultimatum 12, accept-bias control 12 |
| transfer | 25 | Holt-Laury 10, Gneezy-Potters 10, Eckel-Grossman 5 |

| split | content trials | | frame role | content trials |
|---|---|---|---|---|
| disc | 339 | | core | 157 |
| sel | 309 | | heldout | 762 |
| cal | 271 | | | |
| **test** | **0** | | | |

The grid is the plan's starting grid — p in {0.1, 0.25, 0.5, 0.75, 0.9}, s in {20, 50, 100, 500}, x on
a 14-level log grid from 0.3x to 5x the risk-neutral point s/p — and is finalised at B2. The legacy
cell (p = 0.5, s = 50, x = 10..240 step 5, 47 levels) is present exactly, so every new result has a
cell that lines up with the published runs.

## 2. Three invariants, enforced in code rather than documented

1. **Every prompt goes through the chat template.** `to_trial_spec` always sets
   `use_chat_template=True`, and the one function that renders without it, `render_raw_unsafe`, raises
   unless explicitly acknowledged. Nothing in Track B calls it. This follows `reports/G2_legacy_format.md`:
   the legacy raw-string format yields no answer on **88.3%** of trials.
2. **The test split cannot be materialised.** `check_test_access` raises `TestSplitLocked` unless given
   the SHA the `prereg-v1` tag points at; the tag does not exist, so the split cannot be unlocked at
   all. Every attempt, granted or not, is appended to `logs/TEST_ACCESS.log`. `build.py` additionally
   asserts before exit that no test row reached the output.
3. **The transfer battery refuses selection splits.** Asking for `sel` or `cal` raises `TransferMisuse`
   (A11: the battery is never used for selection or calibration).

## 3. Three design bugs the tests caught

These are recorded as BD5 and BD6 in `logs/B_DECISIONS.md`. All three came from tests asserting a
property of the design, not from reading the code.

- **The mini-ultimatum's no-alternative condition was generated zero times.** Its four alternatives are
  *conditions*, not reward levels; a mod-4 split over four conditions put each in exactly one split and
  the no-alternative condition in the locked test split. The contrast the design exists to measure was
  simply absent. Conditions are now replicated across splits; only reward levels are divided.
- **The transfer battery was cut to a quarter.** Splitting Holt-Laury by item index left three of ten
  decisions in `disc`, and a ladder with three rungs has no switching point. Each instrument is now
  emitted whole within each split.
- **Social trials scored fairness as a dominance violation.** Accepting always pays a responder at
  least as much as rejecting, so marking every monetary shortfall as dominated would have counted every
  inequity-averse rejection — the preference under study — as an attention failure. Dominance is now
  recorded only on catch trials, where by construction no preference explains the choice.

## 4. One property of the plan's grid, kept deliberately

The grid starts at 0.3x the risk-neutral point, so wherever p >= 0.3 its lowest levels are **statewise
dominated**: at p = 0.5, s = 20 it starts at x = 12, and a 50% chance of $12 cannot beat $20 for sure.
104 of the 726 risk trials are dominated this way. They are kept — a dominated level is a legitimate
extreme reward level and pins the floor of the choice curve — but every one carries a `dominant` flag so
the dominated-choice rate counts them and the B2 estimator can weight or drop them deliberately rather
than by accident. In a gain frame the sure option dominates; in a loss frame the gamble does, since it
risks losing at most x <= s. Dominance anywhere else, or in the paired and mixed families, is asserted
against as a bug.

## 5. Prompt wording

Fixed now, because it is fixed for every later result: changing a prompt after a run would be a
deviation under `CLAUDE.md` rule 4. The wording follows the plan's own phrasing, "p chance of x,
otherwise 0".

```
You are taking part in a study of decision making.

Safe Option: $20 for sure
Risky Option: a 10% chance of $60 and otherwise nothing

Which do you choose? Answer with exactly one of "Safe Option" or "Risky Option" and nothing else.
```

Stated certainty-equivalent and recall probes are generated by
`risk.certainty_equivalent_prompt` and `risk.recall_prompts`; unparseable outputs are counted by the
runner rather than dropped, per B1.

## 6. What B1 does not include

- **Test-split templates.** `TEMPLATES["test"]` is deliberately empty: the plan says test templates are
  written by a human author and added at unlock.
- **Fact probes.** B1 specifies ridge "fact probes" for log x and log s trained on baseline
  activations. They need a model forward pass, so they belong with B3's anchor work and are not built
  here. The recall *prompts* exist; the probes do not.
- **Instruction-template variation beyond two per split**, which is what the plan specifies.

## 7. Next

B2 (synthetic agents, estimator, recovery study) is CPU-only and unblocked. **Gate B2 is now an
automatic check** under amendment item 5, evaluated exactly as `ICLR_PLAN.md` writes it.

B3.2's LoRA anchors remain blocked on `peft`, which is not installed (BD2); the 4-bit fallback needs a
GPU-node check before it can be relied on. Neither blocks B1 or B2.
