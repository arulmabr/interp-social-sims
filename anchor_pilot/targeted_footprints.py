"""Descriptive footprints for nominated features; does not select interventions."""
import torch

TARGETS = [184, 4237, 31935, 13142, 20117, 4992, 47380]


def summarize(encoder, decoder, base, delta):
    weights, bias = encoder
    atoms = decoder[:, TARGETS]
    norms = atoms.norm(dim=0)
    projection = delta @ atoms / norms
    before = torch.relu(base @ weights[TARGETS].T + bias[TARGETS])
    after = torch.relu((base + delta) @ weights[TARGETS].T + bias[TARGETS])
    change = after - before
    return [{
        'feature': index,
        'mean_unit_decoder_projection': float(projection[:, j].mean()),
        'mean_absolute_unit_decoder_projection': float(projection[:, j].abs().mean()),
        'single_column_coefficient_for_mean_delta': float(projection[:, j].mean() / norms[j]),
        'mean_encoder_before': float(before[:, j].mean()),
        'mean_encoder_after': float(after[:, j].mean()),
        'mean_encoder_change': float(change[:, j].mean()),
        'mean_absolute_encoder_change': float(change[:, j].abs().mean()),
    } for j, index in enumerate(TARGETS)]
