"""Which Slurm jobs belong to THIS session. Never guess by prefix.

Both sessions carry the job-name prefix `cvb_` because FRIDAY_PLAN's coordination
amendment requires it -- so that the 400 and 1,000 GPU-hour caps are evaluated on
one `sacct` total across the project. The prefix is a **budget** key. It is not
an ownership key, and using it as one is how this session cancelled seven of
Track B's jobs on 22 Sept, two of them mid-run (logs/DEVIATIONS.md).

This module is the only sanctioned answer to "which jobs may I cancel":

    python -m cv_bench.mine            # my job ids, one per line
    python -m cv_bench.mine --names    # my task names
    python -m cv_bench.mine --check ID # exit 0 only if ID is mine

`scancel $(python -m cv_bench.mine)` is safe. `squeue | grep cvb_ | xargs scancel`
is not, and nothing in this repository should do it again.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from typing import List, Set

# Track B's tasks all match cvb_b<digit>_*; this session's never do. The
# allowlist below is the authority, and the pattern is a second, independent
# check -- a name has to pass both.
import re

TRACKB_PATTERN = re.compile(r"^cvb_b\d")


# Tasks this session submits that the monitor does not watch. Listed explicitly
# rather than inferred, because an ownership filter that guesses is the thing
# that caused the incident this module exists to prevent.
EXTRA_TASKS = {
    "cvb_monitor", "cvb_analyse", "cvb_choose", "cvb_g4bench",
    "cvb_g3", "cvb_g4b", "cvb_g4q", "cvb_g5", "cvb_g5b", "cvb_g6",
    "cvb_s32", "cvb_s35", "cvb_neutral2",
}


def my_task_names() -> Set[str]:
    from cv_bench.monitor import EXPECTED
    names = set(EXPECTED) | EXTRA_TASKS
    # Belt and braces: drop anything matching Track B's shape even if it somehow
    # reached the allowlist.
    return {n for n in names if not TRACKB_PATTERN.match(n)}


def my_job_ids(states: str = "") -> List[str]:
    mine = my_task_names()
    cmd = ["squeue", "-u", os.environ.get("USER", ""), "-h", "-o", "%i|%j"]
    if states:
        cmd += ["-t", states]
    out = subprocess.run(cmd, capture_output=True, text=True).stdout
    ids = []
    for line in out.splitlines():
        parts = line.split("|")
        if len(parts) != 2:
            continue
        jid, name = parts[0].strip(), parts[1].strip()
        if TRACKB_PATTERN.match(name):
            continue                      # belongs to the other session
        if name in mine:
            ids.append(jid)
    return ids


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--names", action="store_true")
    ap.add_argument("--states", default="")
    ap.add_argument("--check", default="")
    a = ap.parse_args()
    if a.names:
        print("\n".join(sorted(my_task_names())))
        return 0
    if a.check:
        ok = a.check.strip() in my_job_ids()
        print(("mine: " if ok else "NOT MINE: ") + a.check)
        return 0 if ok else 1
    print("\n".join(my_job_ids(a.states)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
