# Feature Labels And Steering Note

Lottery/safe-risk and ultimatum feature descriptions are bundled in
`data/processed/feature_description_lookup.csv`.

The stable key is `feature_index`; text descriptions are cached Neuronpedia labels
for the Goodfire Open-SAE feature space.

Creativity steering provenance is extracted in
`data/processed/creativity/steering_provenance/steering_features.csv`. The saved
creativity steering condition used Goodfire controller nudges on feature indices
`13142`, `20117`, and `4992`.

The executable Open-SAE steering runner is
`scripts/run_open_sae_steering_generation.py`. It hooks `model.layers.50`, encodes
with `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, edits selected feature activations,
decodes back with reconstruction error preserved, and writes a normalized
`response_units.csv`.

The completed creativity steering GPU run is in
`runs/creativity_open_sae_steering_40agent/`: 80 generated response-task units plus
800 post-hoc Open-SAE top-k rows.

The open runner is not claimed to exactly match the deprecated hosted Goodfire
controller's private nudge calibration.
