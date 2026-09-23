"""Analyze saved scores on CPU after paid GPUs stop."""
import argparse
import csv
from dataclasses import asdict
import hashlib
import json
import numpy as np
import torch
from pathlib import Path

from .analysis import condition_summary, cross_entropy
from .cpt import probabilities
from .design import AGENTS
from .smoke import save_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, required=True)
    parser.add_argument('--bootstrap', type=int, default=100)
    parser.add_argument('--feature-labels', type=Path, default=Path(__file__).resolve().parents[1] / 'SAE/data/raw/feature_labels/goodfire_llama33_70b_l50_feature_labels_filtered.csv')
    args = parser.parse_args()
    rows = json.loads((args.run / 'rows.json').read_text())
    manifest = json.loads((args.run / 'report.json').read_text())
    labels = {}
    if args.feature_labels.exists() and not manifest['fixture']:
        with args.feature_labels.open() as handle:
            labels = {int(r['index_in_sae']): r['label'] for r in csv.DictReader(handle)}
    footprint_labels = {}
    for agent, info in manifest.get('footprints', {}).items():
        footprint_labels[agent] = [{**entry, 'label': labels.get(entry['feature']),
                                   'label_source': str(args.feature_labels) if entry['feature'] in labels else None}
                                  for entry in info['top_projection_features']]
    save_json(args.run / 'labeled_footprints.json', footprint_labels)
    baseline = json.loads((args.run / 'scores_baseline.json').read_text())
    summaries, table = {}, []
    for file in sorted(args.run.glob('scores_*.json')):
        name = file.stem.removeprefix('scores_')
        records = json.loads(file.read_text())
        if len(records) != len(rows):
            raise RuntimeError(f'Incomplete condition: {name}')
        planted_name = name.removeprefix('lora_') if name.startswith('lora_') else next(
            (agent for agent in AGENTS if name.startswith(agent + '_') and name.endswith(('_sign+1', '_fitted_magnitude'))), None)
        planted = asdict(AGENTS[planted_name]) if planted_name else None
        # Bootstrap the expensive anchor and baseline estimates first. All rows
        # remain available for an expanded post-pilot bootstrap without GPUs.
        boot = args.bootstrap if (name == 'baseline' or name.startswith(('lora_', 'gradient_'))) else 0
        print(f'Analyzing {name}', flush=True)
        result = condition_summary(rows, records, baseline, bootstrap=boot, planted=planted)
        summaries[name] = result
        frozen = result.get('frozen', {})
        metadata_name = name.rsplit('_sign', 1)[0]
        meta = manifest.get('directions', {}).get(metadata_name, {})
        table.append({'condition': name, **frozen.get('parameters', {}),
            'fit_rmse': frozen.get('probability_rmse'), 'converged': frozen.get('converged'),
            'boundary_parameters': ','.join(frozen.get('boundary_parameters', [])),
            'label_gap': result['label_order_mean_absolute_probability_gap'],
            'min_answer_mass': result['min_answer_mass'], 'layer': meta.get('layer'),
            'answer_mass_below_0_95_count': result['answer_mass_below_0_95_count'],
            'max_relative_norm_error': result.get('displacement', {}).get('max_relative_norm_error'),
            'requested_norm': meta.get('requested_norm', manifest.get('selected_common_rho')) if meta else None,
            'scale_family': meta.get('scale_family', 'common_norm') if meta else None,
            'cosine_readout': meta.get('cosine_readout'), 'cosine_persona': meta.get('cosine_persona'),
            'planted_probability_rmse': result.get('planted_recovery', {}).get('frozen_probability_rmse'),
            'cpt_predictive_rmse': result.get('frozen_predictive_comparison', {}).get('cpt_rmse'),
            'action_predictive_rmse': result.get('frozen_predictive_comparison', {}).get('action_offset_rmse')})
        save_json(args.run / 'analysis.json', summaries)
    with (args.run / 'comparison.csv').open('w') as f:
        writer = csv.DictWriter(f, fieldnames=list(table[0]))
        writer.writeheader()
        writer.writerows(table)
    lines = ['# Provisional action–preference anchor pilot', '',
        '**Random CPU fixture; not scientific evidence.**' if manifest['fixture'] else '**Real bf16 model diagnostic run.**', '',
        f"Recorded {len(table)} conditions across {len(rows)} prompts. GPU execution status: `{manifest['status']}`.", '',
        'Scientific go/pivot remains **unset**: the full decision rule was not supplied. Raw-gradient and LoRA labels describe intended control roles, not demonstrated classifications.', '',
        '**Dose calibration failed; steering comparisons are exploratory at the provisional norm.**' if not manifest.get('dose_calibration_passed', True) else 'Engineering dose calibration passed.', '',
        '## Frozen-split parameter recovery', '',
        '| Condition | Curvature | Weighting | Loss aversion | Inverse temperature | A-label bias | CPT fit RMSE |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for row in table:
        if row['condition'] == 'baseline' or row['condition'].startswith(('lora_', 'gradient_')):
            lines.append('| ' + row['condition'] + ' | ' + ' | '.join(f'{row[k]:.4f}' for k in
                         ('curvature','weighting','loss_aversion','inverse_temperature','label_bias','fit_rmse')) + ' |')
    lines.extend(['', '## Training diagnostics', '',
                  '| Agent | Best training-audit CE | Target entropy floor | Excess CE |',
                  '|---|---:|---:|---:|'])
    train_indices = [i for i, r in enumerate(rows) if r['split'] != 'frozen']
    audit = train_indices[::max(1, len(train_indices) // 48)]
    training = {}
    for name, agent in AGENTS.items():
        path = args.run / f'training_{name}.json'
        if not path.exists():
            continue
        result = json.loads(path.read_text())
        p = probabilities([rows[i] for i in audit], agent)
        floor = cross_entropy(p, p)
        ce = result['best_training_audit_loss']
        training[name] = {'audit_loss': ce, 'entropy_floor': floor, 'excess_cross_entropy': ce - floor,
                          'completed_steps': result['completed_steps']}
        lines.append(f'| {name} | {ce:.4f} | {floor:.4f} | {ce - floor:.4f} |')
    save_json(args.run / 'training_diagnostics.json', training)
    lines.extend(['', '## Preference anchor versus residual replay', '',
        'Frozen conditional-choice RMSE against each planted agent; lower is better. This is diagnostic, not a pass threshold. Consult answer mass before interpreting conditional probabilities.', '',
        '| Agent | Base model | Full LoRA | Raw mean delta | SAE k=1 | SAE k=3 | SAE k=10 |',
        '|---|---:|---:|---:|---:|---:|---:|'])
    frozen_indices = [i for i, r in enumerate(rows) if r['split'] == 'frozen']
    for agent, parameters in AGENTS.items():
        target = probabilities([rows[i] for i in frozen_indices], parameters)
        base_rmse = float(np.sqrt(np.mean((np.array([baseline[i]['p_risky'] for i in frozen_indices]) - target)**2)))
        names = ['lora_' + agent, agent + '_mean_delta_sign+1',
                 *[agent + f'_sae_preference_k{k}_sign+1' for k in (1, 3, 10)]]
        values = [summaries.get(name, {}).get('planted_recovery', {}).get('frozen_probability_rmse') for name in names]
        lines.append(f'| {agent} | {base_rmse:.4f} | ' + ' | '.join(f'{v:.4f}' if v is not None else '—' for v in values) + ' |')
    lines.extend(['', '## Sparse footprint reconstruction', '',
                  '| Agent | Mean delta norm | Relative error k=1 | Relative error k=3 | Relative error k=10 |',
                  '|---|---:|---:|---:|---:|'])
    for agent, info in manifest.get('footprints', {}).items():
        errors = [info['native'].get(str(k), {}).get('relative_error') for k in (1, 3, 10)]
        lines.append(f"| {agent} | {info['mean_delta_norm']:.4f} | " + ' | '.join(f'{v:.4f}' if v is not None else '—' for v in errors) + ' |')
    if manifest.get('fidelity_replay'):
        lines.extend(['', '## Original-magnitude replay', '',
                      'Coefficients and norms come from discovery footprints, with no tuning to frozen outcomes. These controls deliberately use their fitted magnitudes instead of the common rho=1.', '',
                      '| Agent | Raw mean delta | SAE k=1 | SAE k=3 | SAE k=10 |',
                      '|---|---:|---:|---:|---:|'])
        for agent in AGENTS:
            names = [agent + '_mean_delta_fitted_magnitude', *[agent + f'_sae_preference_k{k}_fitted_magnitude' for k in (1, 3, 10)]]
            values = [summaries.get(name, {}).get('planted_recovery', {}).get('frozen_probability_rmse') for name in names]
            lines.append('| ' + agent + ' | ' + ' | '.join(f'{v:.4f}' if v is not None else '—' for v in values) + ' |')
    mean_deltas = {}
    for agent in AGENTS:
        path = args.run / f'footprint_{agent}.pt'
        if path.exists():
            delta = torch.load(path, map_location='cpu', weights_only=True)['delta_h'].mean(0)
            mean_deltas[agent] = delta / delta.norm()
    similarity = {}
    for first, vector in mean_deltas.items():
        similarity[first] = {}
        first_features = set(manifest['footprints'][first]['native'].get('10', {}).get('indices', []))
        for second, other in mean_deltas.items():
            second_features = set(manifest['footprints'][second]['native'].get('10', {}).get('indices', []))
            similarity[first][second] = {'mean_delta_cosine': float(vector @ other),
                'top10_overlap_count': len(first_features & second_features),
                'top10_jaccard': len(first_features & second_features) / len(first_features | second_features) if first_features | second_features else None}
    save_json(args.run / 'footprint_similarity.json', similarity)
    if similarity:
        agents = list(similarity)
        lines.extend(['', '## Similarity across the trained agents', '',
                      'Cosines between discovery mean residual shifts. Similarity can reflect common answer-format and calibration learning; these single-seed comparisons do not establish disentangled preference axes.', '',
                      '| Agent | ' + ' | '.join(agents) + ' |',
                      '|---|' + '---:|' * len(agents)])
        for first in agents:
            lines.append('| ' + first + ' | ' + ' | '.join(f"{similarity[first][second]['mean_delta_cosine']:.3f}" for second in agents) + ' |')
    lines.extend(['', '## Interpretation boundaries', '',
        '- Parameter fits at their bounds or with poor probability fit are model misspecification diagnostics, not evidence for a preference shift.',
        '- The CPT family uses shared gain/loss curvature, shared TK92 weighting, a zero reference point, and logistic choice noise. Other preference families remain untested.',
        '- The full adapter and a fixed layer-50 vector have different capacity. Compare the raw mean-delta replay with its SAE approximation before attributing failure to the dictionary.',
        '- Sparse reconstructions use signed decoder coefficients. They need not be feasible edits of nonnegative SAE encoder activations.',
        '- Three random directions per layer provide a pilot control, not a well-powered null distribution.',
        '- Bootstrap intervals resample economic scenarios together with both answer orders. They measure scenario variability, not repeated stochastic LLM sampling.',
        '- Training targets are the exact expected answer-token loss under the planted stochastic CPT agent; frozen reward levels never train or select adapters.',
        '- The reward probe is a new pilot reward-magnitude probe. Its standardized weights are mapped back to raw residual coordinates.',
        '', 'See `comparison.csv` for all conditions, `analysis.json` for fits, crossings and uncertainty, `labeled_footprints.json` for cached Goodfire labels, `selection_lock.json` for choices frozen before evaluation, and raw `scores_*.json` for reproducibility.', ''])
    (args.run / 'REPORT.md').write_text('\n'.join(lines))
    save_json(args.run / 'analysis_status.json', {'status': 'analysis_complete', 'conditions': len(table),
              'scientific_go_pivot': None, 'fixture': manifest['fixture'],
              'feature_labels_sha256': hashlib.sha256(args.feature_labels.read_bytes()).hexdigest() if args.feature_labels.exists() else None,
              'analysis_source_sha256': {name: hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest()
                                         for name in ('analysis.py', 'cpt.py', 'report.py')}})
    print(f'Wrote {args.run / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
