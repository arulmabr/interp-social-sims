# Action–preference anchor pilot

## Published experiment package

This directory contains the September 16–19 pilot code, protocols, completed
results and coauthor materials. Start with [the final result](DECISION_RESULTS.md),
then [the exported evidence](evidence/README.md). The
[illustrated eight-page PDF](coauthor_explainer/output/pdf/sae_preference_experiment_illustrated.pdf)
is accompanied by [corrections and interpretation limits](coauthor_explainer/ERRATA.md)
and [exact prompt/feature provenance](coauthor_explainer/COAUTHOR_CLARIFICATIONS.md).

The evidence export includes the saved scientific readouts and execution-source
snapshots, with checksums. Model checkpoints and operational account/deployment
records are not included. Historical cost and stopped-pod statements below
refer to the recorded sessions, not a current billing inspection.

With NumPy, SciPy, PyTorch and pytest installed, verify the published results
and run the local software checks from the repository root:

```bash
python -m anchor_pilot.verify_evidence
python -m pytest anchor_pilot -q
```

The test configuration excludes archived execution snapshots from collection.
GPU-only tests are skipped on a CPU host; no GPU instance is started by these
commands. Running full model experiments additionally requires the pinned
dependencies in [requirements.txt](requirements.txt) and approved model access.

## Results by stage

**Latest matched-steering decision experiment complete:** Start with
[DECISION_RESULTS.md](DECISION_RESULTS.md). Do not launch the full SAE sweep yet.
The LoRA passed the latest provisional checks only in the original wording;
its teacher-probability RMSE rose from 0.042 to 0.115 with new wording. Dense
and ten-feature SAE steering each passed 0/8 target × seed × wording cells.
The raw gradient was classified as action-like. These findings do not establish
that the SAE dictionary lacks preference capacity.

All 28 conditions on 432 frozen prompts are saved; 396 remote files passed
SHA-256 verification. The session pod is stopped at $0/hour, with a conservative
session estimate of **$14.55**. Existing smoke-pod storage remains separate.
[DECISION_PLAN.md](DECISION_PLAN.md) records the protocol;
[DECISION_NEXT_STEPS.md](DECISION_NEXT_STEPS.md) gives the bounded follow-up.

**Replay diagnostic complete:** Start with [REPLAY_RESULTS.md](REPLAY_RESULTS.md).
Full-state replay exactly reproduces the LoRA. Restricting positions, averaging
across prompts, and SAE approximation each lose behavioral fidelity. The best
tested SAE oracle improves over baseline but does not reproduce the adapter.
All 16 conditions on 540 new frozen prompts are saved and audited; 124 remote
files verified, and the new GPU pod is stopped. Conservative session estimate:
$2.07. [REPLAY_PLAN.md](REPLAY_PLAN.md) records the predeclared comparisons.

**Repair complete:** Start with [REPAIR_RESULTS.md](REPAIR_RESULTS.md).
The stricter format fixed answer validity, and the repaired LoRA passed
provisional frozen recovery checks. The tested residual/SAE replays still
fell short. All 29 conditions are saved and audited; the GPU is stopped.
The conservative session estimate is $9.00, below the approved $20 cap.
[REPAIR_PLAN.md](REPAIR_PLAN.md) records the predeclared design and tolerances.
The completed first pilot results below remain unchanged.

**The real GPU pilot, analysis, backup and shutdown are complete.**
Start with [PILOT_RESULTS.md](PILOT_RESULTS.md) for the findings and artifact links.
Four CPT adapters, 101 original conditions and an 11-condition fresh-grid
refinement were evaluated. The implementation works, but the positive anchor
still misses the planted parameters and dose calibration failed answer validity.
The full external go/pivot rule was not supplied; scientific classifications
remain unset.

Both new pilot pods are stopped at $0/hour, with 193 raw files verified locally.
The original smoke pod's retained volume continues at $0.083/hour.
[PROTOCOL.md](PROTOCOL.md) records the design, deviations and approved compute
cap. [RESULTS.md](RESULTS.md) retains the earlier engineering smoke.

From the repository root, after raw outputs are copied locally:

```bash
anchor_pilot/.venv/bin/python -m anchor_pilot.report --run PATH_TO_RUN --bootstrap 100
anchor_pilot/.venv/bin/python -m anchor_pilot.refine_report --run PATH_TO_RUN/refinement --bootstrap 100
uv pip install --python anchor_pilot/.venv/bin/python -r anchor_pilot/requirements-report.txt
anchor_pilot/.venv/bin/python -m anchor_pilot.figures --run PATH_TO_RUN
anchor_pilot/.venv/bin/python -m anchor_pilot.audit --backup PATH_TO_BACKUP --run PATH_TO_RUN
```

CPU software checks: 18 passed, one two-GPU test skipped locally. On the
Runpod image, all 19 passed, including the two-GPU bf16 backward path.
The saved credential `first-token` has verified model and SAE access; tokens
are never written into source, result artifacts, or command arguments.

## What the real-model smoke measures

1. Load Llama-3.3-70B-Instruct in bf16 without quantization or CPU/disk offload.
   Resolve and log its exact Hugging Face revision.
2. Read the released layer-50 decoder at the pinned SAE revision.
3. Verify A/B are single continuation tokens in the actual chat template.
4. Use four development prompts: gain/loss crossed with original/swapped option
   labels. This deliberately tiny fixture is not a CPT identification grid.
5. Differentiate risky-minus-safe logits with respect to the final prompt
   residual at zero-based block outputs 48 and 50. Freeze model parameters;
   backpropagate only through the suffix after the edited block.
6. Average the raw prompt gradients, then normalize. Record promptwise
   gradient magnitudes and their alignment with the mean.
7. Check zero-dose identity and finite differences. The bf16 finite-difference
   ladder records errors for review; passing CPU checks does not validate bf16.
8. Apply norm-matched gradient, random, and candidate decoder directions at the
   same final prompt position. Record both intended and realized bf16 norms,
   answer-label probability mass, and risky-vs-safe logit changes.
9. Compute feature cosines and a signed, sparse decoder reconstruction of the
   readout direction. The sparse direction is renormalized before intervention;
   its original reconstruction error is also saved.

The paper candidate features are 184, 4237, 31935, 13142, 20117, and 4992.
The creativity triple uses equal latent weights provisionally. Signed sparse
coefficients are allowed; these are decoder-vector perturbations and are not
guaranteed to correspond to feasible nonnegative encoder activation edits.

The provisional rho is 1 residual unit per edited token. It is an engineering
probe, not a selected or preregistered experimental dose. Results are all
development-only. Scientific thresholds remain null.

## Run locally

From the repository root:

```bash
anchor_pilot/.venv/bin/python -m pytest anchor_pilot/test_core.py -q
anchor_pilot/.venv/bin/python -m anchor_pilot.preflight --hf-token-name first-token
anchor_pilot/.venv/bin/python -m anchor_pilot.smoke --fixture \
  --output anchor_pilot/outputs/new-cpu-check
```

The preflight checks gated model access without downloading model weights or
printing credentials. Authenticate using an HF account already approved for
`meta-llama/Llama-3.3-70B-Instruct`. Do not put credentials into source or chat.
On this Mac, use `--hf-token-name first-token` for both preflight and real-model
smoke commands. On the pod, supply the authorized credential securely through
the runtime environment; the saved-token name is not itself a credential.

## Original engineering-smoke session

- Secure Cloud, 2x H200 SXM, 282GB total advertised VRAM.
- Official template `runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404`.
- 30GB container disk and 300GB volume disk mounted at `/workspace`.
- SSH enabled; Jupyter disabled. Use existing authorized SSH access.
- Observed GPU price: $9.18/hour; running disk: $0.046/hour.
- Total observed running price: approximately $9.226/hour.
- Stopped volume disk continues billing at $0.083/hour at the observed rate.
- Availability and pricing must be rechecked at deployment.

Resolve gated model access before renting. Get authorization for the concrete
paid session before deployment. A proposed two-hour session would be about
$18.45 at the observed running rate, before subsequent stopped storage.
No budget or deployment approval is inferred from the displayed account balance.

On the pod, after transferring this package and securely setting model access:

```bash
bash anchor_pilot/run_smoke.sh
```

The script creates a venv that reuses the template's installed CUDA PyTorch,
then limits the model process to 45 minutes **after setup**. It does not
stop the pod or cap billing. `stop_guard.py` was separately armed and verified
on this pod using its injected pod-scoped credential and the Runpod GraphQL API.
Arrange a separate pod stop deadline before running,
copy outputs back, and stop the GPU promptly. Termination deletes volume-disk
data and should only occur after verified backup and authorization.

Outputs include `report.json`, `prompts.json`, `interventions.json`, and
`directions.pt`. The runner refuses to overwrite an existing output directory.

## Scientific decision boundary

Apply the external scientific go/pivot rule when provided; retain diagnostic
conclusions meanwhile. GPU execution and software validation alone do not
establish a valid preference anchor.

This package does not replace the existing paper reproduction code.
