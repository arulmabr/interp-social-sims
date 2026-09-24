# Label-guided SAE pilot

This package extends the inspected `codex/sae-anchor-pilot` codebase with a small,
reproducible experiment for the workflow **human-readable label → candidate
feature → independent activation evidence → controlled intervention → held-out
behavioral evaluation**. It uses the released Goodfire SAE locally; it does not
call Goodfire's interpretation or inference API and does not train a new SAE.
The initial labels remain Goodfire's annotations, not our independent discoveries.

**Author-review instruction:** do not update the manuscript. Collect all results
in `../output/SAE_RESULTS_FOR_REVIEW.md` (relative to the repository root), with
the raw evidence in `../output/SAE_RESULTS_REVIEW_BUNDLE.zip`. The user will decide
what is ultimately incorporated into the paper.

Originally developed from commit `a9fe806edf6157c115996e0534373a99d6fcc247`.
Generated artifacts under `outputs/` and the full label catalog remain local;
they are not part of the code publication. The label-pilot status below predates
the later original-game replication and EDSL integration; see
[`../edsl_local_sae/README.md`](../edsl_local_sae/README.md) for that workflow.

## Current status and access

- CPU validation: 28 tests pass, including exact zero-edit identity, the algebra
  of reconstruction-error-preserving updates, random-control norms, split
  isolation, immutable inputs, full simulated stage orchestration, and resume.
- Current GPU validation: **plan-v3** completed 176/176 smoke evaluations and
  32 exact zero-edit checks. All 20 positive SAE edits displaced activations;
  all 20 negative SAE edits had zero realized displacement. Harvest completed
  352 prompts, with discovery coverage for 9/20 candidates. Feature 31935 lacks
  task-prompt calibration. These are engineering/coverage results, not held-out
  evidence of behavioral efficacy. The independent interpretation packet is ready
  in `outputs/blind-interpretation-v3` (332 items); descriptions and ratings remain pending.
- GitHub: repository read access already works. No GitHub password or token is
  needed for local work. Use existing `gh` authentication if a later push is wanted.
- Runpod: pod `an57eo60e59tmv` was deployed through the signed-in console. The
  account REST API returned 403, so deployment uses console access and direct SSH;
  shutdown uses a verified pod-scoped credential. See `outputs/readiness.json`
  for the final recorded pod status. The approved replacement `9p6x5c96hkjxga` is stopped; both 300 GB volumes are retained at about $4/day combined. `outputs/GPU_VALIDATION.md` is historical plan-v2 only.
- Hugging Face: gated model and SAE access are verified. Credentials are already
  in the local gitignored, permission-0600 file. No further credentials are
  needed. Do not put secrets in chat, Git, command arguments, or result artifacts.

The current protocol is `outputs/plan-v3`: risk, altruism, fairness, creativity.
It replaces the earlier reciprocity/conformity tasks with the paper's ultimatum
responder game. Plans v1/v2, their calibration and their interpretation packets
are historical artifacts, not inputs for this protocol. The earlier `smoke-v1`
failed during hardware debugging and must be excluded. Successful prior runs
and their exact source archives remain preserved for audit.

The checkpoint pins are in `common.py`. The runner uses Llama **3.3** 70B Instruct
and `Goodfire/Llama-3.3-70B-Instruct-SAE-l50`, matching the existing branch. Layer
50 is zero-based. CSV feature identity must correspond to this exact SAE; label
text alone is not proof of correspondence. Activation examples provide an audit
of the selected IDs before interpreting results.

## Scope and scientific safeguards

The current protocol retrieves five candidates each for risk, altruism,
fairness, and creativity, using predeclared keyword queries and BM25 search.
These are proposed task operationalizations for a deadline pilot. They need
substantive review; changing a choice probability is not evidence of a stable
human personality trait. The retrieval method searches the whole supplied
catalog, while this experiment evaluates only four constructs and 20 candidates.
It does not establish that arbitrary labels are reliable steering controls.

The supplied CSV contains 62,059 labeled feature indices. The 3,477 omitted
indices are recorded as filtered according to the user's Goodfire provenance;
we do not infer or reconstruct their labels. Duplicate label strings retain
distinct feature IDs. Full CSV audit and SQLite search remain local; only selected
candidate metadata and protocol inputs are uploaded.

Stages:

1. `smoke`: engineering checks on separate prompts, with short generations.
   Its calibration cannot be used for scientific stages.
2. `harvest`: collect selected-feature activations and token contexts on discovery
   and selection prompts. Doses use the p95 of positive per-prompt maxima over
   discovery user-content tokens, excluding system and special tokens. Features
   without positive coverage receive no invented scale. Selection prompts never
   set doses. Calibration units and the final-token intervention site differ;
   suppression can be zero when the feature is already inactive at that site.
3. `screen`: diagnostic discovery evaluation of every candidate and dose. Resolve
   implementation or task failures before proceeding; protocol changes require
   a new immutable plan.
4. `selection`: compare the candidates and doses on separate scenarios. Select
   the largest target-aligned effect subject to the answer-mass threshold. This
   is a finite search with possible false positives; confirmation is essential.
5. `confirm`: evaluate only a frozen selection lock on untouched scenarios.

Every choice stage includes A/B order reversal and two wordings. Controls are
unmodified inference, an exactly zero SAE edit, a short persona instruction, a
strong task-specific instruction, and a fixed random residual direction matched
to each feature edit's intended float32 displacement norm. BF16 rounding can
alter the realized norm; the runner records that quantity.

The SAE edit is `h + W_dec(z' - z)` with nonnegative edited latents, preserving
the SAE reconstruction residual. The selected feature receives doses
`{-1, -0.5, +0.5, +1} × discovery positive-activation p95`. Interventions affect
the last token of each forward pass, including subsequent generated tokens.
The runner records feature IDs, dose, model/SAE revisions, source hashes, input
hashes, validity mass, timing, and output. No training or quantization is used.

The final lock includes the fixed rank-1 label-only intervention at +0.5 as well
as the selected intervention, making retrieval-only and empirically selected
results distinguishable. If the rank-1 feature lacks activation coverage, that
failure is retained rather than replaced post hoc.

Risk uses the probability of choosing the lottery. Altruism and fairness feature
families use identical neutral ultimatum accept/reject prompts, with the model
as responder. The altruism family's primary outcome is acceptance probability,
matching the paper; acceptance alone cannot separate altruism from self-interest
or efficiency preferences. The original paper feature 31935 is the rank-1
altruism candidate. Fairness uses below-equal offer rejection minus equal-offer
rejection, with equal-weight stratum means, to distinguish selective rejection
from blanket rejection. Both families report the entire acceptance-by-offer
curve and below/equal/above-equal strata. Reports give paired changes against
the same prompt's baseline; the fairness contrast bootstraps scenarios separately
within its below-equal and equal strata.

Discovery matches the paper's 100-token pot with offers 10–90 in steps of five.
Selection uses an 80-token pot; frozen confirmation uses 120/200-token pots.
This is transfer across stakes within the same game. Identical economic
scenarios are paired across the two feature families and never cross splits.
Interpret confidence intervals as descriptive pilot intervals conditional on
these designed tasks, not population-level or multiplicity-adjusted evidence.
The current risk task includes dominated lotteries: report dominance errors
separately before interpreting changes as risk preference. Some retrieved labels
refer to charities, institutions or mathematical division; these may not match
ultimatum behavior. Retain retrieval failures rather than replacing them using
behavioral outcomes.

Creativity outputs are exported as text. **Length is not a quality score.** No
creative condition is selected by length; the predeclared rank-1 intervention
is carried forward. Blinded relevance, feasibility, novelty, and diversity
ratings must be obtained separately, preferably with human spot checks. This
package does not yet automate those ratings or claim broad language-quality
preservation outside the evaluation tasks.

## Local preparation

Run commands from the repository root. On a fresh checkout, create a local
environment first; the CUDA environment is installed by `bootstrap.sh` on a pod.

```bash
python3 -m venv label_pilot/.venv
label_pilot/.venv/bin/python -m pip install -r label_pilot/requirements.txt
label_pilot/.venv/bin/python -m pytest label_pilot/tests -q
label_pilot/.venv/bin/python -m label_pilot.prepare \
  --csv '../70b feature labels filtered.csv' \
  --output label_pilot/outputs/plan-NEW --candidates 5
label_pilot/.venv/bin/python -m label_pilot.access check --model-only
```

Preparation is CPU-only and makes immutable files. Use a new output directory
for changes. Inspect `candidates.json`, `plan.json`, and the task text before
committing to the scientific run. Never pick features using frozen outputs.

## Runpod deployment

Validated configuration: two RTX PRO 6000 Blackwell Server Edition GPUs, 192 GB
combined VRAM, 376 GB host RAM, official `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`
image, 30 GB container disk, and 300 GB volume at `/workspace`. The intended H200
pair was unavailable before deployment. The deployed console quote on September
23, 2026 was approximately $4.23 per pod-hour including running storage
($4.18/hour GPU). The stopped volume quote was $0.083/hour. Prices and
availability can change; inspect the current quote. Do not terminate the pod
until its results are downloaded, because that deletes this volume.

The durable model/SAE cache uses about 145.4 GB. On this host, direct memory-mapped
loading from the network volume stalled. `cache.py` stages pinned files into
`/dev/shm` using sequential reads, then enables parallel checkpoint loading.
Allow at least 320 GB host RAM and about 154 GB free shared memory. Cold download
took about 9 minutes, RAM staging about 5 minutes, and subsequent model loading
about 30 seconds. A stopped pod retains disk cache but loses RAM cache.

This particular GPU pair silently corrupted direct peer transfers. The runtime
now checks copy integrity before loading the model and, when needed, routes
cross-GPU activations through host memory. The selected transport passed 12/12
checks in the validated run. This fallback preserves BF16 model precision and
records its use; it should not be generalized to every GPU of this type.

Initial budget: at most two hours and $25 per session. The remote guard requests
a provider stop by an absolute deadline, independently of inference; an OS
timeout also bounds the job. API-created sessions add a local deadline watcher.
These are software safeguards, not a provider-guaranteed dollar cap: provisioning,
API/network failure, and retained storage can affect the final bill. No job is
allowed to proceed if the in-pod shutdown credential cannot be verified.

With browser deployment, first verify model access, deploy the prepared pod,
then obtain its **direct SSH** host, port, and pod ID from Connect. Use the existing
private key corresponding to its registered public key. Register immediately:

```bash
label_pilot/.venv/bin/python -m label_pilot.deploy attach \
  --session label_pilot/outputs/session-smoke.json \
  --pod-id POD_ID --host DIRECT_SSH_HOST --port DIRECT_SSH_PORT \
  --key ~/.ssh/runpod_ssp --rate 4.18 --budget 25 \
  --deadline ABSOLUTE_UTC_DEADLINE_WITHIN_TWO_HOURS
```

`attach` verifies pod identity and arms the remote shutdown guard. Set the
deadline relative to deployment time, including provisioning. Substitute the
actual GPU hourly rate. Placeholders above are instructions, not runnable values.

Alternatively, if a Runpod account API key is configured, creation and the local
watcher can be handled by the CLI after the read-only access check succeeds:

```bash
label_pilot/.venv/bin/python -m label_pilot.deploy create \
  --session label_pilot/outputs/session-smoke.json --hours 2 --budget 25
```

Do not retry an uncertain provider-create response until checking the console
for an already-created pod. This API does not supply a transaction-level
idempotency guarantee. A successful creation receipt contains the exact pod ID.

Launch and collect:

```bash
label_pilot/.venv/bin/python -m label_pilot.deploy launch \
  --session label_pilot/outputs/session-smoke.json \
  --plan label_pilot/outputs/plan-v3 --stage smoke --run-id plan-v3-smoke
label_pilot/.venv/bin/python -m label_pilot.deploy collect \
  --session label_pilot/outputs/session-smoke.json \
  --output label_pilot/outputs/collected-smoke --stop-after
```

Collection is manual and must occur after completion, before the shutdown
deadline. Inspect `/workspace/sae-label-pilot/results/smoke/exit.json` and `job.log`
over SSH to determine completion. Exit code zero is necessary, not sufficient:
also inspect the run manifest and zero-edit/validity/coverage report. If stopped
before collection, files remain on the volume; restarting is needed for SSH.
The collector writes SHA-256 checksums and requests stop only for that session's
pod. Confirm the console says stopped. Do not leave a completed job idle.

Each session launches one stage. Later sessions use `--stage harvest`, `screen`,
`selection`, or `confirm`, with a fresh deadline/session receipt. A stopped pod
can be restarted to reuse the model cache. Do not extend a still-running session:
its old guard will still stop it at its original deadline. When reusing a pod,
use a new `--run-id` for a different run; for an interrupted run use its original
`--run-id` plus `--resume`. Source, plan, calibration, and lock must match exactly.
Changing candidates requires a new plan. The launcher refuses to overwrite an
existing result directory without explicit resume.

Stages `screen`, `selection`, and `confirm` require `--calibration` pointing to the
downloaded discovery harvest calibration. Confirmation also requires `--lock`.
Only those files, protocol JSON, and allowlisted source files are uploaded.
The exact source upload is preserved under `outputs/uploads/` by SHA-256. Resume
requires that source version; later edits to Python files invalidate the resume
identity. Preserve the receipt and archive for each run.
The Hugging Face token travels through encrypted SSH stdin, then remains in the
job environment; it is not included in the source archive or manifests.

Build the frozen lock locally after downloading selection results:

```bash
label_pilot/.venv/bin/python -m label_pilot.analyze lock \
  --plan label_pilot/outputs/plan-v3 --run PATH_TO_SELECTION_RUN \
  --calibration PATH_TO_HARVEST_CALIBRATION --output label_pilot/outputs/selection-lock.json
label_pilot/.venv/bin/python -m label_pilot.analyze report \
  --plan label_pilot/outputs/plan-v3 --run PATH_TO_RUN --output label_pilot/outputs/report.json
```

The lock refuses incomplete results and failed zero-edit invariance. The
confirmation runner verifies its integrity before loading frozen prompts.

## Independent explanations

```bash
label_pilot/.venv/bin/python -m label_pilot.interpret export \
  --run PATH_TO_HARVEST_RUN --output label_pilot/outputs/blind-interpretation
label_pilot/.venv/bin/python -m label_pilot.interpret score \
  --export label_pilot/outputs/blind-interpretation \
  --predictions PATH_TO_PREDICTIONS_JSON --output label_pilot/outputs/interpretation-scores.json
```

Have a human or separate model describe each feature using only
`explanation_inputs.json`. Keep Goodfire labels and `private_answer_key.json`
out of that context. Lock those descriptions, then ask a separate evaluator to
predict activation on `heldout_challenges.json`. Predictions have the form
`[{"id": "...", "predicted_active": true}]`. Compare Goodfire descriptions and
independent descriptions on identical challenges with blinded evaluation.

This first export samples our task text, not a broad reference corpus; it has
limited activation coverage and correlated examples. General-corpus validation,
adversarial counterexamples, and a social-scientist usability study are follow-on
work. No label interpretation is accepted as a causal explanation solely because
it predicts activation or changes behavior.

## Deadline and resource envelope

The user's Friday September 25 end-of-day AoE deadline is Saturday September 26,
12:00 UTC / 05:00 PDT. Prefer freezing results Friday afternoon PDT to leave time
for analysis and manuscript checks. Do not wait for a large new labeling system.

The account showed $150 available before deployment. Historical workload
forecasts are in `outputs/GPU_VALIDATION.md`; they describe plan-v2. The revised
plan has a larger frozen ultimatum grid and needs new activation coverage before
its cost can be refined. Generation remains the main forecast cost.
Budget $40–60 for the remaining pilot plus retries, subject to its final scope.
This is a planning allowance, not an automated campaign-wide spending limit.
Track receipts and remaining balance before each stage; do not purchase credits
automatically. Screening, behavioral selection, frozen confirmation, and blinded
creative-quality ratings are still required before claiming scientific results.

Measure choice-forward and generation-token throughput during the smoke before
committing to all candidates. Download/setup can dominate the first run. If
the measured plan exceeds time or budget, make a smaller plan **before** scientific
selection/frozen evaluation and disclose the change. Keep the basic controls,
independent task scenarios, and held-out evaluation; reduce candidates first.
Independent interpretation can proceed in parallel with GPU work once activation
contexts exist. Human construct review and blinded creativity ratings remain
researcher inputs; optional model-assisted ratings require separate model access.

Suggested evidence for the revision: catalog/provenance table; coverage and
independent-description validation; held-out effect estimates versus prompt and
random controls; dose-response plots and negative results; and a precise account
of what the pilot does and does not show about label-guided steering.
