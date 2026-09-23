"""Audit completed frozen outputs and apply the predeclared operational decision."""
import argparse
import csv
import datetime as dt
import json
from pathlib import Path

import numpy as np

from .cpt import fit, probabilities
from .decision_analysis import behavioral_comparison, grouped_rmse_interval, rmse
from .smoke import save_json


def read(root,name):return json.loads((root/name).read_text())


def accuracy(scores):return float(np.mean([r['p_risky']>.5 for r in scores]))


def analyze(root):
    status=read(root,'run_status.json');assert status['status']=='completed' and not status['fixture']
    plan=read(root,'plan.json');rule=plan['rule'];lock=read(root,'selection_lock.json')
    selection=read(root,'selection_rows.json');frozen=read(root,'frozen_rows.json')
    base_selection=read(root,'selection_scores_baseline.json');base=read(root,'frozen_scores_baseline.json')
    base_control=read(root,'control_scores_baseline.json');base_accuracy=accuracy(base_control)
    control_rows=read(root,'control_rows.json');results={}
    assert len({r['id'] for r in frozen})==len(frozen)==432
    assert len(selection)==96 and len(control_rows)==48
    for name in status['conditions']:
        scores=read(root,f'frozen_scores_{name}.json');train=read(root,f'selection_scores_{name}.json');controls=read(root,f'control_scores_{name}.json')
        assert len(scores)==len(frozen) and len(train)==len(selection) and len(controls)==len(control_rows)
        values=np.array([r['p_risky'] for r in scores]);mass=np.array([r['answer_mass'] for r in scores])
        assert np.isfinite(values).all() and np.all((values>=0)&(values<=1)) and np.all((mass>=0)&(mass<=1.00001))
        entry={'control_accuracy':accuracy(controls),'control_accuracy_drop':base_accuracy-accuracy(controls),
               'control_min_answer_mass':min(r['answer_mass'] for r in controls),
               'control_task_accuracy':{task:accuracy([s for r,s in zip(control_rows,controls) if r['task']==task]) for task in ('arithmetic','probability','dominance')},'templates':{}}
        for template in ('original','transfer'):
            ids=[i for i,r in enumerate(frozen) if r['template']==template];rs=[frozen[i] for i in ids];p=values[ids]
            b=[base[i]['p_risky'] for i in ids]
            comparison=behavioral_comparison(selection,[r['p_risky'] for r in train],[r['p_risky'] for r in base_selection],rs,p,b)
            fitted=fit(rs,p,starts=4)
            pairs={}
            for r,v in zip(rs,p):pairs.setdefault(r['economic_id'],{})[r['risky_label']]=float(v)
            ordergap=float(np.mean([abs(v['A']-v['B']) for v in pairs.values()]))
            dominance=[i for i,r in enumerate(rs) if r['dominant_option']]
            violations=sum((p[i]>.5)!=(rs[i]['dominant_option']=='risky') for i in dominance)
            norm_errors=[abs(scores[i]['norm']['mean_realized_norm']/scores[i]['norm']['requested_norm_per_position']-1) for i in ids if 'norm' in scores[i]]
            common={'answer_mass':float(mass[ids].min())>=rule['min_answer_mass'],
                    'order_gap':ordergap<=rule['max_mean_order_gap'],
                    'dominance':violations/max(1,len(dominance))<=rule['max_dominance_rate'],
                    'comprehension':entry['control_accuracy_drop']<=rule['max_control_accuracy_drop'],
                    'control_answer_mass':entry['control_min_answer_mass']>=rule['min_answer_mass'],
                    'realized_norm':not norm_errors or max(norm_errors)<=rule['max_mean_relative_norm_error'],
                    'heldout_cpt_fit':comparison['heldout_cpt_rmse']<=rule['heldout_cpt_rmse'],
                    'beats_shortcut':comparison['cpt_advantage']>=rule['min_shortcut_rmse_advantage'],
                    'fit_identified':fitted['converged'] and not fitted['boundary_parameters'],
                    'comparison_optimizers_converged':comparison['cpt_selection_fit']['converged'] and comparison['shortcut_selection_fit']['converged']}
            template_result={'n':len(rs),'comparison':comparison,'frozen_cpt_fit':fitted,'mean_order_gap':ordergap,
                             'dominance_violations':int(violations),'dominance_n':len(dominance),'min_answer_mass':float(mass[ids].min()),
                             'max_prompt_mean_norm_error':max(norm_errors) if norm_errors else None,
                             'common_gates':common,'preference_like':bool(all(common.values()) and comparison['effect_rmse']>=.03),'targets':{}}
            for target,parameters in plan['targets'].items():
                truth=probabilities(rs,parameters);error=rmse(p,truth);interval=grouped_rmse_interval(rs,p,truth)
                errors={k:fitted['parameters'][k]-v for k,v in parameters.items()}
                checks=dict(common,teacher_rmse=error<=rule['teacher_rmse'],
                            preference_parameters=all(abs(errors[k])<=tol for k,tol in rule['max_preference_parameter_errors'].items()))
                template_result['targets'][target]={'teacher_rmse':error,'teacher_rmse_interval_95':interval,
                    'parameter_errors':errors,'gates':checks,'passed':bool(all(checks.values())),
                    'fails_accuracy_with_interval':bool(interval[0]>rule['teacher_rmse'])}
            entry['templates'][template]=template_result
        results[name]=entry
    methods={}
    for method in plan['methods']:
        conditions=[n for n in results if f'_{method}_' in n]
        assert len(conditions)==4
        tests=[results[n]['templates'][template]['targets'][n.split('_')[0]] for n in conditions for template in ('original','transfer')]
        robust_accuracy_failure=any(all(results[n]['templates'][template]['targets'][target]['fails_accuracy_with_interval']
            for n in conditions if n.startswith(target+'_') for template in ('original','transfer')) for target in plan['targets'])
        methods[method]={'passed_all':all(t['passed'] for t in tests),'passed_cells':sum(t['passed'] for t in tests),'total_cells':len(tests),
                         'robust_accuracy_failure':robust_accuracy_failure,
                         'accuracy_excluded_cells':sum(t['fails_accuracy_with_interval'] for t in tests),'conditions':conditions}
    lora_pass=all(results['lora']['templates'][t]['targets']['combined']['passed'] for t in ('original','transfer'))
    # The raw positive and negative readout controls must behave like shortcuts at a valid dose.
    action_controls={}
    for name in results:
        if not name.startswith('gradient_'):continue
        action_controls[name]=all(v['min_answer_mass']>=.99 and v['comparison']['effect_rmse']>=.03 and
                                  v['comparison']['cpt_advantage']<=-.01 and not v['preference_like']
                                  for v in results[name]['templates'].values())
    action_pass=any(action_controls.values())
    calibration=read(root,'calibration.json')
    if not calibration['passed'] or not lora_pass or not action_pass:
        verdict='INCONCLUSIVE_EVALUATION_OR_ANCHOR_TRANSFER'
    elif methods['sae10']['passed_all']:verdict='PROCEED_WITH_BOUNDED_SAE_CONFIRMATION'
    elif methods['dense']['passed_all'] and methods['sae10']['robust_accuracy_failure']:verdict='PIVOT_TESTED_SPARSE_RECIPE'
    elif all(v['robust_accuracy_failure'] for v in methods.values()):verdict='PIVOT_TESTED_CONSTANT_VECTOR_FORMAT'
    else:verdict='INCONCLUSIVE_FOR_STRONG_NEGATIVE_CLAIM'
    result={'analyzed_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'verdict':verdict,'loRA_anchor_passed':lora_pass,
            'action_anchor_passed':action_pass,'action_controls':action_controls,'methods':methods,'conditions':results,
            'base_control_accuracy':base_accuracy,'calibration':{k:v for k,v in calibration.items() if k!='cases'},
            'scope':plan['limits'],'interval_scope':'Paired-economic-scenario bootstrap; no claim about all possible prompts or model training seeds.'}
    save_json(root/'decision_analysis.json',result)
    fields=['condition','template','target','teacher_rmse','rmse_low','rmse_high','heldout_cpt_rmse','shortcut_rmse','cpt_advantage','order_gap','control_accuracy','passed']
    with (root/'decision_comparison.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for name,entry in results.items():
            target=name.split('_')[0] if name.startswith(('combined_','neutral_')) else 'combined'
            for template,value in entry['templates'].items():
                t=value['targets'][target];c=value['comparison']
                writer.writerow({'condition':name,'template':template,'target':target,'teacher_rmse':t['teacher_rmse'],
                    'rmse_low':t['teacher_rmse_interval_95'][0],'rmse_high':t['teacher_rmse_interval_95'][1],
                    'heldout_cpt_rmse':c['heldout_cpt_rmse'],'shortcut_rmse':c['heldout_shortcut_rmse'],'cpt_advantage':c['cpt_advantage'],
                    'order_gap':value['mean_order_gap'],'control_accuracy':entry['control_accuracy'],'passed':t['passed']})
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('root',type=Path);args=parser.parse_args()
    result=analyze(args.root)
    print(json.dumps({k:v for k,v in result.items() if k!='conditions'},indent=2))
