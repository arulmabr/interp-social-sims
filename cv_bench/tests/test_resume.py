"""Tests for cv_bench/resume.py.

These cover the promise the jobs are built on: a run that is killed at any point
loses at most the unit in flight, and rerunning the same command continues from
the next one. The truncated-record case is the one that matters most, because a
process killed mid-write leaves half a JSON line behind and a naive loader either
crashes on it or silently treats it as done.
"""
from __future__ import annotations

import json
import os

import pytest

os.environ.setdefault("ICLR_RUNROOT", "/tmp/cvb_test_runroot")

from cv_bench.resume import (JsonlSink, complete, install_stop_handler,  # noqa: E402
                             remaining, run_units, stopping)

KEY = lambda r: f"{r['a']}|{r['b']}"
UNITS = [(a, b) for a in range(3) for b in range(3)]
KO = lambda u: f"{u[0]}|{u[1]}"
WORK = lambda u: dict(a=u[0], b=u[1])


def test_finishes_and_is_idempotent(tmp_path):
    s = JsonlSink(tmp_path / "o.jsonl", KEY)
    assert run_units(UNITS, s, KO, WORK, "t") == 9
    s.close()
    s2 = JsonlSink(tmp_path / "o.jsonl", KEY)
    assert len(s2) == 9 and complete(UNITS, s2, KO)
    assert run_units(UNITS, s2, KO, WORK, "t") == 0     # nothing recomputed
    s2.close()
    assert sum(1 for _ in open(tmp_path / "o.jsonl")) == 9


def test_resumes_after_a_partial_run(tmp_path):
    s = JsonlSink(tmp_path / "o.jsonl", KEY)
    run_units(UNITS[:4], s, KO, WORK, "t")
    s.close()
    s2 = JsonlSink(tmp_path / "o.jsonl", KEY)
    assert len(remaining(UNITS, s2, KO)) == 5
    assert run_units(UNITS, s2, KO, WORK, "t") == 5
    assert complete(UNITS, s2, KO)
    s2.close()


def test_a_truncated_final_record_is_dropped_not_parsed(tmp_path):
    p = tmp_path / "o.jsonl"
    s = JsonlSink(p, KEY)
    run_units(UNITS[:4], s, KO, WORK, "t")
    s.close()
    with open(p, "a") as fh:                 # a process killed mid-write
        fh.write('{"a": 9, "b":')
    s2 = JsonlSink(p, KEY)
    assert len(s2) == 4                      # the half-line is not a unit
    assert all(json.loads(l) for l in open(p) if l.strip())   # file is valid again
    assert run_units(UNITS, s2, KO, WORK, "t") == 5
    s2.close()


def test_key_is_derived_from_the_work_so_order_does_not_matter(tmp_path):
    s = JsonlSink(tmp_path / "o.jsonl", KEY)
    run_units(UNITS[:4], s, KO, WORK, "t")
    s.close()
    s2 = JsonlSink(tmp_path / "o.jsonl", KEY)
    shuffled = list(reversed(UNITS))
    assert run_units(shuffled, s2, KO, WORK, "t") == 5
    assert complete(UNITS, s2, KO)
    s2.close()


def test_every_record_is_on_disk_before_the_next_unit_starts(tmp_path):
    """The sink must not buffer: a kill between units keeps what came before."""
    p = tmp_path / "o.jsonl"
    s = JsonlSink(p, KEY)
    seen = []

    def work(u):
        seen.append(sum(1 for _ in open(p)))   # lines on disk before this unit
        return WORK(u)

    run_units(UNITS[:5], s, KO, work, "t")
    assert seen == [0, 1, 2, 3, 4]
    s.close()


def test_a_unit_may_decline_to_produce_a_record(tmp_path):
    s = JsonlSink(tmp_path / "o.jsonl", KEY)
    n = run_units(UNITS, s, KO, lambda u: None if u[0] == 0 else WORK(u), "t")
    assert n == 9 and len(s) == 6
    s.close()


def test_stop_handler_installs_without_a_signal(tmp_path):
    install_stop_handler()
    assert stopping() is False
