"""Common bf16 stack, explicit differentiable model partition, and PEFT LoRA.

Accelerate is used to LOAD the weight partition only. Its inference dispatch
hooks are removed before any training. Ordinary PyTorch .to() transfers at
block boundaries preserve autograd. One process owns both GPUs; no Trainer,
DDP, inference offloading, or quantization is involved.
"""
from contextlib import contextmanager
from collections.abc import Mapping
import hashlib
import json
from pathlib import Path

import torch
from accelerate.hooks import remove_hook_from_module
from huggingface_hub import hf_hub_download
from peft import LoraConfig, get_peft_model_state_dict, inject_adapter_in_model, set_peft_model_state_dict
from peft.tuners.tuners_utils import BaseTunerLayer
from transformers import AutoModelForCausalLM, AutoTokenizer, LlamaConfig, LlamaForCausalLM

from .auth import resolve_token
from .core import hidden_of, replace_hidden
from .preflight import MODEL, SAE
from .smoke import SAE_REVISION, FEATURES

MODEL_REVISION = '6f6073b423013f6a7d4d9f39144961bfbfbc386b'


def move_tree(value, device):
    if torch.is_tensor(value):
        return value.to(device)
    if isinstance(value, tuple):
        return tuple(move_tree(v, device) for v in value)
    if isinstance(value, list):
        return [move_tree(v, device) for v in value]
    if isinstance(value, Mapping):
        return {k: move_tree(v, device) for k, v in value.items()}
    return value


def install_partition_transfers(model):
    remove_hook_from_module(model, recurse=True)
    handles = []
    for module in [*model.model.layers, model.model.norm, model.lm_head]:
        device = next(module.parameters()).device
        def transfer(_module, args, kwargs, target=device):
            return move_tree(args, target), move_tree(kwargs, target)
        handles.append(module.register_forward_pre_hook(transfer, with_kwargs=True))
    return handles


def load_stack(fixture=False, token_name=None):
    torch.manual_seed(17)
    if fixture:
        cfg = LlamaConfig(vocab_size=64, hidden_size=32, intermediate_size=64,
                          num_hidden_layers=4, num_attention_heads=4, num_key_value_heads=2)
        model = LlamaForCausalLM(cfg).eval().requires_grad_(False)
        dictionary = torch.randn(32, 64)
        encoder = torch.randn(64, 32) * .1
        return model, None, dictionary, (encoder, torch.zeros(64)), [1, 2], [1, 3, 5, 7, 9, 11]
    if torch.cuda.device_count() != 2 or not torch.cuda.is_bf16_supported():
        raise RuntimeError('This pilot configuration requires two bf16 CUDA GPUs')
    token = resolve_token(token_name)
    tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, token=token)
    # Approximately equal base-weight allocation, with the cut below the first
    # adapted block. The backward path crosses GPU boundaries explicitly.
    mapping = {'model.embed_tokens': 0, 'model.rotary_emb': 0, 'model.norm': 1, 'lm_head': 1}
    mapping.update({f'model.layers.{i}': 0 if i < 40 else 1 for i in range(80)})
    model = AutoModelForCausalLM.from_pretrained(
        MODEL, revision=MODEL_REVISION, token=token, torch_dtype=torch.bfloat16,
        device_map=mapping, attn_implementation='sdpa', trust_remote_code=False,
    ).eval().requires_grad_(False)
    install_partition_transfers(model)
    if any(p.device.type != 'cuda' or p.dtype != torch.bfloat16 for p in model.parameters()):
        raise RuntimeError('Base weights must remain all-GPU bf16')
    filename = hf_hub_download(SAE, 'Llama-3.3-70B-Instruct-SAE-l50.pt', revision=SAE_REVISION, token=token)
    state = torch.load(filename, map_location='cpu', weights_only=True)
    return (model, tokenizer, state['decoder_linear.weight'].float().contiguous(),
            (state['encoder_linear.weight'].float(), state['encoder_linear.bias'].float()),
            [48, 50], FEATURES)


def prepare_inputs(model, tokenizer, rows):
    device = model.get_input_embeddings().weight.device
    prepared = []
    for row in rows:
        if tokenizer is None:
            encoded = hashlib.sha256(row['text'].encode()).digest()[:6]
            inputs = {'input_ids': torch.tensor([[1, *[int(v) % 48 + 10 for v in encoded], 3]], device=device)}
            ids = {'A': 4, 'B': 8}
        else:
            rendered = tokenizer.apply_chat_template([{'role': 'user', 'content': row['text']}],
                                                       tokenize=False, add_generation_prompt=True)
            inputs = tokenizer(rendered, return_tensors='pt', add_special_tokens=False)
            prefix = inputs['input_ids'][0].tolist()
            ids = {}
            for label in 'AB':
                continuation = tokenizer.encode(rendered + label, add_special_tokens=False)
                if continuation[:-1] != prefix:
                    raise RuntimeError('Answer is not a single continuation token')
                ids[label] = continuation[-1]
            inputs = move_tree(inputs, device)
            if any(v.device != device for v in inputs.values() if torch.is_tensor(v)):
                raise RuntimeError('Tokenizer inputs were not moved to the embedding device')
        prepared.append((inputs, ids[row['risky_label']], ids[row['safe_label']]))
    return prepared


@contextmanager
def capture_residuals(model, layers):
    captured = {}
    handles = []
    for layer in layers:
        def hook(_module, _inputs, output, key=layer):
            captured[key] = hidden_of(output)[:, -1].detach().float().cpu()
        handles.append(model.model.layers[layer].register_forward_hook(hook))
    try:
        yield captured
    finally:
        for handle in handles:
            handle.remove()


def add_lora(model, first_layer, last_layer, rank=8):
    config = LoraConfig(r=rank, lora_alpha=rank * 2, lora_dropout=0,
                        target_modules=['q_proj', 'v_proj'], bias='none',
                        layers_to_transform=list(range(first_layer, last_layer + 1)),
                        layers_pattern='layers')
    inject_adapter_in_model(config, model)
    # Float32 adapter and optimizer state; all frozen base weights stay bf16.
    for name, p in model.named_parameters():
        if 'lora_' in name:
            p.data = p.data.float()
    return config


def enable_lora(model, enabled):
    for module in model.modules():
        if isinstance(module, BaseTunerLayer):
            module.enable_adapters(enabled)
    if not enabled:
        model.requires_grad_(False)


def save_adapter(model, config, destination):
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    config.save_pretrained(destination)
    # CPU state only, compatible PEFT key naming; no base weights or credentials.
    torch.save({k: v.detach().cpu() for k, v in get_peft_model_state_dict(model).items()}, destination / 'adapter.pt')


def restore_adapter(model, destination):
    state = torch.load(Path(destination) / 'adapter.pt', map_location='cpu', weights_only=True)
    result = set_peft_model_state_dict(model, state)
    if result.unexpected_keys:
        raise RuntimeError('Unexpected adapter state keys')


def reset_adapter(model, seed=17):
    torch.manual_seed(seed)
    for module in model.modules():
        if isinstance(module, BaseTunerLayer):
            module.reset_lora_parameters('default', True)
    enable_lora(model, True)


def soft_answer_loss(model, prepared, targets):
    """Expected full-vocabulary answer-token CE under a synthetic choice agent.

    This analytically averages Bernoulli prompt->answer-token examples. It
    preserves the planted choice noise instead of training on argmax labels.
    The softmax covers the vocabulary, so invalid answer mass is penalized.
    """
    losses = []
    for (inputs, risky, safe), target in zip(prepared, targets):
        logits = model(**inputs, use_cache=False, logits_to_keep=1).logits[0, -1].float()
        log_probs = logits.log_softmax(-1)
        losses.append(-float(target) * log_probs[risky] - (1 - float(target)) * log_probs[safe])
    return torch.stack(losses).mean()


def collate(prepared):
    device = prepared[0][0]['input_ids'].device
    length = max(item[0]['input_ids'].shape[1] for item in prepared)
    ids = torch.zeros((len(prepared), length), dtype=torch.long, device=device)
    mask = torch.zeros_like(ids)
    for i, (inputs, _, _) in enumerate(prepared):
        n = inputs['input_ids'].shape[1]
        ids[i, -n:] = inputs['input_ids'][0]
        mask[i, -n:] = 1
    positions = (mask.cumsum(-1) - 1).clamp_min(0)
    return {'input_ids': ids, 'attention_mask': mask, 'position_ids': positions}


def answer_logits(model, prepared):
    logits = model(**collate(prepared), use_cache=False, logits_to_keep=1).logits[:, -1].float()
    index = torch.arange(len(prepared), device=logits.device)
    risky = torch.tensor([x[1] for x in prepared], device=logits.device)
    safe = torch.tensor([x[2] for x in prepared], device=logits.device)
    normalizer = logits.logsumexp(-1)
    return logits[index, risky], logits[index, safe], normalizer


def batched_answer_loss(model, prepared, targets):
    risky, safe, norm = answer_logits(model, prepared)
    target = torch.as_tensor(targets, device=risky.device, dtype=torch.float32)
    return (norm - target * risky - (1 - target) * safe).mean()


def batch_readout_gradients(model, prepared, layer):
    """Independent per-prompt gradients in the same padded bf16 batch as scoring.

    Sum the per-example margins. No attention crosses examples, so each row's
    derivative is its own margin derivative, not a mean-scaled batch gradient.
    """
    captured = []
    def hook(_module, _inputs, output):
        hidden = hidden_of(output).detach().requires_grad_(True)
        captured.append(hidden)
        return replace_hidden(output, hidden)
    handle = model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.enable_grad():
            risky, safe, _ = answer_logits(model, prepared)
            gradient, = torch.autograd.grad((risky - safe).sum(), captured[0])
        return gradient[:, -1].detach().float().cpu()
    finally:
        handle.remove()
