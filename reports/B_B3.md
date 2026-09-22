# B_B3.md — Track B B3: the anchors

**B3.1 (gradient) is complete on Llama-3.3-70B. B3.2 (LoRA) has passed its 8B dry run and is queued
for the 70B.** Values in `MANIFEST_B.csv`; decisions in `logs/B_DECISIONS.md` BD27, BD37, BD40, BD46.

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
- **The fp32-vs-bf16 numerical check** (`b0_numerics`) never completed. Its central question was
  answered directly by B2-cal — numerical noise across five repeat unbatched reads was bit-identical at
  1.1e-16 — and it was cancelled when it began competing with the anchor for the same per-user GPU
  quota. What remains unmeasured is the fp32-vs-bf16 *bias* in z.
