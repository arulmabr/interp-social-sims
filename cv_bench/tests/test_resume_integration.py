"""Interrupt the real read loops and check they resume to the same answer.

The unit tests in test_checkpoint.py cover the checkpoint primitive. These
cover the *wiring*: that `b2_cal.read_z`, `numerics_fp32.score_all` and
`anchors.gradient.average_gradient` actually carry a checkpoint through, resume
where they stopped, and land on the value an uninterrupted run would have
produced. A resume that returns a different answer is worse than no resume.
"""

from types import SimpleNamespace

import numpy as np
import pytest

from cv_bench.anchors import gradient as GRAD
from cv_bench.anchors import numerics_fp32 as NUM
from cv_bench.estimator import b2_cal as CAL
from cv_bench.tasks import core, risk


class Boom(RuntimeError):
    """A crash, at a chosen point."""


@pytest.fixture(scope="module")
def trials():
    return sorted(core.expand_formats(list(risk.generate_risk(splits=("cal",)))),
                  key=lambda t: t.trial_id)[:60]


class FakeReadout:
    """Deterministic z per trial, with an optional crash after `die_after` calls."""

    def __init__(self, die_after=None):
        self.calls = 0
        self.die_after = die_after

    def _value(self, spec):
        h = abs(hash(spec.prompt)) % 10_000
        return h / 1000.0 - 5.0

    def score(self, spec, intervention=None):
        if self.die_after is not None and self.calls >= self.die_after:
            raise Boom("simulated preemption")
        self.calls += 1
        v = self._value(spec)
        return SimpleNamespace(logit_diff=v, valid_mass=0.9, n_prompt_tokens=10)

    def render(self, spec):
        return spec.prompt


def test_b2_cal_read_z_resumes_to_the_same_answer(trials, tmp_path):
    ckpt = tmp_path / "ck.npz"

    whole, mass_whole = CAL.read_z(FakeReadout(), trials, ckpt=tmp_path / "other.npz")

    # Die partway. The checkpoint flushes every 50, so 55 calls keeps 50.
    with pytest.raises(Boom):
        CAL.read_z(FakeReadout(die_after=55), trials, ckpt=ckpt)

    from cv_bench.estimator import checkpoint as CK
    mid = CK.Partial(ckpt, len(trials), chunk=50, n_cols=2,
                     key=CK.items_key([t.trial_id for t in trials]))
    assert 0 < mid.n_done < len(trials), "nothing was checkpointed"

    # A fresh reader finishes the job.
    resumed = FakeReadout()
    z, mass = CAL.read_z(resumed, trials, ckpt=ckpt)
    assert np.allclose(z, whole), "resumed run disagrees with an uninterrupted one"
    assert np.allclose(mass, mass_whole)
    assert resumed.calls == len(trials) - mid.n_done, "resume re-did finished work"


def test_numerics_score_all_resumes(trials, tmp_path):
    ckpt = tmp_path / "ck.npz"
    model = SimpleNamespace(device="cpu")

    import cv_bench.anchors.numerics_fp32 as mod
    made = {}

    def fake_readout_factory(m, t):
        return made["ro"]

    # score_all builds its own Readout; swap the class it imports.
    import cv_bench.readout as RO
    orig = RO.Readout
    try:
        made["ro"] = FakeReadout(die_after=30)
        RO.Readout = fake_readout_factory
        with pytest.raises(Boom):
            mod.score_all(model, None, trials, ckpt=ckpt)

        made["ro"] = FakeReadout()
        z = mod.score_all(model, None, trials, ckpt=ckpt)
        made["ro"] = FakeReadout()
        whole = mod.score_all(model, None, trials, ckpt=tmp_path / "other.npz")
        assert np.allclose(z, whole)
    finally:
        RO.Readout = orig


def test_gradient_average_resumes_and_skips_finished_work(trials, tmp_path, monkeypatch):
    model = SimpleNamespace(config=SimpleNamespace(hidden_size=16), device="cpu")
    ro = object()
    hidden = 16

    state = {"calls": 0, "die_after": None}

    def fake_grad(_model, _tok, _ro, trial, layer):
        state["calls"] += 1
        if state["die_after"] is not None and state["calls"] > state["die_after"]:
            raise Boom("simulated preemption")
        rng = np.random.default_rng(abs(hash(trial.trial_id)) % 2**31)
        return rng.normal(size=hidden)

    monkeypatch.setattr(GRAD, "z_gradient", fake_grad)

    whole = GRAD.average_gradient(model, None, ro, trials, 0,
                                  ckpt=tmp_path / "other.npz")

    state["calls"] = 0
    state["die_after"] = 25
    with pytest.raises(Boom):
        GRAD.average_gradient(model, None, ro, trials, 0, ckpt=tmp_path / "ck.npz")

    done_before = state["calls"]
    state["calls"] = 0
    state["die_after"] = None
    resumed = GRAD.average_gradient(model, None, ro, trials, 0,
                                    ckpt=tmp_path / "ck.npz")

    assert resumed["n"] == whole["n"] == len(trials)
    assert np.allclose(resumed["vector"], whole["vector"]), \
        "the resumed mean gradient differs from an uninterrupted one"
    assert state["calls"] < done_before + len(trials), "resume re-did finished work"
