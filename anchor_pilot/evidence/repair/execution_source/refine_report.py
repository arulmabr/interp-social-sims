"""CPU report for the separately frozen combined-anchor refinement."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from .analysis import condition_summary
from .smoke import save_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--bootstrap',type=int,default=100)
    args=p.parse_args()
    rows=json.loads((args.run/'rows.json').read_text())
    report=json.loads((args.run/'report.json').read_text())
    baseline=json.loads((args.run/'scores_baseline.json').read_text())
    results={}
    table=[]
    for path in sorted(args.run.glob('scores_*.json')):
        name=path.stem.removeprefix('scores_')
        if name=='old_grid_development':
            continue
        records=json.loads(path.read_text())
        if len(records)!=len(rows):
            raise RuntimeError('Fresh-grid score count mismatch')
        print('Analyzing refinement '+name,flush=True)
        result=condition_summary(rows,records,baseline,planted=report['target'],
                                  bootstrap=args.bootstrap if name.startswith('lora_') else 0)
        results[name]=result
        table.append({'condition':name,**result['frozen']['parameters'],
                      'planted_probability_rmse':result['planted_recovery']['frozen_probability_rmse'],
                      'fit_rmse':result['frozen']['probability_rmse'],
                      'min_answer_mass':result['min_answer_mass'],
                      'mean_answer_mass':result['mean_answer_mass'],
                      'answer_mass_below_0_95_count':result['answer_mass_below_0_95_count'],
                      'max_relative_norm_error':result.get('displacement',{}).get('max_relative_norm_error'),
                      'label_order_gap':result['label_order_mean_absolute_probability_gap'],
                      'full_vocab_excess_ce':result['planted_recovery']['full_vocabulary_excess_cross_entropy']})
        save_json(args.run/'analysis.json',results)
    with (args.run/'comparison.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
    truth=report['target']
    label_path=Path(__file__).resolve().parents[1]/'SAE/data/raw/feature_labels/goodfire_llama33_70b_l50_feature_labels_filtered.csv'
    labels={}
    if label_path.exists():
        with label_path.open() as handle:
            labels={int(r['index_in_sae']):r['label'] for r in csv.DictReader(handle)}
    labeled=[{**entry,'label':labels.get(entry['feature'])}
             for entry in report['footprint']['top_projection_features']]
    save_json(args.run/'labeled_footprint.json',labeled)
    targeted=read_targeted(args.run, report, labels)
    lines=['# Combined-anchor refinement','',
        'The first pilot did not recover its planted parameters closely. This follow-up retains that result and evaluates a bounded 600-update refinement on 300 new prompts. Original frozen prompts were not added to training.','',
        f"Planted curvature **{truth['curvature']}**, weighting **{truth['weighting']}**, loss aversion **{truth['loss_aversion']}**, inverse temperature **{truth['inverse_temperature']}**, A-label bias **0**.",'',
        '| Condition | Curvature | Weighting | Loss aversion | Planted-choice RMSE | Min A/B mass |',
        '|---|---:|---:|---:|---:|---:|']
    for row in table:
        lines.append('| '+row['condition']+' | '+' | '.join(f'{row[k]:.4f}' for k in
                      ('curvature','weighting','loss_aversion','planted_probability_rmse','min_answer_mass'))+' |')
    lines.extend(['','## Refined footprint','',
        f"Mean residual-shift norm: {report['footprint']['mean_delta_norm']:.4f}. Ten-feature relative reconstruction error: {report['footprint']['native']['10']['relative_error']:.4f}.",'',
        '| Feature | Cached label | Mean decoder projection | Mean encoder change |',
        '|---|---|---:|---:|'])
    for entry in labeled[:10]:
        label=(entry['label'] or 'Unavailable').replace('|',' / ')
        lines.append(f"| {entry['feature']} | {label} | {entry['mean_unit_decoder_projection']:.4f} | {entry['mean_encoder_change']:.4f} |")
    lines.extend(['','## Limits','',
        '- Original and refined adapters are compared on the SAME fresh grid. Original first-pass results on the earlier grid remain unchanged.',
        '- Checkpoints use training-audit loss only. Fresh evaluation reward ratios and synthetic recovery checks were fixed before the refinement ran.',
        '- Scenario bootstrap intervals are in analysis.json; these are not repeated independent model training runs.',
        '- Common-norm and original-magnitude replays are separate controls. Even original-magnitude replay changes one position at one layer; the full adapter changes several layers and all prompt positions.',
        '- Sparse failure while raw replay also fails cannot isolate an SAE dictionary limitation.',
        '- New reward levels test numerical generalization within the same prompt template, stakes, probabilities, and reference point; other task families remain untested.',
        '- Cached feature labels are interpretation aids, not behavioral ground truth.',
        '- Feature 47380 matches the cached option-selection label text; its identity with the historical Fig. 3 feature is not independently established. See ../TARGETED_FOOTPRINTS.md.',
        '- The external scientific go/pivot rule remains unavailable. No automatic confirmatory pass is assigned.',''])
    (args.run/'REPORT.md').write_text('\n'.join(lines))
    save_json(args.run/'analysis_status.json',{'status':'analysis_complete','conditions':len(table),
        'feature_labels_sha256':hashlib.sha256(label_path.read_bytes()).hexdigest() if label_path.exists() else None,
        'scientific_go_pivot':None,'analysis_source_sha256':{name:hashlib.sha256((Path(__file__).parent/name).read_bytes()).hexdigest() for name in ('analysis.py','cpt.py','refine_report.py')}})


def read_targeted(run, report, labels):
    source=run.parent/'targeted_footprints.json'
    raw=json.loads(source.read_text())
    agents={**raw['agents'],'combined_refined':report['footprint']['nominated_features']}
    rows=[]
    for agent, entries in agents.items():
        for entry in entries:
            rows.append({'agent':agent,'feature':entry['feature'],'label':labels.get(entry['feature']),
                         'cosine_readout':raw['cosine_with_original_readout'][str(entry['feature'])],**entry})
    with (run.parent/'targeted_feature_comparison.csv').open('w') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    lines=['# Nominated feature footprints','',raw['scope'],'',raw['historical_identity_caveat'],'',
        'Projection measures the residual shift along a unit decoder column. Encoder change can be zero when the ReLU threshold hides a shift. Neither quantity alone proves preference semantics.','',
        '| Agent | Feature | Cached label | Mean projection | Mean encoder change |',
        '|---|---:|---|---:|---:|']
    for row in rows:
        label=(row['label'] or 'Unavailable').replace('|',' / ')
        lines.append(f"| {row['agent']} | {row['feature']} | {label} | {row['mean_unit_decoder_projection']:.4f} | {row['mean_encoder_change']:.4f} |")
    (run.parent/'TARGETED_FOOTPRINTS.md').write_text('\n'.join(lines)+'\n')
    return rows


if __name__=='__main__':
    main()
