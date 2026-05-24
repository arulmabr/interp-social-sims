Yeah, I set this up in the repo now.

- Lottery/safe-risk and ultimatum feature descriptions are bundled in `data/processed/feature_description_lookup.csv`.
- The stable key is `feature_index`; the text descriptions are cached Neuronpedia labels for the Goodfire Open-SAE features.
- The safe-risk/lottery bundle has 1,080 lookup rows; ultimatum has 540 lookup rows.
- Creativity steering provenance is extracted in `data/processed/creativity/steering_provenance/steering_features.csv`.
- The saved creativity steering used Goodfire controller nudges on feature indices `13142`, `20117`, and `4992`.
- I also added a phase-2 open-SAE steering entrypoint that validates the feature indices and prompts, but it does not claim to regenerate steered responses yet.

So yes, we can describe lottery and ultimatum from the stored SAE feature numbers. For steering, current repo support is provenance for the saved Goodfire-controller run; full open-SAE steering regeneration is the next GPU phase.
