"""Tests for checkpoint and resume (amendment item 4).

Resumability that has never been interrupted is a claim, not a property, so
these tests interrupt it.
"""

import numpy as np
import pytest

from cv_bench.estimator import checkpoint as CK


def test_partial_resumes_from_where_it_stopped(tmp_path):
    path = tmp_path / "ck.npz"
    key = CK.items_key([f"id{i}" for i in range(100)])

    # First attempt dies after 37 items.
    a = CK.Partial(path, 100, chunk=10, key=key)
    for i in range(37):
        a.append(float(i))
    a.flush()
    assert a.n_done == 37 and not a.complete

    # A fresh process picks it up.
    b = CK.Partial(path, 100, chunk=10, key=key)
    assert b.n_done == 37
    for i in range(37, 100):
        b.append(float(i))
    b.flush()
    assert b.complete
    assert np.allclose(b.column(0), np.arange(100, dtype=float))


def test_unflushed_work_is_lost_but_never_corrupts(tmp_path):
    """A crash between flushes costs at most one chunk, and never a bad file."""
    path = tmp_path / "ck.npz"
    key = CK.items_key(["x"] * 50)
    a = CK.Partial(path, 50, chunk=10, key=key)
    for i in range(25):
        a.append(float(i))          # 20 flushed, 5 in memory
    b = CK.Partial(path, 50, chunk=10, key=key)
    assert b.n_done == 20
    assert np.allclose(b.column(0)[:20], np.arange(20, dtype=float))


def test_checkpoint_from_a_different_item_list_is_refused(tmp_path):
    """Resuming into another run's checkpoint would silently mix two runs."""
    path = tmp_path / "ck.npz"
    a = CK.Partial(path, 10, chunk=2, key=CK.items_key(["a"] * 10))
    for i in range(10):
        a.append(float(i))
    a.flush()
    b = CK.Partial(path, 10, chunk=2, key=CK.items_key(["b"] * 10))
    assert b.n_done == 0, "a checkpoint for other prompts must not be reused"


def test_a_corrupt_checkpoint_starts_over_rather_than_raising(tmp_path):
    path = tmp_path / "ck.npz"
    path.write_bytes(b"not an npz file")
    a = CK.Partial(path, 5, chunk=2, key=CK.items_key(["a"] * 5))
    assert a.n_done == 0


def test_multi_column_checkpoints_round_trip(tmp_path):
    path = tmp_path / "ck.npz"
    key = CK.items_key([f"i{i}" for i in range(20)])
    a = CK.Partial(path, 20, chunk=5, n_cols=2, key=key)
    for i in range(12):
        a.append([float(i), float(i) * 2])
    a.flush()
    b = CK.Partial(path, 20, chunk=5, n_cols=2, key=key)
    assert b.n_done == 12
    z, mass = b.columns()
    assert np.allclose(z[:12], np.arange(12, dtype=float))
    assert np.allclose(mass[:12], np.arange(12, dtype=float) * 2)


def test_shape_change_is_refused(tmp_path):
    path = tmp_path / "ck.npz"
    key = CK.items_key(["a"] * 10)
    a = CK.Partial(path, 10, chunk=2, n_cols=1, key=key)
    for i in range(10):
        a.append(float(i))
    a.flush()
    b = CK.Partial(path, 10, chunk=2, n_cols=3, key=key)
    assert b.n_done == 0


def test_stage_markers(tmp_path):
    assert not CK.stage_done(tmp_path, "fp32")
    CK.mark_stage(tmp_path, "fp32", {"n": 200})
    assert CK.stage_done(tmp_path, "fp32")
    assert not CK.stage_done(tmp_path, "bf16")


def test_heartbeat_is_written_and_survives_a_bad_path(tmp_path):
    hb = tmp_path / "hb.json"
    CK.heartbeat(hb, stage="baseline", done=5, total=100)
    import json
    rec = json.loads(hb.read_text())
    assert rec["stage"] == "baseline" and rec["done"] == 5 and "utc" in rec
    # An unwritable path must not take the job down with it.
    CK.heartbeat(tmp_path / "no" / "such" / "dir" / "hb.json", stage="x")


def test_no_checkpoint_mode_works_without_a_path():
    """The no-checkpoint branch must be usable, not a latent crash."""
    a = CK.Partial(None, 4, chunk=2, n_cols=2)
    for i in range(4):
        a.append([float(i), float(i) * 3])
    a.flush()                       # a no-op, and must not raise
    assert a.complete and a.n_done == 4
    z, w = a.columns()
    assert np.allclose(z, [0, 1, 2, 3]) and np.allclose(w, [0, 3, 6, 9])


def test_checkpoint_key_changes_when_the_prompt_wording_changes(tmp_path):
    """A trial id hashes content and format, not the words shown to the model.

    Renaming a label from "Safe Option" to "Safe" leaves every id identical
    while every prompt differs, so a key built from ids alone would resume into
    stale reads of prompts that no longer exist.
    """
    ids = [f"id{i}" for i in range(20)]
    old = ["Safe Option: $20 for sure"] * 20
    new = ["Safe: 20 tokens for sure"] * 20
    assert CK.items_key(ids, old) != CK.items_key(ids, new)
    assert CK.items_key(ids, old) == CK.items_key(ids, old)

    path = tmp_path / "ck.npz"
    a = CK.Partial(path, 20, chunk=5, key=CK.items_key(ids, old))
    for i in range(20):
        a.append(float(i))
    a.flush()
    b = CK.Partial(path, 20, chunk=5, key=CK.items_key(ids, new))
    assert b.n_done == 0, "a checkpoint for different prompt text must not be reused"
