# Replay diagnostic — September 2026

Status: execution complete, GPU stopped. See [REPLAY_RESULTS.md](REPLAY_RESULTS.md).
The design below was fixed before the new frozen responses were collected;
the immutable JSON manifest is archived with the run.

The repaired LoRA approximately recovered the synthetic preferences, while a
constant final-token shift and its SAE approximation did not. This experiment
locates the loss before attributing failure to the SAE dictionary.

Reuse the saved rank-16 repair checkpoint 700 and pinned bf16 70B model. No new
training. The adapter only changes blocks 0–50, so copying its entire block-50
output into the base model must reproduce the unchanged suffix computation.
Use the same strict A/B instruction, masks, positions, batches and no KV cache.

Run 16 fixed conditions: base, LoRA, all-position state replacement, all-position
additive difference, final-token replacement, context-only replacement, original
mean final-token shift, unit-norm mean shift, encoder-difference SAE replay at all
positions and at the final token, 10/30-feature subspace replay at all positions
and at the final token, and 10/30-feature decoded discovery-mean shifts.

The SAE basis uses the OMP indices already chosen using saved discovery shifts.
Project into the selected decoder span with QR; the result remains a signed
linear combination of those decoder columns. Encoder replay adds the decoded
latent difference to the base residual; it never substitutes the reconstruction
of the baseline. Preserve original magnitudes except the separately named unit
mean control. No selection or dose tuning on new responses.

Prompt-specific raw and SAE replays require LoRA activations for each evaluated
prompt. They are oracle representation diagnostics, not deployable independent
steering. The fixed mean controls do not require those per-prompt adapted states.
The 10/30-feature supports are geometric, not causally selected.

Validate full-state replacement/addition on 36 existing selection prompts; halt
if maximum risky-choice probability difference from LoRA exceeds 1e-6. Freeze
all methods before 540 new held-out prompts, balanced over three frames, five
probabilities, three stakes, six new reward ratios and both answer orders.
Check new prompt strings against saved earlier grids and verify five-parameter
synthetic identifiability before GPU execution. The manifest records source
hashes, feature supports, methods and thresholds.

Report error against LoRA and teacher separately, answer mass, CPT fits,
answer-order effects and dominance violations. A provisional reproduction target
is RMSE to LoRA <=0.01 and minimum answer mass >=0.99. These operational targets
are not the missing externally specified scientific go/pivot rule.

Interpretation: all-state failure indicates implementation trouble; a drop from
all-state to final-only indicates position restriction; an additional drop to
mean-only indicates prompt averaging. SAE-vs-raw comparisons must hold token
scope fixed. Successful oracle SAE replay would show representational capacity,
not a discovered preference feature. Failed replay restricts the tested encoder
or feature-selection method; it cannot establish that no SAE combination works.

Use the existing two-GPU configuration for inference, stay within the previously
used $20/two-hour session ceiling, arm an independent absolute stop guard before
large uploads, continuously back up results, verify hashes, and stop promptly
after completion. Do not broaden into a full feature sweep in this diagnostic.
