"""Pinned two-GPU inference and exact selected-coordinate SAE updates.

For the released linear decoder, h + W_dec (z' - z) is the algebraic
reconstruction-error-preserving update. Only selected encoder rows are needed.
"""
import time
from contextlib import contextmanager

from .common import MODEL, MODEL_REVISION, SAE, SAE_REVISION, SAE_FILENAME, LAYER, hf_token


def configure_transfers(torch):
    """Check actual peer-copy fidelity before trusting multi-GPU inference.

    Some rented GPU pairs report peer access but silently corrupt transfers.
    Accelerate's recursive dispatcher can instead route cross-GPU tensors through
    host memory without changing their values or the model's numerical precision.
    """
    import accelerate.hooks as hooks
    import accelerate.utils.operations as operations
    checks, failures = 0, 0
    samples = []
    for source, target in ((0, 1), (1, 0)):
        for dtype in (torch.bfloat16, torch.float32):
            for length in (64, 128, 200):
                expected = torch.arange(length*8192, dtype=torch.float32).remainder(127).to(dtype).reshape(1,length,8192)
                tensor = expected.to(f'cuda:{source}')
                actual = tensor.to(f'cuda:{target}').cpu()
                checks += 1
                failures += int(not torch.equal(actual, expected))
                samples.append((tensor, expected, torch.device('cuda', target)))
    if failures and not getattr(operations.send_to_device, '_sae_host_bridge', False):
        original = operations.send_to_device
        def host_send(value, device, non_blocking=False, skip_keys=None):
            if isinstance(value, torch.Tensor) and value.device.type == 'cuda':
                destination = torch.device('cuda', device) if isinstance(device, int) else torch.device(device)
                if destination.type == 'cuda':
                    index = torch.cuda.current_device() if destination.index is None else destination.index
                    if index != value.device.index:
                        return value.to('cpu').to(destination, non_blocking=False)
            return original(value, device, non_blocking=non_blocking, skip_keys=skip_keys)
        host_send._sae_host_bridge = True
        # Original dispatch recurses via the operations module's global name.
        operations.send_to_device = host_send
        hooks.send_to_device = host_send
    mode = 'host_staged' if getattr(operations.send_to_device, '_sae_host_bridge', False) else 'direct'
    verified = 0
    for tensor, expected, target in samples:
        # Exercise nested dispatch, including the alias used by model hooks.
        actual = hooks.send_to_device({'hidden': [tensor]}, target)['hidden'][0].cpu()
        if not torch.equal(actual, expected):
            raise RuntimeError('GPU transfer integrity check failed after selecting transport')
        verified += 1
    return {'mode': mode, 'direct_checks': checks, 'direct_failures': failures,
            'selected_transport_checks': verified, 'selected_transport_failures': 0}


def edit_hidden(hidden, encoder, bias, decoder, coordinate, delta, random_direction=None):
    import torch
    if delta == 0:
        return hidden, {'changed_positions': 0, 'realized_norm_mean': 0.0}
    x = hidden.float()
    before = torch.relu(x @ encoder[coordinate] + bias[coordinate])
    after = torch.clamp(before + delta, min=0)
    displacement = (after - before)[..., None] * decoder[:, coordinate]
    if random_direction is not None:
        displacement = displacement.norm(dim=-1, keepdim=True) * random_direction
    updated = (x + displacement).to(hidden.dtype)
    actual = updated.float() - x
    return updated, {'before_mean': before.mean().item(), 'after_mean': after.mean().item(),
                     'changed_positions': int((actual.norm(dim=-1) > 0).sum().item()),
                     'intended_norm_mean': displacement.norm(dim=-1).mean().item(),
                     'realized_norm_mean': actual.norm(dim=-1).mean().item()}


class Runtime:
    def __init__(self, feature_ids):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from huggingface_hub import hf_hub_download
        if torch.cuda.device_count() != 2 or not torch.cuda.is_bf16_supported():
            raise RuntimeError('Pinned configuration requires two bf16-capable CUDA GPUs')
        transfer = configure_transfers(torch)
        self.torch = torch
        self.features = sorted(set(feature_ids))
        token = hf_token()
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL, revision=MODEL_REVISION, token=token)
        mapping = {'model.embed_tokens': 0, 'model.rotary_emb': 0, 'model.norm': 1, 'lm_head': 1}
        mapping.update({f'model.layers.{i}': 0 if i < 40 else 1 for i in range(80)})
        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL, revision=MODEL_REVISION, token=token, torch_dtype=torch.bfloat16,
            device_map=mapping, attn_implementation='sdpa', trust_remote_code=False,
        ).eval().requires_grad_(False)
        if any(p.device.type != 'cuda' or p.dtype != torch.bfloat16 for p in self.model.parameters()):
            raise RuntimeError('Expected all-GPU bf16 model without offload')
        path = hf_hub_download(SAE, SAE_FILENAME, revision=SAE_REVISION, token=token)
        state = torch.load(path, map_location='cpu', weights_only=True)
        if state['encoder_linear.weight'].shape != (65536, 8192):
            raise ValueError('Unexpected SAE dimensions')
        self.device = next(self.model.model.layers[LAYER].parameters()).device
        self.encoder = state['encoder_linear.weight'][self.features].to(self.device, dtype=torch.float32)
        self.bias = state['encoder_linear.bias'][self.features].to(self.device, dtype=torch.float32)
        self.decoder = state['decoder_linear.weight'][:, self.features].to(self.device, dtype=torch.float32)
        del state
        self.metadata = {'gpu_names': [torch.cuda.get_device_name(i) for i in range(2)],
                         'torch': torch.__version__, 'sae_compute_dtype': 'float32',
                         'model_dtype': 'bfloat16', 'feature_ids': self.features,
                         'gpu_transfer': transfer}

    def encode(self, row, extra_instruction=''):
        system = row['system'] + ('\n' + extra_instruction if extra_instruction else '')
        rendered = self.tokenizer.apply_chat_template(
            [{'role': 'system', 'content': system}, {'role': 'user', 'content': row['text']}],
            tokenize=False, add_generation_prompt=True)
        encoded = self.tokenizer(rendered, return_tensors='pt', add_special_tokens=False,
                                 return_offsets_mapping=True)
        offsets = encoded.pop('offset_mapping')[0].tolist()
        start = rendered.rfind(row['text'])
        content_positions = [i for i, (a, b) in enumerate(offsets)
                             if b > a and a >= start and b <= start + len(row['text'])]
        if start < 0 or not content_positions:
            raise RuntimeError('Could not identify user-content tokens')
        inputs = {k: v.to(self.model.get_input_embeddings().weight.device) for k, v in encoded.items()}
        answer_ids = {}
        if row['kind'] == 'choice':
            prefix = inputs['input_ids'][0].tolist()
            for label in ('A', 'B'):
                ids = self.tokenizer.encode(rendered + label, add_special_tokens=False)
                if ids[:-1] != prefix:
                    raise RuntimeError('A/B is not a single continuation token in this template')
                answer_ids[label] = ids[-1]
        return inputs, answer_ids, content_positions

    @contextmanager
    def intervention(self, feature_id=None, delta=0, random_control=False):
        trace = []
        if feature_id is None:
            yield trace
            return
        coordinate = self.features.index(feature_id)
        direction = None
        if random_control:
            rng = self.torch.Generator().manual_seed(1009 + feature_id)
            direction = self.torch.randn(self.decoder.shape[0], generator=rng).to(self.device)
            direction = direction / direction.norm()
        def hook(_module, _args, output):
            h = output[0] if isinstance(output, tuple) else output
            update, stats = edit_hidden(h[:, -1:, :], self.encoder, self.bias, self.decoder,
                                        coordinate, delta, direction)
            trace.append(stats)
            if delta == 0:
                return output
            result = h.clone(); result[:, -1:, :] = update
            return (result, *output[1:]) if isinstance(output, tuple) else result
        handle = self.model.model.layers[LAYER].register_forward_hook(hook)
        try:
            yield trace
        finally:
            handle.remove()

    def evaluate(self, row, condition, max_new_tokens=192):
        inputs, answers, _ = self.encode(row, condition.get('instruction', ''))
        start = time.monotonic()
        with self.torch.inference_mode(), self.intervention(
                condition.get('feature_id'), condition.get('actual_delta', 0),
                condition.get('random_control', False)) as trace:
            if row['kind'] == 'choice':
                logits = self.model(**inputs, use_cache=False, logits_to_keep=1).logits[0, -1].float()
                a, b = logits[answers['A']], logits[answers['B']]
                p_a = self.torch.sigmoid(a - b).item()
                mass = (self.torch.logsumexp(self.torch.stack([a, b]), 0) - logits.logsumexp(0)).exp().item()
                if not __import__('math').isfinite(p_a) or not __import__('math').isfinite(mass):
                    raise FloatingPointError(f'Non-finite choice logits for {row["id"]}')
                value = {'p_target': p_a if row['target_label'] == 'A' else 1 - p_a,
                         'p_A': p_a, 'answer_mass': mass}
            else:
                generated = self.model.generate(**inputs, do_sample=False, max_new_tokens=max_new_tokens,
                                                pad_token_id=self.tokenizer.eos_token_id)
                suffix = generated[0, inputs['input_ids'].shape[1]:]
                value = {'response': self.tokenizer.decode(suffix, skip_special_tokens=True),
                         'generated_tokens': len(suffix), 'quality_score': None}
        return dict(value, elapsed_seconds=time.monotonic() - start,
                    trace={'hook_calls': len(trace), 'changed_positions': sum(t['changed_positions'] for t in trace),
                           'realized_norm_mean': sum(t['realized_norm_mean'] for t in trace)/max(1, len(trace))})

    def activations(self, row):
        import random
        inputs, _, content = self.encode(row)
        captured = {}
        def hook(_module, _args, output):
            h = output[0] if isinstance(output, tuple) else output
            positions = sorted(set(content + [h.shape[1] - 1]))
            # Selected rows, not a dense tokens x 65k matrix.
            z = self.torch.relu(h[0, positions].float() @ self.encoder.T + self.bias)
            captured.update(positions=positions, z=z.detach().cpu())
        handle = self.model.model.layers[LAYER].register_forward_hook(hook)
        try:
            with self.torch.inference_mode():
                self.model(**inputs, use_cache=False, logits_to_keep=1)
        finally:
            handle.remove()
        locations = {pos: i for i, pos in enumerate(captured['positions'])}
        if not self.torch.isfinite(captured['z']).all().item():
            raise FloatingPointError(f'Non-finite SAE activations for {row["id"]}')
        final = captured['z'][locations[inputs['input_ids'].shape[1]-1]].tolist()
        content_indices = [locations[p] for p in content]
        rng = random.Random(row['scenario_id'])
        examples = []
        token_ids = inputs['input_ids'][0].tolist()
        for j, feature_id in enumerate(self.features):
            values = captured['z'][content_indices, j].tolist()
            top = sorted(range(len(content)), key=lambda i: values[i], reverse=True)[:2]
            sampled = rng.sample(range(len(content)), min(2, len(content)))
            for i in sorted(set(top + sampled)):
                pos = content[i]
                examples.append({'feature_id': feature_id, 'activation': values[i],
                                 'token_position': pos, 'token': self.tokenizer.decode([token_ids[pos]]),
                                 'context': self.tokenizer.decode(token_ids[max(content[0], pos-48):pos+1]),
                                 'sampling': 'top' if i in top else 'uniform',
                                 'scope': 'user_content', 'row_id': row['id'],
                                 'scenario_id': row['scenario_id'], 'split': row['split']})
        return dict(zip(map(str, self.features), final)), examples
