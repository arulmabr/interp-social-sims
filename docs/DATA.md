# Data Inventory

## Creativity

Raw source:

`data/raw/creativity/product_innovation_20251102_202650/`

Files:

- `baseline.csv`
- `prompting.csv`
- `high_temperature.csv`
- `high_steering.csv`

Unit: one saved agent response row. Each row has two evaluated creativity response
columns:

- `answer.detailed_ways_to_use_a_brick`
- `answer.improve_the_stapler_with_many_specific_enhancements`

Derived outputs:

- `data/processed/creativity/torrance_gpt5_eval/`
- `data/processed/creativity/open_sae_response_only_frequency/`
- `data/processed/creativity/open_sae_ablation_analysis/`

## Safe-Risk Choice

Raw source:

`data/raw/games/safe_risky/results_20251018_205613/`

Unit: one saved agent response for a condition and risky reward value.

Derived output:

`data/processed/games/safe_risky/open_sae_calibration/`

Verification:

- 4,200 response units
- 42,000 top-k feature rows
- behavior matches the old `reward_experiment_summary.csv` exactly

## Ultimatum Game

Raw source:

`data/raw/games/ultimatum/results_20251008_201139/`

Unit: one saved responder response for an offer and condition.

Source scale:

- 3 conditions: baseline, prompting, steering
- 17 offers: 10 through 90 by 5
- 40 agents per condition-offer cell
- 2,040 saved response units

Source-audit output:

`data/processed/games/ultimatum/source_audit/`

It contains reconstructed response units, accept/reject behavior summaries, the saved
acceptance-rate plot, and a parsed copy of the old `feature_activations.txt` log.
GPU Open-SAE feature regeneration is pending.

## Trust Game

Raw source:

`data/raw/games/trust/results/`

Unit: one saved receiver return decision for a sent amount and condition.

Source scale:

- 2 conditions: baseline, intervention
- 10 sent amounts: 10 through 100 by 10
- 10 agents per condition-sent-amount cell
- 200 saved response units

Source-audit output:

`data/processed/games/trust/source_audit/`

It contains reconstructed response units, mean-return behavior summaries, and the saved
mean-return plot. GPU Open-SAE feature regeneration is pending.
