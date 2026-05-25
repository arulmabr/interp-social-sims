# Strong Prompting Baselines (Few-shot + Chain-of-Thought)

Strengthened **prompting baselines** — few-shot and chain-of-thought (CoT) — for the
social-simulation steering experiments (lottery, ultimatum, divergent creativity,
product innovation) on **Llama-3.3-70B-Instruct**.

These were built to answer a reviewer request: *"strengthen the prompting baseline
with few-shot / CoT examples, so mechanistic steering is compared against robust
prompting rather than simple persona instructions."* The goal is an apples-to-apples,
recognizable-from-the-literature prompting baseline to put head-to-head against
SAE-feature and probe steering.

It reuses the `GameSpec` / EDSL adapter from the companion
[`social-sim-open-sae`](https://github.com/) platform, and adds a self-hosted
vLLM generation path so the runs use the **true full-precision (bf16) non-Turbo**
model rather than the FP8 "Turbo" build that hosted APIs serve.

---

## What's here

```
games/                              strengthened-prompting GameSpecs
  safe_risky_strong_prompting.py    lottery (risk)        — free-text + Final-answer parser
  ultimatum_strong_prompting.py     ultimatum (altruism)  — free-text + Final-answer parser
  creativity_brick_strong_prompting.py    divergent creativity (brick) — list output
  creativity_stapler_strong_prompting.py  product innovation (stapler) — list output
scripts/
  run_local_vllm_generation.py      self-hosted vLLM runner (bf16) -> response_units.csv
  build_brick_exemplars.py          extract human-rated brick few-shot exemplars from Ocsai
  run_edsl_social_simulation.py     EDSL/hosted-API runner (from social-sim-open-sae)
  run_open_sae_feature_inspection.py  Open-SAE feature inspection (from social-sim-open-sae)
  rerun_creativity_torrance_eval.py   GPT Torrance creativity judge (from social-sim-open-sae)
social_sim_open_sae/                core GameSpec + EDSL adapter package (vendored)
data/
  brick_exemplars.json              top human-originality brick exemplars (few-shot demos)
  ocsai_brick_aut.jsonl             brick subset of the Ocsai AUT data (provenance)
  OCSAI_LICENSE.txt / OCSAI_SOURCE.txt   attribution for the vendored data (MIT)
runpod/run_fp16_strong_prompting.sh RunPod recipe for the bf16 run
requirements.txt
runs_fp16/                          outputs from the bf16 run (see "Outputs")
```

---

## Experimental design

**Tasks.** Two preference games — lottery (risk) and ultimatum (altruism), each swept
over a reward/offer parameter with 40 agents — and two capability tasks — divergent
creativity (alternative uses for a brick) and product innovation (improve a stapler).

**Prompting ladder (conditions).** Each preference game runs:

| condition | what it is |
|---|---|
| `baseline` | neutral free-text elicitation |
| `persona` | one-line persona instruction (the *original* weak baseline, re-run here) |
| `cot` | zero-shot chain-of-thought ("think step by step", Kojima et al. 2022) |
| `fewshot` | few-shot demonstrations, no reasoning in demos (Wei et al. 2022) |
| `fewshot_cot_dose000…100` | **few-shot CoT** at a graded "dose" — the fraction of demonstrations exhibiting the target disposition (risk-seeking / accept-leaning). dose100 = headline strong baseline; the family traces a **prompting dose-response** to overlay on the probe/SAE λ/α curves |

**Canonical, not framework-specific.** CoT is implemented as a single completion
(reasoning → `Final answer: X`) that is then parsed — standard Wei/Kojima CoT, not an
EDSL-specific two-question mechanism. Preference games use `free_text` + a
`Final answer:` regex parser so every condition shares one elicitation format.

**Creativity (a deliberate asymmetry).**
- **Brick (divergent creativity):** few-shot exemplars are *human* Alternative Uses Task
  responses for "brick", selected by *human* originality ratings from the
  [Ocsai](https://github.com/massivetexts/ocsai) dataset (MIT; Organisciak et al. 2023).
  Selecting exemplars by human ratings keeps exemplar selection **independent of the
  GPT Torrance judge**, avoiding selection/evaluation circularity. Rebuild with
  `python scripts/build_brick_exemplars.py`.
- **Stapler (product innovation):** **no few-shot** (no comparable public human-rated
  product-improvement dataset exists), so it uses persona + plan-then-list CoT only.
  This asymmetry is intentional and should be disclosed in the paper.

Creativity tasks keep a `list` output so the downstream GPT Torrance judge scores a
clean list.

---

## How to run

### Setup
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # EDSL + analysis stack
```

### Smoke test (no GPU, no network)
```bash
python scripts/run_local_vllm_generation.py \
  --game-module games/safe_risky_strong_prompting.py \
  --output-dir /tmp/dry --dry-run --agents 2 --limit-scenarios 1
```
`--dry-run` builds and dumps the prompts (persona, few-shot block, CoT) without loading a model.

### Option A — hosted API (quick, but FP8/Turbo model)
Via the EDSL runner against any supported provider. **Caveat:** Expected Parrot,
DeepInfra, Together, etc. only serve the **FP8 "Turbo"** build of Llama-3.3-70B. Fine
for a relative comparison; not full precision.

### Option B — self-hosted vLLM (true bf16, non-Turbo) — recommended
On a GPU box (**2× H100/A100 80GB** for bf16 70B). With `HF_TOKEN` set (gated access to
`meta-llama/Llama-3.3-70B-Instruct`):
```bash
pip install vllm jinja2

export HF_HUB_OFFLINE=1          # see Gotchas
export VLLM_USE_DEEP_GEMM=0      # see Gotchas

python scripts/run_local_vllm_generation.py \
  --game-module games/safe_risky_strong_prompting.py \
  --output-dir runs/safe_risky_full \
  --dtype bfloat16 --tensor-parallel-size 2 \
  --temperature 0.7 --max-tokens 512
```
Use `--max-tokens 1536` for the creativity games. `runpod/run_fp16_strong_prompting.sh`
wraps all four games.

### Gotchas (hard-won; needed for the bf16 run to work)
- **`VLLM_USE_DEEP_GEMM=0`** — on Hopper, vLLM auto-enables FP8 DeepGEMM kernels and
  fails (and would not be true bf16). Disable to force bf16 GEMM.
- **`HF_HUB_OFFLINE=1`** — the Llama-3.3-70B repo has **no `tokenizer.model`**; vLLM's
  online check for it 404/401s and aborts model load. Offline mode uses the cached
  `tokenizer.json` (which is all it needs).
- **Download skipping `original/`** — the HF repo also ships the original Meta
  checkpoint (`original/*.pth`, ~140 GB extra). Pull with
  `ignore_patterns=["original/*", "*.pth", "*.gguf"]`.
- **`--temperature > 0`** — the 40 agents are samples; greedy decoding makes them
  identical. Keep temperature constant across conditions (it's the same for all here).

---

## Outputs

Per game, `<game>_full/`:
- `response_units.csv` / `.jsonl` — one row per agent × condition × scenario:
  `condition, reward, system_prompt, user_prompt, answer_text` (full CoT response), …
- `behavior_units.csv` — *(preference games)* parsed choice per agent
  (`choice_risky` / `accept_offer`).
- `behavior_summary.csv` — *(preference games)* aggregated **dose-response**:
  `task, condition, reward, metric, mean, count`.
- `run_manifest.json` — model, dtype, temperature, agent count, etc.

The committed `runs_fp16/` outputs are from a bf16 run on 2× H100 (40 agents):
safe_risky 12,600 records, ultimatum 6,120, creativity_brick 200, creativity_stapler 160.

---

## Results (bf16, 40 agents) — summary

Switch point = reward/offer where P = 0.5.

**Lottery (safe = 50; EV-neutral ≈ 100):** baseline ≈ 103 (risk-neutral). Strong
few-shot+CoT does **not** induce risk-*seeking* (doses 25–100 stay ~97–101); only
risk-*aversion* is inducible (averse demos never switch; `cot` pushes the switch to
~140, i.e. more EV-driven/cautious). Prompting does not give graded risk-seeking control.

**Ultimatum (offer out of 100):** few-shot+CoT **does** control the acceptance
threshold — from ~10 (acceptant) to ~40 (fairness-enforcing), dose-dependent (somewhat
bimodal). A genuinely strong baseline.

**Creativity:** brick (200) + stapler (160) responses are collected; creativity is
scored separately by the GPT Torrance judge (`scripts/rerun_creativity_torrance_eval.py`).

---

## Repo / data notes
- **File sizes:** the largest single file is ~47 MB (`safe_risky_full/response_units.jsonl`);
  every file is well under GitHub's 100 MB hard limit, so a normal `git push` works — no
  Git LFS needed. (GitHub shows a soft warning above 50 MB; nothing here crosses it.) The
  `.jsonl` files duplicate the `.csv` files, so you can delete them to roughly halve the
  size if you want a leaner repo. There's also an empty `runs_fp16/runs/smoke/` you can remove.
- **Vendored data:** `data/ocsai_brick_aut.jsonl` and `data/brick_exemplars.json` are
  derived from the Ocsai project (MIT) — see `data/OCSAI_LICENSE.txt` / `OCSAI_SOURCE.txt`.

## Attribution
- Few-shot CoT: Wei et al. 2022; zero-shot CoT: Kojima et al. 2022.
- Brick exemplars / human AUT originality: Organisciak, Acar, Dumas & Berthiaume (2023),
  *Beyond semantic distance*, Thinking Skills and Creativity 49:101356 (Ocsai, MIT).
- Core platform: the `social-sim-open-sae` EDSL + Open-SAE repository.
