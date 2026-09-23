# Collaborator backups: Llama SAE anchor pilot

**Built with Llama.** These downloadable research backups accompany the
[published experiment evidence](../evidence/README.md). They add the saved
LoRA adapter weights, activation tensors, steering vectors, software environments,
and earlier experiment records omitted from the lightweight Git package.

[Download the repository release](https://github.com/arulmabr/interp-social-sims/releases/tag/sae-anchor-backups-2026-09-22).
The binary archives are release assets; an ordinary Git clone does not download
them. GitHub Releases is designed for distributing these files without adding
them to Git history ([GitHub documentation](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases)).

## Restore

Clone the experiment branch, then run the standard-library-only downloader:

```bash
git clone --branch codex/sae-anchor-pilot https://github.com/arulmabr/interp-social-sims.git
cd interp-social-sims
python -m anchor_pilot.restore_backups
```

This downloads every bundle and restores the original relative paths under
`anchor_pilot/outputs/`. Each archive and each contained file is checked against
the SHA-256 hashes in [manifest.json](manifest.json). Identical local files are
left alone; differing files are never overwritten. Restoring does not execute
archived code, unpickle tensors, access a GPU, or start a Runpod session.

For only the latest work and its source adapter:

```bash
python -m anchor_pilot.restore_backups --groups repair replay decision plans
```

For a separate directory, add `--destination /path/to/empty-directory`.
For downloads obtained manually from the release, add
`--archive-dir /path/to/downloads`. Add `--verify-only` to check archives without
extracting them. Disk space is needed for the compressed download, the extracted
files, and temporary verification buffers.

| Bundle | Contents |
|---|---|
| `repair` | Repaired rank-16 LoRA adapter, configuration, activation footprint, directions, training/evaluation records, and executed source |
| `pilot` | Four original CPT adapters, refinement adapter, base activations, footprints, directions, and the completed initial pilot |
| `decision` | Both optimization stages, saved dense/SAE directions, readout gradients, locked interventions, scores, and analysis |
| `replay` | Replay vectors, environments, scores, geometry, and executed source; uses the adapter in `repair` |
| `plans` | Discovery/selection/frozen prompt grids, preregistered plans, analysis locks, and tokenizer checks |
| `history` | Earlier partial/failed snapshots, engineering smoke runs, and CPU fixtures; these are historical records, not additional confirmatory experiments |

The six bundles contain **1,916 research files**, including **137 tensor files**,
and total approximately **739 MiB compressed** (1.06 GB before compression).
All six were restored into an empty directory and every file hash checked.
All 101 distinct tensor files loaded with PyTorch's `weights_only=True` on CPU;
the saved tensors were finite and every adapter state contained only LoRA keys.
This check includes fixture checkpoints and does not count them as trained 70B
adapters. Details are in [checkpoint_validation.json](checkpoint_validation.json).

Earlier snapshots can duplicate files from later ones. This preserves their
original paths and bytes. The asset manifest records every included file;
[excluded_files.json](excluded_files.json) explains every omission from the
local `outputs/` snapshot. Provider/account state, session logs, transfer records,
and interpreter caches remain local. No credentials are bundled. The original
local backups are unchanged.

## Use the repaired adapter and rerun the replay

The latest replay and decision experiments use this restored directory:

```text
anchor_pilot/outputs/repair-backup-20260917/outputs/repair-20260917T062148Z/
```

It contains `adapter/adapter.pt`, `adapter/adapter_config.json`, `footprint.pt`,
and the corresponding reports. The adapter is a custom PEFT state-dictionary
checkpoint, not a standalone Transformers model or a complete Trainer checkpoint.
Load it with the repository's `add_lora` and `restore_adapter` helpers; the
existing replay command configures the matching architecture automatically.

On a separately provisioned GPU machine with the dependencies in
[requirements.txt](../requirements.txt), authenticated access to the base model
and SAE, and enough GPU memory, the following performs a **new GPU evaluation**:

```bash
python -m anchor_pilot.replay \
  --source anchor_pilot/outputs/repair-backup-20260917/outputs/repair-20260917T062148Z \
  --plan anchor_pilot/outputs/replay-plan-v1 \
  --output anchor_pilot/outputs/replay-rerun
```

The current model loader requires two CUDA GPUs with bf16 support and keeps the
70B base weights on the GPUs; the recorded runs used two H200s. Base and SAE
revisions are pinned in the source. Full Meta base-model and Goodfire dictionary
weights are not in these bundles and must be obtained separately using your own
model access. Saved activations cover the recorded captures, not every layer and
token of every run. Optimizer/RNG training state was not saved, so these weights
support evaluation and further training, not an exact mid-step training resume.

For a CPU check of the published scientific results after setup:

```bash
python -m anchor_pilot.verify_evidence
python -m pytest anchor_pilot -q
```

## Interpretation and license

These are the same saved experiments, not new evidence of stable preference
steering. Read [the final result](../DECISION_RESULTS.md) and
[the coauthor corrections](../coauthor_explainer/ERRATA.md) before interpreting
the historical files. New analysis of previously inspected prompts is exploratory.

The distributed adapter collection is named **Llama SAE anchor pilot adapters**.
The [Llama 3.3 Community License](licenses/LLAMA_3_3_LICENSE.txt) and
[NOTICE](licenses/NOTICE) accompany every archive. The upstream
[Meta base model](https://huggingface.co/meta-llama/Llama-3.3-70B-Instruct) and
[Goodfire SAE](https://huggingface.co/Goodfire/Llama-3.3-70B-Instruct-SAE-l50)
retain their applicable license and access requirements.

To rebuild identical archives where the original local backups are available:

```bash
python -m anchor_pilot.package_backups
```

Do not run historical launcher scripts merely to restore files: launchers manage
paid compute. The downloader above needs neither a Runpod account nor a GPU.
