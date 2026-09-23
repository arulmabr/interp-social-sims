**Prepared by Codex from the saved experiment outputs.** Read [ERRATA.md](ERRATA.md) for the later probe-layer clarification. “SAE is just bias” would be too strong a conclusion.

**What we are testing**

The experiment aims to distinguish a consistent change in risk preferences from a change in how the model selects or expresses an answer. Imagine a guaranteed gain of 40 tokens versus a 50% chance of gaining 100 and otherwise gaining nothing. Choosing the risky option once tells us little. The evaluation needs to establish how choices change across reward amounts, probabilities, gains and losses, and whether the pattern survives rewording and swapping options A/B.

**What CPT means**

CPT is **Cumulative Prospect Theory**, a mathematical model of choices under risk. It separates sensitivity to reward amounts (curvature), how probabilities enter decisions (probability weighting), and the relative impact of losses versus equal-sized gains (loss aversion). “Cumulative” refers to calculating decision weights from cumulative probabilities over ranked outcomes. [Tversky and Kahneman, 1992](https://doi.org/10.1007/BF00122574).

For this experiment, the pilot specified those parameters, providing an artificial decision-maker with a known target policy. The fitted version also includes choice sensitivity and A/B-label bias, so it has five fitted parameters. It is a restricted preference model, not every possible account of preferences.

**What the interventions were**

- The **readout gradient** is a direction calculated from the model’s sensitivity to the risky-versus-safe answer scores. It is the action-control reference.
- **LoRA means Low-Rank Adaptation:** a way to train relatively small weight updates while freezing the original model weights. The pilot reused a LoRA trained to imitate the specified CPT policy as the intended preference reference. It is not built with an SAE. [Hu et al., 2021](https://arxiv.org/abs/2106.09685).
- **Dense steering** adds a freely learned direction to the model’s residual stream, meaning its internal hidden state.
- **SAE means Sparse Autoencoder:** a learned representation of internal activity using feature directions. The pilot used Goodfire’s existing SAE and added a weighted combination of ten decoder features. No new SAE was trained. [Released model](https://huggingface.co/Goodfire/Llama-3.3-70B-Instruct-SAE-l50).

**How the comparison was made**

Dense and SAE steering used the same base model, layer, token positions and residual displacement norm. Both were trained toward the same two target policies: the combined CPT agent and a neutral, linear-value/probability-unweighted agent. The weight-space LoRA is a separate reference; it cannot be norm-matched to a residual edit in the same way.

The pilot used 216 discovery prompts to select features and learn directions, 96 selection prompts to choose checkpoints/settings, then 432 held-out prompts per condition: 108 economic scenarios, each with two answer orders and two phrasings. The final round had 28 conditions. The analysis used risky-answer probabilities directly, rather than treating one sampled response as a stable preference. Everything ran on the same large language model in bfloat16, a 16-bit numerical format.

**Why the results were described as “bias-like”**

The analysis asked two distinct questions. First: did the intervention reproduce the intended CPT policy? Second: what model best predicts the behavior it actually produced?

For the second question, the analysis fitted a CPT model and an answer-bias/confidence model on selection responses, then tested both on held-out responses. The bias model starts with the base model’s answer probabilities and applies a shift and confidence rescaling separately for gain, loss and mixed gambles, plus an A/B-label preference.

Across the eight SAE target/seed/wording combinations, this bias model predicted actual steered behavior better: **RMSE 0.038–0.056 versus 0.111–0.164 for CPT**. RMSE means **Root Mean Squared Error**; lower means closer predicted and measured probabilities. These numbers describe prediction of the actual steered behavior, not agreement with the planted target.

That is evidence for a bias-like behavioral description within this comparison, not proof of an internal mechanism. The bias model has seven parameters versus five for the restricted CPT model and uses the base model’s responses. Those advantages limit how strongly the analysis can interpret its better prediction.

**What passed, and what remains unresolved**

The raw gradient behaved as the intended action control. The LoRA passed the latest provisional checks with original wording, but its error against the planted target rose from **0.042 to 0.115** after rewording; the declared accuracy limit was **0.060**. Dense and SAE steering each passed **0/8 complete acceptance evaluations**: two targets × two training seeds × two wordings. That does not mean every individual check failed.

On probes, both the original probe steering and this new dense baseline use dense residual directions. Their training objectives and intervention settings differ: a classifier-derived direction versus direct optimization toward CPT choices, with different token scopes; the exact layer hooks also need to be aligned. No matched head-to-head with the original probe was run. Shreyas subsequently reported that his experiment used layer 50; layer and token-scope details must be aligned before claiming different behavior.

The supported decision is to **defer the full SAE sweep**. The tested recipe did not demonstrate robust preference control, and the positive LoRA reference also failed wording transfer. The next step is to validate that reference on fresh phrasings first, then repeat the small matched comparison. The feature labels remain existing Neuronpedia descriptions; these results do not independently establish what the features mean.
