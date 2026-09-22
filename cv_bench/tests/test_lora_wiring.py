"""Drive lora.main() end to end with the model stubbed out.

Job 23508417 loaded the 70B for 640 seconds and then died on
`UnboundLocalError: retrain`, a one-line ordering mistake. `pytest -q` and
`pyflakes` both passed on that code, because neither executes `main`. This does,
in about a second, so a wiring mistake costs that instead of a GPU hour.

Two things it pins: every argument path runs, and `--init-from-reference` is
recorded in the result so a paired run can never be mistaken for an
independently initialised one afterwards.
"""
from __future__ import annotations

import json
from pathlib import Path
from unittest import mock

import numpy as np
import pytest

from cv_bench.anchors import lora


def _fake_read(peft_model, ro, name, trials, out):
    rng = np.random.default_rng(abs(hash(name)) % 2 ** 32)
    return rng.normal(size=len(trials))


def _run(tmp_path: Path, argv):
    stubs = (
        mock.patch.object(lora, "load_base",
                          lambda *a, **k: (mock.MagicMock(), mock.MagicMock())),
        mock.patch.object(lora, "attach_adapters", lambda m, rank=16: mock.MagicMock()),
        mock.patch("torch.load", lambda *a, **k: {}),
        mock.patch("torch.save", lambda *a, **k: None),
        mock.patch("peft.set_peft_model_state_dict", lambda *a, **k: None),
        mock.patch("peft.get_peft_model_state_dict", lambda *a, **k: {}),
        mock.patch.object(lora, "train_adapter", lambda *a, **k: {"stub": True}),
        mock.patch.object(lora, "read_adapter", _fake_read),
        mock.patch.object(lora, "_sha256", lambda p: "stub"),
    )
    for s in stubs:
        s.start()
    try:
        rc = lora.main(argv + ["--out", str(tmp_path)])
    finally:
        for s in reversed(stubs):
            s.stop()
    assert rc == 0
    return json.loads((tmp_path / "b3_lora.json").read_text())


BASE = ["--model", "llama70b", "--tau", "0.1186",
        "--clone-content", "3", "--max-content", "3"]


def test_paired_retrain_wiring_runs_and_is_recorded(tmp_path):
    d = _run(tmp_path, BASE + ["--adapters-from", str(tmp_path),
                               "--retrain", "preference", "--init-from-reference"])
    assert d["retrained"] == ["preference"]
    assert d["init_from_reference"] is True
    # the flag must survive into the per-adapter record: a paired adapter and an
    # independently initialised one are not interchangeable and the contrast's
    # noise floor depends on which it was.
    assert d["adapters"]["preference"]["init_from_reference"] is True
    assert d["adapters"]["reference"]["init_from_reference"] is False


def test_reuse_without_retraining_records_no_paired_init(tmp_path):
    d = _run(tmp_path, BASE + ["--adapters-from", str(tmp_path)])
    assert d["retrained"] == []
    assert d["init_from_reference"] is False
