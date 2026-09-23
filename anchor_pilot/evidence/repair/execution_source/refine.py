"""One bounded combined-anchor refinement, with a fresh fixed evaluation grid.

The original frozen split is now explicitly development evidence after its
first inspection. It is never added to training. Fresh reward ratios include
6.5, extending beyond both the training maximum 4.5 and old test maximum 6.
"""
import argparse
from dataclasses import asdict
import datetime as dt
import hashlib
import json
from pathlib import Path
import time

import numpy as np
import torch

from .cpt import fit, identifiability, probabilities
from .design import AGENTS, build_rows, digest, render
from .modeling import (add_lora, batched_answer_loss, enable_lora, load_stack,
                       prepare_inputs, restore_adapter, save_adapter)
from .pilot import evaluate, footprint
from .smoke import save_json, gpu_memory
from .targeted_footprints import TARGETS, summarize as targeted_footprint


def prepare(destination):
    original = build_rows()
    templates = [r for r in original if r['ratio'] == .4]
    fresh = []
    ratios = [.55, 1.25, 2.3, 3.3, 6.5]
    for template in templates:
        for index, ratio in enumerate(ratios):
            row = dict(template)
            reward = round(row['stake'] * ratio, 6)
            p = row['probability']
            row.update(ratio=ratio, reward=reward, split='frozen',
                       economic_id=row['grid_id'] + f'_v2r{index:02d}')
            row['id'] = row['economic_id'] + '_' + row['risky_label']
            if row['frame'] == 'gain':
                row['risky'] = [[reward, p], [0., 1-p]]
            elif row['frame'] == 'loss':
                row['risky'] = [[-reward, p], [0., 1-p]]
            else:
                row['risky'] = [[reward, p], [-row['stake'], 1-p]]
            row['dominant_option'] = 'safe' if max(x for x,_ in row['risky']) < row['safe'][0][0] else 'risky' if min(x for x,_ in row['risky']) > row['safe'][0][0] else None
            row['text'] = render(row)
            fresh.append(row)
    assert not {r['text'] for r in fresh} & {r['text'] for r in original}
    target = AGENTS['combined']
    recovery = fit(fresh, probabilities(fresh, target))
    identification = identifiability(fresh, target)
    assert identification['rank'] == 5
    assert max(abs(recovery['parameters'][k] - v) for k, v in asdict(target).items()) < .01
    destination.mkdir(parents=True, exist_ok=False)
    save_json(destination / 'rows.json', fresh)
    save_json(destination / 'plan.json', {'declared_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'rows_sha256': digest(fresh), 'rows': len(fresh), 'new_reward_ratios': ratios,
        'target': asdict(target), 'training': 'Original discovery and selection rows only; no original frozen rows.',
        'additional_steps': 600, 'learning_rate': .00005, 'batch_size': 8,
        'checkpoint_choice': 'Lowest fixed training-audit cross entropy; no fresh evaluation before choice.',
        'original_frozen_status': 'Inspected development evidence; first-pass failure retained.',
        'purpose': 'Bounded attempt to repair combined positive anchor after first-pass parameter recovery failed.',
        'controls': 'Base, refined LoRA, raw mean delta and k=1,3,10 SAE reconstructions, at common norm 1 and original fitted magnitudes.',
        'synthetic_recovery': recovery, 'local_identifiability': identification})


def run(plan_dir):
    torch.set_num_threads(8)
    source = sorted(Path('/workspace/anchor_pilot/outputs').glob('pilot-*/selection_lock.json'))[-1].parent
    parent_report = json.loads((source / 'report.json').read_text())
    if not parent_report.get('fidelity_replay'):
        raise RuntimeError('Original comparisons and fidelity controls must finish first')
    output = source / 'refinement'
    output.mkdir(exist_ok=False)
    rows = json.loads((source / 'rows.json').read_text())
    fresh = json.loads((plan_dir / 'rows.json').read_text())
    plan = json.loads((plan_dir / 'plan.json').read_text())
    if digest(fresh) != plan['rows_sha256']:
        raise RuntimeError('Fresh evaluation grid hash mismatch')
    save_json(output / 'plan.json', plan)
    save_json(output / 'rows.json', fresh)
    provenance = {
        'started_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
        'source_sha256': {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in Path(__file__).parent.glob('*.py')},
        'model_revision': parent_report['model_revision'],
        'sae_revision': parent_report['sae_revision'],
        'versions': parent_report['versions'],
        'original_adapter_sha256': hashlib.sha256((source / 'adapters/combined/adapter.pt').read_bytes()).hexdigest(),
    }
    save_json(output / 'provenance.json', provenance)
    start = time.monotonic()
    model, tokenizer, decoder, encoder, layers, _ = load_stack(False)
    base_saved = torch.load(source / 'base_residuals.pt', map_location='cpu', weights_only=True)
    targeted = {}
    for agent in AGENTS:
        saved_delta = torch.load(source / f'footprint_{agent}.pt', map_location='cpu', weights_only=True)['delta_h']
        targeted[agent] = targeted_footprint(encoder, decoder, base_saved['hidden'][layers[-1]], saved_delta)
    saved_directions = torch.load(source / 'directions.pt', map_location='cpu', weights_only=True)
    g = saved_directions['gradient_l50']['vector']
    cosines = {str(index): float(g @ decoder[:, index] / decoder[:, index].norm()) for index in TARGETS}
    save_json(source / 'targeted_footprints.json', {'agents': targeted,
              'cosine_with_original_readout': cosines,
              'scope': 'Post-hoc descriptive measurement from saved discovery residuals; not used for direction or checkpoint selection.',
              'historical_identity_caveat': 'Feature 47380 matches the cached label text; the exact historical Fig. 3 feature identity is not independently established.'})
    prepared = prepare_inputs(model, tokenizer, rows)
    fresh_inputs = prepare_inputs(model, tokenizer, fresh)
    config = add_lora(model, 40, layers[-1], rank=8)
    restore_adapter(model, source / 'adapters/combined')
    enable_lora(model, True)
    train = [i for i,r in enumerate(rows) if r['split'] != 'frozen']
    discovery = [i for i,r in enumerate(rows) if r['split'] == 'discovery']
    audit = train[::max(1, len(train)//48)]
    target = probabilities(rows, AGENTS['combined'])
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=.00005, weight_decay=.01)
    rng = np.random.default_rng(170)
    history = []
    best = float('inf')
    checkpoint = output / 'adapter'
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    for step in range(601):
        if step:
            model.train()
            optimizer.zero_grad(set_to_none=True)
            batch = rng.choice(train, 8, replace=False).tolist()
            loss = batched_answer_loss(model, [prepared[i] for i in batch], target[batch])
            if not torch.isfinite(loss):
                raise RuntimeError('Nonfinite refinement loss')
            loss.backward()
            torch.nn.utils.clip_grad_norm_([p for p in model.parameters() if p.requires_grad], 1.)
            optimizer.step()
        if step % 100 == 0:
            model.eval()
            with torch.no_grad():
                audit_loss = sum(float(batched_answer_loss(model, [prepared[i] for i in audit[j:j+8]], target[audit[j:j+8]])) * len(audit[j:j+8])
                                 for j in range(0, len(audit), 8)) / len(audit)
            history.append({'additional_step': step, 'training_audit_loss': audit_loss})
            if audit_loss < best:
                best = audit_loss
                save_adapter(model, config, checkpoint)
            save_json(output / 'training.json', {'history': history, 'best_training_audit_loss': best})
            print(f'Combined refinement step {step}/600; training audit CE={audit_loss:.5f}', flush=True)
    del optimizer
    restore_adapter(model, checkpoint)
    model.eval().requires_grad_(False)
    model.gradient_checkpointing_disable()
    _, adapted = evaluate(model, [prepared[i] for i in discovery], 8, [layers[-1]])
    if base_saved['prompt_ids'] != [rows[i]['id'] for i in discovery]:
        raise RuntimeError('Discovery footprint alignment mismatch')
    raw, native, info, delta = footprint(encoder, decoder, base_saved['hidden'][layers[-1]], adapted[layers[-1]], [1,3,10])
    info['nominated_features'] = targeted_footprint(encoder, decoder, base_saved['hidden'][layers[-1]], delta)
    save_json(output / 'selection_lock.json', {'best_training_audit_loss': best, 'footprint': info,
              'fresh_evaluation_seen': False, 'plan': plan,
              'locked_at_utc': dt.datetime.now(dt.timezone.utc).isoformat()})
    torch.save({'delta_h': delta}, output / 'footprint.pt')
    torch.save({'mean_delta': raw, **{f'sae_k{k}': vector for k, (vector, _) in native.items()}},
               output / 'directions.pt')
    # Only now inspect any responses on the fresh grid.
    enable_lora(model, False)
    baseline, _ = evaluate(model, fresh_inputs, 8)
    save_json(output / 'scores_baseline.json', baseline)
    enable_lora(model, True)
    model.eval().requires_grad_(False)
    restore_adapter(model, source / 'adapters/combined')
    original_scores, _ = evaluate(model, fresh_inputs, 8)
    save_json(output / 'scores_lora_combined_original.json', original_scores)
    restore_adapter(model, checkpoint)
    scores, _ = evaluate(model, fresh_inputs, 8)
    save_json(output / 'scores_lora_combined_refined.json', scores)
    old_scores, _ = evaluate(model, prepared, 8)
    save_json(output / 'scores_old_grid_development.json', old_scores)
    enable_lora(model, False)
    specs = [('mean_delta', raw, info['mean_delta_norm'])]
    specs += [(f'sae_k{k}', vector, meta['decoded_norm']) for k,(vector,meta) in native.items()]
    for name, direction, magnitude in specs:
        for scale, norm in [('common_norm', 1.), ('fitted_magnitude', magnitude)]:
            print(f'Refined-anchor replay {name}/{scale}', flush=True)
            result, _ = evaluate(model, fresh_inputs, 8, direction=direction, layer=layers[-1], rho=norm)
            save_json(output / f'scores_{name}_{scale}.json', result)
    save_json(output / 'report.json', {'status': 'completed', 'rows_sha256': digest(fresh),
              'elapsed_seconds': time.monotonic()-start, 'gpu_memory': gpu_memory(),
              'best_training_audit_loss': best, 'footprint': info, 'target': plan['target'],
              'provenance': provenance, 'completed_at_utc': dt.datetime.now(dt.timezone.utc).isoformat(),
              'scientific_go_pivot': None, 'original_pilot_failure_retained': True})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare',type=Path)
    p.add_argument('--plan',type=Path,default=Path('/workspace/anchor_pilot/outputs/refinement-plan'))
    args=p.parse_args()
    prepare(args.prepare) if args.prepare else run(args.plan)


if __name__=='__main__':
    main()
