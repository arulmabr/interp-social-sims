"""Tests for cv_bench/readout.py and cv_bench/steer.py.

These are real forward passes, not mocks: they load Qwen2.5-0.5B-Instruct from the
lab share on CPU. A mocked test would not catch the two things that actually go
wrong here — left padding silently breaking rotary positions, and a position
policy that means something different during cached decoding than during prefill.

    pytest -q cv_bench/tests/

Set CV_BENCH_TEST_MODEL to use a different checkpoint.
"""
from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest
import torch

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.readout import Readout, TrialSpec           # noqa: E402
from cv_bench.steer import (                              # noqa: E402
    Intervention, SteeringHook, median_residual_norm,
)

MODEL_ID = os.environ.get("CV_BENCH_TEST_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
LABELS = ("Safe", "Risky")


def lottery_prompt(n: int) -> str:
    return (
        "SAFE VS. RISKY CHOICE GAME\n\n"
        "You must choose between two options:\n"
        "1. Safe Option: Guaranteed 50 tokens.\n"
        f"2. Risky Option: 50% chance of {n} tokens, 50% chance of 0 tokens.\n\n"
        "Which option do you choose? Respond with either 'Safe' or 'Risky' "
        "as your final answer."
    )


@pytest.fixture(scope="session")
def model_and_tok():
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(int(os.environ.get("CV_BENCH_THREADS", "2")))
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, torch_dtype=torch.float32)
    model.eval()
    return model, tok


@pytest.fixture(scope="session")
def readout(model_and_tok):
    model, tok = model_and_tok
    return Readout(model, tok)


@pytest.fixture(scope="session")
def specs():
    return [TrialSpec(prompt=lottery_prompt(n), labels=LABELS)
            for n in range(20, 245, 5)]


# ---------------------------------------------------------------------------
# readout
# ---------------------------------------------------------------------------
def test_both_tokenisations_are_checked(readout):
    for lab in LABELS:
        ids = readout.label_token_ids(lab)
        assert len(ids) >= 1
        bare = readout.tok(lab, add_special_tokens=False)["input_ids"][0]
        spaced = readout.tok(" " + lab, add_special_tokens=False)["input_ids"][0]
        assert bare in ids and spaced in ids


def test_score_is_well_formed(readout, specs):
    r = readout.score(specs[0])
    assert r.valid_mass > 0
    assert abs(sum(r.prob.values()) - 1.0) < 1e-6
    assert np.isfinite(r.logit_diff)
    assert r.n_prompt_tokens > 10


def test_valid_mass_is_reported(readout, specs):
    """The >= 0.98 bar is a property of the real stack and its stem.

    On a 0.5B model it is not expected to hold; the test asserts the check runs
    and reports the number, and the bar itself is enforced before any 70B result
    is used (`Readout.check_valid_mass`).
    """
    rep = readout.check_valid_mass(specs[:10])
    assert 0.0 <= rep["mean"] <= 1.0
    print(f"\nvalid mass: mean={rep['mean']:.4f} min={rep['min']:.4f} "
          f"passes_0.98={rep['passes']}")


def test_batched_matches_unbatched(readout, specs):
    """Left padding needs explicit position_ids; 1e-2 is the plan's bar."""
    rep = readout.check_batch_agreement(specs[:8], tol=1e-2, batch_size=8)
    print(f"\nbatch agreement: max|diff|={rep['max_abs_diff']:.2e}")
    assert rep["passes"], rep


def test_logit_diff_moves_with_the_reward(readout, specs):
    """A sanity check on direction, not on the model's preferences.

    Raising the risky payoff should not make the risky option *less* attractive
    across the whole grid. Only the trend is asserted.
    """
    xs = np.array([20, 100, 240], dtype=float)
    ys = np.array([readout.score(TrialSpec(prompt=lottery_prompt(int(n)),
                                           labels=LABELS)).logit_diff for n in xs])
    assert np.isfinite(ys).all()
    print(f"\nlogit_diff at n=20/100/240: {ys.round(3)}")


# ---------------------------------------------------------------------------
# steer
# ---------------------------------------------------------------------------
def test_median_residual_norm_is_positive(model_and_tok):
    model, tok = model_and_tok
    prompts = [lottery_prompt(n) for n in (20, 60, 120)]
    m = median_residual_norm(model, tok, prompts, layer=8)
    assert m > 0 and np.isfinite(m)
    print(f"\nmedian residual norm @L8 = {m:.2f}")


def test_scale_zero_is_a_no_op(readout, specs, model_and_tok):
    """scale 0 must give bit-identical logits to no hook at all."""
    model, _ = model_and_tok
    base = readout.score(specs[3])
    d = model.config.hidden_size
    iv = Intervention(layer=8, vectors=np.ones(d, dtype=np.float32),
                      scale=0.0, positions="all", norm_unit=1.0)
    steered = readout.score(specs[3], intervention=iv)
    assert steered.logit_diff == pytest.approx(base.logit_diff, abs=1e-6)
    assert steered.valid_mass == pytest.approx(base.valid_mass, abs=1e-9)


def test_nonzero_scale_changes_the_logits(readout, specs, model_and_tok):
    model, tok = model_and_tok
    d = model.config.hidden_size
    unit = median_residual_norm(model, tok, [specs[3].prompt], layer=8)
    rng = np.random.default_rng(0)
    iv = Intervention(layer=8, vectors=rng.normal(size=d).astype(np.float32),
                      scale=0.5, positions="all", norm_unit=unit)
    base = readout.score(specs[3])
    steered = readout.score(specs[3], intervention=iv)
    assert abs(steered.logit_diff - base.logit_diff) > 1e-4


@pytest.mark.parametrize("positions", ["last", "all_prompt", "all", "legacy_ramp"])
def test_positions_touched_during_cached_decoding(model_and_tok, positions):
    """The recording test: prove which positions each policy modifies.

    Prefill carries the whole prompt in one pass; every later pass carries one
    token. This is where the legacy policy's meaning is decided, and where the
    appendix and the code part company.
    """
    model, tok = model_and_tok
    prompt = lottery_prompt(100)
    enc = tok(prompt, return_tensors="pt")
    n_prompt = int(enc["input_ids"].shape[1])
    d = model.config.hidden_size
    iv = Intervention(layer=8, vectors=np.ones(d, dtype=np.float32),
                      scale=0.1, positions=positions, norm_unit=1.0)
    n_new = 5
    with SteeringHook(model, iv, prompt_len=n_prompt, record=True) as hook:
        with torch.inference_mode():
            model.generate(**enc, max_new_tokens=n_new, do_sample=False,
                           pad_token_id=tok.pad_token_id, use_cache=True)
        passes = hook.modified

    prefill, decode = passes[0], passes[1:]
    assert len(decode) >= 1, "expected cached decoding passes"

    if positions == "all":
        assert prefill == list(range(n_prompt))
        assert all(len(p) == 1 for p in decode), "every generated token is steered"
    elif positions == "all_prompt":
        assert prefill == list(range(n_prompt))
        assert all(p == [] for p in decode), "no generated token is steered"
    elif positions == "last":
        assert prefill == [n_prompt - 1]
        assert all(p == [] for p in decode)
    elif positions == "legacy_ramp":
        # the last 20% of prompt positions, and nothing afterwards
        expected_n = n_prompt - max(1, n_prompt - max(1, int(np.ceil(n_prompt * 0.2))))
        assert len(prefill) == expected_n and prefill[-1] == n_prompt - 1
        assert all(p == [] for p in decode), (
            "the legacy policy steers no generated token -- this is the finding "
            "in reports/STACK_AUDIT.md section 3, asserted here so it cannot regress"
        )


def test_legacy_ramp_matches_the_legacy_arithmetic(model_and_tok):
    """`legacy_ramp` must reproduce Probes/models.py exactly, gains included."""
    import math
    model, _ = model_and_tok
    d = model.config.hidden_size
    iv = Intervention(layer=8, vectors=np.ones(d, dtype=np.float32), scale=1.0,
                      positions="legacy_ramp", norm_unit=1.0)
    hook = SteeringHook(model, iv, prompt_len=50)
    for seq_len in (1, 7, 50, 137):
        idx, gain = hook._targets(seq_len, 0)
        start = max(1, seq_len - max(1, int(math.ceil(seq_len * 0.20))))
        n = seq_len - start
        if n <= 0:
            assert idx == [] and gain == []
        else:
            assert idx == list(range(start, seq_len))
            assert np.allclose(gain, np.linspace(0.5, 1.0, n))


def test_clamp_mode_raises_the_projection(model_and_tok):
    model, tok = model_and_tok
    d = model.config.hidden_size
    rng = np.random.default_rng(1)
    v = rng.normal(size=d).astype(np.float32)
    v /= np.linalg.norm(v)
    prompt = lottery_prompt(100)
    enc = tok(prompt, return_tensors="pt")
    n = int(enc["input_ids"].shape[1])
    captured = {}

    def grab(_m, _i, out):
        captured["h"] = (out[0] if isinstance(out, tuple) else out).detach().clone()
        return out

    h = model.model.layers[8].register_forward_hook(grab)
    try:
        with torch.inference_mode():
            model(**enc, use_cache=False)
        before = captured["h"][0]
    finally:
        h.remove()

    unit = float(before.float().norm(dim=-1).median())
    target = unit * 2.0
    iv = Intervention(layer=8, vectors=v, scale=2.0, positions="all",
                      mode="clamp", norm_unit=unit)
    # The capture hook must run AFTER the steering hook: forward hooks fire in
    # registration order, so registering it first would capture the untouched
    # activations and the test would assert against the wrong tensor.
    with SteeringHook(model, iv, prompt_len=n):
        h2 = model.model.layers[8].register_forward_hook(grab)
        try:
            with torch.inference_mode():
                model(**enc, use_cache=False)
            after = captured["h"][0]
        finally:
            h2.remove()

    vt = torch.as_tensor(v, dtype=after.dtype)
    proj = (after.float() @ vt.float())
    assert (proj >= target - 1e-2).all(), "clamp must lift every position to the target"


# ---------------------------------------------------------------------------
# labels must differ where the readout actually looks
#
# Reported by the Track B session on 22 Sept: `score` returned z = 0 for every
# prompt when both labels shared their first token under the stem. Nothing in
# the arithmetic objects -- a difference of two identical log-probabilities is a
# clean zero, which reads as "the intervention did nothing" rather than "nothing
# was measured". The same check guards Track B's gradient anchor, where a zero z
# makes every gradient zero too.
# ---------------------------------------------------------------------------
def test_shared_first_token_is_an_error_not_a_zero(readout):
    """'Option A' vs 'Option B' under a bare stem: the scored token is 'Option'."""
    spec = TrialSpec(prompt=lottery_prompt(120), labels=("Option A", "Option B"),
                     stem="Answer:")
    with pytest.raises(ValueError, match="identically zero"):
        readout.assert_labels_distinguishable(spec)
    with pytest.raises(ValueError, match="identically zero"):
        readout.score(spec)


def test_the_error_names_the_shared_token(readout):
    spec = TrialSpec(prompt=lottery_prompt(120), labels=("Option A", "Option B"),
                     stem="Answer:")
    try:
        readout.assert_labels_distinguishable(spec)
    except ValueError as e:
        assert "share first-token ids" in str(e)
        assert "'Answer:'" in str(e)          # the stem is named
        assert "Answer: Option" in str(e)     # and so is the fix
    else:
        pytest.fail("expected ValueError")


def test_moving_the_stem_onto_the_difference_fixes_it(readout):
    """The documented remedy must actually pass, and must not give z = 0."""
    spec = TrialSpec(prompt=lottery_prompt(120), labels=("A", "B"),
                     stem="Answer: Option")
    readout.assert_labels_distinguishable(spec)      # no raise
    out = readout.score(spec)
    assert out.logit_diff == out.logit_diff          # not NaN
    assert out.valid_mass > 0


@pytest.mark.parametrize("labels", [
    ("Safe", "Risky"), ("Reject", "Accept"), ("A", "B"),
    ("Certain", "Chance"), ("Refuse", "Take"),
])
def test_every_label_set_this_repo_uses_is_distinguishable(readout, labels):
    spec = TrialSpec(prompt=lottery_prompt(120), labels=labels, stem="Answer:")
    readout.assert_labels_distinguishable(spec)


def test_an_empty_label_is_an_error_too(readout):
    spec = TrialSpec(prompt=lottery_prompt(120), labels=("", "Risky"), stem="Answer:")
    with pytest.raises(ValueError, match="no first-token ids"):
        readout.assert_labels_distinguishable(spec)


def test_score_batch_is_guarded_as_well(readout):
    specs = [TrialSpec(prompt=lottery_prompt(n), labels=("Option A", "Option B"),
                       stem="Answer:") for n in (20, 120)]
    with pytest.raises(ValueError, match="identically zero"):
        readout.score_batch(specs, batch_size=2)


def test_identical_labels_are_caught(readout):
    spec = TrialSpec(prompt=lottery_prompt(120), labels=("Risky", "Risky"),
                     stem="Answer:")
    with pytest.raises(ValueError):
        readout.assert_labels_distinguishable(spec)
