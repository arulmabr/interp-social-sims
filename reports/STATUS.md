# STATUS.md

Rewritten by `cv_bench/monitor.py` every 10 minutes. Cycle 3.

**2026-09-21 20:34 UTC** — cutoff Thu 24 Sept 06:00 UTC, **57.4 h remaining**.

**GPU-hours consumed, both sessions, `sacct` on job names starting `cvb_`: 3.62** of the 400 approved.


## Live jobs

| job | name | state | elapsed | left | reason |
|---|---|---|---|---|---|
| 23414443 | cvb_g4_recon_L50 | PENDING | 0:00 | 8:00:00 | (Dependency) |
| 23414442 | cvb_g4_recon_L48 | PENDING | 0:00 | 8:00:00 | (Dependency) |
| 23414441 | cvb_g4_as_wr_L50 | PENDING | 0:00 | 8:00:00 | (Dependency) |
| 23414440 | cvb_g4_as_wr_L48 | PENDING | 0:00 | 8:00:00 | (Dependency) |
| 23414439 | cvb_neutral | PENDING | 0:00 | 3:00:00 | (Dependency) |
| 23414416 | cvb_instr | RUNNING | 12:25 | 2:47:35 | node4309 |

## Recent jobs

| job | name | state | elapsed | exit |
|---|---|---|---|---|
| 23379474 | g2_qwen | COMPLETED | 00:09:28 | 0:0 |
| 23379475 | g2_llama | COMPLETED | 03:42:51 | 0:0 |
| 23379816 | bench70b | COMPLETED | 00:04:10 | 0:0 |
| 23412430 | cvb_instr | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23414416 | cvb_instr | RUNNING | 00:12:25 | 0:0 |

## Outputs


### bench70b — complete

| output | rows | expected |
|---|---:|---:|
| `bench/bench_llama.json` | 1 | — |

### cvb_g4_as_wr_L48 — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `g4/readout_as_written_L48.jsonl` | — | — |
| `g4/sampled_as_written_L48.jsonl` | — | — |

### cvb_g4_as_wr_L50 — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `g4/readout_as_written_L50.jsonl` | — | — |
| `g4/sampled_as_written_L50.jsonl` | — | — |

### cvb_g4_recon_L48 — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `g4/readout_reconstruction_L48.jsonl` | — | — |
| `g4/sampled_reconstruction_L48.jsonl` | — | — |

### cvb_g4_recon_L50 — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `g4/readout_reconstruction_L50.jsonl` | — | — |
| `g4/sampled_reconstruction_L50.jsonl` | — | — |

### cvb_instr — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `instr/norms_llama.jsonl` | 50 | 50 |
| `instr/readout_grid_llama.jsonl` | 128 | 128 |
| `instr/freegen_llama.jsonl` | 153 | 840 |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `norms_llama.jsonl` | 50 | 1.0000 | 50 | legacy/strict |
| `readout_grid_llama.jsonl` | 128 | 1.0000 | 128 | legacy/strict |
| `freegen_llama.jsonl` | 153 | 0.0000 | 0 | /strict |

### cvb_neutral — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `neutral/mass_llama.jsonl` | — | 400 |
| `neutral/free_llama.jsonl` | — | 640 |

### g2_llama — complete

| output | rows | expected |
|---|---:|---:|
| `g2_lambda0/llama_legacy_lottery.jsonl` | 1800 | 1800 |
| `g2_lambda0/llama_legacy_ultimatum.jsonl` | 760 | 760 |
| `g2_lambda0/llama_chat_lottery.jsonl` | 1800 | 1800 |
| `g2_lambda0/llama_chat_ultimatum.jsonl` | 760 | 760 |
| `g2_lambda0/llama_chat64_lottery.jsonl` | 1800 | 1800 |
| `g2_lambda0/llama_chat64_ultimatum.jsonl` | 760 | 760 |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `llama_legacy_lottery.jsonl` | 1800 | 0.9961 | 844 | no |
| `llama_legacy_ultimatum.jsonl` | 760 | 0.9842 | 176 | no |
| `llama_chat_lottery.jsonl` | 1800 | 1.0000 | 0 | no |
| `llama_chat_ultimatum.jsonl` | 760 | 1.0000 | 0 | legacy/strict |
| `llama_chat64_lottery.jsonl` | 1800 | 0.5906 | 0 | no |
| `llama_chat64_ultimatum.jsonl` | 760 | 1.0000 | 0 | legacy/strict |

### g2_qwen — complete

| output | rows | expected |
|---|---:|---:|
| `g2_lambda0/qwen_legacy_lottery.jsonl` | 840 | 840 |
| `g2_lambda0/qwen_legacy_ultimatum.jsonl` | 360 | 360 |
| `g2_lambda0/qwen_chat_lottery.jsonl` | 840 | 840 |
| `g2_lambda0/qwen_chat_ultimatum.jsonl` | 360 | 360 |
| `g2_lambda0/qwen_chat64_lottery.jsonl` | 840 | 840 |
| `g2_lambda0/qwen_chat64_ultimatum.jsonl` | 360 | 360 |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `qwen_legacy_lottery.jsonl` | 840 | 0.9976 | 0 | no |
| `qwen_legacy_ultimatum.jsonl` | 360 | 0.9778 | 26 | no |
| `qwen_chat_lottery.jsonl` | 840 | 1.0000 | 0 | no |
| `qwen_chat_ultimatum.jsonl` | 360 | 1.0000 | 0 | no |
| `qwen_chat64_lottery.jsonl` | 840 | 0.9738 | 0 | no |
| `qwen_chat64_ultimatum.jsonl` | 360 | 0.9944 | 0 | no |
