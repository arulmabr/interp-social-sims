# STACK_AUDIT.md — S0.3

Every inference path in the repository. All settings are read from logged run records or from the code
that produced them, never from the paper. Values with a `MANIFEST.csv` id are recomputed by
`cv_bench/s0_recon.py`.

**There are three mutually incompatible stacks.** Every cross-stack comparison in the paper — Table 1,
§5, and any sentence that places prompting, SAE steering and probe steering on one scale — is confounded
by service, precision, temperature, prompt format, chat template and intervention semantics. The table
below is the evidence for that.

| | **Stack A** hosted Goodfire | **Stack B** local vLLM | **Stack C** local HF probe | **Stack D** local open-SAE |
|---|---|---|---|---|
| serves | Fig. 3, Fig. 5, §4.1 features | the unpublished prompting ladder | Figs. 4, 6, 9–18 | twelve reruns, unpublished |
| service | `goodfire` via EDSL | vLLM, tensor-parallel 2 | HF `transformers`, `device_map="auto"` | HF + `Goodfire/...SAE-l50.pt` |
| model | `meta-llama/Llama-3.3-70B-Instruct` | same | same, and `Qwen/Qwen2-7B-Instruct` | same |
| precision | not exposed | bfloat16 | bfloat16 | bfloat16 base, **4-bit** load |
| chat template | applied by EDSL | applied by EDSL | **not applied** | applied |
| system prompt | `Your traits: {...}` | `Your traits: {...}` | **none** | inherited from Stack A prompts |
| temperature | **0.5** (1.0 for `high_temperature`) | **0.7** | **0.7** choice / **0.9** creativity | **greedy**, `do_sample=False` |
| top-p | 1 | 1.0 | 0.95 | n/a |
| max tokens | 1000 | from manifest | 12 choice / 1024 creativity | 256 |
| readout | sampled text, EDSL multiple-choice parse | sampled text | sampled text, regex on last label match | sampled text, label parse |
| intervention | Goodfire `nudge`, no position mask | prompt only | `h += λ·ŵ` on part of the prompt | SAE `clamp_min` at `last_token` |
| layer | 50 | — | 48 (Llama), 17 (Qwen) | 50 |

---

## 1. Stack A — hosted Goodfire / EDSL

Source: `SAE/data/raw/games/{safe_risky,ultimatum}/…`, `SAE/data/raw/creativity/…`.
Settings read from the `model.*` columns of the logged EDSL records.

- `model.inference_service = goodfire`, `model.model = meta-llama/Llama-3.3-70B-Instruct`
- `model.temperature = 0.5` in **every** condition except `high_temperature`, which is `1`
  (this settles PAPER_AUDIT §2.6: the appendix's "e.g. 0.9 or 1.0" is wrong, and the other
  conditions' settings were logged all along)
- `model.top_p = 1`, `model.max_tokens = 1000`, `model.top_logprobs = 3`, `model.logprobs = False`
- Precision/quantisation: never exposed by the service. Unrecoverable.
- Choice obtained by sampling, then EDSL's `multiple_choice` parse over
  `['Safe Option', 'Risky Option']`. No logits.
- Seeds: none recorded. The "40 agents" differ only in `subject_id` (`A1`…`A40`); the persona
  conditions differ only in an added `personality` string.

### Verbatim serialised prompts

Lottery, all five conditions (only the system prompt differs):

```
system: Your traits: {'subject_id': 'A1'}
user:
SAFE VS. RISKY CHOICE GAME

You must choose between two options:
1. Safe Option: Guaranteed 50 tokens.
2. Risky Option: 50% chance of {n} tokens, 50% chance of 0 tokens.

Which option do you choose?
```

- `slightly_prompting`: `{'subject_id': 'SR1', 'personality': 'slightly likes to take risks'}`
- `barely_prompting`: `{'subject_id': 'BR1', 'personality': 'barely likes to take risks'}`
- `steering`, `lite_steering`: the baseline system prompt, plus a controller.

Ultimatum (`prompting` is the altruism persona):

```
system: Your traits: {'subject_id': 'A1'}          # prompting: {'subject_id': 'F1',
                                                   #   'personality': 'Altruistic and selfless
                                                   #   behavior or intentions'}
user:
ULTIMATUM GAME - RESPONDER

You are participating in an economic decision-making experiment called the Ultimatum Game.

Situation:
1. Another participant (the proposer) was given 100 tokens (which have real monetary value).
2. The proposer has decided to offe…
```

Creativity (brick). Note the response-format instruction, which the paper does not quote and which
caps fluency at ten items:

```
user:
List very detailed ways you can use a brick. Each answer should be a paragraph.

The list must not contain more than 10 items.

Return your answers on one line, in a comma-separated list of your responses, with square
brackets and each answer in quotes E.g., ["A", "B", "C"]
```

The `prompting` creativity condition's system prompt is **the three steered features' labels, verbatim**:

```
Your traits: {'trait1': 'Enabling or empowering creative expression and exploration',
              'trait2': "Descriptions of creative unconventional thinking, especially
                         'thinking outside the box'",
              'trait3': 'Professional innovation and creative problem-solving'}
```

So "prompting" and "SAE steering" are not independent arms: one is the natural-language rendering of
the other's labels. Any claim that one beats the other is a claim about label text versus decoder
direction, not about prompting versus steering in general.

### Controllers actually used (recovered in full)

Written to `results/S/goodfire_labels.json`; `MANIFEST.csv:S0.A.goodfire.n_named_features` = 8.
`mode` is `nudge` throughout; `max_activation_strength` is 1 for every feature.

| task / condition | idx | uuid | label | value |
|---|---:|---|---|---:|
| lottery `steering` | 184 | `7f0e30ffb55c412cacd711909b11e5d0` | Willing to take risks or make sacrifices for a goal | 0.7 |
| lottery `steering` | 4237 | `b53742bf6f5040e0a8aeba37766335ff` | Executing potentially risky operations that require caution | 0.5 |
| lottery `lite_steering` | 184 | `7f0e30ffb55c412cacd711909b11e5d0` | (same) | 0.6 |
| lottery `lite_steering` | 4237 | `b53742bf6f5040e0a8aeba37766335ff` | (same) | 0.4 |
| ultimatum `steering` | 31935 | `a239616d4dcf470497b32ad3500f0145` | Altruistic and selfless behavior or intentions | 0.5 |
| creativity `high_steering` | 13142 | `2c83bf952a3a4213b45f098aa8c015e2` | Enabling or empowering creative expression and exploration | 0.3 |
| creativity `high_steering` | 20117 | `96f91d8ed8934998b52bf66a5951dafd` | Descriptions of creative unconventional thinking… | 0.3 |
| creativity `high_steering` | 4992 | `c148476f6cdc4cd9a2110c24045bfcbe` | Professional innovation and creative problem-solving | 0.3 |

This answers Q5 and settles PAPER_AUDIT §4.10. Appendix A.1.3's "two overlapping presets (0.5 to 0.7,
0.4 to 0.6)" are not alternatives to choose between: they are the two published conditions,
`steering` = (0.7, 0.5) and `lite_steering` = (0.6, 0.4). The UUIDs are not placeholders; they are the
real ones, and they are now saved locally, so the retired hosted service is no longer a dependency for
identifying the features.

What is **not** recoverable: how Goodfire normalised `nudge` internally, which token positions it
touched, and the serving precision. `SAE/docs/STEERING.md` states plainly that the private nudge
calibration is gone. Every dose comparison against Stack A carries that gap.

---

## 2. Stack B — local vLLM, the prompting ladder

`Revised Prompting/runs_fp16/runs/*/run_manifest.json`: Llama-3.3-70B-Instruct, `bfloat16`,
`tensor_parallel_size: 2`, temperature **0.7**, top-p **1.0**. Nine conditions, 40 agents per cell,
lottery on 35 rewards (10–180) and ultimatum on 17 offers (10–90). Few-shot demonstrations come from
`data/brick_exemplars.json`, built from the OCSAI AUT dataset.

Results exist and are complete (Q6). They are not in the paper, and on their own stack they do not
reproduce the paper's picture: the baseline lottery switching point is **102.9**
(`S0.B.lottery.switch.vllm.baseline`) against **127.6** on Stack A, and the persona moves it to
**97.3**, against **19.8** on Stack A. The ultimatum baseline never crosses 0.5 at all — it accepts
78% of 10-token offers, where Stack A's baseline accepts none.

---

## 3. Stack C — local HF, probe steering

`Probes/models.py`, `Probes/config.py`, `Probes/tasks/`.

### Prompting and readout

- Prompts are the raw strings in `tasks/prompts.py`, tokenised directly:
  `self.tokenizer(prompt, return_tensors="pt")`. **No chat template, no system prompt, no persona.**
  The lottery prompt ends `Respond with either 'Safe' or 'Risky' as your final answer.` — a different
  wording and a different answer vocabulary from Stack A's `Safe Option` / `Risky Option`.
- Sampled, `max_new_tokens=12`, temperature 0.7, top-p 0.95, per-agent seed
  `seed_base + param_idx*1000 + agent_id`. Creativity: 1024 tokens at temperature 0.9.
- Parsing: `re.finditer(r"\b(Risky|Safe)\b", …)`, **last** match wins. Unparseable → `parsed_choice = -1`.

### The steering hook, as written

```python
v_scaled = v_unit                       # the "scale to match activation magnitudes" comment is a no-op
start_idx = max(1, seq_len - max(1, ceil(seq_len * 0.20)))
n = seq_len - start_idx
if n <= 0: return output                # unchanged
scale = torch.linspace(0.5, 1.0, n)
hidden[:, start_idx:, :] += (sign * lambda_value) * v_scaled * scale
```

Three facts follow, each checkable by arithmetic rather than by running the model:

1. **`v_scaled` is defined, and it is the unit probe direction.** PAPER_AUDIT §4.3 records it as
   undefined in the appendix; in the code it exists and equals `v_unit`, so the norm-matching the
   appendix implies never happens. λ is in raw residual-stream units, not in units of the layer's norm.
   (`S0.G.steering.v_scaled_is_unit_vector`)
2. **Nothing is steered during generation.** `model.generate` runs with the KV cache on, so every
   decoding step has `seq_len == 1`; then `start_idx = max(1, 1-1) = 1` and `n = 0`, and the hook
   returns the output untouched. (`S0.G.steering.tokens_steered_per_decode_step` = 0.) This is a
   correction to PAPER_AUDIT §4.3, which reads the same code as applying a constant 0.5 to every
   generated token. It applies **nothing**. The intervention is confined to the last 20% of the
   *prompt*, ramped 0.5→1.0, exactly as the appendix's "last 20%" says but for the opposite reason.
   `config.STEERING["apply_during_generation"] = True` is never read by any code path.
3. **The probe and the hook live in different spaces.** `Probe.score` standardises first
   (`(h - mean)/scale`) and then projects onto the unit weight; `install_steering` adds the unit
   weight to the **raw** residual stream. The steering direction is therefore not the direction the
   probe scores, unless the per-feature standard deviations happen to be uniform.

### Sign convention (Q2)

Calibrated λ for the preference probes is **negative throughout**:
range −5.999 … −0.308 (`S0.D.lambda.preference.{min,max}`), and `figure_11`'s own metadata records
`lambda_range: [-6.0, 0.0]`. The probe's positive class is the risky/accept choice, so a negative λ
pushes toward safe/reject and raises the switching point — slope −36.1 tokens per unit λ for the
Llama lottery (`S0.D.lottery.switch_vs_lambda.slope.llama_l48`). The creativity probes' λ is
**positive** throughout (0.169 … 6.0), because there the positive class is the high-score class.

Fig. 10a plots λ rising with the target, so it is plotting |λ| or −λ. The text at ll. 397–398 is
correct about the *signed* λ. The figure and the text use opposite conventions without saying so.

---

## 4. Stack D — local open-SAE reruns

`SAE/runs/*/open_sae_steering_metadata.json`. Twelve runs, all on a RunPod H100
(`/workspace/...`), Linux 6.8, Python 3.11.10, torch bfloat16, `device_map=auto`, **`load_in_4bit`**.

- SAE: `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, hook `model.layers.50`.
- Patch: `features = sae.encode(resid); features[idx] = edit(...); steered = sae.decode(features) + error`,
  i.e. the reconstruction error is added back. This is the honest version of the equation PAPER_AUDIT §4.4
  objects to in Fig. 1 — Fig. 1 replaces the hidden state with the reconstruction, the code does not.
- `steering_mode: clamp_min`, `patch_scope: last_token`, `strength_calibration: raw`.
- Generation: `do_sample: False`, `max_new_tokens: 256`, no seed.

These are a different intervention from Stack A's `nudge` and must not be pooled with it. What they show
is reported in `PHASE0_SUMMARY.md` §Q1; briefly, the lottery result replicates (switch 57.5 against
59.1) and the ultimatum result does not (17.5 against 32.9), and the two lottery doses are
behaviourally indistinguishable — `S0.C.lottery.dose_gap_risky_count` = 0 out of 1,400 trials.

---

## 5. Sampling settings never stated in the paper, now recovered

| setting | value | source |
|---|---|---|
| Stack A temperature, all published conditions | 0.5 | `model.temperature` |
| Stack A `high_temperature` | 1.0 | `model.temperature` |
| Stack A top-p, max tokens | 1, 1000 | `model.*` |
| Stack C choice temperature / top-p | 0.7 / 0.95 | `config.DECODING_DEFAULTS` |
| Stack C creativity temperature | 0.9 | `config.DECODING_DEFAULTS` |
| Stack C max new tokens | 12 / 1024 | `config.DECODING_DEFAULTS` |
| Stack B temperature / top-p | 0.7 / 1.0 | `run_manifest.json` |
| Stack D decoding | greedy | `open_sae_steering_metadata.json` |

All of this belongs in the appendix; App. A.6's "held constant" is not accurate across stacks, and is
not checkable from the paper as written.

---

## 6. Secrets

`SAE/tests/verify_no_secrets.py` and `verify_release_anonymity.py` exist. No key is committed. The
logged run metadata contains absolute RunPod paths (`/workspace/.cache/huggingface/...`) — those must be
scrubbed before any supplement, and `SAE/runs/*/open_sae_steering_metadata.json` is where they are.
