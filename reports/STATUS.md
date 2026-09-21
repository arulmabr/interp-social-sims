# STATUS.md

Rewritten by `cv_bench/monitor.py` every 10 minutes. Cycle 1.

**2026-09-21 09:51 UTC** — cutoff Thu 24 Sept 06:00 UTC, **68.1 h remaining**.

**GPU-hours consumed by this project so far: 1.02** of the 400 approved.


## Live jobs

| job | name | state | elapsed | left | reason |
|---|---|---|---|---|---|
| 23379475 | g2_llama | RUNNING | 21:39 | 11:38:21 | node3807 |

## Recent jobs

| job | name | state | elapsed | exit |
|---|---|---|---|---|
| 23379474 | g2_qwen | COMPLETED | 00:09:28 | 0:0 |
| 23379475 | g2_llama | RUNNING | 00:21:40 | 0:0 |
| 23379816 | bench70b | COMPLETED | 00:04:10 | 0:0 |

## Outputs


### bench70b — complete

| output | rows | expected |
|---|---:|---:|
| `bench/bench_llama.json` | 1 | — |

### g2_llama — INCOMPLETE

| output | rows | expected |
|---|---:|---:|
| `g2_lambda0/llama_legacy_lottery.jsonl` | 1280 | 1800 |
| `g2_lambda0/llama_legacy_ultimatum.jsonl` | — | 760 |
| `g2_lambda0/llama_chat_lottery.jsonl` | — | 1800 |
| `g2_lambda0/llama_chat_ultimatum.jsonl` | — | 760 |
| `g2_lambda0/llama_chat64_lottery.jsonl` | — | 1800 |
| `g2_lambda0/llama_chat64_ultimatum.jsonl` | — | 760 |

| file | n | legacy vs strict agreement | blank gens | constant? |
|---|---:|---:|---:|---|
| `llama_legacy_lottery.jsonl` | 1280 | 0.9969 | 591 | no |

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
