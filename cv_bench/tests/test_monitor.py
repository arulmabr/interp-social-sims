"""Tests for cv_bench/monitor.py's log scanner.

The NaN case has its own test because it regressed once: the scanner used to
report a standalone `nan` only when the log *also* contained the word "loss",
which silently dropped it in every log that is not a training log — a readout
sweep, a calibration pass, an attribution run. Reported by the Track B session
on 22 Sept.
"""
from __future__ import annotations

import os

import pytest

os.environ.setdefault("ICLR_RUNROOT", "/tmp/cvb_test_runroot")

from cv_bench.monitor import scan_log  # noqa: E402


def write(tmp_path, text: str):
    p = tmp_path / "job_1.out"
    p.write_text(text)
    return p


def test_standalone_nan_is_reported_without_the_word_loss(tmp_path):
    """The regression: no 'loss' anywhere, and the nan must still be caught."""
    p = write(tmp_path, "readout sweep\nlevel 12/45 z=nan\nlevel 13/45 z=-1.2\n")
    assert "loss" not in p.read_text().lower()
    assert "nan" in scan_log(p)


@pytest.mark.parametrize("line", [
    "z=nan", "value NaN here", "slope=0.000 r=nan", "tensor([nan, 1.0])",
    "logit_diff -nan", "NAN",
])
def test_nan_shapes_that_must_be_caught(tmp_path, line):
    assert "nan" in scan_log(write(tmp_path, f"progress\n{line}\n"))


@pytest.mark.parametrize("line", [
    "finance report", "the tenant moved", "banana bread", "nanometre scale",
    "/path/to/nanobench/out", "covariance matrix", "Kernighan",
])
def test_words_containing_nan_are_not_flagged(tmp_path, line):
    assert "nan" not in scan_log(write(tmp_path, f"progress\n{line}\n"))


def test_other_patterns_still_fire(tmp_path):
    p = write(tmp_path, "Traceback (most recent call last):\n  File x\n")
    assert "traceback" in scan_log(p)
    p = write(tmp_path, "torch.cuda.OutOfMemoryError: CUDA out of memory.\n")
    assert "cuda_oom" in scan_log(p)
    p = write(tmp_path, "srun: JOB 123 CANCELLED AT 2026-09-22 DUE TO PREEMPTION\n")
    assert "preempted" in scan_log(p)


def test_clean_log_is_clean(tmp_path):
    p = write(tmp_path, "node=node3805 job=1\nloaded in 3.1 min\nG2 DONE\n")
    assert scan_log(p) == []


def test_missing_file_is_not_a_failure(tmp_path):
    assert scan_log(tmp_path / "nope.out") == []
    assert scan_log(None) == []
