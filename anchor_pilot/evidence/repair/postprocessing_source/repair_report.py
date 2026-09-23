"""Report a bounded repair, including early failure with frozen responses unopened."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from .analysis import condition_summary
from .cpt import probabilities
from .smoke import save_json


def build_report(run, bootstrap=100):
    report=json.loads((run/'report.json').read_text())
    truth=report['plan']['target']
    lines=['# Anchor recovery and format repair','',
           f"Execution status: **{report['status']}**. Frozen model responses opened: **{report['frozen_responses_opened']}**.",'',
           'This follow-up has newly declared operational targets. The external scientific go/pivot rule remains unavailable; no scientific pass is assigned.','']
    if report['fixture']:
        lines += ['**Software fixture only.** This tiny random CPU model bypasses scientific gates to exercise the pipeline; its output is not evidence about the 70B model.','']
    if 'response_format' in report:
        lines += [f"Selected format: `{report['response_format']['name']}`. Common steering norm: {report.get('common_rho', 'not selected')}.",'']
    if 'selected_validation' in report:
        metric=report['selected_validation']
        lines += [f"Selected checkpoint: update {report['best_step']}. Validation teacher-choice RMSE: {metric['teacher_probability_rmse']:.5f}. Operational validation recovery passed: {metric['passed_operational_recovery_target']}.",'']
    if (run/'training.json').exists():
        history=json.loads((run/'training.json').read_text())['history']
        lines += ['| Update | Training-audit RMSE | Validation RMSE | All validation recovery targets passed |',
                  '|---:|---:|---:|---|']
        for entry in history:
            if 'selection' in entry:
                lines.append(f"| {entry['step']} | {entry['training_audit']['teacher_probability_rmse']:.5f} | {entry['selection']['teacher_probability_rmse']:.5f} | {entry['selection']['passed_operational_recovery_target']} |")
        lines += ['']
    lines += ['Operational recovery requires teacher-choice RMSE ≤ 0.04, minimum A/B mass ≥ 0.99, a converged interior CPT fit, and parameter errors no larger than curvature 0.10, weighting 0.10, loss aversion 0.20, inverse temperature 0.40, and A-label bias 0.10. Every common-norm additive condition must have minimum A/B mass ≥ 0.95 and displacement error ≤ 2%.','']
    results={};table=[];groups={}
    if (run/'scores_baseline.json').exists():
        rows=json.loads((run/'frozen_rows.json').read_text())
        baseline=json.loads((run/'scores_baseline.json').read_text())
        for path in sorted(run.glob('scores_*.json')):
            name=path.stem.removeprefix('scores_');records=json.loads(path.read_text())
            if len(records)!=len(rows):raise RuntimeError('Frozen score count mismatch')
            result=condition_summary(rows,records,baseline,planted=truth,
                                     bootstrap=bootstrap if name=='lora_combined' and not report['fixture'] else 0)
            results[name]=result
            if name in ('baseline','lora_combined','mean_delta','sae_preference_k10',
                        'mean_delta_fitted_magnitude','sae_preference_k10_fitted_magnitude'):
                expected=probabilities(rows,truth)
                error=np.array([r['p_risky'] for r in records])-expected
                groups[name]={}
                for field in ('frame','probability','stake','risky_label'):
                    summaries=[]
                    for value in sorted({r[field] for r in rows}):
                        mask=np.array([r[field]==value for r in rows])
                        summaries.append({'value':value,'n':int(mask.sum()),
                                          'teacher_rmse':float(np.sqrt(np.mean(error[mask]**2))),
                                          'mean_signed_error':float(error[mask].mean())})
                    assert abs(sum(s['n']*s['teacher_rmse']**2 for s in summaries)/len(rows)-float(np.mean(error**2)))<1e-10
                    groups[name][field]=summaries
                groups[name]['largest_errors']=[{'id':rows[i]['id'],'frame':rows[i]['frame'],
                    'probability':rows[i]['probability'],'stake':rows[i]['stake'],'ratio':rows[i]['ratio'],
                    'risky_label':rows[i]['risky_label'],'teacher_probability':float(expected[i]),
                    'model_probability':records[i]['p_risky'],'error':float(error[i])}
                    for i in np.argsort(np.abs(error))[-20:][::-1]]
            table.append({'condition':name,**result['frozen']['parameters'],
                          'teacher_probability_rmse':result['planted_recovery']['frozen_probability_rmse'],
                          'min_answer_mass':result['min_answer_mass'],
                          'answer_mass_below_0_95_count':result['answer_mass_below_0_95_count'],
                          'max_relative_norm_error':result.get('displacement',{}).get('max_relative_norm_error'),
                          'dominance_argmax_violation_rate':result['dominance']['argmax_violation_rate'],
                          'label_order_gap':result['label_order_mean_absolute_probability_gap']})
        save_json(run/'analysis.json',results)
        save_json(run/'grouped_probability_errors.json',groups)
        with (run/'comparison.csv').open('w') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(table[0]));writer.writeheader();writer.writerows(table)
        lines += [f"Operational repair passed: **{report.get('operational_repair_passed', False)}**. Planted curvature {truth['curvature']}, weighting {truth['weighting']}, loss aversion {truth['loss_aversion']}, inverse temperature {truth['inverse_temperature']}, A-label bias {truth['label_bias']}.",'',
                  '| Condition | Curvature | Weighting | Loss aversion | Teacher-choice RMSE | Min A/B mass |',
                  '|---|---:|---:|---:|---:|---:|']
        for row in table:
            lines.append('| '+row['condition']+' | '+' | '.join(f'{row[k]:.4f}' for k in
                         ('curvature','weighting','loss_aversion','teacher_probability_rmse','min_answer_mass'))+' |')
        lines += ['']
    else:
        lines += ['No frozen response scores were produced. This is a recorded early stop, not evidence that parameter recovery or the SAE comparison succeeded. See report.json for the failed gate and training.json for checkpoint diagnostics when training ran.','']
    if 'footprint' in report:
        fp=report['footprint']
        lines += [f"Mean residual-shift norm: {fp['mean_delta_norm']:.4f}; ten-feature relative reconstruction error: {fp['native']['10']['relative_error']:.4f}.",'']
        if (run/'residual_heterogeneity.json').exists():
            geometry=json.loads((run/'residual_heterogeneity.json').read_text())
            lines += [f"The constant mean shift accounts for {100*geometry['fraction_shift_energy_in_constant_mean']:.1f}% of the total squared per-prompt shift on discovery prompts. Its per-prompt relative reconstruction error is {geometry['constant_mean_relative_reconstruction_error']:.4f}. This measures information lost before the SAE projection; it does not by itself predict behavioral performance.",'']
        if (run/'sparse_geometry_diagnostic.json').exists():
            sparse=json.loads((run/'sparse_geometry_diagnostic.json').read_text())
            lines += [sparse['scope'],'',
                      f"Greedy sparse discovery reconstruction errors: k=10, {sparse['methods']['10']['relative_error']:.4f}; k=30, {sparse['methods']['30']['relative_error']:.4f}. These alternative reconstructions have no behavioral evaluation in this run.",'']
        label_path=Path(__file__).resolve().parents[1]/'SAE/data/raw/feature_labels/goodfire_llama33_70b_l50_feature_labels_filtered.csv'
        labels={}
        if label_path.exists():
            with label_path.open() as handle:labels={int(r['index_in_sae']):r['label'] for r in csv.DictReader(handle)}
        labeled=[{**entry,'label':labels.get(entry['feature'])} for entry in fp['top_projection_features']]
        save_json(run/'labeled_footprint.json',{'features':labeled,
                  'label_file_sha256':hashlib.sha256(label_path.read_bytes()).hexdigest() if label_path.exists() else None})
        lines += ['| Largest footprint feature | Cached label | Mean projection | Mean encoder change |',
                  '|---:|---|---:|---:|']
        for entry in labeled[:10]:
            label=(entry['label'] or 'Unavailable').replace('|',' / ')
            lines.append(f"| {entry['feature']} | {label} | {entry['mean_unit_decoder_projection']:.4f} | {entry['mean_encoder_change']:.4f} |")
        lines += ['']
        if (run/'targeted_footprints.json').exists():
            targeted=json.loads((run/'targeted_footprints.json').read_text())
            lines += [targeted['scope'],'',targeted['historical_identity_caveat'],'',
                      '| Nominated feature | Cached label | Readout cosine | Mean projection | Mean encoder change |',
                      '|---:|---|---:|---:|---:|']
            for entry in targeted['features']:
                label=(labels.get(entry['feature']) or 'Unavailable').replace('|',' / ')
                lines.append(f"| {entry['feature']} | {label} | {entry['cosine_readout']:.4f} | {entry['mean_unit_decoder_projection']:.4f} | {entry['mean_encoder_change']:.4f} |")
            lines += ['']
    lines += ['Limits: the larger adapter acts across layers and prompt positions; its mean residual replay is one vector at one layer and position. A sparse replay failure does not by itself isolate a dictionary limitation. Original-magnitude replays are separate diagnostics and are excluded from the common-norm gate. New reward levels use the same task template; repeated training seeds and external task generalization remain untested. Scenario bootstrap intervals describe variation across paired scenarios, not independent training runs.','']
    (run/'REPORT.md').write_text('\n'.join(lines))
    source=run/'postprocessing_source';source.mkdir(exist_ok=True)
    source_hashes={}
    for name in ('repair_report.py','analysis.py','cpt.py','repair_audit.py','repair_geometry.py','repair_targeted.py','repair_sparse_geometry.py'):
        data=(Path(__file__).parent/name).read_bytes();(source/name).write_bytes(data)
        source_hashes[name]=hashlib.sha256(data).hexdigest()
    save_json(run/'analysis_status.json',{'status':'analysis_complete','conditions':len(table),
              'scientific_go_pivot':None,'source_sha256':source_hashes})
    return len(table)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--bootstrap',type=int,default=100);args=p.parse_args()
    print(json.dumps({'conditions':build_report(args.run,args.bootstrap),'report':str(args.run/'REPORT.md')}))


if __name__=='__main__':main()
