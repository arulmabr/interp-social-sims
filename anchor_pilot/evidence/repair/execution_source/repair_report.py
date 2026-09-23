"""Report a bounded repair, including early failure with frozen responses unopened."""
import argparse
import csv
import hashlib
import json
from pathlib import Path

from .analysis import condition_summary
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
    lines += ['Operational recovery requires teacher-choice RMSE ≤ 0.04, minimum A/B mass ≥ 0.99, a converged interior CPT fit, and parameter errors no larger than curvature 0.10, weighting 0.10, loss aversion 0.20, inverse temperature 0.40, and A-label bias 0.10. Every common-norm additive condition must have minimum A/B mass ≥ 0.95 and displacement error ≤ 2%.','']
    results={};table=[]
    if (run/'scores_baseline.json').exists():
        rows=json.loads((run/'frozen_rows.json').read_text())
        baseline=json.loads((run/'scores_baseline.json').read_text())
        for path in sorted(run.glob('scores_*.json')):
            name=path.stem.removeprefix('scores_');records=json.loads(path.read_text())
            if len(records)!=len(rows):raise RuntimeError('Frozen score count mismatch')
            result=condition_summary(rows,records,baseline,planted=truth,
                                     bootstrap=bootstrap if name=='lora_combined' and not report['fixture'] else 0)
            results[name]=result
            table.append({'condition':name,**result['frozen']['parameters'],
                          'teacher_probability_rmse':result['planted_recovery']['frozen_probability_rmse'],
                          'min_answer_mass':result['min_answer_mass'],
                          'answer_mass_below_0_95_count':result['answer_mass_below_0_95_count'],
                          'max_relative_norm_error':result.get('displacement',{}).get('max_relative_norm_error'),
                          'dominance_argmax_violation_rate':result['dominance']['argmax_violation_rate'],
                          'label_order_gap':result['label_order_mean_absolute_probability_gap']})
        save_json(run/'analysis.json',results)
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
    lines += ['Limits: the larger adapter acts across layers and prompt positions; its mean residual replay is one vector at one layer and position. A sparse replay failure does not by itself isolate a dictionary limitation. Original-magnitude replays are separate diagnostics and are excluded from the common-norm gate. New reward levels use the same task template; repeated training seeds and external task generalization remain untested. Scenario bootstrap intervals describe variation across paired scenarios, not independent training runs.','']
    (run/'REPORT.md').write_text('\n'.join(lines))
    source=run/'postprocessing_source';source.mkdir(exist_ok=True)
    source_hashes={}
    for name in ('repair_report.py','analysis.py','cpt.py'):
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
