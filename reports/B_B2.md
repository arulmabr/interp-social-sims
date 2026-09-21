# B_B2.md — Track B B2: synthetic agents, estimator, recovery study

# GATE B2: **FAIL** — 0 of 18 configurations pass

Evaluated automatically, exactly as `ICLR_PLAN.md` writes it, with plan v4's thresholds, under
amendment item 5. **Track B stops here and reports.** Per the amendment the remedy for a B2 failure is
to iterate on the synthetic grid only, never on the thresholds, and the two remedies below are both
grid decisions that carry a cost — so they are the authors', not Track B's.

Code in `cv_bench/estimator/`, values in `MANIFEST_B.csv`, 22 estimator tests (80 repo-wide). Run as
Slurm array `cvb_b2_recovery` (23410348), 18 CPU tasks in parallel, ~7 minutes. **No GPU-hours.**

`$TRACKB_SHARE` is the project directory on the lab share; outputs are in
`$TRACKB_SHARE/trackB/b2_recovery/`.

## 1. What passes, and it is most of it

At the primary configuration — template noise 0.5, no numerical noise, dominated trials excluded:

| Gate B2 requirement | Result | |
|---|---|---|
| α RMSE ≤ 0.05 | **0.0091** | pass |
| γ RMSE ≤ 0.05 | **0.0044** | pass |
| λ RMSE ≤ 0.15 | **0.416** | **fail** |
| ≥95% of preference agents called preference-like | 0.70 (α), 0.70 (γ), 0.00 (λ) | **fail** |
| ≥95% of action/belief/noise/format agents called *not* | **1.00, 1.00, 1.00, 1.00** | pass |
| the two misspecified agents handled on the model-free layer | both | pass |

**Specificity is perfect and is not bought cheaply.** Every non-preference agent is matched on
behavioural effect size before the comparison — action, belief, noise and format all move behaviour by
~0.012 mean |ΔP| against the preference agents' 0.018 — and every one is rejected in every one of 20
replications, in all 18 configurations. Each is caught by the diagnostic meant to catch it: format bias
by D5's transfer ratio (0.00 in band), belief distortion by D6's recall check (0.00 intact), action and
noise by the parametric share (0.000).

## 2. The two failures, with arithmetic

**λ is not identified on this grid.** Predicted in `logs/B_DECISIONS.md` BD10 *before* any fitting.
Under the contextual-utility normalisation the plan mandates, λ cancels exactly on any trial whose
outcomes share a sign: the largest change in z from moving λ by its full minimum detectable change is
**0.000000** across all 245 sure-gain and all 245 sure-loss trials. Only 36 of 726 risk trials are
mixed-frame. A full-MDC λ shift moves behaviour by **0.0013** mean |ΔP| — below the noise floor. The
remedy is a denser mixed-frame grid. It is not a looser bound.

**The decision rule is power-limited at the minimum detectable change.** For a true α shift the rule's
individual criteria pass at 0.90 (preference share), 0.85 (out-of-frame prediction) and 0.70 (action
rejected); requiring all seven at once gives 0.70 against the required 0.95. Nothing here is
mis-measured — the effect is simply small: **mean Δz at the MDC is +0.0109 logits**, against a
numerical-noise floor on a format subset's mean of **0.0023**.

## 3. The finding the authors asked for: numerical noise breaks the rule

Amendment item 5(b) asked for an independent numerical-noise component at SD 0.1 and 0.25 on top of
template noise, standing for the Friday session's measured SD ≈ 0.094 in z across batch compositions on
the 70B in bf16. It is not a rounding detail:

| numerical noise SD | pref_α classified correctly |
|---|---|
| 0.00 | 0.70 |
| 0.10 (≈ the measured bf16 value) | 0.25 |
| 0.25 | 0.05 |

**At the noise level actually measured on the 70B in bf16, the decision rule's sensitivity falls from
0.70 to 0.25.** Numerical non-determinism alone, with no change to the science, is enough to break the
diagnostic at the minimum detectable change. This is the strongest argument yet for amendment item
5(a) — read unbatched for anything reported — and it says that B3 and B4 will need either fp32 reads,
repeated reads averaged per prompt, or an effect larger than the MDC to be detectable at all.

## 4. The dominated-trial policy: BD9 resolves to "exclude"

Fixed in advance (BD9) so the result could not pick the policy. Over the three template-noise levels at
the primary numerical setting, excluding the flagged dominated trials from the parametric likelihood
beats keeping them with a free lapse parameter on α (0.0091 vs 0.0111), on λ (0.416 vs 0.661) and on
the classification rate that the gate actually reads (0.70 vs 0.50). The lapse variant is better on γ
alone (0.0007 vs 0.0044). **The default stands: dominated trials feed D1 only.**

## 5. Three estimator corrections made before this verdict

All recorded in BD14. The first run of the study failed with *every* agent — preference shifts included
— classified as not preference-like, which is not a result but a broken rule, so it was diagnosed:
a missing per-template intercept (preference share 0.265 → 0.591); fitting binary choices when the
readout returns z (α RMSE 0.055 → 0.0054); and D5 dividing two squashed probability differences, which
failed genuine preference shifts on noise alone. No threshold was touched — plan v4's numbers live in
one place in `decision.py` and a test asserts them.

## 6. What the authors have to decide

1. **The mixed-frame grid.** λ needs many more mixed trials to be identified at all. How many is a
   budget question.
2. **D5's transfer band, or the grid behind it.** Holding 0.8–1.25 at the MDC needs roughly **nine
   times** the rows per format subset, or about nine independent reads per prompt to average the
   numerical noise down. Widening the band instead is an AUTHOR DECISION frozen at B6 and is not
   Track B's to make.
3. **The reading of "including for the two misspecified agents on the model-free layer"** (BD14).
   Mean-variance utility genuinely violates stochastic dominance, so D1 flags it. Track B reads the
   requirement as "not called preference-like, and the model-free layer is what catches it" rather
   than "must look clean". Under the other reading these two agents fail.
4. **The 0.95 cluster-bootstrap threshold for "the action model is rejected"** (BD12). The plan
   requires the action model rejected but does not say how. At 0.90 instead of 0.95 the primary
   configuration's sensitivity rises, but that is a threshold and so is frozen at B6.

## 7. What B2 does not include

- **B2 ran on the risk domain only.** The social and transfer generators exist and are tested, but the
  plan's agent zoo and decision rule are written for the risk fingerprint.
- **D6 is simulated, not decoded.** The recall probes exist as prompts; the ridge fact probes need a
  forward pass and belong with B3.
