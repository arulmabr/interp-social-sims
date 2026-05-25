# Feature Labels

The old project used Goodfire's hosted Ember API for feature inspection and returned
hosted natural-language feature labels.

For this release, Goodfire's old hosted endpoint is unavailable. The open-source
replacement uses:

- `meta-llama/Llama-3.3-70B-Instruct`
- `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`
- `model.layers.50`

The SAE weights provide feature indices and decoder/encoder parameters. They do not
include the original hosted Ember label database. We therefore fetch/cache
Neuronpedia/Open-SAE labels when available and fall back to feature indices otherwise.

For the released outputs, the repo includes an offline label bundle:

`data/processed/feature_description_lookup.csv`

This file is built from already-cached labels in the processed Open-SAE folders. It
does not require a live Neuronpedia request to reproduce the released bundle. It includes
safe-risk/lottery, ultimatum, creativity, and trust top-feature descriptions with:

- `feature_index`: stable SAE feature identifier.
- `feature_label`: cached Neuronpedia description.
- `label_source`: `cached_neuronpedia` for current released rows.
- `neuronpedia_api_url`: the matching feature endpoint, e.g.
  `https://www.neuronpedia.org/api/feature/llama3.3-70b-it/50-resid-post-gf/<feature_index>`.

The short answer is: the SAE is still Goodfire; the replacement descriptions are cached
Neuronpedia labels attached to the same feature indices.

For paper-facing historical Goodfire activation labels, use:

- `data/processed/paper_activation_label_crosswalk.csv`
- `data/processed/steering_feature_label_crosswalk.csv`
- `reports/PAPER_ACTIVATION_LABEL_CROSSWALK.md`
- `reports/PAPER_ACTIVATION_INDEX_SEARCH_AUDIT.md`
- `reports/PAPER_ACTIVATION_GIT_HISTORY_AUDIT.md`
- `data/processed/paper_activation_neuronpedia_approx_matches.csv`
- `reports/PAPER_ACTIVATION_NEURONPEDIA_APPROX_MATCHES.md`

These files separate exact `feature_index` matches from historical rows that only
preserve the old Goodfire label. Do not treat old-label-only rows as exact
Neuronpedia feature identity matches.

The approximate-match table is a human-readable bridge for old labels that lack a
recoverable index. It uses Neuronpedia explanation search and should be described
as semantic label replacement, not as feature identity.

Recommended language:

> Behavior and saved-response data are reproduced exactly where stated. Feature
> activations are reproduced from the open Goodfire SAE. Natural-language labels are
> replacement interpretability labels and may differ from historical Goodfire Ember
> labels.
