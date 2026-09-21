# SCHEDULE.md

Required by the 22 Sept amendment. **Cutoff: Thu 24 Sept 06:00 UTC**, 68 h from writing.
Estimates are `load + items ÷ measured throughput, × 1.5`, plus the queue wait Slurm predicts,
plus dependencies. Posted, then started without waiting for approval; veto anything.

Rewritten whenever a measurement changes it. Live job state is in `reports/STATUS.md`, rewritten
every 10 minutes by `cv_bench/monitor.py` under tmux.

---

## 1. Measured throughput — no estimate below is guessed

`meta-llama/Llama-3.3-70B-Instruct`, bf16, **2 × A100 80 GB PCIe**, `ou_bcs_low`
(`results/S/.../bench/bench_llama.json`, job 23379816, 8-minute benchmark):

| quantity | measured |
|---|---:|
| model load from the lab share | **185 s** |
| generation, 12 new tokens (legacy settings) | **0.93 /s** |
| generation, 64 new tokens | **0.40 /s** |
| readout, one forward pass, unbatched | **6.35 /s** |
| readout, batch 8 / 16 / 32 | 10.9 / **11.6** / 12.0 /s |
| LoRA seconds per step | **not available — `peft` is not installed** |

`Qwen/Qwen2-7B-Instruct`, 1 GPU: load 30 s, **6.90 gen/s** (from the completed `g2_qwen`).
`Qwen2.5-0.5B-Instruct` on CPU is used for tests only.

**Two S2.1 acceptance criteria fail on the 70B and gate everything readout-based** (§4).

## 2. What the account may actually run

Read, not guessed. QOS `ou_bcs_low` would cap a user at 64 GPUs / 256 submitted jobs, but this
account's association permits only QOS **`normal`** on that partition, which carries **no GPU cap**;
the association cap is `MaxSubmit=500` and `MaxArraySize` is 25,000.

**So Slurm is not the binding constraint — the budget is, and barely.** 400 GPU-hours over 68 hours
is 5.9 GPUs sustained. But the whole remaining V/G/S3 list below costs **≈ 60 GPU-hours**. The real
constraints are wall-clock to the cutoff and how fast each job's code can be written and validated.
Both G2 jobs started within 17 s of submission, so queue wait on `ou_bcs_low` is currently ~0.

**GPUs actually obtained so far: 3 concurrently** (2 for `g2_llama`, 1 for `g2_qwen`), plus 2 for the
benchmark. Consumed to date: **≈ 1.3 GPU-hours of 400**.

## 3. The schedule

"Value" is value to the Sept 25 paper per GPU-hour, which is the amendment's ordering rule after G2
and G4.

| task | depends on | GPUs | est. run | est. finish (UTC) | GPU-h | when |
|---|---|---:|---:|---|---:|---|
| **G2** llama λ=0, 3 arms | — | 2 | 3.4 h | **21 Sept 13:2​0** | 6.8 | **running** |
| G2 qwen | — | 1 | 0.16 h | done | 0.2 | **done** |
| **G2-analysis** switching points, rates, coding agreement | G2 | 0 (CPU array) | 0.2 h | 21 Sept 14:00 | 0 | **run now** |
| **S2.1-fix** revise the stem, settle batch disagreement | benchmark | 2 | 0.5 h | 21 Sept 15:00 | 1.0 | **run now — blocks G3/G4** |
| **G4a** probe rebuild, legacy recipe as written | S2.1-fix | 2 | 0.6 h | 21 Sept 16:00 | 1.2 | **run now** |
| **G4b** probe rebuild with chat template (reconstruction) | S2.1-fix | 2 | 0.6 h | 21 Sept 17:00 | 1.2 | **run now** |
| **G4c** dose-response generation arm, 5 doses × 2 layers, both games | G4a/b | 2 × 3 replicas | 4.0 h | 21 Sept 21:00 | 24.0 | **run now** |
| **G3** S3.4 label-neutral test, readout only | S2.1-fix | 2 | 0.4 h | 21 Sept 18:00 | 0.8 | **run now** |
| **G5** local open-SAE steering at the two published doses | G2 | 2 | 1.3 h | 22 Sept 00:00 | 2.6 | **run now** |
| **S3.1** difference-of-means and PCA directions, cosine matrix | G4a/b | 2 | 0.8 h | 22 Sept 02:00 | 1.6 | **run now** |
| **S3.2** position and layer ablation (48 vs 50, last / all_prompt / legacy_ramp) | S3.1 | 2 | 1.0 h | 22 Sept 04:00 | 2.0 | **run now** |
| **S3.3** SAE ablation and attribution over 65,536 features | G5 | 2 | 1.5 h | 22 Sept 07:00 | 3.0 | **run now** |
| **S3.5** temperature sweep + five-judge rescoring | — | 2 | 1.0 h | — | 2.0 | **blocked — paid API, rule 7 unchanged** |
| V1 Fig. 5 source search | — | 0 (CPU array) | 0.5 h | 21 Sept 14:00 | 0 | **run now** |
| V2 judge identities | — | 0 (CPU array) | 0.2 h | 21 Sept 14:00 | 0 | **run now** |
| W1–W6 patches | V1, V2, paper_src | 0 | — | — | 0 | run now, CPU |
| **Track B B0–B5** | — | — | — | — | — | **other session** — see §5 |

Sum of run-now GPU-hours: **≈ 44**, against a 400 cap. Everything on this list finishes well before
the cutoff, so nothing is deferred to Sat 26 Sept on time grounds.

## 4. Two blockers, both real

**S2.1's acceptance criteria fail on the 70B.** Both are plan requirements, not nice-to-haves:

| criterion | required | measured on the 70B | on Qwen2.5-0.5B (CPU, fp32) |
|---|---|---:|---:|
| valid answer mass | ≥ 0.98 | **0.371** (min 0.102) | 0.324 |
| batched vs unbatched logit diff | ≤ 1e-2 | **0.125** | 0.000 |

The mass failure means the stem `"My choice: "` does not concentrate probability on the two labels —
so the renormalised probability is being taken over a small and possibly unrepresentative slice. The
plan's instruction is explicit: *"otherwise revise the stem"*. The batch failure is almost certainly
bf16 plus left padding, since the same code is exact in fp32 on CPU; the fix is to compare in fp32 or
to run the readout unbatched, which at 6.35/s is affordable for everything on this list.

**`peft` is not installed**, so B3.2's LoRA anchors cannot run and `lora_seconds_per_step` is null
rather than estimated. Installing it is a one-line dependency addition, reported rather than made
silently.

## 5. Two items in the amendment that do not exist here

- **G4b and G6** are named as remaining tasks. `FRIDAY_PLAN.md` defines only **G1–G5**. I have used
  "G4a/G4b/G4c" above for the three parts G4 now has under amendment 9 — that is my labelling, not a
  claim to have found the author's G4b, and **G6 has no definition anywhere**. Tell me what it is and
  it gets scheduled.
- The cap "replaces the earlier 40 and 60". Only **40** was ever communicated to this session
  (`GATE_S0_RESPONSE.md` §1.2). No 60 exists in any document here.

## 6. Track B and the shared budget

Track B runs in the other session on `iclr-trackB`. **The 400 GPU-hour cap presumably covers both
sessions**, and neither can see the other's spend. `cv_bench/monitor.py` counts only the job names in
its registry, so it is currently counting this session's jobs alone. Two ways to make the cap real:
either the other session adopts the same monitor and registry, or one session owns the accounting and
the other reports to it. Until that is settled, **the number in `reports/STATUS.md` is this session's
spend, not the project's** — it is labelled that way.

## 7. What may enter the Sept 25 PDF

Per amendment item 6: only what is finished, verified and committed before the cutoff. A Track B
result additionally needs Gate B2 and Gate B3 passed, the label *"exploratory, selection split, not
pre-registered"*, and an author having read its report.

One thing already will not make it in its original form: the probe figures. `G2_legacy_format.md`
shows the committed legacy code path yields no answer on 88% of trials while the published data has
0% unparseable, so those figures cannot be regenerated from this repository. That is an author
decision, and it is on the critical path for W3 and W4.
