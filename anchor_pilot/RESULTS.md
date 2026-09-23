# GPU smoke-test results — 2026-09-16 Pacific

**Completed on Llama-3.3-70B-Instruct in bf16. GPUs stopped and independently verified in the Runpod UI.**

This was the approved provisional engineering smoke test, not the full CPT/LoRA pilot. Scientific go/pivot thresholds remain unset. No LoRA was trained and no preference parameters were recovered.

## Execution and verification

- Pod: `9xc474y2j2oumc` (`sae-anchor-smoke`), Secure Cloud, 2×H200.
- Base model revision: `6f6073b423013f6a7d4d9f39144961bfbfbc386b`.
- SAE revision: `128ee921ecd1b8b3a87d776cbcc357c0855da134`.
- Unquantized bf16 parameters; model placement on GPUs, with no CPU/disk offload.
- Six unit checks passed locally and on the pod.
- Four development prompts: gain/loss × original/swapped A/B labels; 89 tokens per prompt.
- A and B are valid single continuation tokens (IDs 32 and 33).
- Two runs, each with 48 intervention records. The second run refined finite-difference step sizes; it is not an independent scientific replication.
- All eight raw result files were copied to this Mac and verified against remote SHA-256 hashes.
- Zero-dose logits and answer probabilities were exactly unchanged at both tested layers.
- Largest relative discrepancy between requested and realized residual norm: 0.0764%.
- Peak allocated GPU memory: GPU 0: 65.83 GiB, GPU 1: 66.51 GiB.
- Initial model run (including model download/load): 104.5s; cached refinement run: 37.7s. These durations exclude deployment/setup.

## Gradient validation

Central finite differences at epsilon = 0.1 residual units:

| Block output (zero-based) | Autograd derivative | Numerical derivative | Relative difference |
|---|---:|---:|---:|
| 48 | 39.4304 | 40.0000 | 1.44% |
| 50 | 36.7015 | 36.8750 | 0.47% |

The smallest tested steps were noisy in bf16; larger steps were nonlinear. The complete step ladder is retained in the two raw reports. The comparison above is an engineering diagnostic selected after examining the initial ladder, not a preregistered scientific test.

## Diagnostic findings

1. **Answer order matters substantially in this fixture.** The averaged direction increased risky-minus-safe logits in both original-label prompts and decreased them in both swapped-label prompts, at both layers. This documents dependence on answer labeling in the provisional averaged anchor. The four-prompt result is not a population estimate or evidence of preference change.
2. **Candidate-feature cosines with the mean layer-50 gradient were small in this fixture.** These values do not establish construct validity or invariance across a larger reward grid.

| Feature | Cosine with mean layer-50 gradient |
|---|---:|
| 184 | 0.01139 |
| 4237 | -0.00535 |
| 31935 | 0.00320 |
| 13142 | 0.01136 |
| 20117 | 0.01274 |
| 4992 | 0.01271 |

3. **The signed three-feature approximation was poor:** relative reconstruction error 0.9616; selected features 2450, 42445, 33657. The best positive-cosine single feature was 2450 (0.1957). This concerns this k=3 approximation of this averaged direction; it does not demonstrate that the full SAE dictionary cannot represent an action shortcut.

## Cost and retained state

- Compute: stopped; Runpod UI showed **Not running** and a Start button after the stop request.
- Deployment requested at 03:42 UTC; stop verified at 03:54 UTC. Approximately 12 minutes elapsed, well inside the approved two-hour window.
- Running rate was $9.226/hour including storage. The displayed balance moved from $122.96 to $121.45 at verification; this observed difference is not a finalized billing statement.
- The 300GB volume is retained with model cache and outputs, at **$0.083/hour (about $1.99/day)**. GPU compute charges have stopped.
- The approved HF token was supplied via the process environment rather than written by our code to a token file.
- A separate pod-scoped stop watchdog had been armed for 05:35 UTC and was no longer needed after the early stop.

## Remaining work for the full pilot

The shared bf16 gradient/additive-steering path is operational. Next come the CPT identification grid and synthetic recovery checks, frozen splits and doses, probe/persona directions, LoRA training and held-out recovery, LoRA SAE footprints and replay, and the final scientific go/pivot rule. Answer-label/order controls need explicit treatment in that design.

## Artifacts

- [Initial raw report](evidence/smoke_initial/report.json)
- [Refined raw report](evidence/smoke/report.json)
- [Refined intervention records](evidence/smoke/interventions.json)
- Verified artifact hashes (retained in the local operational archive)
- [Runpod status record](runpod_draft.json)
