"""Watch a named set of Slurm jobs and stop the moment one of them goes wrong.

Built per-job on purpose. Two earlier versions of this watcher were wrong in the
same way -- they asked a global question ("is anything running?", "has anything
failed today?") where a per-job one was needed, so they replayed old history and
called deliberate cancellations failures. This one tracks an explicit job-id
list, records each job's state when it first sees it, and reports only
transitions.

It exits when every watched job reaches a terminal state, or immediately on the
first real failure, so the caller is woken by the exit rather than by polling.

    python -m cv_bench.watch_b33 23499720 23500280 23500281 --interval 60
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

TERMINAL_OK = {"COMPLETED"}
TERMINAL_BAD = {"FAILED", "TIMEOUT", "OUT_OF_MEMORY", "NODE_FAIL",
                "BOOT_FAIL", "DEADLINE", "REVOKED"}
# PREEMPTED and CANCELLED are ambiguous: with --requeue a preemption is a
# transient, and a cancellation is usually me. Both are reported, neither
# aborts the watch on its own.
LOG_SIGNATURES = (
    (re.compile(r"CUDA out of memory", re.I), "CUDA OOM"),
    (re.compile(r"\bTraceback \(most recent call last\)"), "python traceback"),
    (re.compile(r"DUE TO PREEMPTION"), "preempted"),
    (re.compile(r"DUE TO TIME LIMIT"), "hit the time limit"),
    (re.compile(r"srun: error|slurmstepd: error"), "slurm step error"),
    (re.compile(r"AssertionError|RuntimeError|KeyError|ValueError"), "python exception"),
)


def squeue_state(job: str) -> Optional[str]:
    r = subprocess.run(["squeue", "-j", job, "-h", "-o", "%T"],
                       capture_output=True, text=True)
    s = r.stdout.strip()
    return s.splitlines()[0] if s else None


def sacct_state(job: str) -> str:
    r = subprocess.run(["sacct", "-j", job, "-X", "-n", "-P", "--format=State"],
                       capture_output=True, text=True)
    s = r.stdout.strip()
    return s.splitlines()[0].split()[0] if s else "UNKNOWN"


def scan_logs(logdir: Path, job: str) -> List[str]:
    hits = []
    for f in sorted(logdir.glob(f"*_{job}.err")) + sorted(logdir.glob(f"*_{job}.out")):
        try:
            tail = f.read_text(errors="replace")[-20000:]
        except OSError:
            continue
        for rx, label in LOG_SIGNATURES:
            if rx.search(tail):
                hits.append(f"{f.name}: {label}")
    return sorted(set(hits))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jobs", nargs="+")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--logdir", type=Path, default=Path("logs"))
    ap.add_argument("--max-hours", type=float, default=12.0)
    a = ap.parse_args(argv)

    seen: Dict[str, str] = {}
    reported_logs: Dict[str, set] = {j: set() for j in a.jobs}
    t0 = time.time()
    print(f"watching {', '.join(a.jobs)} every {a.interval}s", flush=True)

    while True:
        now = datetime.now(timezone.utc).strftime("%H:%M:%S")
        done, bad = 0, []
        for j in a.jobs:
            live = squeue_state(j)
            state = live or sacct_state(j)
            if seen.get(j) != state:
                print(f"[{now}] {j}: {seen.get(j, '-')} -> {state}", flush=True)
                seen[j] = state
            if live is None and state not in ("PENDING", "RUNNING", "UNKNOWN"):
                done += 1
                if state in TERMINAL_BAD:
                    bad.append(f"{j} ended {state}")
            # per-job log signatures, reported once each
            for h in scan_logs(a.logdir, j):
                if h not in reported_logs[j]:
                    reported_logs[j].add(h)
                    print(f"[{now}] {j}: LOG {h}", flush=True)
                    if "OOM" in h or "traceback" in h or "exception" in h:
                        bad.append(f"{j}: {h}")

        if bad:
            print(f"\nFAILURE: {'; '.join(sorted(set(bad)))}", flush=True)
            return 1
        if done == len(a.jobs):
            print(f"\nall {len(a.jobs)} jobs finished: "
                  f"{ {j: seen[j] for j in a.jobs} }", flush=True)
            return 0
        if (time.time() - t0) / 3600 > a.max_hours:
            print(f"\nwatch expired after {a.max_hours}h; states: "
                  f"{ {j: seen[j] for j in a.jobs} }", flush=True)
            return 2
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
