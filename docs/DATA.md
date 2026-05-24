# Data Inventory

## Generated EDSL Runs

New social simulations should be collected with
`scripts/run_edsl_social_simulation.py`. Each generated run folder has:

- `run_manifest.json`: game id, model settings, EDSL game module, questions,
  conditions, scenario limits, and output counts.
- `response_units.csv`: one row per model response to inspect with Open-SAE.
- `response_units.jsonl`: audit copy of the normalized response units.
- `edsl_results/*.csv`: raw EDSL result exports by condition.
- `behavior_units.csv`, `behavior_summary.csv`, and `behavior_summary.png` when
  the game spec defines behavior metrics.

The Open-SAE runner consumes these folders through `--run-dir`. The archived
datasets below remain regression fixtures and paper-replication examples.

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

Derived outputs:

- `data/processed/games/ultimatum/source_audit/`
- `data/processed/games/ultimatum/open_sae_full/`

The source audit contains reconstructed response units, accept/reject behavior
summaries, the saved acceptance-rate plot, and a parsed copy of the old
`feature_activations.txt` log. The full Open-SAE output contains 20,400 top-k rows
over 2,040 response units, reward-level aggregate features, condition-level aggregate
features, behavior summaries, and diagnostics.

## Trust Game

Raw source:

`data/raw/games/trust/results/`

Unit: one saved receiver return decision for a sent amount and condition.

Source scale:

- 2 conditions: baseline, intervention
- 10 sent amounts: 10 through 100 by 10
- 10 agents per condition-sent-amount cell
- 200 saved response units

Derived outputs:

- `data/processed/games/trust/source_audit/`
- `data/processed/games/trust/open_sae_full/`

The source audit contains reconstructed response units, mean-return behavior summaries,
and the saved mean-return plot. The full Open-SAE output contains 2,000 top-k rows over
200 response units, sent-amount-level aggregate features, condition-level aggregate
features, behavior summaries, and diagnostics.
