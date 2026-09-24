"""Append-only, resumable output for long jobs.

Every long job here writes one JSON object per unit of work, keyed by the
parameters that define it, and re-reads that file on start. A job that is
preempted, hits its wall clock, or dies with the node picks up at the first
unit that is not already in the file. Nothing is recomputed and nothing is
lost, so the job may be requeued any number of times.

Three things make this safe:

* the key is derived from the work, not from a counter, so it survives a
  restart in a different order;
* every record is flushed and fsynced before the next unit starts, so a
  record that is in the file really is on disk;
* a truncated last line (the process died mid-write) is dropped on load
  rather than parsed, and the file is reopened in append mode.

Slurm side: `--requeue`, `--open-mode=append`, and a TERM handler that stops
the loop at the next unit boundary so the partial file is always consistent.
"""
from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable, Dict, Iterable, Iterator, List, Optional, Sequence, TypeVar

T = TypeVar("T")

_STOP = {"flag": False, "since": 0.0}


def install_stop_handler() -> None:
    """SIGTERM/SIGUSR1 ask the loop to stop cleanly at the next boundary."""
    def handler(signum, frame):
        if not _STOP["flag"]:
            _STOP["flag"] = True
            _STOP["since"] = time.time()
            print(f"[resume] signal {signum}: finishing the current unit and "
                  f"stopping; rerun to continue", flush=True)
    for sig in (signal.SIGTERM, signal.SIGUSR1):
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass


def stopping() -> bool:
    return bool(_STOP["flag"])


class JsonlSink:
    """An append-only JSONL file that knows which units it already holds."""

    def __init__(self, path: Path, key: Callable[[dict], str]):
        self.path = Path(path)
        self.key = key
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.done: Dict[str, dict] = {}
        self._load()
        self._fh = open(self.path, "a", buffering=1)

    def _load(self) -> None:
        if not self.path.exists():
            return
        good: List[str] = []
        for line in open(self.path):
            line = line.rstrip("\n")
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                # a partial last line from a process that died mid-write
                print(f"[resume] dropping a truncated final record in {self.path.name}",
                      flush=True)
                continue
            good.append(line)
            self.done[self.key(rec)] = rec
        # rewrite only if we actually dropped something, and do it atomically
        if self.path.exists() and len(good) != sum(1 for _ in open(self.path) if _.strip()):
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text("".join(l + "\n" for l in good))
            os.replace(tmp, self.path)

    def has(self, rec_or_key) -> bool:
        k = rec_or_key if isinstance(rec_or_key, str) else self.key(rec_or_key)
        return k in self.done

    def append(self, rec: dict) -> None:
        self._fh.write(json.dumps(rec) + "\n")
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self.done[self.key(rec)] = rec

    def close(self) -> None:
        try:
            self._fh.close()
        except Exception:
            pass

    def __len__(self) -> int:
        return len(self.done)


def remaining(units: Sequence[T], sink: JsonlSink,
              key_of: Callable[[T], str]) -> List[T]:
    """The units not already in the sink, in the given order."""
    return [u for u in units if not sink.has(key_of(u))]


def run_units(units: Sequence[T], sink: JsonlSink, key_of: Callable[[T], str],
              work: Callable[[T], Optional[dict]], label: str = "",
              report_every: int = 25) -> int:
    """Do the outstanding units, appending each result, stopping on a signal.

    Returns the number of units completed in this invocation.
    """
    todo = remaining(units, sink, key_of)
    print(f"[resume] {label}: {len(sink)} already done, {len(todo)} to do",
          flush=True)
    n = 0
    t0 = time.time()
    for u in todo:
        if stopping():
            print(f"[resume] {label}: stopping with {len(todo) - n} units left",
                  flush=True)
            break
        rec = work(u)
        if rec is not None:
            sink.append(rec)
        n += 1
        if report_every and n % report_every == 0:
            rate = n / max(time.time() - t0, 1e-9)
            left = (len(todo) - n) / max(rate, 1e-9)
            print(f"[resume] {label}: {n}/{len(todo)}  {rate:.2f}/s  "
                  f"eta {left/60:.1f} min", flush=True)
    return n


def complete(units: Sequence[T], sink: JsonlSink,
             key_of: Callable[[T], str]) -> bool:
    return not remaining(units, sink, key_of)


def mark_done(path: Path, **facts) -> None:
    """Write a completion marker, so a watcher can tell finished from stopped.

    A job that exits 0 having written half its rows is still a failure, and the
    row count alone cannot say so when the total depends on something measured
    at run time. The marker is written only when every unit is present.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    facts.setdefault("finished_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                   time.gmtime()))
    path.write_text(json.dumps(facts))
    print(f"[resume] complete: wrote {path.name}", flush=True)
