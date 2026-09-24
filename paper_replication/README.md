# Original lottery and ultimatum replication

This runner generates new responses locally from the original archived EDSL
prompts. It uses Llama-3.3-70B-Instruct and Goodfire's released layer-50 SAE,
without calling Goodfire's platform. The manuscript must remain unchanged;
results belong in separate author-review files.

The immutable input plan contains 7,000 lottery trials (baseline, barely
prompting, slightly prompting, lite steering, steering) and 2,040 ultimatum trials
(baseline, prompting, steering). Each original reward/offer-condition cell has
40 model-agent trials. Archived outputs are retained separately for comparison
and are never sent as answers to the inference runner.

Original rendered system/user messages, temperature 0.5, top-p 1 and a 1,000-token
generation limit are preserved. The local sampler explicitly disables top-k
filtering; the historical hosted top-k default is unknown. Generation is batched
in fixed groups of eight, with recorded seeds shared across corresponding
condition batches. Seeds and the exact historical hosted checkpoint are not
available, so bitwise replay is not claimed.

Before the first GPU launch, scheduling was fixed to cover each game's midpoint,
then endpoints and remaining gaps, with baseline and steering prioritized in
both games within each coverage round. This makes a time-limited session useful
across the domain. Scheduling does not use generated or historical outcomes;
it changes neither trials nor their fixed batch seeds. Incomplete coverage must
still be reported as partial, not as a result for the entire reward/offer grid.

The local edit is additive in **raw released-SAE units**, clipped at zero and
applied at the last token of every forward pass. It preserves the SAE
reconstruction residual. Lottery uses features 184 and 4237 simultaneously, with
the original numeric values (0.7/0.5 standard and 0.6/0.4 lite); ultimatum uses
31935 at 0.5. These numbers are not asserted to equal the hosted controller's
private scale. This is an explicitly specified local replication, not verified
server equivalence. Natural baseline activation is not required for a positive
edit.

A mandatory GPU smoke checks 16 exact zero-edit replays and 16 positive edits
before full generation. Full responses, token counts, truncation, sampling seeds
and feature-edit traces are saved. An invalid first-line answer receives one
documented local repair prompt at the original temperature; both attempts are
preserved. Invalid final outputs remain in reported denominators, with valid-only
rates also available. This repair template is not claimed to reproduce EDSL's
unavailable historical repair wording.

Preparation verifies controller IDs/UUIDs against the supplied feature catalog.
On a fresh checkout, first run `python -m label_pilot.prepare --csv
<local-label-csv> --output label_pilot/outputs/plan-v3 --candidates 5` to create
the required `catalog.sqlite`. The full label CSV and generated plans are not
committed to this repository. Use `python -m paper_replication.prepare --output
<new-plan-directory>` to extract inputs from the tracked historical game CSVs.
The prepared `outputs/original-games-v1` is immutable. CPU verification:
`python -m pytest paper_replication/tests label_pilot/tests -q`.

The deployment adapter accepts a freshly attached `label_pilot.deploy` session
with an exact pod ID, SSH endpoint and at most two hours remaining. It uploads
only allowlisted source plus the plan/request file, checks the remote shutdown
guard, and never puts credentials in an archive. The absolute session deadline is
passed into the runner and recalculated after bootstrap, reserving collection
time before the independent pod stop. Every new paid session needs
a new absolute deadline; an expired guard or session must not be reused.

Launch `python -m paper_replication.deploy launch --session <session.json> --plan
<plan-directory> --run-id <unique-run-id>`. The default runs mandatory smoke and
then both games. Use `--smoke-only` for engineering validation alone. A resumed
run requires the identical source, plan and batch size. Collect with
`python -m paper_replication.deploy collect --session <session.json> --output
<fresh-collection-directory> --stop-after`.

Analysis compares local baseline/prompting/steering curves with historical
hosted curves, separately labeled. Model-agent repetitions are not independent
human participants. A changed acceptance curve is not by itself evidence of
altruism; changed lottery choices are not by themselves a stable preference.
