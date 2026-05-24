# Current Replication Status

Date: 2026-05-23

## Complete

- Creativity GPT-5 Torrance judging over 320 saved response-task rows.
- Creativity Open-SAE response-only frequency decomposition over 320 response-task rows.
- Safe-risk Open-SAE calibration over 4,200 saved responses.
- Safe-risk behavior exactly matches the old saved behavior summary.
- Ultimatum source audit over 2,040 saved responses, with 51 behavior cells and parsed old Goodfire log rows.
- Trust-game source audit over 200 saved responses, with 20 behavior cells.
- Open-SAE runner supports `creativity`, `safe_risky`, `ultimatum`, and `trust` dataset kinds.

## Caveats

- Goodfire Ember hosted natural-language labels are unavailable.
- Natural-language labels in processed Open-SAE outputs are Neuronpedia/Open-SAE
  replacement labels.
- The old unmasked creativity Open-SAE output collapsed to `<|begin_of_text|>` and is
  retained only as a failure control in the ablation report.

## Pending

- Run GPU feature decompositions for ultimatum and trust-game.
- Produce final paper-style figures for all games from the open pipeline.
