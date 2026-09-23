"""Analyze saved scores on CPU after paid GPUs stop."""
import argparse
import csv
from dataclasses import asdict
import json
from pathlib import Path

from .analysis import condition_summary
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
        planted = asdict(AGENTS[name.removeprefix('lora_')]) if name.startswith('lora_') else None
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
              'scientific_go_pivot': None, 'fixture': manifest['fixture']})
    print(f'Wrote {args.run / "REPORT.md"}', flush=True)


if __name__ == '__main__':
    main()
