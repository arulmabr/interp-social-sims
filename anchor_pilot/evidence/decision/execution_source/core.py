"""Residual interventions and readout gradients at block OUTPUT, zero-based.

All interventions affect only the final prompt position, whose logits predict
the answer. No generation cache or post-answer text is involved in this smoke.
"""
from contextlib import contextmanager

import torch


def unit(vector):
    vector = vector.detach().float()
    norm = torch.linalg.vector_norm(vector)
    if not torch.isfinite(vector).all() or norm <= 1e-12:
        raise ValueError("Cannot normalize a zero or nonfinite direction")
    return vector / norm


def hidden_of(output):
    return output[0] if isinstance(output, tuple) else output


def replace_hidden(output, hidden):
    return (hidden, *output[1:]) if isinstance(output, tuple) else hidden


@contextmanager
def residual_patch(model, layer, delta, trace=None):
    def hook(_module, _inputs, output):
        hidden = hidden_of(output)
        patched = hidden.clone()
        # Sum in float32 and cast once. Record bf16 rounding in the actual norm.
        actual_delta = delta.to(device=hidden.device, dtype=torch.float32)
        patched[:, -1, :] = (hidden[:, -1, :].float() + actual_delta).to(hidden.dtype)
        if trace is not None:
            realized = patched[:, -1, :].float() - hidden[:, -1, :].float()
            trace.append({
                "requested_norm": float(actual_delta.norm()),
                "actual_norm": float(realized.norm(dim=-1).mean()),
                "actual_norms_per_prompt": realized.norm(dim=-1).cpu().tolist(),
                "baseline_residual_norm": float(hidden[:, -1, :].float().norm(dim=-1).mean()),
                "baseline_residual_norms_per_prompt": hidden[:, -1, :].float().norm(dim=-1).cpu().tolist(),
                "positions_per_prompt": 1,
            })
        return replace_hidden(output, patched)

    handle = model.model.layers[layer].register_forward_hook(hook)
    try:
        yield
    finally:
        handle.remove()


def choice_margin(logits, risky_id, safe_id):
    return logits[0, -1, risky_id].float() - logits[0, -1, safe_id].float()


def readout_gradient(model, inputs, layer, risky_id, safe_id):
    """Freeze model first; build the backward graph only after the hooked block."""
    captured = []

    def hook(_module, _inputs, output):
        hidden = hidden_of(output).detach().requires_grad_(True)
        captured.append(hidden)
        return replace_hidden(output, hidden)

    handle = model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.enable_grad():
            logits = model(**inputs, use_cache=False).logits
            margin = choice_margin(logits, risky_id, safe_id)
            gradient, = torch.autograd.grad(margin, captured[0])
            result = gradient[0, -1].detach().float().cpu()
            residual_norm = float(captured[0][0, -1].detach().float().norm())
            return result, float(margin.detach()), residual_norm
    finally:
        handle.remove()


@torch.no_grad()
def readout(model, inputs, risky_id, safe_id):
    logits = model(**inputs, use_cache=False).logits[0, -1].float()
    probs = logits.softmax(-1)
    margin = logits[risky_id] - logits[safe_id]
    return {
        "margin": float(margin),
        "p_risky_conditional_on_labels": float(margin.sigmoid()),
        "answer_label_probability_mass": float(probs[risky_id] + probs[safe_id]),
    }


def sparse_match(decoder, target, k):
    """Signed orthogonal matching pursuit; atoms are decoder columns.

    This is an unrestricted signed decoder-vector perturbation, NOT a claim
    that every coefficient is a valid nonnegative encoder activation change.
    """
    if not 1 <= k <= min(decoder.shape):
        raise ValueError("k is outside the dictionary dimensions")
    target = target.detach().float().cpu()
    atoms = decoder.detach().float().cpu()
    norms = atoms.norm(dim=0)
    normalized = atoms / norms.clamp_min(1e-12)
    residual = target.clone()
    indices = []
    coefficients = None
    for _ in range(k):
        scores = (normalized.T @ residual).abs()
        scores[norms <= 1e-12] = -1
        if indices:
            scores[indices] = -1
        index = int(scores.argmax())
        if scores[index] <= 1e-10:
            break
        indices.append(index)
        selected = atoms[:, indices]
        coefficients = torch.linalg.lstsq(selected, target).solution
        residual = target - selected @ coefficients
        if residual.norm() <= 1e-6 * target.norm():
            break
    if not indices:
        raise ValueError("No nonzero dictionary projection")
    decoded = atoms[:, indices] @ coefficients
    return decoded, indices, coefficients, float(residual.norm() / target.norm())
