import torch
import pytest

from anchor_pilot.modeling import (add_lora, enable_lora, install_partition_transfers, load_stack,
                                  prepare_inputs, restore_adapter, save_adapter, soft_answer_loss)
from anchor_pilot.design import build_rows
from anchor_pilot.core import readout


def test_huggingface_batch_encoding_is_moved_as_a_mapping():
    from transformers.tokenization_utils_base import BatchEncoding
    from anchor_pilot.modeling import move_tree
    batch = BatchEncoding({'input_ids': torch.ones(1, 3, dtype=torch.long),
                           'attention_mask': torch.ones(1, 3, dtype=torch.long)})
    moved = move_tree(batch, torch.device('meta'))
    assert all(value.device.type == 'meta' for value in moved.values())
    assert batch['input_ids'].device.type == 'cpu'


def test_batch_gradient_has_no_cross_example_or_mean_scaling():
    from anchor_pilot.modeling import batch_readout_gradients
    from anchor_pilot.core import readout_gradient
    model, tokenizer, _, _, _, _ = load_stack(fixture=True)
    prepared = prepare_inputs(model, tokenizer, build_rows()[:2])
    prepared[1][0]['input_ids'] = prepared[1][0]['input_ids'][:, -4:]
    batched = batch_readout_gradients(model, prepared, 2)
    expected = torch.stack([readout_gradient(model, inputs, 2, risky, safe)[0] for inputs, risky, safe in prepared])
    assert torch.allclose(batched, expected, atol=1e-6, rtol=1e-5)


def test_left_padding_matches_individual_readout():
    from anchor_pilot.modeling import answer_logits
    model, tokenizer, _, _, _, _ = load_stack(fixture=True)
    inputs = prepare_inputs(model, tokenizer, build_rows()[:2])
    inputs[1][0]['input_ids'] = inputs[1][0]['input_ids'][:, -4:]
    with torch.no_grad():
        risky, safe, _ = answer_logits(model, inputs)
    for i, item in enumerate(inputs):
        assert abs(float(risky[i] - safe[i]) - readout(model, *item)['margin']) < 1e-6


@pytest.mark.skipif(torch.cuda.device_count() < 2, reason='Needs two CUDA devices')
@pytest.mark.parametrize('expanded', [False, True])
def test_actual_two_gpu_bf16_training_path(expanded):
    from anchor_pilot.modeling import batched_answer_loss
    from anchor_pilot.repair_design import MODULES
    model, tokenizer, _, _, _, _ = load_stack(fixture=True)
    model.to(device='cuda:0', dtype=torch.bfloat16)
    for layer in model.model.layers[2:]:
        layer.to('cuda:1')
    model.model.norm.to('cuda:1')
    model.lm_head.to('cuda:1')
    install_partition_transfers(model)
    prepared = prepare_inputs(model, tokenizer, build_rows()[:2])
    add_lora(model, 0 if expanded else 1, 2, rank=2,
             target_modules=MODULES if expanded else None)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.train()
    loss = batched_answer_loss(model, prepared, [.7, .3])
    loss.backward()
    devices_with_grad = {p.device.index for p in model.parameters() if p.grad is not None and p.grad.norm() > 0}
    assert devices_with_grad == {0, 1}
    assert all(p.grad is None for name, p in model.named_parameters() if 'lora_' not in name)


def test_adapter_training_disable_restore_and_partition(tmp_path):
    model, tokenizer, _, _, layers, _ = load_stack(fixture=True)
    inputs = prepare_inputs(model, tokenizer, build_rows()[:2])
    baseline = readout(model, *inputs[0])
    handles = install_partition_transfers(model)
    assert readout(model, *inputs[0]) == baseline
    config = add_lora(model, 1, 2, rank=2)
    assert readout(model, *inputs[0]) == baseline
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.train()
    trainable = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(trainable, lr=.02)
    old_loss = float(soft_answer_loss(model, inputs, [.9, .1]).detach())
    for _ in range(5):
        optimizer.zero_grad()
        loss = soft_answer_loss(model, inputs, [.9, .1])
        loss.backward()
        assert any(p.grad is not None and p.grad.norm() > 0 for p in trainable)
        assert all(p.grad is None for p in model.parameters() if not p.requires_grad)
        optimizer.step()
    assert float(soft_answer_loss(model, inputs, [.9, .1]).detach()) < old_loss
    model.eval()
    adapted = readout(model, *inputs[0])
    assert adapted != baseline
    save_adapter(model, config, tmp_path)
    enable_lora(model, False)
    assert readout(model, *inputs[0]) == baseline
    enable_lora(model, True)
    restore_adapter(model, tmp_path)
    assert readout(model, *inputs[0]) == adapted
    for handle in handles:
        handle.remove()
