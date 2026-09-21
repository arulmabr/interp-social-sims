# ICLR_PLAN.md

Work plan for extending "Interpreting and Steering LLM Agents for Social Simulations".
Audience: Claude Code working in `/home/guna23/shrey/risk`. Standing rules are in `CLAUDE.md`. Problems already verified in the current draft are in `PAPER_AUDIT.md`. The authors' own plan is `mech_interp_paper_ICLR_extension_plan*.docx` (read it with `pandoc -t plain`), and the automated review is `feedback.txt`.

How to use this file: tasks have ids (S1.3, B4.2). Do them in order within a track, stop at every GATE, and do not start Track B compute until the authors say so after Gate S0.

---

## 0. Orientation

### 0.1 Situation

- ICLR 2027: the abstract deadline (2026-09-18) has passed; the full paper is due **2026-09-25 23:59 AoE**. Main text limit is 9 pages at submission and 10 during the discussion period (Nov 5–18, 2026) and for the camera-ready. An AI-use statement is mandatory. The title and abstract may be edited until the deadline but must not read like a different paper from the registered abstract. After decisions, all submissions are public and de-anonymised, including rejected and withdrawn ones. A paper withdrawn *before* the Sept 25 deadline is deleted from OpenReview; one withdrawn after it stays public and is de-anonymised immediately.
- The current draft is over the page limit, has results promised in the abstract that appear nowhere, and contains several contradictions between text and figures (`PAPER_AUDIT.md`). Those are Track S.
- The authors' extension turns the paper into a construct-validity study. It cannot be completed with integrity by Sept 25. It is Track B, scheduled for the discussion-period revision or a later venue. Which tracks run, and whether to submit on Sept 25 at all, is an AUTHOR DECISION.

### 0.2 Thesis of the extension

Interventions move the lottery switching point, the ultimatum acceptance threshold and the judged creativity score. What those shifts represent is unknown. A direction that looks behavioural may bias an action, drive the answer readout, distort the model's reading of the payoff, or change a preference. The contribution is a benchmark, built on the paper's own tasks plus parameter variants, that tells these apart. Every steering effect is compared with random directions of the same norm at the same layer and positions, and with a direction of the same norm trained to encode the stated reward. Two anchors inside the real model bracket all other interventions: the gradient of the risky-minus-safe logit (action-like by construction) and a LoRA trained on choices of a synthetic agent with known utility (preference-like by construction). An estimator that misplaces either anchor is not used.

### 0.3 Author decisions in force

1. **"Dense steering" is dropped.** It is not mentioned in the paper and performed poorly. Do not extend or run it. Do not delete it either: see S0.6.
2. **Anchors kept:** the LoRA anchor and the gradient (answer-readout) anchor.
3. **Families under test:** linear probes and SAE features, each examined against both anchors, with the prompting ladder as the non-mechanistic comparator on the same scale.

### 0.4 Amendments to the authors' plan

Each changes or adds to plan v4. Reasons are given so the authors can overrule; treat all of them as AUTHOR DECISION until confirmed at Gate S0.

- **A1. Loss aversion needs mixed gambles.** In a choice between a sure loss and a gamble over losses, the loss-aversion coefficient multiplies both options and drops out of the indifference point; it survives only as a slope, confounded with choice noise. It is identified cleanly only from gambles that mix a gain and a loss against zero. Add a mixed frame.
- **A2. Sign reversal is a diagnostic, not a pass criterion.** Plan v4 says an action bias keeps its sign across gain and loss frames while a curvature change reverses. But a plain taste for variance also raises gambling in both frames, and that is a legitimate preference change. Requiring reversal would misclassify it. Replace the criterion with an out-of-frame predictive check: fit the mechanism models on the core frame, predict the held-out frames, and ask which model predicts them. The sign pattern then says *which* parameter moved.
- **A3. Paired-lottery trials.** Two lotteries with equal expected value and different spread, no sure option, neutral labels. A "pick the gamble over the sure thing" bias is silent here; a variance preference is not. This is the cleanest separator of the two.
- **A4. Stake variation.** Vary the sure amount (20, 50, 100, 500) and the probability, not only n. The legacy design varies only n at s = 50 and p = 0.5, where an additive bias and a threshold shift are observationally the same thing. Whether stake variation separates them depends on how the model's logit scales with stakes (it does under a choice rule on raw utility differences, it does not under range-normalised utility), so B2 measures this instead of assuming it.
- **A5. Reference and bias LoRAs.** The unmodified model is not a prospect-theory agent, so "LoRA vs. base" mixes the known parameter shift with becoming prospect-theoretic at all. Train three adapters on identical data and schedule: reference (θ0), preference-shifted (θ0 + Δ), and bias-shifted (θ0 plus an additive logit bias). The anchors are the *contrasts* against the reference adapter, where the true difference is exact. The bias adapter is a weight-space negative control that matches the gradient anchor in activation space.
- **A6. Select SAE features on the anchor contrast, not on causal effect on the choice logit.** Features chosen by their effect on the risky-minus-safe logit are aligned with the readout gradient, which the plan itself defines as action-like. Select instead on what differs between the preference-shifted and reference adapters, or between persona and neutral prompts at fixed n, and let the benchmark judge.
- **A7. Dictator Game and hyper-fair catch trials.** Altruism is measured by giving when refusal is impossible. Add the Dictator Game to the social arm. Treat rejections of offers ≥ 50% as catch trials, the counterpart of dominated gambles.
- **A8. Covariance-matched random directions.** Isotropic random directions in 8,192 dimensions typically do very little at the norms used for steering, so beating them proves little. Add random directions drawn with the empirical activation covariance at that layer, norm-matched.
- **A9. Iso-behavioural dose.** Compare families at doses that produce the *same* shift of the legacy switching point on the calibration split, then ask what moved underneath. This equalises the number everyone reports.
- **A10. Build on a small model first.** Develop the whole pipeline on Llama-3.1-8B-Instruct with Goodfire's open layer-19 SAE (`Goodfire/Llama-3.1-8B-Instruct-SAE-l19`), then port to 70B. It fits on one GPU, and it lets the SAE arm replicate on a second model, which the Qwen replication currently lacks.
- **A11. Transfer battery.** Three instruments never used for selection: a Holt–Laury price list, the Gneezy–Potters investment question, and an Eckel–Grossman gamble menu. A valid risk-preference knob should move them in the predicted direction; a shortcut tied to the lottery prompt's format should not.

### 0.5 Roles

You: code, runs, analyses, figures, reports, draft text patches. The authors: every AUTHOR DECISION, unlocking the test split, uploading the pre-registration, paid API approvals, and the paper itself.

---

## 1. Track S — sprint (needed for any submission)

### S0. Reconnaissance. Read-only, no GPU.

**S0.1 Repo map** → `reports/REPO_MAP.md`. Tree to depth 3 with sizes. For each script and notebook: purpose, inputs, outputs, last modified. Environments, where model and SAE weights live, git status. Move and rename nothing.

**S0.2 Provenance** → `reports/PROVENANCE.md`. One row per figure (3–18), Table 1, and each inline number (82%; 5.57 vs 5.18; 6.25 vs 5.23; Spearman 0.77 and range 0.68–0.85; ≈85% and ≈92%; switching points 125, 20, 50, 30, 10). Columns: item, generating script, input data, inference stack, regenerable today (yes / partly / no), notes.

**S0.3 Stack audit** → `reports/STACK_AUDIT.md`. For every inference path in the repo: model id and precision or quantisation; whether the chat template is applied; system prompt; one verbatim serialised prompt per task and condition (copy from logs where logged, e.g. the `prompt.*_user_prompt` columns); how the choice is obtained (sampling and parsing, or logits); temperature, top-p, max tokens, seeds. For steering: layer, how the vector is built, the `v_scaled` formula, sign convention, which positions are modified during prefill and during cached decoding. For Goodfire: the nudge values and preset actually used for each published curve, and the feature UUIDs.

**S0.4 Probe provenance** → `reports/PROBE_PROVENANCE.md`. For every probe artefact: what the training inputs were and how they were produced, the label definition, N per class, the token position of the activation, the layer-sweep table, held-out accuracy, regularisation. State which of the paper's three descriptions (§3.3, Fig. 2, App. B.4) is true. **List every source of variation across the training inputs** (reward level, persona text, subject id, paraphrase, response text). If the reward level is the only thing that varies, say so plainly: a probe reading the final prompt token can then encode nothing but a function of n, because the sampled choice at a fixed prompt is noise.

**S0.5 Blocking questions.** Answer each in `reports/PHASE0_SUMMARY.md` with file and line evidence.

- Q1. On the local stack, what are the lottery switching point and the ultimatum threshold at λ = 0? (Fig. 10 extrapolates to ≈20 and ≈25; the text says 125; Fig. 3B shows ≈38.)
- Q2. Which class is the positive side of each probe, and what is the sign convention of λ in code, in Fig. 10, and in ll. 397–398?
- Q3. In Fig. 11, is the probe score computed with the hook active, and on which tokens?
- Q4. How do creativity targets (3, 5, 7, 9) map to λ? What is the local-stack creativity score at λ = 0, and does it match the 5.18 baseline from the API stack?
- Q5. Which preset, value and features produced the SAE curve in Fig. 3A?
- Q6. Do results exist for `cot`, `fewshot`, `fewshot_cot` and the ρ sweep (look in `Revised Prompting/`)? On which stack, for which tasks, how complete?
- Q7. What is in `cleaned/`?
- Q8. Are per-response scores from all five judges stored? What do the error bars in Fig. 5 represent?
- Q9. Is Fig. 16 Qwen data scored under the five-judge protocol, as its caption says?
- Q10. Hardware: GPUs, memory, disk, who else uses the machine. Are Llama-3.3-70B-Instruct, Qwen-2-7B-Instruct and the Goodfire SAE weights on disk? Does the Goodfire API key still work (one minimal call)? If it does, save the label and UUID of every feature the paper names to `results/S/goodfire_labels.json` now, since the hosted API is an external dependency.

**S0.6 Dense steering.** Find it (names may vary: dense, learned vector, optimised vector). Write `reports/EXCLUDED_ARMS.md`: what it is, what was run, the results as logged, and the authors' reason for dropping it. Move nothing yet; propose an `archive/` location. **If it turns out to be a difference-of-means or contrastive-activation direction, flag that at the gate**, because reviewers explicitly asked for that baseline (S3.1) and the authors should decide knowing this. **Flag it as well if it is an optimised dense vector trained to reproduce a target agent's choices**, i.e. an activation-space counterpart of the LoRA anchor: a vector that cannot be trained to produce a preference shift which a LoRA can produce is evidence for the third row of the outcome table in §3, and the authors may prefer one appendix line reporting it to silence about it.

**S0.7** List every paper claim that cannot be reproduced from the repo.

**GATE S0.** Deliver `reports/PHASE0_SUMMARY.md`. The authors confirm the amendments in 0.4, assign GPUs, and choose tracks. While waiting you may continue with S1, which needs no GPU and no decisions. Start nothing else.

### S1. Analyses of existing results. CPU only.

Each task yields a CSV, a figure, and a short plain description in `reports/S1_<n>.md`. Use existing logs. Describe what the data show; do not argue for the thesis.

**S1.1 Dominated and negative-premium choices (lottery).** For every condition and every calibrated target already run: P(risky | n < 50), where the gamble is dominated, and P(risky | 50 ≤ n < 100), where it loses in expectation, with Wilson intervals.

**S1.2 Catch trials (ultimatum).** For every condition and target: P(reject | offer ≥ 50), which no standard fairness preference produces, and for description P(accept | offer ≤ 10), with intervals.

**S1.3 Switching points with uncertainty.** Logistic fit per curve, bootstrap intervals, pairwise differences between conditions. State in the report that the 40 "agents" are i.i.d. samples of one prompt, so the intervals describe sampling noise at one temperature.

**S1.4 What the choice probe encodes, without new steering.** (a) Correlation of the logged baseline probe score with n and with log n. (b) Held-out accuracy of the probe against the accuracy of a one-parameter threshold rule on n alone; if the rule matches the probe, the probe adds nothing beyond n. (c) If activations are cached: fit a ridge probe for log n, report its cosine with the choice probe, and the choice probe's accuracy after projecting that direction out.

**S1.5 Capability scores.** (a) Condition ordering per judge, as a table. (b) Mixed-effects model on response-level scores with random effects for judge and response; effect sizes with intervals for each pair of conditions. (c) Length: regress score on log word count per judge, residualise, recompute (b). (d) Inter-judge Spearman within each condition, and overall with and without the high-temperature condition, next to the published 0.77.

**S1.6 Judge-independent measures on the existing texts.** Number of distinct ideas; category spread by clustering sentence embeddings; mean semantic distance between the object and each proposed use; Divergent Semantic Integration. Correlate each with each judge. Use the Ocsai scorer only if it is openly accessible; otherwise note it as unavailable.

**S1.7 Prompt ladder.** If Q6 found results: overlay `cot`, `fewshot`, `fewshot_cot` on the Fig. 3 and Fig. 5 panels, plot the ρ dose-response, and tabulate switching points and scores. If results are partial, list what is missing and the cost of completing it on the same stack as the rest of Fig. 3. Extract the verbatim CoT trigger and the six demonstrations per task into `paper_patches/appendix_prompts.md`.

**GATE S1.** Stop. Deliver `reports/PHASE1_FINDINGS.md`.

### S2. One stack, one readout. GPU, small.

**S2.1 Logit-readout harness** in `cv_bench/readout.py`. Input: a trial spec and an optional intervention. Apply the chat template, append a fixed assistant stem (for example "My choice: Option"), run one forward pass, and return the logits of the two option tokens, their renormalised probabilities, the logit difference, and the total probability mass on valid option tokens. Check both tokenisations of each label (with and without leading space). Requirements: valid mass ≥ 0.98 on 50 baseline prompts, otherwise revise the stem; batched and unbatched logits agree within 1e-2 (left padding needs explicit `position_ids`); on 200 prompts × 20 samples the readout probability tracks the sampled choice frequency (report the calibration plot; flag a slope outside 0.8–1.2). For the legacy EDSL prompt format, skip the stem and read the first answer token that format expects (for example the first token of "Safe Option" vs. "Risky Option"). For readouts that need generation (CoT, stated amounts, creativity), decode greedily and then read the answer token the same way.

**S2.2 Steering hook** in `cv_bench/steer.py` with explicit semantics: `Intervention(layer, vectors, scale, positions)`. `scale` is in units of the median residual-stream norm at that layer over calibration prompts, excluding the first token. `positions` is one of `last` (final prompt token), `all_prompt`, or `all` (prompt plus every generated token). Keep the legacy "last 20% with ramp" as a named mode only to reproduce old numbers. For SAE features, add scale × unit decoder column to the residual stream; offer a clamp mode as a secondary. Tests: scale 0 gives identical logits to no hook; a recording test proves the intended positions are modified during cached decoding.

**S2.3 Unsteered baselines on the local stack**, legacy prompts verbatim, lottery and ultimatum grids, bf16. This settles Q1. If the local baseline differs from the published API baseline, report both and stop for the authors.

**S2.4 Local SAE.** Load `Goodfire/Llama-3.3-70B-Instruct-SAE-l50` from its `.pt` file. Verify index alignment by re-encoding logged prompt–response pairs and comparing the top-k features with the saved `feature_activations.txt` files. Report overlap.

**S2.5 The paper's four conditions on one stack.** Unmodified model, persona prompt, SAE features, probe (at the targets of Fig. 4); logit readout; both response formats (multiple choice and free text scored by sequence log-probability); lottery and ultimatum. This is the item in plan v4 that settles whether the contradictions belong to the model or to the stack.

**GATE S2.**

### S3. Baselines and causal checks the reviewers asked for.

**S3.1 Difference-of-means and PCA directions.** From the same activations as the probes: class-mean difference (the contrastive-activation-addition recipe) and the first principal component of paired differences (the representation-engineering recipe). Report the cosine matrix among probe, difference-of-means, PCA, reward probe, readout gradient and the decoder directions of the named SAE features, all computed at layer 50 as the common layer and additionally at layer 48. Steering curves at matched norm.

**S3.2 Position and layer ablation for probe steering.** Layer 48 vs 50; `last` vs `all_prompt` vs legacy ramp.

**S3.3 Causal tests of the SAE features named in §4.1 and App. A.** Ablation: subtract each feature's contribution at layer 50 and measure the change in logit difference across the grid, against 100 random active features matched on activation. Attribution: activation × (decoder · gradient) for all 65,536 features; report the rank of each named feature and the top 20. This converts the "considers ethics" and "writing instruments" readings into tested statements, whichever way they come out.

**S3.4 Label-neutral format test.** Legacy labels ("Safe Option", "Risky Option") vs neutral labels ("Option A", "Option B") × both option orders × {baseline, persona, probe at its lowest calibrated target}. Report switching points and dominated-choice rates. If the persona's dominated choices vanish under neutral labels, the persona effect was label matching; if they persist, it is something else. Either result goes in the paper.

**S3.5 Temperature sweep** for the creativity tasks (0.7, 1.0, 1.2, 1.5) with a coherence check (valid-text rate, language identification). Judge calls are a paid batch; estimate and ask.

**GATE S3.**

### S4. Hand-off package

Figures and tables with `MANIFEST.csv` ids; `paper_patches/` with suggested text for each item in `PAPER_AUDIT.md` §2–§4 and the prompt appendix; a supplement checklist (no absolute paths, usernames, keys, or git history); `logs/AI_USE_LOG.md` up to date.

---

## 2. Track B — construct-validity benchmark

Do not start B-tasks that need a GPU until the authors say so after Gate S0. B1 and B2 need no GPU and no model.

### B0. Infrastructure

Reuse `cv_bench/readout.py` and `cv_bench/steer.py`. Add a model registry so every task runs unchanged on the development model (A10) and on Llama-3.3-70B-Instruct in bf16. Optional speed-up, only after it reproduces full forward passes to 1e-2: cache the residual stream entering the intervention layer and recompute only the layers above it. Before any sweep, measure throughput and write `reports/COMPUTE_BUDGET.md`.

### B1. Trial generators, formats, splits

**Risk domain, in `cv_bench/tasks/risk.py`.**

- *Sure-gain:* s for sure vs. p chance of x, otherwise 0.
- *Sure-loss:* lose s for sure vs. p chance of losing x, otherwise lose 0.
- *Mixed (A1):* 0 for sure vs. 50% win G, 50% lose L.
- *Paired (A3):* (50%: m + d1, 50%: m − d1) vs. (50%: m + d2, 50%: m − d2), d2 > d1, no sure option.
- *Catch trials:* sure-gain with x ≤ s (the gamble is dominated); sure-loss with x ≤ s (the gamble dominates); paired trials in which one lottery is better in every outcome.
- Starting grid, to be finalised by B2: p ∈ {0.1, 0.25, 0.5, 0.75, 0.9}; s ∈ {20, 50, 100, 500}; x on a log grid of 12–16 levels around s/p, from 0.3× to 5×. Always include the legacy cell (p = 0.5, s = 50, n = 10…240 in steps of 5).
- Formats: option order (2) × labels (legacy "Safe/Risky", neutral "A/B") × response format (multiple choice; free text scored by sequence log-probability) × instruction templates.
- *Stated certainty equivalent:* "What is the smallest sure amount you would accept instead of this gamble?" Greedy decoding, parse one number, count unparseable outputs rather than dropping them.
- *Recall probes:* after the decision, ask the model to restate x and s. Train ridge "fact probes" for log x and log s on baseline activations for decoding under intervention.

**Splits.** `split ∈ {disc, sel, cal, test}` by reward-level index mod 4 within each cell, and by template (two templates per split). The test templates should be written by a human author and added only at unlock. `frame_role ∈ {core, heldout}`: core is sure-gain with p ∈ {0.25, 0.5, 0.75}; everything else is heldout. Before unlock, intervention families touch only (disc, sel, cal) × core. The unmodified model and the anchors may also touch heldout frames on non-test splits. Nothing touches `test`. Enforce this in the runner: loading a test trial without `--unlock-test <prereg SHA>` raises, and every access is appended to `logs/TEST_ACCESS.log`.

**Social domain, in `cv_bench/tasks/social.py`.** Responder (offers 0–100% in steps of 5, pies of 20, 100 and 1,000; offers ≥ 50% are catch trials). Proposer. Dictator Game (A7). Mini-ultimatum: the proposer's (8, 2) offer judged against the alternatives (5, 5), (2, 8), (10, 0), or no alternative. Accept-bias control: unrelated accept/reject and yes/no items with an objectively correct answer.

**Transfer battery (A11), in `cv_bench/tasks/transfer.py`.** Holt–Laury, Gneezy–Potters, Eckel–Grossman. Never used for selection or calibration.

### B2. Synthetic agents, estimator, recovery study. CPU only.

**Synthetic agents.** Cumulative prospect theory with v(x) = x^α for gains and −λ(−x)^α for losses, the Tversky–Kahneman weighting function with parameter γ, and a logit choice rule with temperature τ, action bias, position bias and label bias. Normalise the utility difference by the trial's utility range (contextual utility) to tame the curvature–temperature trade-off. Agent types: baseline; preference shift in α, γ or λ at the minimum detectable change (0.10, 0.10, 0.30, fixed in plan v4); action bias; format bias; belief distortion (x perceived as κx); noise (τ change); and two non-prospect-theory agents (mean–variance utility; an arbitrary monotone choice curve), so the diagnostics are tested where the parametric model is wrong.

**Estimator, two layers.**

- *Model-free fingerprint (co-primary).* With z the risky-minus-safe logit and Δz its change under intervention: D1 dominance-violation rates on catch trials; D2 decomposition of the variance of Δz into a constant (action), format terms, and payoff terms (log x/s, p, frame); D3 shift toward the wider lottery on paired trials; D4 stated-CE shift against the shift predicted from choices; D5 format transfer ratio with the pre-registered band 0.8–1.25; D6 recall accuracy and fact-probe decoding of x and s; D7 stability of the n*/s shift across stakes.
- *Parametric decomposition.* Nested extensions of the baseline fit: preference frees (α, γ, λ); action frees the action bias; format frees position and label biases; belief frees κ; noise frees τ. Shares are computed from predictive log-likelihood on held-out reward levels. Action vs. preference is compared by a paired cluster bootstrap over reward level × template, with the Vuong statistic reported alongside.

**Decision rule** (plan v4, with A2). A direction is preference-like only if all hold: preference share ≥ 0.8 and the action model is rejected; dominance violations within 2 points of baseline; the preference model fitted on core frames predicts the held-out frames better than the action and belief models (parameters the core frame cannot identify, such as λ, are held at baseline for this prediction and re-estimated on the held-out frames as a secondary analysis); transfer ratio within 0.8–1.25; recall intact; choice-based and CE-based estimates agree. Thresholds are AUTHOR DECISIONS and are frozen at B6.

**Recovery study.** Run every agent type through the actual grid, with template-level noise at several assumed levels (SD of z across templates of 0.5, 1 and 2 logits), updated to the measured level once baseline discovery-split data exist.

**GATE B2.** Pass when parameter RMSE is at most half of each minimum detectable change, and the decision rule classifies at least 95% of preference-shift agents as preference-like and at least 95% of action, belief and noise agents (matched on behavioural effect size) as not, including for the two misspecified agents on the model-free layer. If it fails, change the grid, never the thresholds. All of this is synthetic, so iterating here is legitimate.

### B3. Anchors

**B3.1 Gradient anchor.** The gradient of z with respect to the residual stream at the intervention layer, final prompt token, averaged over calibration-split core prompts. Two versions: within one format, and averaged over option orders and label sets. Apply at `last` only.

**B3.2 LoRA anchors (A5).** PEFT, rank 16, all linear layers, bf16. Three adapters with identical data order and seed, attached to one loaded base model and switched with `set_adapter`: reference θ0 = (α 0.88, γ 0.61, λ 2.25); preference-shifted (one adapter per shifted parameter, as budget allows; α first); bias-shifted. Training prompts come from all frames but only from non-test reward levels and templates. Loss is soft-label cross-entropy over the full vocabulary at the answer token, with the synthetic agent's choice probabilities on the two option tokens, so the ground truth is exact and valid mass stays high. Check cloning on selection-split prompts (correlation ≥ 0.95, calibration slope 0.9–1.1) before using an adapter as an anchor. If 70B bf16 training does not fit, train with 4-bit base weights and evaluate the anchors against the reference adapter on that same stack, since the anchor contrasts are internally consistent; record it as a deviation.

**B3.3 Anchor-derived candidates** (these are families, not anchors): the mean activation difference between the preference-shifted and reference adapters; a probe trained to separate them at matched prompts; SAE features ranked by activation difference between them (A6).

**GATE B3, the go-or-pivot rule of plan v4.** On the selection split: proceed if the gradient and bias-adapter anchors fail the rule and the preference adapter passes with the estimated shift within the minimum detectable change of the truth. If both kinds pass, redesign the frames using B2 and the anchors only. If the preference anchor fails, fix cloning or the estimator. Never consult a family result to make these choices.

### B4. Families and controls

All directions are built from the discovery split, core frames only, as a practitioner would.

| id | family | recipe |
|---|---|---|
| F1 | persona prompt | the paper's personas |
| F2 | optimised persona | best of K candidates on the calibration split, same budget as steering |
| F3–F5 | few-shot, CoT, few-shot CoT | the paper's ladder, including ρ |
| F6 | choice-labelled probe | the paper's probe |
| F7 | difference-of-means on choice labels | S3.1 |
| F8 | contrastive persona direction | mean activation, persona minus neutral, at fixed n |
| F9 | SAE features, label-selected | the paper's features |
| F10 | SAE features, anchor-selected | B3.3 |
| F11 | anchor-derived probe / direction | B3.3 |
| F6⊥, F8⊥, F9⊥ | readout-orthogonalised variants | project out the gradient anchor |
| C1 | isotropic random directions | 20 in discovery, 200 in confirmation |
| C2 | covariance-matched random directions (A8) | same counts |
| C3 | reward probe | ridge probe for log x; expected to look like belief distortion, which also validates D6 |

Dense steering is not in this table by author decision.

### B5. Selection and calibration

Per family, choose layer and position policy on the selection split (SAE families stay at the SAE's layer; report every probe-type family at its selected layer and also at the SAE's layer, so that comparisons are not confounded by layer) by a rule fixed beforehand: reach the iso-behavioural target (A9) with the smallest KL divergence on neutral prompts, subject to valid mass ≥ 0.9. Targets: move the legacy-cell switching point by ×0.75 and ×1.33 (moderate) and ×0.5 and ×2 (strong). Solve for dose on the calibration split with the existing bracketed search. A family that cannot reach a target without breaking outputs is recorded as such; that is a result. Report calibration-split and test-split estimates side by side; their gap is the circularity removed, against the ≈2-token in-sample calibration error of the current paper.

### B6. Pre-registration and the frozen test

Write `PREREG.md`: hypotheses H1–H6 of plan v4 plus the transfer battery; the decision rule and every threshold; grid, splits and family list; SHA of the analysis scripts; what is exploratory (everything already seen, including all of Track S); the outcome table in §3 below; the deviations policy. Tag `prereg-v1`. The authors upload it to a registry with an anonymised view-only link.

**GATE B6.** Stop. After a human unlocks: one confirmatory run per family and construct on `test`, Benjamini–Hochberg across families at q = 0.05, and the expected number of false passes from the C1 and C2 pass rates reported beside the observed passes. Intervals by resampling reward levels and templates, never trials. Recompute every result leaving out one frame, one template and one model at a time. For any family that passes: directional ablation and addition against the persona prompt (necessity and sufficiency), then count how many successive orthogonalised directions still pass.

### B7. Social arm (H5)

Trace each intervention over dose in the space of responder threshold, Dictator giving and proposer offer: the altruism persona, the altruism SAE feature, the ultimatum probe, anchor-selected features, an accept/reject readout gradient as the action control, and the random controls. Report hyper-fair rejections, the accept-bias items, the mini-ultimatum pattern, and stake invariance. Specificity in both directions: a social direction should leave the lottery fingerprint inside the random band, and a risk direction should leave the responder threshold there. Re-derive the altruism features of Zhang et al. only if their recipe can be applied to this model and SAE; otherwise cite and say why not.

### B8. Creativity arm (H6)

Keep the brick and stapler tasks and the five judges. Score the probe-training responses with all five judges, train the probe on the z-scored mean of four, evaluate on the fifth, rotate. Residualise on length and also run a fixed-format control ("exactly five ideas, at most 40 words each"). One cross-object procedure only: leave one object out, for both classification and steering. Report the judge-independent measures from S1.6 next to the judges. Compare prompting, SAE steering and the probe at equal budget and claim no winner. Human ratings on a subset would be the strongest addition; that is an AUTHOR DECISION with ethics-review implications.

### B9. Collateral effects and transfer

For every family at its calibrated doses: KL divergence on neutral prompts; a 100-item arithmetic subset; a 100-item instruction-following subset; the other domain's fingerprint. Then the transfer battery, with predictions derived from the choice-based fit before looking.

### B10. Replication

Probe and prompt families on Qwen-2-7B-Instruct as in the paper; the full set including SAE families on the development model (A10).

### B11. Release

Generators, splits, directions, probes, adapters, scoring scripts, the pre-registration, and a one-command reproduction of every figure, scrubbed for anonymity.

---

## 3. Outcome table: what the paper says in each branch

The design aims at zero *uninformative* outcomes. It does not aim at a particular direction of result, and nothing in this plan may be adjusted to obtain one.

| what happens | what is reported |
|---|---|
| The estimator cannot separate synthetic agent types (B2) | Nothing yet; the grid is redesigned on synthetic data at no cost to validity |
| Anchors separate on synthetic data but not inside the model (B3) | The parametric layer is withdrawn; the model-free layer (dominance, format transfer, certainty equivalents, paired lotteries, recall) stands without it |
| Anchors behave; the paper's own families (F1, F6, F9) fail | A documented shortcut: label-selected probes and SAE features shift behaviour without shifting a preference, shown by an instrument that places both anchors correctly. The anchor-derived candidates (F10, F11) are the constructive arm: if they pass, the paper offers a recipe for finding valid directions; if they fail too, the preference adapter is the existence proof that the change is reachable in weights but not by single-layer addition |
| Anchors behave; some families pass | A league table, a validated preference knob with necessity and sufficiency, and the size of its equivalence class |
| Anchors behave; all families pass | Steering for social simulation is construct-valid on these tasks, certified by an instrument that rejects the action controls |
| In every branch | Track S facts: dominated choices under the persona prompt and the probe, hyper-fair rejections, the label-neutral test, what the choice probe encodes, the per-judge creativity picture |

## 4. Compute and schedule (indicative)

- Track S: Sept 20–24. S0 and S1 on day 1–2, S2 on day 2–3, S3 on day 3–4, S4 on day 5.
- Track B: B0–B2 in week 1 after the deadline; B3 in week 2 on the development model, then 70B; B4–B5 in weeks 3–4; pre-registration at the end of week 4; test split, social and creativity arms in weeks 5–6; revision during Nov 5–18.
- Logit readouts are single forward passes, so the risk and social arms are cheap relative to the creativity arm, whose cost is generation plus five paid judges. Random-direction controls use a reduced prompt set (one template, two formats) to stay affordable; state this in the pre-registration.
