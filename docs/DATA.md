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

Primary Open-SAE calibration raw source:

`data/raw/games/safe_risky/results_20251018_205613/`

Unit: one saved agent response for a condition and risky reward value.

Derived output:

`data/processed/games/safe_risky/open_sae_calibration/`

Verification:

- 4,200 response units
- 42,000 top-k feature rows
- behavior matches the old `reward_experiment_summary.csv` exactly

Paper five-condition source fixture:

`data/raw/games/safe_risky/results_20251008_225522/`

Source scale:

- 5 conditions: baseline, barely_prompting, slightly_prompting, lite_steering,
  steering
- 35 risky rewards: 10 through 180 by 5
- 40 agents per condition-reward cell
- 7,000 saved response units

Derived source audit:

`data/processed/games/safe_risky/source_audit_five_condition/`

This source audit reconstructs response units and behavior plots for the paper
Figure 6-style five-condition safe-risk run. It does not load the model or SAE.
The full Open-SAE feature rerun over all 7,000 units is also included:

`data/processed/games/safe_risky/open_sae_five_condition_full/`

The GPU helper used for that refresh is:

`runpod/run_safe_risky_five_condition_open_sae.sh`

Full-refresh scale with `--top-k 10`: 70,000 top-k feature rows.

## Release Manifests

- `DATA_MANIFEST.tsv`: file sizes and SHA-256 hashes for release files.
- `reports/RELEASE_COMPLETION_AUDIT.json`: machine-readable requirement audit.
- `reports/RELEASE_COMPLETION_AUDIT.md`: human-readable version of the same audit.

`DATA_MANIFEST.tsv` includes the selected completed `runs/` evidence folders used
by the release audit, but excludes ad hoc future runs, Python caches, local model
caches, logs, and prior archives.

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
