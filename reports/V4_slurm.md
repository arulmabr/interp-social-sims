# V4_slurm.md — what this account may run, and the smallest allocation that holds M4

Task V4 of `FRIDAY_PLAN.md`, moved ahead by amendment 1. Values as `MANIFEST.csv:V4.*`.
Nothing here uses an entitlement the account did not already have.

---

## 1. Entitlements

Slurm associations (`sacctmgr show assoc user=guna23`), cluster `eofe7`:

| account | default partition | QOS |
|---|---|---|
| `mit_amf_advanced_cpu` | `mit_normal` | `mit_amf_advanced_cpu`, `normal` |
| `mit_amf_advanced_gpu` | `mit_normal_gpu` | `mit_amf_advanced_gpu`, `normal` |
| `mit_general` | — (any) | `normal` |

Partitions reachable through group membership (`AllowGroups` intersected with `id -Gn`):

| partition | GPUs | time limit | QOS accepted |
|---|---|---|---|
| **`ou_bcs_low`** | h100 ×4 and a100 ×8 nodes | **1-00:00:00** | `ou_bcs_low`, `ou_bcs_high`, `pi_satra`, `unlimited`, **`normal`** |
| `ou_bcs_high` | h100 ×4 | 4:00:00 | `ou_bcs_high`, `unlimited`, `normal` |
| `ou_bcs_normal` | h100 ×4, a100 ×8 | 1-00:00:00 | `ou_bcs_normal`, `unlimited`, `normal` |
| `mit_normal`, `mit_normal_gpu`, `mit_quicktest`, `mit_preemptable` | mixed | — | all |

**Use `ou_bcs_low` with `--account=mit_general --qos=normal`.** That combination is what the standing
instruction for this project specifies, it is accepted by the partition's `AllowQos`, and it was
confirmed working by the probe job below. Its 24-hour limit is the longest available and comfortably
covers G2–G5.

`mit_normal_gpu` currently holds **23 of my own pending or running jobs** from an unrelated project.
Nothing in this work touches that partition or those jobs.

## 2. GPU memory, measured

Slurm does not record per-GPU memory, and `AvailableFeatures` on the relevant nodes is only
`rocky8`/`numa_node`. So a three-minute one-GPU probe was submitted to `ou_bcs_low`
(job 23379050, node3805):

```
index, name, memory.total [MiB], driver_version, compute_cap
0, NVIDIA A100 80GB PCIe, 81920 MiB, 590.48.01, 8.0
```

**A100s on this partition are 80 GB**, not 40 GB. H100 nodes are the usual 80 GB SXM.
`V4.gpu_memory_mib.a100` = 81920.

## 3. The smallest allocation that holds M4 in bf16

G1 verified the checkpoint at **141.12 GB** across 30 safetensors shards
(`results/S/g1_download_verification.json`).

| allocation | memory | verdict |
|---|---|---|
| 1 × 80 GB | 80 GB | no — half the weights |
| **2 × 80 GB** | **160 GB** | **yes** — 141 GB of weights leaves ~19 GB for activations and KV cache |
| 4 × 80 GB | 320 GB | comfortable; needed only if a job holds gradients or a LoRA |

`V4.min_gpus_for_m4_bf16` = 2.

Nineteen gigabytes of headroom is ample for G2 and G3, which are short prompts — the legacy lottery
prompt is under 100 tokens and generation is capped at 12 — but it is not generous. Two practical
points for the job scripts:

- request `--gres=gpu:2` and let `device_map="auto"` shard across them; on a node with 4 or 8 GPUs,
  asking for exactly 2 queues faster than asking for a whole node;
- an a100 node has 8 GPUs and ~2 TB of host RAM, so `--mem` should be set explicitly (128 GB is
  plenty) rather than inheriting a per-node default.

## 4. Job template for G2–G5

```bash
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --requeue
```

`--requeue` is there because `ou_bcs_low` is the low-priority partition and jobs can be preempted;
every G-task must checkpoint and be safe to re-run. The 40 GPU-hour budget the authors approved is
measured against `--gres=gpu:2`, so it buys roughly 20 hours of wall clock across G2–G5.

## 5. Budget note

At 2 GPUs, the approved 40 GPU-hours is about 20 hours of wall clock. G2's own cost is small: the
legacy lottery grid is 45 reward levels × 40 agents = 1,800 generations of 12 tokens per condition, and
G2 runs four conditions (raw strings and chat template, two games). That is well under an hour of
generation on two A100s once the weights are resident. Loading 141 GB from the lab share over NFS is
likely to dominate, which is an argument for doing G2 and G3 in **one** allocation rather than two.
