# STATUS.md

Rewritten by `cv_bench/monitor.py` every 10 minutes. Cycle 52.

**2026-09-22 09:01 UTC** — cutoff Thu 24 Sept 06:00 UTC, **45.0 h remaining**.

**GPU-hours consumed, both sessions, `sacct` on job names starting `cvb_`: 47.81** of the 400 approved.


## Live jobs

*none*

## Recent jobs

| job | name | state | elapsed | exit |
|---|---|---|---|---|
| 23432509 | cvb_g4_recon_L50 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23432941 | cvb_g4_recon_L48 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23432942 | cvb_g4_recon_L50 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23433099 | cvb_g4_recon_L48 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23433100 | cvb_g4_recon_L50 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23433101 | cvb_neutral2 | COMPLETED | 00:02:48 | 0:0 |
| 23435661 | cvb_neutral2 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23437068 | cvb_neutral2 | COMPLETED | 00:00:24 | 0:0 |
| 23437338 | cvb_neutral2 | CANCELLED by 234238 | 00:00:00 | 0:0 |
| 23437447 | cvb_g4_recon_L48 | COMPLETED | 02:13:58 | 0:0 |
| 23437448 | cvb_g4_recon_L50 | COMPLETED | 01:12:26 | 0:0 |
| 23437451 | cvb_neutral2 | COMPLETED | 00:34:32 | 0:0 |

## Outputs


### bench70b — complete

| output | rows | expected |
|---|---:|---:|
| `bench/bench_llama.json` | 1 | — |

### cvb_g4_as_wr_L48 — complete

| output | rows | expected |
|---|---:|---:|
| `g4/readout_as_written_L48.jsonl` | 2816 | — |
| `g4/sampled_as_written_L48.jsonl` | 678 | — |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `sampled_as_written_L48.jsonl` | 27120 | 0.9816 | 6385 | no |

### cvb_g4_as_wr_L50 — complete

| output | rows | expected |
|---|---:|---:|
| `g4/readout_as_written_L50.jsonl` | 2816 | — |
| `g4/sampled_as_written_L50.jsonl` | 678 | — |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `sampled_as_written_L50.jsonl` | 27120 | 0.9819 | 6798 | no |

### cvb_g4_recon_L48 — complete

| output | rows | expected |
|---|---:|---:|
| `g4/readout_reconstruction_L48.jsonl` | 4928 | — |
| `g4/sampled_reconstruction_L48.jsonl` | 894 | — |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `sampled_reconstruction_L48.jsonl` | 17800 | 0.6430 | 449 | no |

### cvb_g4_recon_L50 — complete

| output | rows | expected |
|---|---:|---:|
| `g4/readout_reconstruction_L50.jsonl` | 4928 | — |
| `g4/sampled_reconstruction_L50.jsonl` | 894 | — |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `sampled_reconstruction_L50.jsonl` | 17800 | 0.7071 | 449 | no |

### cvb_instr — complete

| output | rows | expected |
|---|---:|---:|
| `instr/norms_llama.jsonl` | 50 | 50 |
| `instr/readout_grid_llama.jsonl` | 128 | 128 |
| `instr/freegen_llama.jsonl` | 840 | 840 |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `freegen_llama.jsonl` | 840 | 0.0000 | 0 | no |

### cvb_neutral2 — complete

| output | rows | expected |
|---|---:|---:|
| `neutral/mass_llama.jsonl` | 344 | 344 |
| `neutral/free_llama.jsonl` | 640 | 640 |

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

## Automatic resubmissions

- `cvb_instr`: 2 of 2
- `cvb_neutral`: 2 of 2
- `cvb_g4_as_wr_L50`: 2 of 2
- `cvb_neutral2`: 1 of 2

## Stopped — needs a human

- **`cvb_neutral`** exhausted its retries.
