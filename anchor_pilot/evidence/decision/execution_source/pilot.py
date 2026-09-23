"""End-to-end provisional anchor pilot. Scientific decision thresholds unset.

All selection uses discovery or selection rows. Frozen responses are collected
only after directions, dose, candidate ranking, and adapter checkpoint choices
are written. Simulator targets are expected answer-token cross entropy.
"""
import argparse
from contextlib import nullcontext
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
import torch

from .analysis import condition_summary, switches
from .core import readout_gradient, residual_patch, sparse_match, unit
from .cpt import fit, probabilities
from .design import AGENTS, digest, render
from .modeling import (MODEL_REVISION, SAE_REVISION, add_lora, answer_logits, batched_answer_loss, batch_readout_gradients,
                       capture_residuals, enable_lora, load_stack, prepare_inputs,
                       reset_adapter, restore_adapter, save_adapter)
from .smoke import save_json, gpu_memory


def evaluate(model, prepared, batch_size, layers=(), direction=None, layer=None, rho=1.0):
    records, activations = [], {key: [] for key in layers}
    with torch.no_grad():
        for offset in range(0, len(prepared), batch_size):
            batch = prepared[offset:offset + batch_size]
            trace = []
            context = residual_patch(model, layer, rho * direction, trace) if direction is not None else nullcontext()
            with context, capture_residuals(model, layers) as captured:
                risky, safe, norm = answer_logits(model, batch)
            margins = (risky - safe).cpu()
            mass = ((risky - norm).exp() + (safe - norm).exp()).cpu()
            for j in range(len(batch)):
                displacement = {}
                if trace:
                    displacement = {k: v for k, v in trace[0].items()
                                    if k not in ('actual_norms_per_prompt', 'baseline_residual_norms_per_prompt')}
                    displacement['actual_norm'] = trace[0]['actual_norms_per_prompt'][j]
                    displacement['baseline_residual_norm'] = trace[0]['baseline_residual_norms_per_prompt'][j]
                records.append({'margin': float(margins[j]), 'p_risky': float(margins[j].sigmoid()),
                                'answer_mass': float(mass[j]), **displacement})
            for key in layers:
                activations[key].append(captured[key])
    return records, {k: torch.cat(v) for k, v in activations.items()}


def probe_direction(hidden, labels):
    """L2 logistic reward-magnitude probe, standardized fit -> raw residual w/s."""
    x = hidden.double().numpy()
    mean, scale = x.mean(0), x.std(0).clip(1e-6)
    standardized = (x - mean) / scale
    target = np.asarray(labels)
    def objective(theta):
        w, b = theta[:-1], theta[-1]
        logits = standardized @ w + b
        probability = 1 / (1 + np.exp(-np.clip(logits, -50, 50)))
        loss = np.mean(np.logaddexp(0, logits) - target * logits) + .05 * (w @ w)
        residual = (probability - target) / len(target)
        gradient = np.r_[standardized.T @ residual + .1 * w, residual.sum()]
        return loss, gradient
    result = minimize(objective, np.zeros(x.shape[1] + 1), jac=True, method='L-BFGS-B')
    if not result.success:
        raise RuntimeError('Reward probe optimizer did not converge')
    raw = torch.from_numpy(result.x[:-1] / scale).float()
    return unit(raw), {'intercept': float(result.x[-1]), 'standardized_weight': result.x[:-1].tolist(),
                       'scaler_mean': mean.tolist(), 'scaler_scale': scale.tolist(),
                       'labels': 'absolute lottery reward / stake >= 2.1; otherwise lower reward',
                       'definition': 'provisional reward-magnitude probe fitted on discovery residuals',
                       'raw_mapping': 'w / scaler_scale', 'converged': bool(result.success)}


def train_agent(model, config, prepared, rows, name, output, args, deadline):
    reset_adapter(model)
    train_indices = [i for i, r in enumerate(rows) if r['split'] in ('discovery', 'selection')]
    # Both permitted training splits are used. Best checkpoint is chosen on
    # training loss at a fixed cadence, never on frozen model responses.
    targets = probabilities(rows, AGENTS[name])
    rng = np.random.default_rng(170 + list(AGENTS).index(name))
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.learning_rate, weight_decay=.01)
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    checkpoint = output / 'adapters' / name
    history, best = [], float('inf')
    # Deterministic balanced audit subset of TRAINING rows, not a validation set.
    audit = train_indices[::max(1, len(train_indices) // 48)]
    completed_steps = 0
    for step in range(args.steps):
        if time.monotonic() > deadline - args.reserve_seconds:
            break
        model.train()
        optimizer.zero_grad(set_to_none=True)
        indices = rng.choice(train_indices, size=args.train_batch, replace=False).tolist()
        loss = batched_answer_loss(model, [prepared[i] for i in indices], targets[indices])
        if not torch.isfinite(loss):
            raise RuntimeError('Nonfinite LoRA training loss')
        loss.backward()
        trainable = [p for p in model.parameters() if p.requires_grad]
        if step == 0:
            if not any(p.grad is not None and p.grad.norm() > 0 for p in trainable):
                raise RuntimeError('LoRA received no gradient')
            if any(p.grad is not None for n, p in model.named_parameters() if 'lora_' not in n):
                raise RuntimeError('Frozen base model received a parameter gradient')
        # clip_grad_norm groups parameters by device internally.
        grad_norm = float(torch.nn.utils.clip_grad_norm_(trainable, 1.0))
        optimizer.step()
        completed_steps = step + 1
        history.append({'step': step + 1, 'loss': float(loss.detach()), 'gradient_norm': grad_norm})
        if step == 0 or (step + 1) % args.checkpoint_every == 0 or step + 1 == args.steps:
            model.eval()
            with torch.no_grad():
                audit_loss = sum(float(batched_answer_loss(model, [prepared[i] for i in audit[j:j + args.batch_size]],
                                                           targets[audit[j:j + args.batch_size]])) * len(audit[j:j + args.batch_size])
                                 for j in range(0, len(audit), args.batch_size)) / len(audit)
            history[-1]['training_audit_loss'] = audit_loss
            if audit_loss < best:
                save_adapter(model, config, checkpoint)
                best = audit_loss
            save_json(output / f'training_{name}.json', {'history': history, 'best_training_audit_loss': best,
                       'target': asdict(AGENTS[name]), 'training_rows': len(train_indices),
                       'loss': 'expected full-vocabulary answer-token cross entropy',
                       'frozen_rows_seen_by_training': 0, 'completed_steps': completed_steps})
            print(f'{name} step {step + 1}/{args.steps}; training audit CE={audit_loss:.5f}', flush=True)
    del optimizer
    if completed_steps == 0:
        raise TimeoutError('No remaining training window')
    restore_adapter(model, checkpoint)
    model.eval().requires_grad_(False)
    model.gradient_checkpointing_disable()
    return {'completed_steps': completed_steps, 'requested_steps': args.steps,
            'best_training_audit_loss': best, 'stopped_early_for_time': completed_steps < args.steps}


def footprint(encoder, decoder, base, adapted, ks):
    delta = adapted - base
    mean_delta = delta.mean(0)
    norms = decoder.norm(dim=0).clamp_min(1e-12)
    projection = (delta @ decoder) / norms
    enc_w, enc_b = encoder
    dz = torch.relu(adapted @ enc_w.T + enc_b) - torch.relu(base @ enc_w.T + enc_b)
    # Rank by mean signed geometric footprint magnitude. Fit selected atoms
    # jointly to mean delta, accounting for correlated decoder columns.
    ranking = projection.mean(0).abs().argsort(descending=True)
    native = {}
    for k in ks:
        indices = ranking[:k].tolist()
        selected = decoder[:, indices]
        coefficients = torch.linalg.lstsq(selected, mean_delta).solution
        decoded = selected @ coefficients
        native[k] = (unit(decoded), {'indices': indices, 'coefficients': coefficients.tolist(),
                    'relative_error': float((mean_delta - decoded).norm() / mean_delta.norm()),
                    'decoded_norm': float(decoded.norm()),
                    'coefficient_constraint': 'signed decoder perturbation; no latent nonnegativity claim'})
    return unit(mean_delta), native, {
        'mean_delta_norm': float(mean_delta.norm()), 'mean_per_prompt_delta_norm': float(delta.norm(dim=1).mean()),
        'top_projection_features': [{'feature': int(i), 'mean_unit_decoder_projection': float(projection[:, i].mean()),
                                    'mean_encoder_change': float(dz[:, i].mean()),
                                    'mean_absolute_encoder_change': float(dz[:, i].abs().mean())} for i in ranking[:50]],
        'native': {str(k): v[1] for k, v in native.items()}}, delta


def run(args):
    torch.set_num_threads(min(8, torch.get_num_threads()))
    args.output.mkdir(parents=True, exist_ok=False)
    rows = json.loads((args.design / 'rows.json').read_text())
    manifest = json.loads((args.design / 'manifest.json').read_text())
    if digest(rows) != manifest['rows_sha256']:
        raise RuntimeError('Frozen design hash mismatch')
    if args.fixture:
        # Tiny subset retains each split/frame/order; software fixture only.
        rows = [r for r in rows if r['probability'] == .5 and r['stake'] == 25 and r['ratio'] in (.4, .65, 1.15)]
    start = time.monotonic()
    deadline = start + args.max_seconds
    report = {'status': 'started', 'fixture': args.fixture, 'scientific_go_pivot': None,
              'design_sha256': manifest['rows_sha256'], 'runtime_rows_sha256': digest(rows),
              'model_revision': MODEL_REVISION, 'sae_revision': SAE_REVISION,
              'layers_are': 'zero-based block output', 'token_scope': 'final prompt token only',
              'arguments': {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()},
              'hypotheses': {'readout': 'action negative control', 'lora': 'preference positive control'},
              'scientific_scope': 'provisional diagnostic pilot; hypotheses are not automatic classifications'}
    report['source_sha256'] = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}
    report['versions'] = {name: importlib.metadata.version(name) for name in ('torch', 'transformers', 'accelerate', 'peft', 'scipy')}
    save_json(args.output / 'report.json', report)
    save_json(args.output / 'rows.json', rows)
    directions, metadata, scores = {}, {}, {}
    try:
        model, tokenizer, decoder, encoder, layers, features = load_stack(args.fixture, args.hf_token_name)
        prepared = prepare_inputs(model, tokenizer, rows)
        discovery = [i for i, r in enumerate(rows) if r['split'] == 'discovery']
        selection = [i for i, r in enumerate(rows) if r['split'] == 'selection']
        frozen = [i for i, r in enumerate(rows) if r['split'] == 'frozen']
        development = discovery + selection
        dev_inputs = [prepared[i] for i in development]
        disc_inputs = [prepared[i] for i in discovery]
        print('Collecting development baseline and layer residuals', flush=True)
        baseline_dev, hidden_dev = evaluate(model, dev_inputs, args.batch_size, layers)
        disc_hidden = {l: h[:len(discovery)] for l, h in hidden_dev.items()}
        # Verify batched padding, zero-dose, and explicit-partition backward path.
        single, _ = evaluate(model, disc_inputs[:1], 1)
        batch, _ = evaluate(model, disc_inputs[:args.batch_size], args.batch_size)
        gap = abs(single[0]['margin'] - batch[0]['margin'])
        report['batch_single_margin_gap'] = gap
        report['batch_single_diagnostic'] = {'single': single[0], 'batched': batch[0],
            'probability_gap': abs(single[0]['p_risky'] - batch[0]['p_risky']),
            'note': 'bf16 batch kernels can round differently; all interventions and gradients use the same batching. CPU fp32 padding invariance is tested separately.'}
        if args.fixture and gap > 1e-5:
            raise RuntimeError('CPU padding invariance failed')
        zero, _ = evaluate(model, disc_inputs[:args.batch_size], args.batch_size,
                            direction=torch.zeros(decoder.shape[0]), layer=layers[-1])
        report['zero_dose_exact_batch_identity'] = all(a['margin'] == b['margin'] for a, b in zip(zero, batch))
        if not report['zero_dose_exact_batch_identity']:
            raise RuntimeError('Zero-dose identity failed on the actual batch')
        for layer in layers:
            print(f'Computing batched discovery gradients at layer {layer}', flush=True)
            grads = torch.cat([batch_readout_gradients(model, disc_inputs[j:j + args.batch_size], layer)
                               for j in range(0, len(disc_inputs), args.batch_size)])
            gradient = grads.mean(0)
            directions[f'gradient_l{layer}'] = (layer, unit(gradient))
            metadata[f'gradient_l{layer}'] = {'raw_mean_norm': float(gradient.norm()),
                'per_prompt_norms': [float(g.norm()) for g in grads],
                'cosines_with_mean': [float(unit(g) @ unit(gradient)) for g in grads],
                'split': 'discovery', 'n': len(grads)}
            print(f'Fitting the reward probe at layer {layer}', flush=True)
            labels = [rows[i]['ratio'] >= 2.1 for i in discovery]
            if len(set(labels)) < 2 and args.fixture:
                labels = [j % 2 for j in range(len(discovery))]
            probe, info = probe_direction(disc_hidden[layer], labels)
            directions[f'reward_probe_l{layer}'] = (layer, probe)
            metadata[f'reward_probe_l{layer}'] = info
            for seed in range(args.random_directions):
                generator = torch.Generator().manual_seed(101 + seed)
                directions[f'random_{seed}_l{layer}'] = (layer, unit(torch.randn(decoder.shape[0], generator=generator)))
        sae_layer = layers[-1]
        gradient = directions[f'gradient_l{sae_layer}'][1]
        cosines = decoder.T @ gradient / decoder.norm(dim=0).clamp_min(1e-12)
        for feature in features:
            directions[f'feature_{feature}'] = (sae_layer, unit(decoder[:, feature]))
            metadata[f'feature_{feature}'] = {'cosine_readout': float(cosines[feature]),
                                             'decoder_norm': float(decoder[:, feature].norm())}
        directions['creativity_triple'] = (sae_layer, unit(decoder[:, features[-3:]].sum(1)))
        highest = int(cosines.argmax())
        directions['sae_readout_highest_cosine'] = (sae_layer, unit(decoder[:, highest]))
        metadata['sae_readout_highest_cosine'] = {'feature': highest, 'cosine_readout': float(cosines[highest])}
        for k in args.sparse_k:
            reconstruction, indices, coef, error = sparse_match(decoder, gradient, k)
            name = f'sae_readout_k{k}'
            directions[name] = (sae_layer, unit(reconstruction))
            metadata[name] = {'indices': indices, 'coefficients': coef.tolist(), 'relative_error': error,
                              'decoded_norm': float(reconstruction.norm()), 'signed_coefficients': True}
        persona_inputs = {}
        persona_hidden = {}
        for persona in ('risk_averse', 'risk_seeking'):
            altered = [{**r, 'text': render(r, persona)} for r in rows]
            persona_inputs[persona] = prepare_inputs(model, tokenizer, altered)
            _, captured = evaluate(model, [persona_inputs[persona][i] for i in discovery], args.batch_size, layers)
            persona_hidden[persona] = captured
        for layer in layers:
            direction = unit((persona_hidden['risk_seeking'][layer] - persona_hidden['risk_averse'][layer]).mean(0))
            directions[f'persona_contrast_l{layer}'] = (layer, direction)
        # Common rho chosen using selection-only answer-format and realized norm
        # diagnostics, not CPT shifts or frozen preference responses.
        calibration = []
        for rho in args.rho_grid:
            checks = []
            for layer in layers:
                for sign in (-1, 1):
                    output, _ = evaluate(model, [prepared[i] for i in selection], args.batch_size,
                                          direction=sign * directions[f'gradient_l{layer}'][1], layer=layer, rho=rho)
                    checks.extend(output)
            valid = all(r['answer_mass'] >= args.min_answer_mass and abs(r['actual_norm'] - rho) / rho < .02 for r in checks)
            calibration.append({'rho': rho, 'valid': valid, 'min_answer_mass': min(r['answer_mass'] for r in checks),
                'max_relative_norm_error': max(abs(r['actual_norm'] - rho) / rho for r in checks),
                'answer_mass_failure_count': sum(r['answer_mass'] < args.min_answer_mass for r in checks),
                'norm_failure_count': sum(abs(r['actual_norm'] - rho) / rho >= .02 for r in checks)})
        valid_rhos = [r['rho'] for r in calibration if r['valid']]
        rho = min(valid_rhos or args.rho_grid, key=lambda r: abs(np.log(r)))
        report['dose_calibration'] = calibration
        report['selected_common_rho'] = rho
        report['dose_calibration_passed'] = bool(valid_rhos)
        report['dose_interpretation'] = ('Engineering calibration passed' if valid_rhos else
            'Calibration failed. Continue only as exploratory diagnostics at prespecified rho nearest 1; do not claim validated answer-format retention or norm precision.')
        print(json.dumps({'dose_calibration': calibration, 'selected_rho': rho, 'passed': bool(valid_rhos)}), flush=True)
        save_json(args.output / 'calibration.json', {k: report[k] for k in ('dose_calibration', 'selected_common_rho', 'dose_calibration_passed', 'dose_interpretation', 'batch_single_diagnostic')})
        torch.save({'prompt_ids': [rows[i]['id'] for i in discovery], 'hidden': disc_hidden}, args.output / 'base_residuals.pt')
        torch.save({name: {'layer': layer, 'vector': vector} for name, (layer, vector) in directions.items()}, args.output / 'development_directions.pt')
        # Reselect only among the stated candidate feature set in this pilot.
        # Rank causal curvature shifts across the entire discovery reward grid;
        # never rank by gradient dot products. Both signs are prespecified.
        base_fit = fit([rows[i] for i in discovery], [r['p_risky'] for r in baseline_dev[:len(discovery)]], starts=3)
        candidate_ranking = []
        for feature in features:
            for sign in (-1, 1):
                output, _ = evaluate(model, disc_inputs, args.batch_size,
                                      direction=sign * directions[f'feature_{feature}'][1], layer=sae_layer, rho=rho)
                fitted = fit([rows[i] for i in discovery], [r['p_risky'] for r in output], starts=3)
                shift = fitted['parameters']['curvature'] - base_fit['parameters']['curvature']
                candidate_ranking.append({'feature': feature, 'sign': sign, 'curvature_shift': shift,
                    'absolute_curvature_shift': abs(shift), 'fit': fitted, 'cosine_readout': float(cosines[feature]),
                    'switches': switches([rows[i] for i in discovery], [r['p_risky'] for r in output])})
        candidate_ranking.sort(key=lambda r: r['absolute_curvature_shift'], reverse=True)
        report['candidate_selection'] = candidate_ranking
        report['candidate_selection_caveat'] = 'Exploratory ranking within six prespecified candidates; boundary or poor CPT fits invalidate a preference interpretation.'
        first_lora = 1 if args.fixture else 40
        config = add_lora(model, first_lora, sae_layer, rank=args.rank)
        report['adapter_layers'] = list(range(first_lora, sae_layer + 1))
        report['trainable_parameters'] = sum(p.numel() for p in model.parameters() if p.requires_grad)
        report['training'] = {}
        footprints = {}
        for agent in args.agents:
            print(f'Training planted agent {agent}', flush=True)
            report['training'][agent] = train_agent(model, config, prepared, rows, agent, args.output, args, deadline)
            _, hidden_adapted = evaluate(model, disc_inputs, args.batch_size, [sae_layer])
            raw, native, info, delta = footprint(encoder, decoder, disc_hidden[sae_layer], hidden_adapted[sae_layer], args.sparse_k)
            directions[f'{agent}_mean_delta'] = (sae_layer, raw)
            for k, (vector, _) in native.items():
                directions[f'{agent}_sae_preference_k{k}'] = (sae_layer, vector)
            footprints[agent] = info
            torch.save({'economic_prompt_ids': [rows[i]['id'] for i in discovery],
                        'delta_h': delta}, args.output / f'footprint_{agent}.pt')
        enable_lora(model, False)
        model.eval()
        for name, (layer, vector) in directions.items():
            metadata.setdefault(name, {})['layer'] = layer
            metadata[name]['cosine_readout'] = float(vector @ directions[f'gradient_l{layer}'][1])
            metadata[name]['cosine_persona'] = float(vector @ directions[f'persona_contrast_l{layer}'][1])
        report['footprints'] = footprints
        report['directions'] = metadata
        report['status'] = 'selection_locked_before_frozen_evaluation'
        save_json(args.output / 'selection_lock.json', report)
        torch.save({name: {'layer': layer, 'vector': vector} for name, (layer, vector) in directions.items()},
                   args.output / 'directions.pt')
        torch.save({'prompt_ids': [rows[i]['id'] for i in discovery], 'hidden': disc_hidden}, args.output / 'base_residuals.pt')
        print('Selection locked; evaluating all conditions on the frozen grid', flush=True)
        baseline, _ = evaluate(model, prepared, args.batch_size)
        scores['baseline'] = baseline
        save_json(args.output / 'scores_baseline.json', baseline)
        # Collect the actual positive anchors first, so a bounded session
        # cannot finish with only surrogate-vector results and no LoRA readout.
        for agent in args.agents:
            enable_lora(model, True)
            restore_adapter(model, args.output / 'adapters' / agent)
            model.eval().requires_grad_(False)
            scores['lora_' + agent], _ = evaluate(model, prepared, args.batch_size)
            save_json(args.output / f'scores_lora_{agent}.json', scores['lora_' + agent])
        enable_lora(model, False)
        conditions = [(name, layer, sign * vector, sign) for name, (layer, vector) in directions.items() for sign in (-1, 1)]
        for index, (name, layer, vector, sign) in enumerate(conditions):
            if time.monotonic() > deadline - 60:
                raise TimeoutError('Pilot time limit reached during evaluation; partial artifacts preserved')
            key = f'{name}_sign{sign:+d}'
            print(f'Evaluating {index + 1}/{len(conditions)}: {key}', flush=True)
            scores[key], _ = evaluate(model, prepared, args.batch_size, direction=vector, layer=layer, rho=rho)
            save_json(args.output / f'scores_{key}.json', scores[key])
        for persona, inputs in persona_inputs.items():
            scores['prompt_' + persona], _ = evaluate(model, inputs, args.batch_size)
            save_json(args.output / f'scores_prompt_{persona}.json', scores['prompt_' + persona])
        enable_lora(model, False)
        report['status'] = 'gpu_execution_complete_analysis_pending'
        report['condition_count'] = len(scores)
    except Exception as error:
        report['status'] = 'failed_or_partial'
        report['error_type'] = type(error).__name__
        raise
    finally:
        report['elapsed_seconds'] = time.monotonic() - start
        report['gpu_memory'] = gpu_memory()
        save_json(args.output / 'report.json', report)
    print(json.dumps({'status': report['status'], 'output': str(args.output)}), flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--design', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--fixture', action='store_true')
    p.add_argument('--hf-token-name')
    p.add_argument('--steps', type=int, default=200)
    p.add_argument('--train-batch', type=int, default=8)
    p.add_argument('--batch-size', type=int, default=8)
    p.add_argument('--learning-rate', type=float, default=0.0002)
    p.add_argument('--rank', type=int, default=8)
    p.add_argument('--checkpoint-every', type=int, default=50)
    p.add_argument('--agents', nargs='+', choices=list(AGENTS), default=list(AGENTS))
    p.add_argument('--random-directions', type=int, default=3)
    p.add_argument('--sparse-k', nargs='+', type=int, default=[1, 3, 10])
    p.add_argument('--rho-grid', nargs='+', type=float, default=[.25, 1., 4.])
    p.add_argument('--min-answer-mass', type=float, default=.95)
    p.add_argument('--max-seconds', type=int, default=6000)
    p.add_argument('--reserve-seconds', type=int, default=2400)
    args = p.parse_args()
    if args.train_batch < 1 or args.steps < 1 or min(args.rho_grid) <= 0 or args.batch_size < 1:
        p.error('Batch sizes, steps, and doses must be positive')
    run(args)


if __name__ == '__main__':
    main()
