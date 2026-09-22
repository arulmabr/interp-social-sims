# appendix_prompts.md

Verbatim prompts for the prompting ladder (`cot`, `fewshot`, `fewshot_cot` and its
rho sweep). The paper's abstract refers to these conditions; no appendix contains them.
Extracted by `cv_bench/s1_ladder.py` from
`cleaned/behavioral_games_combined.csv`, at the 50-token cell of each condition.

All of these ran on the **local vLLM stack**: Llama-3.3-70B-Instruct, bfloat16,
tensor-parallel 2, temperature 0.7, top-p 1.0, no system prompt except in `persona`.
They did **not** run on the hosted Goodfire stack that produced Figures 3 and 5.

> Draft for the authors. Every quantitative claim that cites these prompts must carry its
> `MANIFEST.csv` id.

## Lottery

### `baseline_rp`

System prompt: *(none)*

User prompt:

```text
You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.

End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `persona`

System prompt:

```text
You are inclined to take advantageous risky opportunities.
```

User prompt:

```text
You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.

End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `cot`

System prompt: *(none)*

User prompt:

```text
You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
Think step by step about the expected value of each option and your own attitude toward risk, then decide.
End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `fewshot`

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: Option safe gives 50 tokens for sure. Option risky gives 132 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 33 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 166 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 99 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 51 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 67 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: Final answer: risky

You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.

End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `fewshot_cot_dose000`  (rho = 0.00)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: Option safe gives 50 tokens for sure. Option risky gives 132 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 132 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 33 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 33 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 166 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 166 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 99 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 99 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 51 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 51 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 67 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 67 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
Think step by step about the expected value of each option and your own attitude toward risk, then decide.
End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `fewshot_cot_dose025`  (rho = 0.25)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: Option safe gives 50 tokens for sure. Option risky gives 132 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 132 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 33 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 33 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 166 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 166 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 99 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 99 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 51 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 51 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 67 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 67 has enough upside that I'd rather take the chance. Final answer: risky

You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
Think step by step about the expected value of each option and your own attitude toward risk, then decide.
End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `fewshot_cot_dose050`  (rho = 0.50)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: Option safe gives 50 tokens for sure. Option risky gives 132 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 132 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 33 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 33 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 166 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 166 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 99 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 99 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 51 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 51 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 67 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 67 has enough upside that I'd rather take the chance. Final answer: risky

You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
Think step by step about the expected value of each option and your own attitude toward risk, then decide.
End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `fewshot_cot_dose075`  (rho = 0.75)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: Option safe gives 50 tokens for sure. Option risky gives 132 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 132 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 33 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 33 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 166 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 166 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 99 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 99 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 51 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A 50/50 shot at 51 could leave me with nothing, so I'd rather lock in the certain 50. Final answer: safe

Q: Option safe gives 50 tokens for sure. Option risky gives 67 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 67 has enough upside that I'd rather take the chance. Final answer: risky

You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
Think step by step about the expected value of each option and your own attitude toward risk, then decide.
End your response with exactly "Final answer: safe" or "Final answer: risky".
```

### `fewshot_cot_dose100`  (rho = 1.00)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: Option safe gives 50 tokens for sure. Option risky gives 132 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 132 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 33 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 33 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 166 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 166 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 99 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 99 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 51 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 51 has enough upside that I'd rather take the chance. Final answer: risky

Q: Option safe gives 50 tokens for sure. Option risky gives 67 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
A: A guaranteed 50 is fine, but a 50/50 shot at 67 has enough upside that I'd rather take the chance. Final answer: risky

You are playing a lottery game. Option safe gives 50 tokens for sure. Option risky gives 50 tokens with 50 percent probability and 0 tokens otherwise. Choose one option.
Think step by step about the expected value of each option and your own attitude toward risk, then decide.
End your response with exactly "Final answer: safe" or "Final answer: risky".
```

## Ultimatum

### `baseline_rp`

System prompt: *(none)*

User prompt:

```text
You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?

End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `persona`

System prompt:

```text
You prefer practical outcomes and avoid destroying value.
```

User prompt:

```text
You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?

End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `cot`

System prompt: *(none)*

User prompt:

```text
You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
Think step by step about what you gain from accepting versus rejecting and how fair the split is, then decide.
End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `fewshot`

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: The proposer offers you 72 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: Final answer: accept

Q: The proposer offers you 13 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: Final answer: accept

Q: The proposer offers you 86 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: Final answer: accept

Q: The proposer offers you 58 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: Final answer: accept

Q: The proposer offers you 27 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: Final answer: accept

Q: The proposer offers you 41 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: Final answer: accept

You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?

End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `fewshot_cot_dose000`  (rho = 0.00)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: The proposer offers you 72 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 72 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 13 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 13 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 86 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 86 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 58 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 58 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 27 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 27 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 41 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 41 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
Think step by step about what you gain from accepting versus rejecting and how fair the split is, then decide.
End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `fewshot_cot_dose025`  (rho = 0.25)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: The proposer offers you 72 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 72 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 13 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 13 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 86 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 86 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 58 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 58 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 27 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 27 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 41 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 41 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
Think step by step about what you gain from accepting versus rejecting and how fair the split is, then decide.
End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `fewshot_cot_dose050`  (rho = 0.50)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: The proposer offers you 72 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 72 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 13 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 13 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 86 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 86 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 58 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 58 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 27 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 27 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 41 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 41 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
Think step by step about what you gain from accepting versus rejecting and how fair the split is, then decide.
End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `fewshot_cot_dose075`  (rho = 0.75)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: The proposer offers you 72 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 72 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 13 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 13 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 86 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 86 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 58 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 58 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 27 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 27 out of 100 is a lopsided split; I'd rather we both get nothing than reward an unfair offer. Final answer: reject

Q: The proposer offers you 41 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 41 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
Think step by step about what you gain from accepting versus rejecting and how fair the split is, then decide.
End your response with exactly "Final answer: accept" or "Final answer: reject".
```

### `fewshot_cot_dose100`  (rho = 1.00)

System prompt: *(none)*

User prompt:

```text
Here are example responses:

Q: The proposer offers you 72 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 72 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 13 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 13 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 86 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 86 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 58 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 58 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 27 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 27 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

Q: The proposer offers you 41 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
A: 41 out of 100 isn't a lot, but taking it beats walking away with nothing. Final answer: accept

You are responding in an ultimatum game. The proposer offers you 50 tokens out of 100. If you accept, you receive the offer. If you reject, both players receive 0. Do you accept or reject?
Think step by step about what you gain from accepting versus rejecting and how fair the split is, then decide.
End your response with exactly "Final answer: accept" or "Final answer: reject".
```

