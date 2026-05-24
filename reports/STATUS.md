# Current Platform And Replication Status

Date: 2026-05-23

## Platform Layer

- Public framing is platform-first: build EDSL social simulations, collect fresh
  model-agent responses, then inspect mechanisms with Goodfire Open-SAE.
- Reusable EDSL game specs exist for creativity, safe-risk/lottery, ultimatum,
  and trust.
- New EDSL runs write `run_manifest.json`, `response_units.csv`, and
  `response_units.jsonl`.
- Open-SAE inspection supports normalized EDSL run folders through `--run-dir`.

## Complete

- Creativity GPT-5 Torrance judging over 320 saved response-task rows.
- Creativity Open-SAE response-only frequency decomposition over 320 response-task rows.
- Safe-risk Open-SAE calibration over 4,200 saved responses.
- Safe-risk behavior exactly matches the old saved behavior summary.
- Ultimatum source audit over 2,040 saved responses, with 51 behavior cells and parsed old Goodfire log rows.
- Trust-game source audit over 200 saved responses, with 20 behavior cells.
- Ultimatum Open-SAE GPU rerun over 2,040 saved responses, with 20,400 top-k rows.
- Trust-game Open-SAE GPU rerun over 200 saved responses, with 2,000 top-k rows.
- Offline feature-description lookup for creativity, safe-risk/lottery, ultimatum, and trust.
- Creativity high-steering Goodfire controller provenance for features `13142`, `20117`, and `4992`.
- Open-SAE runner supports `creativity`, `safe_risky`, `ultimatum`, and `trust` dataset kinds.
- Legacy archived-output loaders remain available for the existing paper fixtures.

## Caveats

- Goodfire Ember hosted natural-language labels are unavailable.
- Natural-language labels in processed Open-SAE outputs are Neuronpedia/Open-SAE
  replacement labels.
- Current steering support documents saved Goodfire controller provenance; open-SAE
  steering regeneration remains a phase-2 GPU extension.
- The old unmasked creativity Open-SAE output collapsed to `<|begin_of_text|>` and is
  retained only as a failure control in the ablation report.

## Pending

- Optional polish: produce a final paper-layout figure deck from the included per-game plots.
