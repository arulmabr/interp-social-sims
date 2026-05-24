# Creativity Steering Provenance

Generated from `data/raw/creativity/product_innovation_20251102_202650/high_steering.csv` and
written to `data/processed/creativity/steering_provenance/steering_features.csv`.

The saved high-steering creativity condition used Goodfire hosted controller nudges.
This is provenance for the historical run, not an open-SAE regeneration run.

| Feature index | Old Goodfire label | Nudge | Occurrences |
| ---: | --- | ---: | ---: |
| 4992 | Professional innovation and creative problem-solving | 0.3 | 40 |
| 13142 | Enabling or empowering creative expression and exploration | 0.3 | 40 |
| 20117 | Descriptions of creative unconventional thinking, especially 'thinking outside the box' | 0.3 | 40 |

Phase 2 is to regenerate steered responses with the open Hugging Face SAE by applying
the same feature indices to `meta-llama/Llama-3.3-70B-Instruct` at
`model.layers.50` with `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`.
