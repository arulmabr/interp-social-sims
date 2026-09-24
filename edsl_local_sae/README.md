# EDSL surveys with locally hosted SAE steering

EDSL manages the questions, agents and answer validation. `LocalSAEModel`
connects its model calls to `paper_replication.runtime.PaperRuntime`, which runs
the pinned Llama-3.3-70B model and released Goodfire layer-50 SAE on your GPUs.
Baseline, persona prompting, and SAE steering all use that same model runtime.
No Goodfire inference API or Expected Parrot hosted inference is used.
The model and SAE downloads still require the applicable Hugging Face access.

This is a separate adapter. The existing 5,032-response experiment, its source
identity, and the manuscript remain unchanged. Adapter smoke outputs are
engineering evidence, not additional lottery/ultimatum research results.

## What has been checked

- Pinned EDSL version: **1.0.8**. The historical EDSL version is not established.
- All **9,040** archived system/user message pairs can be generated through EDSL
  without changing their text. Explicit question templates retain the historical
  EDSL option and rationale instructions without adding current defaults twice.
- The actual EDSL survey/validation path is exercised with clearly marked
  synthetic CPU responses for both games, with baseline, zero-edit and positive
  steering request configurations.
- Tests cover exact prompt checks, single generation per fixed batch, condition
  isolation, concurrent-call serialization, model copies, duplicate requests,
  invalid-output preservation, remote-mode rejection, and fresh-guard checks.
- **GPU validation passed on September 24, 2026.** All 80 smoke responses passed
  the direct/EDSL, zero-edit and hidden-state checks for both games. All 320
  full-length diagnostic replays matched the prior direct-local run exactly in
  choices, response text, and input/generated token counts. There were no invalid
  or truncated full-length replies. These fixed-seed replays do not constitute
  additional independent scientific observations.
- Collected evidence: `outputs/collected-session-01/edsl-results/edsl-diagnostic-01/run`.
  Comparison and consistency audit: `outputs/analysis-session-01/`.
  The GPU pod was stopped after collection and has no retained storage.

## Local CPU checks

From the repository root, use a separate virtual environment:

```bash
python3 -m venv edsl_local_sae/.venv
edsl_local_sae/.venv/bin/python -m pip install -r edsl_local_sae/requirements.txt pytest==8.3.5
edsl_local_sae/.venv/bin/python -m pytest edsl_local_sae/tests -q
```

These tests use the checked-in 32-request fixture and need no GPU, credentials,
private label catalog, or generated output directories.

The full prompt audit and diagnostic session additionally require the generated
original-game plan. On a fresh checkout, first supply the matching feature-label
CSV locally and create the catalog used to verify feature IDs and UUIDs:

```bash
edsl_local_sae/.venv/bin/python -m label_pilot.prepare \
  --csv '/path/to/70b feature labels filtered.csv' \
  --output label_pilot/outputs/plan-v3 --candidates 5
edsl_local_sae/.venv/bin/python -m paper_replication.prepare \
  --output paper_replication/outputs/original-games-v1
```

The preparation commands are CPU-only. They use the archived game CSVs already
in this repository and the supplied label catalog; they do not perform model
inference. Existing plan directories are immutable, so reuse an existing valid
plan rather than rerunning preparation over it. Generated plans, results and
the full label catalog are not included in this code publication. The local
evidence paths above describe the completed validation session.

Then run:

```bash
edsl_local_sae/.venv/bin/python -m edsl_local_sae.check audit-prompts \
  --plan paper_replication/outputs/original-games-v1 \
  --output edsl_local_sae/outputs/new-prompt-audit
edsl_local_sae/.venv/bin/python -m edsl_local_sae.check mock-smoke \
  --plan paper_replication/outputs/original-games-v1 \
  --output edsl_local_sae/outputs/new-mock-smoke
```

Output directories must be fresh. CPU checks do not start a pod or load model
weights. A `mock: true` record is never scientific output. The CPU test suite
blocks socket connections while exercising the adapter.

## GPU validation in a new approved session

Use the same two-GPU BF16 runtime environment, then install this adapter's pinned
EDSL requirement. An already running, independently verified shutdown guard is
mandatory. Do not reuse the expired deadline from the preceding paid session.

```bash
python -m edsl_local_sae.check gpu-smoke \
  --plan replication-plan \
  --output edsl-local-validation/new-session \
  --pod-id YOUR_ACTIVE_POD \
  --guard-pid YOUR_VERIFIED_GUARD_PID \
  --deadline YOUR_APPROVED_UTC_DEADLINE
```

This command does not provision, restart or extend a pod. It checks the exact
pod/deadline guard before loading and between batches, leaving four minutes of
reserve. The independent guard remains responsible for stopping provider billing.

The GPU check uses the original lottery reward 100 and ultimatum offer 30,
eight trials per batch, fixed original seeds, and a 96-token engineering cap:

1. Compare direct local baseline output with EDSL-driven local baseline output.
2. Check that EDSL-driven zero-edit steering replays its baseline.
3. Compare direct local steering output with EDSL-driven local steering output.
4. Check actual hidden-state displacement and trace token counts.

It generates 48 EDSL-path and 32 direct-path responses, all marked engineering
only. Exact comparisons mean response text and generated-token counts. The full
research protocol uses 1,000 tokens, so these smoke samples are kept separate.

## Using the adapter for an EDSL research batch

```python
from edsl_local_sae.bridge import FixedBatch, run_batch
from paper_replication.runtime import PaperRuntime

# Instantiate once inside an approved, guarded GPU session.
runtime = PaperRuntime()
# rows: one fixed batch from the immutable request plan; seed: its recorded seed.
backend = FixedBatch(runtime, rows, seed, raw_path=raw_output_path)
edsl_results = run_batch(backend)
```

`rows` carry the game, original prompts, generation settings and feature edits.
Baseline/prompting rows contain no edits; steered rows contain the original
feature IDs and raw-unit additive values. The callback first verifies every
EDSL-rendered prompt, then generates the ordered batch once and routes each
response to its matching EDSL agent. Scheduling cannot mix condition hooks.

Use a new run ID and manifest for EDSL-collected research data. This package
provides the batch adapter and diagnostic CLI, not a new full-sweep scheduler.
Do not append its smoke samples to the prior 5,032-response collection.
Invalid raw answers are retained and cause a visible failure; no silent repair
or hidden additional generation is allowed. A full-sweep invalid-answer policy
must be specified before a new scientific collection.

## Bounded diagnostic session

`edsl_local_sae.session` runs the 80-response GPU gate, followed only on success
by 320 full-length diagnostic replays: baseline and steering for lottery rewards
115 and 125 and ultimatum offers 35 and 40, with all 40 original agents in each
cell. These cells were selected from known discrepancies. Original seeds and
eight-agent batch composition are preserved. Do not pool the replays with prior
data or count them as additional independent observations.

The entire session can be checked on CPU without allocating GPUs:

```bash
edsl_local_sae/.venv/bin/python -m edsl_local_sae.session --mock \
  --plan paper_replication/outputs/original-games-v1 \
  --output edsl_local_sae/outputs/new-session-mock
```

This check passed for all 400 synthetic responses. On a newly approved GPU
session, `label_pilot.deploy attach` verifies the exact pod and arms a fresh
shutdown guard. Then `edsl_local_sae.deploy launch` uploads the source and plan
and runs a separate virtual environment. Use its `status` and
`collect --stop-after` actions to inspect the job, save its outputs and stop the
pod. It does not create or restart pods. An expired authorization/deadline must
never be reused.

`edsl_local_sae.analyze` compares a completed real GPU session against the saved
direct-local run, checking matching seeds, batch sizes, source hashes, token
counts, raw text, choices and steering traces. It refuses synthetic or
incomplete runs. Reports go to a separate output directory, not the manuscript.

## Implementation notes and limits

EDSL 1.0.8 has a closed inference-service enum. This custom `LanguageModel` uses
its `test` in-process slot, while its model name is
`local-llama-3.3-70b-instruct-sae-l50`. It does **not** use EDSL's canned TestService
for GPU inference. `raw_model_response.local_sae.backend` explicitly records
`local_transformers` or `synthetic_cpu_check`. The service enum is not evidence
that a GPU response is synthetic. Always inspect the manifest and backend field.

The adapter uses EDSL's async local runner, with remote inference, API proxy,
remote cache and execution offloading disabled. Model cost is recorded as zero
API-token fees; GPU rental and retained storage are separate provider charges.

Retaining EDSL does not establish numerical equivalence to historical Goodfire
inference or steering. The original platform's strength normalization, exact
model backend, token scope, and full chat framing remain unverified. This
integration lets us isolate the survey-framework contribution instead of
changing survey orchestration and inference together.
