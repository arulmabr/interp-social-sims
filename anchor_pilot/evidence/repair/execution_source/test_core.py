import pytest
import torch
from transformers import LlamaConfig, LlamaForCausalLM

from anchor_pilot.core import readout, readout_gradient, residual_patch, sparse_match, unit
from anchor_pilot.prompts import smoke_prompts


@pytest.fixture
def tiny_model():
    torch.manual_seed(17)
    config = LlamaConfig(vocab_size=32, hidden_size=24, intermediate_size=48,
                         num_hidden_layers=3, num_attention_heads=4,
                         num_key_value_heads=2, max_position_embeddings=64)
    model = LlamaForCausalLM(config).eval().requires_grad_(False)
    return model, {"input_ids": torch.tensor([[1, 5, 7, 3]])}


def test_frozen_model_gradient_matches_finite_difference(tiny_model):
    model, inputs = tiny_model
    grad, _, _ = readout_gradient(model, inputs, 1, 4, 8)
    direction = unit(grad)
    eps = 0.0001
    values = []
    for sign in (-1, 1):
        with residual_patch(model, 1, sign * eps * direction):
            values.append(readout(model, inputs, 4, 8)["margin"])
    numerical = (values[1] - values[0]) / (2 * eps)
    assert numerical == pytest.approx(float(grad @ direction), rel=0.003)
    assert all(parameter.grad is None for parameter in model.parameters())


def test_zero_patch_identity_and_hook_cleanup(tiny_model):
    model, inputs = tiny_model
    baseline = readout(model, inputs, 4, 8)
    with residual_patch(model, 1, torch.zeros(24)):
        assert readout(model, inputs, 4, 8) == baseline
    with pytest.raises(RuntimeError):
        with residual_patch(model, 1, torch.ones(24)):
            raise RuntimeError("intentional fixture failure")
    assert not model.model.layers[1]._forward_hooks
    assert readout(model, inputs, 4, 8) == baseline


def test_patch_only_last_token_and_exact_norm(tiny_model):
    model, inputs = tiny_model
    captured = []
    handle = model.model.layers[1].register_forward_hook(lambda m, i, o: captured.append(o.detach().clone()))
    readout(model, inputs, 4, 8)
    handle.remove()
    trace = []
    with residual_patch(model, 1, 0.1 * unit(torch.arange(24)), trace):
        handle = model.model.layers[1].register_forward_hook(lambda m, i, o: captured.append(o.detach().clone()))
        readout(model, inputs, 4, 8)
        handle.remove()
    assert torch.equal(captured[0][:, :-1], captured[1][:, :-1])
    assert trace[0]["actual_norm"] == pytest.approx(0.1, rel=1e-5)


def test_error_preserving_decode_equals_addition():
    torch.manual_seed(4)
    decoder = torch.randn(6, 10)
    bias, hidden, z, delta_z = torch.randn(6), torch.randn(6), torch.rand(10), torch.randn(10)
    original = decoder @ z + bias
    edited = decoder @ (z + delta_z) + bias + (hidden - original)
    assert torch.allclose(edited, hidden + decoder @ delta_z, atol=1e-5)


def test_sparse_reconstruction_and_zero_guard():
    decoder = torch.eye(8)
    target = torch.tensor([0., 2., 0., 0., -3., 0., 0., 0.])
    decoded, indices, coefficients, error = sparse_match(decoder, target, 2)
    assert set(indices) == {1, 4}
    assert torch.allclose(decoded, target)
    assert error < 1e-6
    assert coefficients.min() < 0
    with pytest.raises(ValueError):
        unit(torch.zeros(8))


def test_prompt_balance_and_answer_mapping():
    rows = smoke_prompts()
    assert len(rows) == 4
    assert {row["frame"] for row in rows} == {"gain", "loss"}
    for frame in ("gain", "loss"):
        assert {row["risky_label"] for row in rows if row["frame"] == frame} == {"A", "B"}
