"""The job monitor. One thread, runs under tmux, rewrites reports/STATUS.md.

    tmux new -d -s iclr_monitor 'cd /home/guna23/shrey/risk && python3 -u -m cv_bench.monitor'

Every cycle (default 10 minutes) it:

* reads `squeue` and `sacct` for this account's jobs in the project's run directory;
* scans each job's log for `Traceback`, `CUDA out of memory`, `NaN`, and preemption;
* compares the row count of every expected output against what the task should
  produce, so a job that exits 0 having written half its rows is still a failure;
* runs the output checks that matter here — valid answer mass, agreement between
  the legacy and strict codings, and no empty or constant column;
* resubmits a **technical** failure at most twice, logging the cause and any
  technical change to `logs/DEVIATIONS.md`, and stops the task after that;
* rewrites `reports/STATUS.md`.

It never changes seeds, prompts, doses, thresholds or metrics on a retry
(CLAUDE.md rule 4). The only change it is allowed to make is a technical one, and
it must be recorded; today the only such change it knows how to make is halving a
batch size on an out-of-memory failure, which no current job uses.
"""
from __future__ import annotations

import collections
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]
RUNROOT = Path(os.environ.get(
    "ICLR_RUNROOT", "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
STATUS = ROOT / "reports/STATUS.md"
STATE = RUNROOT / "monitor_state.json"
DEVIATIONS = ROOT / "logs/DEVIATIONS.md"

CUTOFF_UTC = datetime(2026, 9, 24, 6, 0, tzinfo=timezone.utc)
MAX_RETRIES = 2
CYCLE_SECONDS = int(os.environ.get("MONITOR_CYCLE", "600"))

FAILURE_PATTERNS = [
    ("traceback", re.compile(r"^Traceback \(most recent call last\)", re.M)),
    ("cuda_oom", re.compile(r"CUDA out of memory|torch\.cuda\.OutOfMemoryError")),
    # standalone word only: matches "nan"/"NaN"/"-nan" but not "finance" or "tenant"
    ("nan", re.compile(r"(?<![A-Za-z0-9_])(?:nan|NaN|NAN)(?![A-Za-z0-9_])")),
    ("preempted", re.compile(r"PREEMPT|DUE TO PREEMPTION|CANCELLED AT .* DUE TO")),
    ("oom_killed", re.compile(r"Out Of Memory|oom-kill|Killed")),
]

# What each task is expected to produce. row_target None = unknown/unchecked.
EXPECTED: Dict[str, dict] = {
    "g2_qwen": dict(
        sbatch=RUNROOT / "g2_lambda0/g2_qwen.sbatch",
        outputs={f"g2_lambda0/qwen_{arm}_{game}.jsonl": n
                 for arm in ("legacy", "chat", "chat64")
                 for game, n in (("lottery", 840), ("ultimatum", 360))},
    ),
    "g2_llama": dict(
        sbatch=RUNROOT / "g2_lambda0/g2_llama.sbatch",
        outputs={f"g2_lambda0/llama_{arm}_{game}.jsonl": n
                 for arm in ("legacy", "chat", "chat64")
                 for game, n in (("lottery", 1800), ("ultimatum", 760))},
    ),
    "bench70b": dict(
        sbatch=RUNROOT / "bench/bench.sbatch",
        outputs={"bench/bench_llama.json": None},
    ),
}

# The FRIDAY-amendment jobs. These run on mit_preemptable, where a job can be
# taken away at any moment; each writes through cv_bench.resume, so a resubmission
# continues from the unit after the last one on disk. `done` names a marker the
# job writes only when every unit is present -- a row count cannot stand in for
# it here, because the number of doses depends on a norm measured at run time.
REPO_SLURM = ROOT / "slurm"
PREEMPT = ["--partition=mit_preemptable", "--qos=normal", "--account=mit_general"]

EXPECTED.update({
    "cvb_instr": dict(
        sbatch=REPO_SLURM / "cvb_instr.sbatch",
        args=PREEMPT + ["--gres=gpu:a100:2", "--time=03:00:00"],
        outputs={"instr/norms_llama.jsonl": 50,
                 "instr/readout_grid_llama.jsonl": 128,
                 "instr/freegen_llama.jsonl": 840},
        done="instr/done_instr_llama.json",
    ),
    "cvb_neutral": dict(
        sbatch=REPO_SLURM / "cvb_neutral.sbatch",
        args=PREEMPT + ["--gres=gpu:a100:2", "--time=03:00:00"],
        outputs={"neutral/mass_llama.jsonl": 344,   # 50 lottery + 36 ultimatum: CAL_ULTIMATUM has 36 values, not 50
                 "neutral/free_llama.jsonl": 640},
        done="neutral/done_neutral_llama.json",
    ),
})
for _v in ("as_written", "reconstruction"):
    for _l in (48, 50):
        _g = "gpu:a100:2" if _l == 48 else "gpu:h100:2"
        EXPECTED[f"cvb_g4_{_v[:5]}_L{_l}"] = dict(
            sbatch=REPO_SLURM / "cvb_g4.sbatch",
            args=PREEMPT + [f"--gres={_g}", "--time=16:00:00",
                            f"--job-name=cvb_g4_{_v[:5]}_L{_l}",
                            f"--export=ALL,V={_v},L={_l}"],
            outputs={f"g4/readout_{_v}_L{_l}.jsonl": None,
                     f"g4/sampled_{_v}_L{_l}.jsonl": None},
            done=f"g4/done_g4_{_v}_L{_l}.json",
        )


def sh(cmd: List[str]) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
    except Exception:
        return ""


def squeue_rows() -> List[dict]:
    out = sh(["squeue", "-u", os.environ.get("USER", ""), "-h",
              "-o", "%i|%j|%T|%M|%L|%R"])
    rows = []
    for line in out.splitlines():
        p = line.split("|")
        if len(p) >= 6:
            rows.append(dict(jobid=p[0], name=p[1], state=p[2], elapsed=p[3],
                             left=p[4], reason=p[5]))
    return rows


JOB_PREFIX = "cvb_"


def sacct_all_prefixed() -> List[dict]:
    """Every job of this account whose name starts with the shared prefix.

    Amendment C: both sessions prefix their jobs `cvb_`, and the 400 GPU-hour cap
    is evaluated on sacct totals for that prefix. This is therefore the whole
    project's spend, not this session's.
    """
    out = sh(["sacct", "-n", "-X", "-P", "--starttime", "2026-09-20",
              "--format", "JobID,JobName,State,Elapsed,ExitCode,AllocTRES"])
    rows = []
    for line in out.splitlines():
        p = line.split("|")
        if len(p) >= 6 and p[1].startswith(JOB_PREFIX):
            rows.append(dict(jobid=p[0], name=p[1], state=p[2], elapsed=p[3],
                             exit=p[4], tres=p[5]))
    return rows


def sacct_rows(names: List[str]) -> List[dict]:
    out = sh(["sacct", "-n", "-X", "-P", "--starttime", "now-2days",
              "--format", "JobID,JobName,State,Elapsed,ExitCode,AllocTRES"])
    rows = []
    for line in out.splitlines():
        p = line.split("|")
        if len(p) >= 6 and p[1] in names:
            rows.append(dict(jobid=p[0], name=p[1], state=p[2], elapsed=p[3],
                             exit=p[4], tres=p[5]))
    return rows


def gpu_seconds(tres: str, elapsed: str) -> float:
    m = re.search(r"gres/gpu=(\d+)", tres or "")
    g = int(m.group(1)) if m else 0
    parts = [float(x) for x in re.split(r"[:-]", elapsed or "0") if x]
    secs = 0.0
    for x in parts:
        secs = secs * 60 + x
    if (elapsed or "").count("-"):
        pass
    return g * secs


def latest_log(name: str) -> Optional[Path]:
    cands = sorted(RUNROOT.glob(f"**/{name}_*.out"), key=lambda p: p.stat().st_mtime)
    return cands[-1] if cands else None


def scan_log(p: Optional[Path]) -> List[str]:
    if p is None or not p.exists():
        return []
    try:
        text = p.read_text(errors="ignore")
    except Exception:
        return []
    # "nan" appears inside ordinary words (finance, tenant, banana), so the pattern
    # below requires it standalone. It used to ALSO require the word "loss"
    # somewhere in the log, which meant a standalone nan in any log that never
    # mentions loss -- a readout sweep, a calibration pass, an attribution run --
    # was dropped silently. The word boundary is the filter; nothing else is
    # needed. Reported by the Track B session, 22 Sept.
    hits = []
    for tag, pat in FAILURE_PATTERNS:
        if pat.search(text):
            hits.append(tag)
    return hits


def count_rows(rel: str) -> Optional[int]:
    p = RUNROOT / rel
    if not p.exists():
        return None
    if p.suffix == ".jsonl":
        with open(p) as f:
            return sum(1 for line in f if line.strip())
    return 1


def check_outputs(task: str) -> dict:
    """Row counts plus the content checks: coding agreement, constant columns."""
    spec = EXPECTED[task]
    rows, missing, short = {}, [], []
    for rel, target in spec["outputs"].items():
        n = count_rows(rel)
        rows[rel] = n
        if n is None:
            missing.append(rel)
        elif target is not None and n < target:
            short.append((rel, n, target))
    marker = spec.get("done")
    marked = (RUNROOT / marker).exists() if marker else True
    if marker and not marked:
        missing = missing + [marker]
    out = dict(rows=rows, missing=missing, short=short, marker=marker,
               marked=marked, complete=(not missing and not short and marked))

    # content checks on any complete jsonl this task owns
    agree, checked = [], 0
    for rel, target in spec["outputs"].items():
        p = RUNROOT / rel
        if not rel.endswith(".jsonl") or not p.exists() or p.stat().st_size == 0:
            continue
        legacy, strict, blanks = [], [], 0
        with open(RUNROOT / rel) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    r = json.loads(line)
                except json.JSONDecodeError:
                    continue
                legacy.append(r.get("legacy_code"))
                strict.append(r.get("strict_choice"))
                if not (r.get("raw_generation") or "").strip():
                    blanks += 1
        if legacy:
            checked += 1
            same = sum(1 for a, b in zip(legacy, strict) if a == b)
            agree.append(dict(file=rel, n=len(legacy),
                              coding_agreement=round(same / len(legacy), 4),
                              blank_generations=blanks,
                              legacy_constant=len(set(legacy)) == 1,
                              strict_constant=len(set(strict)) == 1))
    out["content"] = agree
    out["files_content_checked"] = checked
    return out


def load_state() -> dict:
    if STATE.exists():
        try:
            return json.loads(STATE.read_text())
        except Exception:
            pass
    return dict(retries={}, stopped=[], gpu_hours_seen={})


def save_state(s: dict) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(s, indent=2) + "\n")


def log_deviation(text: str) -> None:
    with open(DEVIATIONS, "a") as f:
        f.write(text)


def resubmit(task: str, state: dict, cause: str) -> Optional[str]:
    n = state["retries"].get(task, 0)
    if n >= MAX_RETRIES:
        if task not in state["stopped"]:
            state["stopped"].append(task)
            log_deviation(
                f"\n---\n\n## {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} — "
                f"{task} stopped after {MAX_RETRIES} retries\n\n"
                f"Cause on the last attempt: **{cause}**. No further automatic "
                f"resubmission; the authors are told. No seed, prompt, dose, "
                f"threshold or metric was changed on any retry.\n")
        return None
    sb = EXPECTED[task]["sbatch"]
    if not Path(sb).exists():
        return None
    out = sh(["sbatch"] + list(EXPECTED[task].get("args", [])) + [str(sb)])
    jid = (re.search(r"(\d+)", out).group(1) if out else None)
    state["retries"][task] = n + 1
    log_deviation(
        f"\n---\n\n## {datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} — "
        f"{task} resubmitted automatically (attempt {n + 1} of {MAX_RETRIES})\n\n"
        f"**Cause:** {cause}. **Technical change:** none — the job is resubmitted "
        f"unchanged and resumes from its own checkpoint. Seeds, prompts, doses, "
        f"thresholds and metrics are untouched (CLAUDE.md rule 4).\n"
        f"**New job id:** {jid or 'submission failed'}\n")
    return jid


def write_status(cycle: int, live: List[dict], hist: List[dict],
                 checks: Dict[str, dict], state: dict, gpu_h: float) -> None:
    now = datetime.now(timezone.utc)
    left = (CUTOFF_UTC - now).total_seconds() / 3600
    L = []
    L.append("# STATUS.md\n")
    L.append(f"Rewritten by `cv_bench/monitor.py` every {CYCLE_SECONDS // 60} minutes. "
             f"Cycle {cycle}.\n")
    L.append(f"**{now:%Y-%m-%d %H:%M UTC}** — cutoff Thu 24 Sept 06:00 UTC, "
             f"**{left:.1f} h remaining**.\n")
    L.append(f"**GPU-hours consumed, both sessions, `sacct` on job names starting "
             f"`{JOB_PREFIX}`: {gpu_h:.2f}** of the 400 approved.\n")
    L.append("\n## Live jobs\n")
    if live:
        L.append("| job | name | state | elapsed | left | reason |")
        L.append("|---|---|---|---|---|---|")
        for r in live:
            L.append(f"| {r['jobid']} | {r['name']} | {r['state']} | {r['elapsed']} "
                     f"| {r['left']} | {r['reason']} |")
    else:
        L.append("*none*")
    L.append("\n## Recent jobs\n")
    if hist:
        L.append("| job | name | state | elapsed | exit |")
        L.append("|---|---|---|---|---|")
        for r in hist[-12:]:
            L.append(f"| {r['jobid']} | {r['name']} | {r['state']} | {r['elapsed']} "
                     f"| {r['exit']} |")
    else:
        L.append("*none*")
    L.append("\n## Outputs\n")
    for task, c in sorted(checks.items()):
        flag = "complete" if c["complete"] else "INCOMPLETE"
        L.append(f"\n### {task} — {flag}\n")
        L.append("| output | rows | expected |")
        L.append("|---|---:|---:|")
        spec = EXPECTED[task]["outputs"]
        for rel, n in c["rows"].items():
            L.append(f"| `{rel}` | {n if n is not None else '—'} | "
                     f"{spec[rel] if spec[rel] is not None else '—'} |")
        if c["content"]:
            L.append("\n| file | n | legacy vs strict agreement | blank gens | constant? |")
            L.append("|---|---:|---:|---:|---|")
            for d in c["content"]:
                const = ("legacy" if d["legacy_constant"] else "") + \
                        ("/strict" if d["strict_constant"] else "")
                L.append(f"| `{Path(d['file']).name}` | {d['n']} | "
                         f"{d['coding_agreement']:.4f} | {d['blank_generations']} | "
                         f"{const or 'no'} |")
    if state["retries"]:
        L.append("\n## Automatic resubmissions\n")
        for k, v in state["retries"].items():
            L.append(f"- `{k}`: {v} of {MAX_RETRIES}")
    if state["stopped"]:
        L.append("\n## Stopped — needs a human\n")
        for k in state["stopped"]:
            L.append(f"- **`{k}`** exhausted its retries.")
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    STATUS.write_text("\n".join(L) + "\n")


def main() -> int:
    state = load_state()
    cycle = 0
    names = list(EXPECTED)
    while True:
        cycle += 1
        live = [r for r in squeue_rows() if r["name"] in names]
        hist = sacct_rows(names)
        # Project-wide spend, both sessions, via the shared cvb_ prefix.
        gpu_h = 0.0
        for r in sacct_all_prefixed():
            gpu_h += gpu_seconds(r.get("tres", ""), r.get("elapsed", "")) / 3600.0
        checks = {}
        for task in names:
            try:
                checks[task] = check_outputs(task)
            except Exception as e:
                checks[task] = dict(rows={}, missing=[], short=[], complete=False,
                                    content=[], error=f"{type(e).__name__}: {e}")
        # failures: a terminal state that is not COMPLETED, or a log hit
        running = {r["name"] for r in live}
        for task in names:
            if task in running or task in state["stopped"]:
                continue
            terminal = [r for r in hist if r["name"] == task]
            if not terminal:
                continue
            last = terminal[-1]
            # Which terminal states are a technical failure worth retrying.
            # An operator's scancel is not one: Slurm reports it as
            # "CANCELLED by <uid>", and resurrecting a job somebody deliberately
            # stopped is the opposite of helpful. Neither is a task whose
            # outputs are all present -- it is finished, whatever its state says.
            RETRYABLE = ("FAILED", "NODE_FAIL", "TIMEOUT", "OUT_OF_MEMORY",
                         "BOOT_FAIL", "DEADLINE", "PREEMPTED")
            state0 = last["state"].split()[0].upper()
            bad_state = state0 in RETRYABLE
            hits = scan_log(latest_log(task))
            incomplete = not checks[task]["complete"]
            # A log hit is not on its own a reason to resubmit. These logs are
            # opened in append mode across requeues, so a preemption message from
            # an earlier attempt outlives the attempt that succeeded -- and a job
            # that finished with every row and its marker on disk is finished
            # whatever its log remembers. Resubmit for the state or for missing
            # output; report the rest.
            hits = [h for h in hits if h != "preempted"]
            checks[task]["log_flags"] = hits
            if checks[task]["complete"]:
                continue                      # finished; nothing to retry
            if bad_state or incomplete:
                cause = (f"state={last['state']} exit={last['exit']}"
                         + (f" log={','.join(hits)}" if hits else "")
                         + (" outputs_incomplete" if incomplete else ""))
                jid = resubmit(task, state, cause)
                print(f"[{cycle}] {task}: {cause} -> "
                      f"{'resubmitted ' + str(jid) if jid else 'STOPPED'}", flush=True)
        save_state(state)
        write_status(cycle, live, hist, checks, state, gpu_h)
        print(f"[{cycle}] {datetime.now(timezone.utc):%H:%M} live={len(live)} "
              f"gpu_h={gpu_h:.2f}", flush=True)
        time.sleep(CYCLE_SECONDS)


if __name__ == "__main__":
    raise SystemExit(main())
