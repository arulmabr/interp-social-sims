# B_B3.md — Track B B3: the anchors

**B3.1 (gradient) is complete on Llama-3.3-70B. B3.2 (LoRA) is now complete on Llama-3.3-70B too, and
GATE B3 FAILS.** All three adapters clone. At n = 1016 with the contrast floor MEASURED rather than
assumed independent (BD49: the adapters share a seed and data order, rho = +0.576), the preference
interval is [+0.0054, +0.0522] -- clear of zero, 0.38 MDC from the truth, but 1.33 MDC wide against
the <= 1 MDC the gate requires. Earlier intervals in this report assumed independence and were too
wide; see BD49. Values in `MANIFEST_B.csv`; decisions in `logs/B_DECISIONS.md` BD27, BD37, BD40, BD46.

`$TRACKB_SHARE` is the project directory on the lab share.

---

## 1. B3.1 — the gradient anchor

The gradient of z with respect to the residual stream at the intervention layer, final prompt token,
averaged over calibration-split core prompts, legacy labels, `Answer:` stem. Completed in **4:01** on
4 GPUs.

The gradient is taken with respect to **the output of `model.model.layers[L]`**, which is the tensor
`steer.SteeringHook` adds to. A gradient taken anywhere else would not be the direction a dose actually
moves, and the anchor would be measuring something the intervention cannot do.

### The result: the direction is order-invariant

| layer | \|g1\| | \|g2\| | \|g1+g2\| | \|g1−g2\| | cos(g1,g2) | coherence |
|---|---|---|---|---|---|---|
| 48 | 13.19 | 11.20 | **22.68** | 9.19 | **+0.7274** | 0.882 / 0.927 |
| 50 | 12.58 | 10.65 | **21.67** | 8.59 | **+0.7386** | 0.888 / 0.931 |

The order-invariant component `g1+g2` is about **2.4 times larger** than the position component
`g1−g2`. Within a single option order the per-prompt gradients are coherent at 0.88–0.93, so each of
g1 and g2 is a real direction rather than an average of noise.

**Track B's B3.1 anchor is `legacy_sum`.** `legacy_diff` is a position-bias direction by construction
and joins the controls; it is the smaller of the two, as a control should be.

### A withdrawn claim, and why it matters

An earlier run of this same job reported **cos(g1,g2) = −0.814**, and BD27 read that as A6's warning
confirmed: the readout gradient being "not merely somewhat action-like but predominantly a position
signal". That was an artefact of a prompt bug — option order was relabelling the two options rather
than reordering them, so the word naming the gamble swapped between orders and the z-raising direction
swapped with it (BD28). The claim was **withdrawn outright rather than qualified**, because a hedged
version ("somewhat position-contaminated") would also have been false. On corrected prompts the
conclusion reverses: **A6's concern is not borne out on this model.**

A second failure mode is worth recording. The first rerun "completed" in **32 seconds** by skipping
every version, because the skip-if-done check tested only that `grad_*.npy` existed — the filenames
were unchanged and the words were not, so it returned the withdrawn vectors (BD37). The metadata now
carries a fingerprint over trial ids **and rendered prompt text**, and recomputes unless it matches.

### Files

Ten directions under `$TRACKB_SHARE/trackB/b3_gradient/`, each with a sha256 in `b3_gradient.json`
plus a `how_to_load` block naming the tensor the gradient is taken against:

| file | role |
|---|---|
| `grad_L{48,50}_legacy_order0.npy` | g1 |
| `grad_L{48,50}_legacy_order1.npy` | g2 |
| `grad_L{48,50}_legacy_sum.npy` | **the order-invariant anchor** |
| `grad_L{48,50}_legacy_diff.npy` | position-bias control |
| `grad_L{48,50}_legacy_one_format.npy` | **what the Friday session loads for G4b** |

---

## 2. B3.2 — the LoRA anchors

Three adapters per A5 on identical data, order and schedule, attached to one loaded base and switched
with `set_adapter`: reference at θ0, α-shifted by its minimum detectable change, and a bias-shifted
negative control. Loss is soft-label cross-entropy over the full vocabulary at the answer token, with
the synthetic agent's exact choice probabilities on the two option tokens. Training uses `disc`+`cal`
so the selection split is genuinely held out.

### The 8B dry run passes

At the temperature fitted by B2-cal (τ = 0.1186), with cosine decay and checkpoint selection:

| adapter | selected step | cloning r (≥0.95) | slope (0.9–1.1) | |
|---|---|---|---|---|
| reference | 500 | 0.9902 | 0.9796 | **PASS** |
| preference | 500 | 0.9923 | 0.9875 | **PASS** |
| bias | 500 | 0.9912 | 0.9871 | **PASS** |

**The plan's specified loss meets the plan's specified cloning bar.** It took six dry runs to establish
that, and three of the failures were avoidable: a learning-rate change made alongside a step-count
change, which stopped the loss falling at all; a single peak probe reported as a pass when the curve was
oscillating; and four runs on prompts that carried the option-order bug.

What actually fixed it was **cosine decay**. With a constant learning rate the loss went flat near 0.30
by step 600 while the calibration slope kept swinging between 0.77 and 0.91 — the adapter was orbiting
a solution rather than settling on one, so whether it "passed" depended on which step the probe landed
on. Checkpoint selection by held-out slope, which the plan's amendment names, then picks the weights
that actually clone.

There was never a generalisation gap: train and held-out slopes stayed within 0.008–0.053 of each other
at every probe.

### But the contrast — which is what the anchor *is* — does not clone

A5 is explicit that **the anchors are the contrasts against the reference adapter**, not the adapters.
Measured on the selection split:

| contrast | true signal | recovered | ratio | r |
|---|---|---|---|---|
| bias − reference | 0.6000 | 0.6818 | **1.136** | 0.0148 |
| **preference − reference** | **0.0302** | 0.1408 | **4.665** | 0.3914 |

The arithmetic accounts for both rows. At r = 0.990 with a clone-set z SD of 3.62, each adapter's
cloning residual has SD about **0.506**, so a contrast of two independent adapters carries **0.715**:

- the **bias** contrast has a true signal of 0.600, giving S/N ≈ 0.84. Its magnitude recovers at 1.14x,
  which is what matters for a constant offset; its near-zero correlation is expected, since a constant
  shift has no per-trial variation to correlate against.
- the **preference** contrast has a true signal of **0.0302**, giving S/N ≈ **0.042**. The quantity the
  anchor exists to measure is about **twenty-four times smaller than the noise floor created by the
  adapters' own imperfection**, which is why its recovery ratio comes back at 4.7x rather than 1.0.

**Passing the cloning bar is therefore not sufficient for the contrast to be usable, and the plan
checks the contrast nowhere.** This is the same root cause as Gate B2's failure (BD45): a preference
shift at the minimum detectable change produces a mean Δz of 0.030, which is small against every noise
source measured in this session — the template effect at 2.13 and the cloning residual at 0.506.

Three remedies exist and each is an AUTHOR DECISION: a **larger Δ**, which is pre-registered; **tighter
cloning**, which would need r ≈ 0.99995 and is probably unreachable; or **training the adapters so
their residuals correlate and cancel in the contrast**, which A5 gestures at by requiring identical
data order and seed but which evidently is not sufficient. Changing an anchor's objective after a
passing dry run is a hard stop under the autonomy amendment, so none has been applied.

### The 70B run

Queued: 4 GPUs, bf16, 500 steps, τ = 0.1186, `--exclude=node2119`, checkpointing every 25 steps. Its
value is not whether it clones — the 8B settled the recipe — but **whether a larger model clones
tightly enough to lift the preference contrast off its noise floor.** On the 8B arithmetic that needs
r ≈ 0.99995, so the expectation is that it will not, and the contrast numbers will say so directly.

**No anchor is scored with the B2 decision rule until Gate B2 passes**, which it does not (BD45).

---

## 3. What B3 does not include

- **B3.3 anchor-derived candidates** — the mean activation difference between the preference-shifted
  and reference adapters, a probe trained to separate them, and SAE features ranked by their
  difference. These are families rather than anchors and wait on the 70B adapters.
- **The fp32-vs-bf16 numerical check** (`b0_numerics`) **has now completed** (22 Sept, 4x A100-80GB,
  196 calibration prompts, layer 50, unbatched, no CPU offload). It is no longer an open item, but it
  does not come back clean. Two different numbers matter and they say different things:

  | quantity | bias (bf16 - fp32) | SD | max abs |
  |---|---|---|---|
  | absolute z | **-0.0170** | 0.0990 | 0.3425 |
  | dosed-minus-baseline difference | **-0.0018** | 0.0998 | 0.2535 |

  bf16 carries a systematic offset of about -0.017 in z, which **largely cancels in a contrast**,
  leaving -0.0018. So any quantity read as a difference between two conditions on the same stack is
  safe; an absolute z compared across stacks is not.

  **The number that should worry us is `error_to_effect_ratio = 0.1494`**: the numerical error is about
  15% of the steering effect it has to resolve. That is small next to a full-dose effect and large next
  to the B3.2 preference contrast, whose true signal is 0.0302 -- roughly a third of this check's own
  per-prompt scatter.

  **Limitation.** The dose used was a `matched-norm random stand-in (B3.1 anchor not yet built)`: the
  sbatch script predates the gradient anchor. The check therefore bounds numerical error along a
  *random* direction of matched norm, not along the B3.1 anchor. Re-running it against the real anchor
  is cheap (about 25 min on 4 GPUs) and is the honest way to close this.

---

## 4. The 70B run, and GATE B3

Job 23460913, `ou_bcs_normal`/node3910, 2x A100-80GB PCIe, bf16, 1h38m, 500 steps per adapter.
Values registered under `B3.2.70b.*`; verdict computed by `cv_bench/anchors/gate_b3.py`.

### All three adapters clone

| adapter | selected step | r | slope | z_sd | cloning residual SD |
|---|---|---|---|---|---|
| reference | 250 | 0.9909 | 0.9553 | 3.524 | 0.4740 |
| preference | 500 | 0.9948 | 0.9761 | 3.674 | 0.3760 |
| bias | 500 | 0.9930 | 0.9363 | 3.447 | 0.4067 |

Every one clears the bar (r >= 0.95, slope 0.9-1.1), with train-minus-held-out gaps at or below 0.04,
so this is not memorisation. **Scaling from 8B to 70B did what it was asked to do at the adapter level.**

### The contrasts do not follow

A5 is explicit that the anchors are the **contrasts against the reference adapter**. Each adapter's
cloning residual has SD ~0.38-0.47 even at r ~= 0.99, and a contrast of two independently trained
adapters carries the two in quadrature:

| contrast | true signal | noise floor SD | buried | estimate | 95% CI | resolved |
|---|---|---|---|---|---|---|
| preference - reference | 0.0302 | 0.6050 | **20.0x** | 0.0474 | [-0.0291, +0.1239] | **no** |
| bias - reference | 0.6000 | 0.6246 | 1.0x | 0.4968 | [+0.4178, +0.5759] | yes, biased low |

**The preference point estimate lands 0.98 MDC from the truth — and that is luck, not measurement.**
The interval is 4.35 MDC wide and contains zero. It cannot separate the true shift from no shift, nor
from four times the shift. The 8B had it buried 24x (BD46); the 70B has it buried 20x. Scale did not
fix it, and there is no reason to expect the next model size to either.

The bias contrast resolves because its signal is 20x larger, but it recovers 0.497 against a truth of
0.600 — 5.9 MDC low, so it is detected and mis-estimated rather than measured.

### Verdict

**GATE B3 = FAIL**, on the preference anchor. `ICLR_PLAN.md:186` routes a failing preference anchor to
**"fix cloning or the estimator"**, not to B3.3 or B4. Per the standing amendment a numeric gate that
fails stops that branch and reports, so nothing downstream has been started and no family result was
consulted in reaching this.

**What would actually move it.** The failure is variance, not correctness: the estimator recovers the
large signal and the adapters clone. Three levers, cheapest first:
1. **Paired adapters.** The floor is two *independent* residuals added in quadrature. Training the
   preference adapter from the reference adapter's weights, or with a shared data order and seed at
   every step, correlates the residuals and cancels most of the floor. This is a training-protocol
   change and needs an author decision.
2. **A larger true signal.** 0.0302 is the mean dz from shifting alpha by its MDC. Anchoring at a
   multiple of the MDC would lift the signal without touching the estimator, at the cost of no longer
   testing the detection limit.
3. **More clone rows -- CORRECTED, and now the cheapest lever, not the impossible one.** An earlier
   version of this section said a 20x burial needs n ~ 10^5 and that the lever "does not work". **That
   was wrong arithmetic** -- it squared the burial ratio and multiplied by the current n, instead of
   applying the gate's own criterion. The gate reads the CI half-width, `1.96 * floor / sqrt(n)`:
     - to make the CI **exclude zero** (half-width < the 0.0302 signal): **n >= 1,543**
     - to make the half-width **<= 1 MDC** (0.0176): **n >= 4,539**
   against n = 240 today. **The legitimate pool is smaller than it first appears.** `cloning_trials()`
   yields 1,016 rows and the run used only the first 240, so a 4.2x increase is free. The 8,128 rows
   available across all 32 formats are **not** usable for this: `training_trials()` is `mc`/`legacy`
   only, so probing other formats would measure format generalisation, not cloning.
   At n = 1,016 the CI half-width falls from 4.35 MDC to **2.11 MDC** (0.0372). That is very likely
   enough to push the interval clear of zero -- the estimate is 0.0474 -- but **still short of the
   gate's half-width <= 1 MDC**, which needs n >= 4,539. So this lever improves the result markedly
   and does not on its own clear Gate B3.

   **The caveat that decides whether it actually works.** Those 8,128 rows come from only **254 distinct
   content items**. If the cloning residual is driven by content rather than by format, the effective n
   saturates near 254 and this lever fails for a subtler reason than the one first given. That is a
   measurable quantity -- the intraclass correlation of the residual within content -- but it cannot be
   recovered from what the run saved: `ckpt_read_*.npz` holds the model-side reads only, and an attempt
   to reconstruct the agent-side z from `cloning_trials()` came back at corr = -0.081 against the
   recorded 0.9909, i.e. misaligned. **`lora.py` should persist the per-row residual and content id**;
   then the ICC settles this at zero GPU cost.

**AUTHOR DECISION.** Levers 1 and 2 both change a pre-registered quantity -- the anchor's training
protocol and the anchor's dose respectively. Track B stops here.
