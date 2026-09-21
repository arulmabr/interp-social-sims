# PROBE_PROVENANCE.md — S0.4

What the probes were trained on, read out of `Probes/experiments/_common.py`,
`Probes/probes.py`, `Probes/models.py` and `Probes/config.py`.

## 0. The short version

No probe artefact survives in this repository — no weight vector, no bias, no scaler, no chosen layer,
no CV accuracy, no layer-sweep table, no cached activation. The accuracy numbers in the paper (82%,
≈85%, ≈92%) cannot be checked against anything, and Figs. 11/16's probe scores cannot be recomputed.
The training design, however, is fully determined by the code, and it is the decisive finding of S0:

- **The preference probe sees 45 distinct inputs (lottery) or 19 (ultimatum), each repeated 8 times,
  and differing only in one integer.**
- **The capability probe sees exactly 2 distinct inputs.**

---

## 1. Preference probes (lottery, ultimatum)

`build_preference_probe(model, game, n_samples_per_param=8, layer_sweep=True)`

| | lottery | ultimatum |
|---|---|---|
| prompts | `prompts.lottery_prompt(n)` for n = 20,25,…,240 | `prompts.ultimatum_prompt(o)` for o = 10,15,…,100 |
| distinct prompts | **45** (`S0.G.lottery.n_distinct_prompts`) | **19** |
| samples per prompt | 8 | 8 |
| training rows | 360 | 152 |
| label | the agent's own parsed choice on that sample: Risky/Accept = 1 | same |
| activation | `capture_activations(prompt, layer)` — **final token of the prompt**, a separate forward pass, no chat template, no steering | same |
| candidate layers | `range(40, 61, 2)` = 11 layers (Llama); `range(12, 25, 2)` = 7 (Qwen) | same |
| selection | 5-fold stratified CV over (layer, C∈{0.01,0.1,1,10}), pick best mean accuracy, refit on all data | same |
| standardisation | `StandardScaler` fitted on the full data | same |
| unparseable | dropped, uncounted | same |
| seed base | `SEED.get("probe_data", 100_000)` → 100,000, since `SEED` has no `probe_data` key | same |

### Every source of variation across the training inputs

The plan asks for this list explicitly. It has **one** entry:

1. the reward level `n` (lottery) or the offer `o` (ultimatum).

There is no persona, no paraphrase, no subject id, no template variation, and the response text never
enters the activation — `capture_activations` is called on the prompt, not on the prompt plus the
sampled completion. So the eight samples drawn at a given `n` produce **eight byte-identical activation
vectors**, carrying whatever labels the sampler happened to emit.

Three consequences follow, and none of them needs a GPU to establish:

1. **The probe can encode nothing but a function of `n`.** Its input is a deterministic function of a
   single integer. Whatever it separates, it separates by reading the reward level off the prompt.
   This is the S0.4 statement the plan asks to be made plainly, and it is true here.
2. **Its ceiling is the best threshold rule on `n`.** At a fixed prompt the sampled choice is a
   Bernoulli draw; the Bayes-optimal predictor of that draw from that prompt is the choice probability
   at that `n`, i.e. a one-parameter threshold. An 82% held-out accuracy is therefore consistent with a
   probe that has learned `n` and nothing about a disposition. S1.4(b) will measure the gap directly
   from the logged choices.
3. **The reported CV accuracy is optimistic by construction.** `StratifiedKFold` splits rows, not
   prompts, so each of the 45 activation vectors appears in the training fold and the validation fold
   of the same split. There is no prompt-level held-out set anywhere in the code.

One further mismatch: the probe is *scored* in standardised space and *steers* in raw space
(`STACK_AUDIT.md` §3). The direction added to the residual stream is `ŵ`, not `ŵ / σ`.

---

## 2. Capability probes (creativity)

`build_capability_probe(model, task, obj, n_samples_baseline=80, n_samples_persona=80)`

- Class 0 inputs: the task prompt, e.g. `"List very detailed ways you can use a brick. Each answer
  should be a paragraph."`, sampled 80 times.
- Class 1 inputs: `"You are a highly creative and unconventional thinker. Think outside the box. Be
  imaginative. "` + the same task prompt, sampled 80 times.
- Activation: `capture_activations(prompt_text, layer)` for class 0 and
  `capture_activations(persona_prefix + prompt_text, layer)` for class 1.
- Labels: `median_split` of the **judge score of the generated text** — not of the group.
- Then the same CV over (layer, C) and refit.

**There are two distinct activation vectors in the entire training set**
(`S0.G.capability.n_distinct_prompts` = 2), one per group, each repeated 80 times. The labels are a
median split of a judge score that is correlated with, but not identical to, the group.

This resolves PAPER_AUDIT §4.2 in a sharper form than the audit states. The audit says the final prompt
token "cannot separate high from low creativity, let alone reach ≈92%". In fact it can reach a high
number very easily, and that is the problem: a classifier over two point masses achieves exactly the
rate at which the median split agrees with the persona/baseline split. The probe is a
**persona-prompt detector**. ≈92% is a statement about how often the persona produced an
above-median-scoring response, not about creativity being linearly decodable.

That also explains the range compression in Fig. 6 and the λ=0 mismatch in Q4 without any appeal to the
model: steering along a baseline-vs-persona contrast at increasing λ walks the output along that one
axis, and its λ=0 intercept (≈3.96) is a property of the fitted line, not of the unsteered model.

---

## 3. Which of the paper's three descriptions is true

PAPER_AUDIT §4.1 lists three incompatible accounts. Against the code:

| description | verdict |
|---|---|
| §3.3 — "82% accuracy on held-out preference trials" | **Half true.** Preference trials, yes. "Held out" is not implemented: CV splits rows, and each prompt's activation vector appears on both sides of every fold. |
| Fig. 2 — trained on synthetic low-/high-altruism statements | **False.** No synthetic statement set exists in the repository. Nothing in `build_preference_probe` generates or reads one. |
| App. B.4 — median split of the target metric across calibration runs | **False for the preference probes, true for the capability probes.** `median_split`'s own docstring explicitly forbids feeding it a switching point, and `build_preference_probe` labels by the observed choice. `build_capability_probe` does median-split, on the judge score. |

The accurate sentence for the paper is: *preference probes are trained on the model's own sampled
choices at the task prompts, labelled by that choice; capability probes are trained on baseline versus
creative-persona prompts, labelled by a median split of the judge's score.* A draft patch belongs in
`paper_patches/` at S4.

---

## 4. Layer, regularisation, N per class, held-out accuracy

| item | status |
|---|---|
| chosen layer | 48 (Llama) / 17 (Qwen) per `config.py`, and stamped into every logged row as `probe_layer`. Whether CV chose it or it was pinned is not recorded. |
| layer sweep table | **not available.** `train_probe` keeps only the winner; nothing writes the per-layer scores. |
| regularisation | chosen from C ∈ {0.01, 0.1, 1, 10} by the same CV; the winner is stored in `Probe.meta["best_C"]`, and no `Probe` was saved. **Not available.** |
| N per class | **not available** as run. Derivable upper bounds: 360 lottery rows, 152 ultimatum rows, 160 capability rows, minus unparseable drops, which are not counted anywhere. |
| held-out accuracy | **not available.** `Probe.cv_accuracy` is computed and never written to disk. |
| cross-object accuracies | available, in `figure_13/19`: in-distribution 0.91 (bowl, n_runs 7), and the rest of the 8-row table. `eval_probe_split` uses `n_seeds` fresh `random_state`s over the *same* split, so `std_score` measures solver seed variation, not data variation, and `CROSS_OBJECT["min_train_accuracy"] = 0.6` seed filtering described in `config.py` is not implemented in `probes.py`. |

## 5. What this blocks, and what it does not

Blocked until a GPU run: the 82% / ≈85% / ≈92% accuracies; any cosine between the probe and another
direction; S1.4(c), which assumes cached activations that do not exist.

Not blocked: S1.4(a) and S1.4(b), which need only the logged per-agent choices and the reward levels;
the whole of S1.1–S1.3; and the design argument above, which is settled by reading the code.
