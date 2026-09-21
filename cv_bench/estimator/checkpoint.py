"""Checkpoint and resume for long Track B jobs.

Amendment item 4 requires every job to checkpoint, be requeue-safe and write a
heartbeat. Slurm jobs already survive a dropped connection -- they run on a
compute node with no tie to the submitting shell -- but they do *not* survive
preemption or a timeout unless they can pick up where they stopped. `ou_bcs_low`
is the low-priority partition, so preemption is expected rather than unusual.

Two primitives:

* `Partial` -- an append-only array on disk. A loop asks how many items are
  already done, starts there, and flushes every `chunk` items. A crash costs at
  most `chunk` items of work.
* `stage_done` / `mark_stage` -- a coarse marker for whole phases, so a job that
  has finished reading fp32 does not read it again to get at bf16.

Writes are atomic: a temporary file is written and then renamed, so a job killed
mid-flush leaves the previous good checkpoint rather than a truncated one.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


def _atomic_savez(path: Path, **arrays) -> None:
    tmp = path.with_name(path.name + ".tmp.npz")
    np.savez(tmp, **arrays)
    os.replace(tmp, path)


class Partial:
    """A resumable 1-D float array, keyed by position in a fixed item list."""

    def __init__(self, path: Optional[Path], total: int, chunk: int = 50,
                 n_cols: int = 1, key: Optional[str] = None):
        # `path=None` means "no checkpoint": the array lives in memory and every
        # flush is a no-op. Callers that do not want to checkpoint must get a
        # working object rather than an exception, or the no-checkpoint branch
        # becomes a crash that only appears when someone takes it.
        self.path = Path(path) if path is not None else None
        self.total = int(total)
        self.chunk = int(chunk)
        self.n_cols = int(n_cols)
        self.key = key
        self.data = np.full((self.total, self.n_cols), np.nan, dtype=float)
        self.n_done = 0
        self._since_flush = 0
        self._load()

    def _load(self) -> None:
        if self.path is None or not self.path.exists():
            return
        try:
            z = np.load(self.path, allow_pickle=False)
        except Exception:
            return                      # corrupt checkpoint: start over
        arr = z["data"]
        stored_key = str(z["key"]) if "key" in z else None
        if arr.shape != self.data.shape or (self.key and stored_key != self.key):
            # A different item list or a different shape: the checkpoint is not
            # about this run and must not be silently reused.
            return
        self.data = arr
        self.n_done = int(z["n_done"])

    def flush(self) -> None:
        if self.path is None:
            self._since_flush = 0
            return
        payload = {"data": self.data, "n_done": np.array(self.n_done)}
        if self.key:
            payload["key"] = np.array(self.key)
        _atomic_savez(self.path, **payload)
        self._since_flush = 0

    def append(self, values) -> None:
        """Record the next item's value(s) and flush on the chunk boundary."""
        self.data[self.n_done, :] = np.atleast_1d(np.asarray(values, dtype=float))
        self.n_done += 1
        self._since_flush += 1
        if self._since_flush >= self.chunk:
            self.flush()

    @property
    def complete(self) -> bool:
        return self.n_done >= self.total

    def columns(self) -> List[np.ndarray]:
        return [self.data[:, i] for i in range(self.n_cols)]

    def column(self, i: int = 0) -> np.ndarray:
        return self.data[:, i]


def items_key(ids: Sequence[str], texts: Optional[Sequence[str]] = None) -> str:
    """A fingerprint of the item list a checkpoint belongs to.

    The ids alone are not enough. A trial id hashes the trial's *content and
    format*, not the words the model is shown, so changing a label from
    "Safe Option" to "Safe" or a currency from dollars to tokens leaves every id
    identical while every prompt differs. A checkpoint keyed on ids alone would
    then be silently reused and half the run would be stale reads of prompts
    that no longer exist. `texts` folds the rendered prompts into the key so a
    change of wording invalidates the checkpoint, which is what it must do.
    """
    import hashlib
    h = hashlib.sha256("\n".join(ids).encode()).hexdigest()[:12]
    if texts is None:
        return f"{len(ids)}:{h}"
    t = hashlib.sha256("\n".join(texts).encode()).hexdigest()[:12]
    return f"{len(ids)}:{h}:{t}"


def stage_done(out: Path, name: str) -> bool:
    return (Path(out) / f".done_{name}").exists()


def mark_stage(out: Path, name: str, info: Optional[Dict] = None) -> None:
    p = Path(out) / f".done_{name}"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
         **(info or {})}, sort_keys=True) + "\n")


def heartbeat(path: Path, **fields) -> None:
    """One line of liveness, overwritten. The monitor reads this."""
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(
            {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
             "pid": os.getpid(), **fields}, sort_keys=True, default=str) + "\n")
    except OSError:
        pass
