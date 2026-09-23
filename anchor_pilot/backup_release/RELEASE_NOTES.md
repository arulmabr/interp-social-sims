Built with Llama.

This research archive accompanies the `codex/sae-anchor-pilot` branch. It adds
the local scientific backups from the September SAE steering experiments:
trained LoRA adapters, saved activation tensors, steering vectors, intermediate
and final readouts, environment versions, archived execution source, plans, and
earlier trial/fixture records.

**Six bundles, 1,916 research files, 137 tensor files, approximately 739 MiB
compressed.** The original relative paths and file bytes are preserved. The
`history` bundle includes incomplete/failed trials and CPU fixtures, separately
from the completed runs. No new model experiment was performed to create this
release. These are provisional research artifacts, not a validated preference
steering model.

After cloning the experiment branch, restore all bundles with:

```bash
python -m anchor_pilot.restore_backups
```

For only the latest comparisons and their source adapter:

```bash
python -m anchor_pilot.restore_backups --groups repair replay decision plans
```

The downloader verifies the archive and per-file SHA-256 hashes and refuses
to overwrite different local files. No GPU or Runpod account is needed for
restoration. All six archives were successfully restored into an empty
directory before publication; 40 software tests passed, with 3 GPU-only tests
skipped. All 101 distinct tensor checkpoints loaded on CPU using
`weights_only=True` and contained finite tensors; adapter states contained
only LoRA keys. These counts include test fixtures.

See `anchor_pilot/backup_release/README.md` for adapter loading, replay commands,
bundle contents, and exclusions. The tracked manifest supplies individual file
checksums; `SHA256SUMS` verifies the downloaded archives.

Full base-model and Goodfire SAE weights, credentials, account/deployment state,
operational logs, and interpreter caches are excluded. Each archive includes the
Llama 3.3 Community License and attribution notice. The adapter collection is
named **Llama SAE anchor pilot adapters**. Obtain the upstream base model and
SAE separately with your own access. Optimizer/RNG state was not saved, so the
checkpoints support evaluation and further training, not exact mid-step resumption.
