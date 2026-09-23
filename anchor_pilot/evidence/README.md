# Saved evidence for the September anchor pilot

These files are byte-identical exports from the completed local backups. They
contain synthetic task prompts, saved model readouts, plans, fitted analyses,
tables, figures and archived execution code. Exporting them did not run any
new experiment. [manifest.json](manifest.json) records the original relative
archive path, size and SHA-256 hash of each file.

| Stage | Start here | Scope |
|---|---|---|
| Final matched comparison | [decision_analysis.json](decision/decision_analysis.json), [table](decision/decision_comparison.csv) | 28 conditions; 432 frozen prompts per condition |
| Replay diagnostic | [report](replay/REPORT.md), [table](replay/comparison.csv) | 16 conditions; 540 frozen prompts per condition |
| Repaired LoRA | [report](repair/REPORT.md), [table](repair/comparison.csv) | Provisional recovery and residual/SAE diagnostics |
| Initial pilot | [report](pilot/REPORT.md), [table](pilot/comparison.csv) | 101 conditions; retained to show earlier failures |
| Initial pilot refinement | [report](pilot/refinement/REPORT.md), [table](pilot/refinement/comparison.csv) | 11-condition fresh-grid follow-up |
| Engineering smoke | [initial](smoke_initial/report.json), [refined](smoke/report.json) | Execution checks, not scientific confirmation |

Use the [current interpretation](../DECISION_RESULTS.md) and
[coauthor corrections](../coauthor_explainer/ERRATA.md) when reading older
reports. The LoRA's earlier provisional pass did not establish robustness to
the wording change in the later comparison. Older embedded paths and historical
audit statements are preserved in the exported records as provenance.

## Verify without a GPU

From the repository root, in a Python environment with NumPy and SciPy:

```bash
python -m anchor_pilot.verify_evidence
```

This verifies all exported hashes, checks prompt/readout counts, recomputes
teacher-probability errors for the final 28 conditions and replay errors for
all 16 replay conditions, and checks the exact full-state replay identities.
It does not refit the behavioral models or repeat their bootstrap intervals.
The recorded fits, raw readouts and executed analysis source are included for
that deeper review.

## Additional checkpoints and backups

Adapter weights, activation tensors, vector checkpoints, and earlier research
snapshots are now available in the [collaborator backup release](../backup_release/README.md).
They remain outside Git history; the restore command downloads and verifies them.
A fresh clone can inspect the numerical evidence immediately, while evaluating
saved adapters additionally requires those downloads and separate model access.
Full base-model/SAE weights, account/billing and deployment state, virtual
environments, caches and operational logs are not distributed.

Archived execution code may reference its original `outputs/...` locations.
Historical transfer-audit scripts also require the private provider records
that are not in the release. Use the CPU verifier above for this evidence
subset, and the backup restore tool for the released archive checksums.

To recreate this export where the original local archives are available:

```bash
python -m anchor_pilot.package_evidence
```

No GPU rental or new scientific result is implied by either command.
