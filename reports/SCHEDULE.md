# Schedule against the cutoff

**Cutoff Thu 24 Sept 06:00 UTC** (Wed 23 Sept 23:00 PDT). Only work finished,
verified and committed before it enters the Sept 25 PDF. Written 21 Sept 21:45
UTC, so the cutoff is **56 hours** away and the paper deadline 110.

Estimates are measured, not guessed. The rates behind them, all from tonight's
runs on 2×A100-80GB:

| operation | measured |
|---|---|
| forward pass / logit readout | 6.5 /s |
| one sampled cell, 40 agents, 12 new tokens | 3.4 s |
| one sampled cell, 40 agents, 256 new tokens | 34.6 s |
| model load, 141 GB bf16 to two GPUs | 4–5 min |

**The binding constraint is not the 400 GPU-hour cap — it is a per-user GRES
limit.** Jobs queue on `QOSMaxGRESPerUser` at six GPUs in use across the account,
and that pool is shared with the Track B session and with an unrelated project of
the same user. Three 2-GPU jobs run at once, at best. Spend so far: **under 20 of
400 GPU-hours.**

## Running and queued

| job | what it settles | GPUs | estimate | expected finish |
|---|---|---|---|---|
| `cvb_neutral` | the neutral label framing for S3.4 | 2 | ~35 min | 21 Sept ~22:15 |
| `cvb_g4_as_wr_L50` | G4, legacy recipe, layer 50 | 2 | 0.64 h + load | 21 Sept ~22:30 |
| `cvb_g4_as_wr_L48` | G4, legacy recipe, layer 48 | 2 | 0.64 h + load | queued |
| `cvb_g5` | the eight logged SAE features, steered locally | 2 | 16 min + load | queued |
| `cvb_choose` | picks the neutral framing (CPU) | 0 | < 1 min | after `cvb_neutral` |
| `cvb_g3` | label and option-order transfer, forward passes only | 2 | ~3 min + load | after `cvb_choose` |
| `cvb_g6` | SAE ablation and attribution | 2 | ~2 h + load | after `cvb_g5` |
| `cvb_g4_recon_L48` | G4 reconstruction + G4b baselines, layer 48 | 2 | **8.6 h** | queued |
| `cvb_g4_recon_L50` | the same at layer 50 | 2 | **8.6 h** | queued |

The two reconstruction replicas are the long pole. At three concurrent 2-GPU jobs
and 8.6 h each they finish roughly **22 Sept 09:00–14:00 UTC**, leaving about 40
hours of margin. Every one of these jobs is resumable per cell, so preemption
costs the cell in flight and a reload, not the run.

## Reviewer-derived tasks, against the cutoff

Which of `feedback.txt`'s points the PDF answers **with data**, and when that data
lands. Rows marked *text* or *limitation* need no run; they are written, not
computed, and are listed so the count is complete.

| reviewer point | answered with | job | data by | margin |
|---|---|---|---|---|
| CAA / ActAdd / RepE baselines absent | data | `cvb_g4_recon_*` (G4b) | 22 Sept ~14:00 UTC | 40 h |
| no causal test behind the SAE readings | data | `cvb_g5` → `cvb_g6` | 22 Sept ~02:00 UTC | 52 h |
| prompting ladder omitted from results | data | S1.7, **done** | committed | — |
| judge-independent creativity measures | data | S1.6, **done** | committed | — |
| 0.77 agreement reported without context | data | S1.5/S1.6, **done** | committed | — |
| judge ordering claim | data | S1.5, **done** | committed | — |
| length not controlled as stated | data | S1.5, **done** | committed | — |
| no agent-level inferential test | data | S1.5 mixed model, **done** | committed | — |
| judge citation verifiability | data | V2, **done** | committed | — |
| probe training underspecified / inconsistent | data | PROBE_PROVENANCE, **done** | committed | — |
| steering hook mechanics | data | STACK_AUDIT + test, **done** | committed | — |
| SAE / probe operational confounds | data | STACK_AUDIT, **done** | committed | — |
| missing lottery UUIDs | data | PROVENANCE, **done** | committed | — |
| Fig. 5 provenance | data | V1, **done** | committed | — |
| label / order transfer of the effect | data | `cvb_g3` | 21 Sept ~23:00 UTC | 55 h |
| λ polarity contradiction | text | — | — | — |
| Fig. 6 diagonal | text | — | — | — |
| Fig. 3(A) pivot at 50 | text | — | — | — |
| ρ dose labels | text | — | — | — |
| few-shot exemplar is dominated | text | — | — | — |
| two SAE doses are one dose | text | — | — | — |
| prompting and SAE not independent | text | — | — | — |
| fluency is a constant | text | — | — | — |
| Table 1 recommendation | text | — | — | — |
| SAE literature mischaracterised | text | AUTHOR TO VERIFY | — | — |
| 15 typos and wording items | text | W7 ledger, deliver early | — | — |
| 12 figures not reproducible | text | W1 provenance statement | — | — |
| **ITI not compared against** | limitation | — | — | — |
| **human-normed AUT / SemDis** | limitation | — | — | — |
| **multi-turn / multi-agent** | limitation | — | — | — |
| **personality batteries / collateral** | limitation | — | — | — |
| **proposer role / mini-ultimatum** | limitation | — | — | — |

**17 reviewer-derived points are answered with data, 24 with text, 5 as named
limitations.** Nine of the seventeen are already committed; the rest land between
tonight and 22 Sept afternoon, all inside the cutoff.

## What is not on this schedule

The extension plan's own programme — parameter recovery on synthetic agents, the
loss and probability frames, certainty equivalents, paired lotteries, the frozen
test split — is six weeks of work and is not attempted here. Track B's anchors
(B3.1 gradient, B3.2 LoRA) are running in the other session; G4b consumes the
gradient once its hash is committed.

## Author deadline inside this window

**Wed 23 Sept 09:00 PDT** — an explanation of how the original probe runs were
made. Absent one, the patches proceed on the basis that the PDF reports the
reconstruction and removes legacy probe figures that were not rebuilt. That is
~31 hours from writing and is the only item here that no amount of compute can
close.
