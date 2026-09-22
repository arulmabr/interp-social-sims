# G4 decision memo — which probe figures the evidence supports

Due Wed 23 Sept 08:00 PDT. Written 2026-09-22 05:20 UTC, ahead of the deadline,
because every input except G5b's creativity generations is on disk.

Sources: `results/S/s1/g4_curves.csv` (672+ rows), `g4_agreement.csv`,
`g4b_geometry.csv`, `instr_agreement.csv`, `reports/G2_RESULTS.md`. Every number
below has a MANIFEST id and a script behind it.

---

## 1. The two variants are not comparable, because one of them produces no data

| variant | no answer (phrase coding) | trials coded | legacy vs phrase agreement |
|---|---|---|---|
| **as-written**, L48 | **0.991** | 8 of 920 | 1.000 on 8 trials (0.9% of them) |
| **as-written**, L50 | **0.995** | 5 of 920 | 1.000 on 5 trials (0.5%) |
| **reconstruction**, L48 | **0.020** | 902 of 920 | 0.9989 on 902 (98.0%) |
| **reconstruction**, L50 | **0.020** | 902 of 920 | 0.9989 on 902 (98.0%) |
| reconstruction, Qwen L17 | 0.111 | 391 of 440 | 1.000 on 391 (88.9%) |

The as-written arm's agreement of 1.000 is computed on **eight trials**. Quoted
without its denominator it would read as perfect reliability; it is the opposite.
This is why every agreement figure in this project carries `n_both_coded` and its
share.

**Run exactly as committed, the probe pipeline yields nothing to fit a curve to.**
That is the same finding G2 made on the unsteered model (88.3% no answer) now
reproduced under steering at every dose.

## 2. Layer 48 shows no dose-response; layer 50 does

Llama, reconstruction, probe direction, lottery, switching point by dose
(dose in units of the median residual-stream norm; legacy and phrase codings agree
to 0.3 tokens throughout, so one column is shown):

| dose | L48 | L50 |
|---|---|---|
| 0.000 | 104.1 | 104.1 |
| 0.055 | 105.0 | 104.8 |
| 0.109 | 105.7 | 105.1 |
| 0.164 | 105.9 | 107.4 |
| 0.232 | 107.1 | **122.9** |
| 0.250 | 105.7 | **123.8** |
| 0.327 | 106.7 | **125.4** |
| 0.500 | 105.9 | **155.3** |
| 1.000 | 104.3 | **124.5** |

**Layer 48 moves the switching point by at most 3 tokens across a 60-fold range of
dose — under one grid step.** The layer the paper's probe figures steer does not
move the choice curve.

**Layer 50 moves by about 50 tokens, ten grid steps, and does so non-monotonically**:
it rises to 155.3 at dose 0.5 and falls back to 124.5 at dose 1.0. A preference
dial that reverses at high dose is not a dial.

## 3. The readout is not a substitute for sampled generation

The instrument check (`instr_agreement.csv`) compared the logit readout with free
generation at the same grid points. The bar was crossings within one grid step and
a slope in 0.8–1.2:

| coding | readout crossing | free crossing | gap | slope | r | agrees |
|---|---|---|---|---|---|---|
| legacy | 234.1 | 62.6 | 34 steps | 0.751 | 0.26 | no |
| strict | 234.1 | 110.0 | 25 steps | 0.268 | 0.16 | no |
| phrase | 234.1 | 63.2 | 34 steps | 0.959 | 0.31 | no |

**Sampled generation is primary and the readout is secondary**, per the standing
rule. The readout's own crossing at 233.9 also never appears on the sampled grid,
which is why the `readout` column in §2 is empty at every non-zero dose.

## 4. What the probe direction is, geometrically

Cosines against a null of 1/sqrt(8192) = 0.011 (`g4b_geometry.csv`):

| pair | L48 | L50 | multiples of null |
|---|---|---|---|
| probe × **readout gradient** | +0.029 | +0.031 | 2.6–2.8× |
| probe × reward probe | −0.054 | −0.076 | 4.9–6.8× |
| probe × **difference-of-means** (CAA / ActAdd) | +0.188 | +0.192 | **17×** |
| probe × first PCA (RepE / LAT) | +0.101 | +0.109 | 9–10× |
| probe × ridge on log n | +0.113 | +0.096 | 9–10× |
| gradient × gradient (both orders) | +0.638 | +0.642 | 58× |

The probe is **nearly orthogonal to the answer-readout gradient** and closest to the
difference-of-means direction. On Qwen L17 the payoff relationship is far stronger:
a probe for "payoff above the grid median" is **1.000 accurate**, and
cos(choice, reward) = **+0.590**, about 35× that model's null.

About a third of the gradient anchor is format rather than readout: its
`legacy_one_format` and `both_orders` versions correlate at 0.64, not 1.0.

*These gradients are the Friday-session version, computed here because Track B's
B3.1 was being rebuilt. They are a second measurement of the same defined quantity
and are to be reconciled with B3.1, not treated as it.*

## 5. Recommendation for the probe figures

Applying the default the authors set: **the PDF reports the reconstruction, and
legacy probe figures that were not rebuilt are removed.**

| figure | recommendation | why |
|---|---|---|
| Figs. 9, 10, 13, 14 (L48 dose-response) | **drop** | §2: no dose-response exists at L48 under a rebuilt probe. Reporting a rebuilt null in place of a published effect would be a different claim, not a correction. |
| Figs. 11, 12, 15, 16 (probe-score tracking) | **drop** | provenance unverifiable (`PROVENANCE.md`); the shipped script cannot produce the shipped numbers |
| Figs. 17, 18 (layer comparison) | **replace** | §2 supports a layer-48/layer-50 difference, but as *non-monotone* movement at L50 against none at L48 — not the published monotone pair |
| Fig. 4 (pipeline schematic) | **replace** | it depicts `apply_during_generation`, which the released hook does not do |
| Fig. 6 (target vs achieved) | **replace** | regression to the baseline mean, per the review and S1.5 |
| Qwen replication (Fig. 19 if present) | **replace** | reconstruction works on Qwen (11% no answer) and shows the payoff relationship in §4 |

**What replaces them.** One figure of the reconstruction dose-response at both
layers, with no-answer rates and coding agreement in the caption; one table of the
§4 cosines; and a statement that the released code does not reproduce the original
runs.

## 6. What this memo does not settle

* **G5b's creativity arm** is still generating (~4 h) and its judging runs with
  **three of five** judges — `deepseek-v4-pro` and `kimi-k2.6` have no credentials
  here. Any G5b judge figure is a three-judge figure.
* **The excess-over-staircase statistic** returns 0.0 with no interval for the
  as-written arm (too few coded trials) and is only defined for Qwen at low dose.
  It is reported where valid and omitted where not, rather than presented as zero
  effect.
* **The neutral-label question is lottery-specific**: on the ultimatum two framings
  track free generation inside the 0.8–1.2 band; on the lottery none does.
* **Track B's B3.1** has not landed, so §4's gradients remain the duplicate.
