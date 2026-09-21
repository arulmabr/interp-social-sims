# V3_model_ids.md — which checkpoint each legacy stack names

Task V3 of `FRIDAY_PLAN.md`. Data: `results/S/s1/v3_model_ids.csv` (27 rows).
Script: `cv_bench/v3_model_ids.py`. Values as `MANIFEST.csv:V3.*`.
Read-only, CPU only, no network — nothing here contacted the Hugging Face hub.

---

## The stop condition does not trigger

> "If the legacy probe runs name `Llama-3.1-70B-Instruct`, stop and tell the authors before anything
> else."

**They do not.** `MANIFEST.csv:V3.stop_condition.legacy_probe_names_3_1_70B` = **false**.
`Llama-3.1-70B-Instruct` appears nowhere: not in `Probes/config.py`, not in any probe run record, not
in any other stack's code or records, and not at any commit on any branch
(`git log --all -S`, three patterns, **no hits**).

**The download is clear to proceed**, and G2 belongs on the 3.3 checkpoint.

The repository contains exactly four `Llama-3.1` strings, all the same thing
(`V3.bare_3_1_strings_in_code`):

```
SAE/scripts/run_open_sae_feature_inspection.py:1091   Llama-3.1-8B-Instruct-SAE-l19
SAE/scripts/run_open_sae_feature_inspection.py:1092   Llama-3.1-8B-Instruct-SAE-l19.pth
Revised Prompting/scripts/run_open_sae_feature_inspection.py:1091-1092   (identical copy)
```

They are a filename helper — `resolve_sae_filename()` maps an SAE repo id to the file inside it, and
covers the **8B** open SAE alongside the 70B one. No 8B model or SAE was run: no `SAE/runs/*`
metadata names either. This is dead code for a model the repo never used.

## The table

| stack | where the id is recorded | id | a real HF id? | coverage |
|---|---|---|---|---|
| **A** hosted Goodfire/EDSL | `cleaned/behavioral_games_combined.csv :: model.model` | `meta-llama/Llama-3.3-70B-Instruct` | yes | 9,040 rows (lottery + ultimatum) |
| **A** | `SAE/data/raw/creativity/…/baseline.csv :: model.model` | `meta-llama/Llama-3.3-70B-Instruct` | yes | creativity |
| **B** local vLLM | `cleaned/behavioral_games_combined.csv :: model.model` | `meta-llama/Llama-3.3-70B-Instruct` | yes | 18,720 rows |
| **B** | `Revised Prompting/runs_fp16/runs/*/run_manifest.json :: model` | `meta-llama/Llama-3.3-70B-Instruct` | yes | 4 manifests, bfloat16, TP 2 |
| **C** probe / Llama | `Probes/config.py :: ModelConfig.hf_id` | `meta-llama/Llama-3.3-70B-Instruct` | yes | **the only HF id for this arm** |
| **C** probe / Llama | `Probes/config.py :: ModelConfig.name` | `Llama-3.3-70B-Instruct` | **no** — display string | — |
| **C** probe / Llama | `Probes/raw_data/probe_results_final.json :: metadata.model` and `row.model` | `Llama-3.3-70B-Instruct` | **no** — display string | 14 figure keys, 45,302 rows |
| **C** probe / Qwen | `Probes/config.py :: ModelConfig.hf_id` | **`Qwen/Qwen2-7B-Instruct`** | yes | **the only HF id for this arm** |
| **C** probe / Qwen | `Probes/config.py :: ModelConfig.name` | `Qwen-2-7B-Instruct` | **no** — display string | — |
| **C** probe / Qwen | probe JSON `metadata.model` and `row.model` | `Qwen-2-7B-Instruct` | **no** — display string | 6 figure keys, 10,947 rows |
| **D** local open-SAE | `SAE/runs/*/open_sae_steering_metadata.json :: model_id`, `sae_repo` | `meta-llama/Llama-3.3-70B-Instruct` + `Goodfire/Llama-3.3-70B-Instruct-SAE-l50` | yes | 10 runs, 4-bit |

Every stack names the same model. Nothing contradicts the paper.

## Three caveats the paper should carry

**1. The probe run records do not independently attest the checkpoint.** They store
`ModelConfig.name`, a human-readable display string, not `hf_id`. Both fields live in the same
dataclass in `Probes/config.py`, so all 45,302 Llama rows and 10,947 Qwen rows are echoing the one file
that also supplies the id. If `hf_id` had been edited at any point, no run record would show it. The
evidence that the probe arms ran on 3.3 and on Qwen2 is a single line of configuration each, not a
logged fact. Stacks A, B and D do better: their records carry the id itself.

**2. No model revision is pinned anywhere.** No stack records a commit hash for the 70B, so the legacy
runs cannot be reproduced to the revision. G1 must record the revision it downloads, and the paper
should say the legacy runs' revision is unknown rather than imply otherwise.

**3. The SAE *is* pinned, and the pin is usable.** Both local open-SAE runs record the same snapshot
(`V3.sae_snapshot_paths`):

```
models--Goodfire--Llama-3.3-70B-Instruct-SAE-l50/
  snapshots/128ee921ecd1b8b3a87d776cbcc357c0855da134/Llama-3.3-70B-Instruct-SAE-l50.pt
```

G1 should fetch **revision `128ee921ecd1b8b3a87d776cbcc357c0855da134`** so the new SAE work matches
the logged runs exactly. (Only the path is recorded, so the revision is attested but the file's hash
is not; G1 hashes what it downloads.)

## The open question from GATE_S0_RESPONSE §1

> "For Claude Code to answer from logs, not the authors: the exact model id of the 'Qwen' arm."

**`Qwen/Qwen2-7B-Instruct`** — `Probes/config.py:34`, probe layer 17, layer sweep 12–24. The paper's
"Qwen-2-7B-Instruct" matches it, so **the paper is not wrong about the Qwen arm**.

The `Qwen2.5-7B-Instruct` on the lab share is a **different model** and must not be substituted for it.
Neither `Qwen/Qwen2-7B-Instruct` nor any Qwen2 checkpoint is on any storage I can reach, so the Qwen
replication cannot be re-run without a second download (~15 GB). That is not on the Friday critical
path: `FRIDAY_PLAN` G2–G5 are all on M4.

## What this unblocks

- **G1 may start.** `meta-llama/Llama-3.3-70B-Instruct` is the right target, confirmed by four
  independent stacks.
- **G2** runs on 3.3, and there is no second checkpoint to also run it on — V3's conditional
  ("and on 3.3 if that is a different one") does not apply.
- The complete `Llama-3.1-70B-Instruct` already on the share is **not** the paper's model and is not
  used.
