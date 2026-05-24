# Build A New EDSL Game

This repo is meant to let researchers build new EDSL social simulations and add
mechanistic-interpretability analysis on top. The archived datasets are examples;
new work should start from an EDSL game spec.

## 1. Copy A Game Template

Start with one of the examples in `examples/games/`:

```bash
cp examples/games/safe_risky.py examples/games/my_game.py
```

Each game module must expose:

```python
def build_game_spec() -> GameSpec:
    ...
```

The spec defines the game id, EDSL questions, experimental conditions, agents,
scenario/value sweeps, optional behavior metrics, and a behavior parser.

## 2. Define The Simulation

Use `QuestionSpec` for EDSL questions and `ConditionSpec` for treatment arms.
For games with value sweeps, put scenario dictionaries on each condition and set
`value_field` to the scenario key that should be treated as the reward/offer/sent
amount in downstream plots.

The normalized output schema is:

- `run_manifest.json`: game metadata, model settings, conditions, and output counts.
- `response_units.csv`: one row per model response inspected by Open-SAE.
- `response_units.jsonl`: audit copy of the same response units.
- `behavior_units.csv` and `behavior_summary.csv`: written when the game has a behavior parser.

## 3. Collect Responses With EDSL

Check the local environment first:

```bash
python scripts/check_environment.py
```

Run a tiny deterministic smoke test first:

```bash
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/my_game.py \
  --output-dir runs/my_game_smoke \
  --mock-model \
  --agents 2 \
  --limit-scenarios 1
```

Then run the real model-agent simulation:

```bash
python scripts/run_edsl_social_simulation.py \
  --game-module examples/games/my_game.py \
  --output-dir runs/my_game_full \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --agents 40
```

For local development beside the EDSL checkout:

```bash
pip install -e ../edsl
```

## 4. Inspect With Goodfire Open-SAE

Validate the run folder locally without loading the model:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/my_game_full \
  --dry-run
```

Run Open-SAE inspection on a GPU:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/my_game_full \
  --output-dir runs/my_game_full/open_sae \
  --model-id meta-llama/Llama-3.3-70B-Instruct \
  --sae-repo Goodfire/Llama-3.3-70B-Instruct-SAE-l50 \
  --hook model.layers.50 \
  --top-k 10 \
  --load-in-4bit
```

## 5. Interpret Outputs

The Open-SAE run writes top features per response, aggregate top features by task
and condition, feature summaries, metadata, and plots. Feature indices are the
stable identifiers. Natural-language labels are cached or live Neuronpedia
descriptions for the Goodfire Open-SAE feature space.

## 6. Optional: Generate A Steered Condition

After you identify candidate feature indices, you can generate a new steered run
with the live Open-SAE steering runner. This requires the same GPU/model setup as
Open-SAE inspection.

First validate the prompt selection locally:

```bash
python scripts/run_open_sae_steering_generation.py \
  --run-dir runs/my_game_full \
  --output-dir runs/my_game_steering_smoke_plan \
  --feature-indices 13142,20117,4992 \
  --strengths 0.3,0.3,0.3 \
  --smoke-mode
```

Then run a small GPU generation smoke test:

```bash
python scripts/run_open_sae_steering_generation.py \
  --run-dir runs/my_game_full \
  --output-dir runs/my_game_steered_smoke \
  --feature-indices 13142,20117,4992 \
  --strengths 0.3,0.3,0.3 \
  --steering-mode clamp_min \
  --patch-scope last_token \
  --limit-units 4 \
  --max-new-tokens 256 \
  --load-in-4bit \
  --execute
```

The generated folder is another normalized EDSL run folder. Inspect it with:

```bash
python scripts/run_open_sae_feature_inspection.py \
  --run-dir runs/my_game_steered_smoke \
  --output-dir runs/my_game_steered_smoke/open_sae \
  --top-k 10 \
  --load-in-4bit
```

Steering strength is explicit and recorded. Do not describe these runs as exact
reproductions of the old hosted Goodfire controller unless you have separately
validated that calibration.
