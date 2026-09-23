"""Freeze the follow-up's data and operational targets before GPU evaluation."""
import argparse
from dataclasses import asdict
import datetime as dt
import json
from pathlib import Path

from .cpt import fit, identifiability, probabilities
from .design import AGENTS, build_rows, digest, render
from .smoke import save_json


SYSTEM = 'Choose between the two options. Your answer must contain only the option letter A or B. Do not explain.'
FORMATS = [
    {'name': 'original'},
    {'name': 'system_letter', 'system': SYSTEM},
    {'name': 'answer_prefill', 'system': SYSTEM, 'prefill': 'Answer:', 'continuation_prefix': ' '},
    {'name': 'option_prefill', 'system': SYSTEM, 'prefill': 'I choose option', 'continuation_prefix': ' '},
]
RATIOS = {
    'discovery': [.2,.4,.6,.8,1.,1.2,1.4,1.6,1.8,2.,2.4,2.8,3.2,3.6,4.,4.4,4.8,5.2,5.6,6.,6.4,6.8,7.2,8.],
    'selection': [.35,.95,1.55,2.65,4.15,7.],
    'frozen': [.45,1.05,1.85,2.95,4.75,7.6],
}
TOLERANCES = {'curvature': .10, 'weighting': .10, 'loss_aversion': .20,
              'inverse_temperature': .40, 'label_bias': .10}
MODULES = ['q_proj','k_proj','v_proj','o_proj','gate_proj','up_proj','down_proj']


def build_repair_rows(fixture=False):
    rows=[]
    for split, ratios in RATIOS.items():
        for frame in ('gain','loss','mixed'):
            for probability in ((.5,) if fixture else (.1,.25,.5,.75,.9)):
                for stake in ((25.,) if fixture else (25.,50.,75.)):
                    for index,ratio in enumerate(ratios[:2] if fixture else ratios):
                        reward=round(stake*ratio,6)
                        if frame=='gain': risky,safe=[[reward,probability],[0.,1-probability]],[[stake,1.]]
                        elif frame=='loss': risky,safe=[[-reward,probability],[0.,1-probability]],[[-stake,1.]]
                        else: risky,safe=[[reward,probability],[-stake,1-probability]],[[0.,1.]]
                        grid=f'{frame}_p{probability:g}_s{stake:g}'
                        economic=f'repair_{split}_{grid}_r{index}'
                        dominance='safe' if max(x for x,_ in risky)<safe[0][0] else 'risky' if min(x for x,_ in risky)>safe[0][0] else None
                        for label in 'AB':
                            row={'id':economic+'_'+label,'economic_id':economic,'grid_id':grid,
                                 'frame':frame,'split':split,'probability':probability,'stake':stake,
                                 'reward':reward,'ratio':ratio,'risky':risky,'safe':safe,
                                 'risky_label':label,'safe_label':'B' if label=='A' else 'A',
                                 'dominant_option':dominance}
                            row['text']=render(row);rows.append(row)
    return rows


def recovery_check(rows, records, target=None):
    import numpy as np
    truth=target or asdict(AGENTS['combined'])
    p=np.array([r['p_risky'] for r in records]);q=probabilities(rows,truth)
    result=fit(rows,p,starts=4)
    errors={k:result['parameters'][k]-v for k,v in truth.items()}
    rmse=float(np.sqrt(np.mean((p-q)**2)))
    minimum=min(r['answer_mass'] for r in records)
    passed=bool(result['converged'] and not result['boundary_parameters'] and rmse<=.04
                and minimum>=.99 and all(abs(errors[k])<=limit for k,limit in TOLERANCES.items()))
    return {'passed_operational_recovery_target':passed,'teacher_probability_rmse':rmse,
            'fit':result,'parameter_errors':errors,'min_answer_mass':minimum,
            'thresholds':{'teacher_rmse':.04,'min_answer_mass':.99,'absolute_parameter_errors':TOLERANCES},
            'scientific_go_pivot':None}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    rows=build_repair_rows();truth=asdict(AGENTS['combined']);validation={}
    old_text={r['text'] for r in build_rows()}
    # The previous fresh-grid ratios are also excluded from the new test grid.
    assert not set(RATIOS['frozen']) & {.55,1.25,2.3,3.3,6.5}
    assert not {r['text'] for r in rows if r['split']=='frozen'} & old_text
    for split in RATIOS:
        subset=[r for r in rows if r['split']==split]
        prediction=probabilities(subset,truth);result=fit(subset,prediction);rank=identifiability(subset)
        assert rank['rank']==5
        assert max(abs(result['parameters'][k]-v) for k,v in truth.items())<1e-4
        validation[split]={'rows':len(subset),'synthetic_recovery':result,'identifiability':rank}
    args.output.mkdir(exist_ok=False,parents=True)
    save_json(args.output/'rows.json',rows)
    save_json(args.output/'manifest.json',{
        'declared_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'rows_sha256':digest(rows),
        'target':truth,'splits':validation,'formats':FORMATS,
        'rho_grid_descending':[1.,.5,.25,.1],
        'calibration_subset':{'split':'discovery','ratios':[.4,1.8,3.6,6.8],'stakes':[25,75],
                              'all_probabilities_frames_and_orders':True,'rows':240},
        'format_selection':'Training-only calibration subset; baseline min mass >= .99; edited min mass >= .95 and norm error <= .02 at both layers and both signs. Lock the first passing dose in descending order for the highest-ranked eligible format.',
        'format_validation':'Validate the locked format and dose on the separate selection split. Fail closed before training if baseline/gradient validity does not generalize.',
        'training':{'layers':[0,50],'modules':MODULES,'rank':16,'max_updates':2400,
                    'micro_batch':8,'accumulation':2,'effective_batch':16,'paired_answer_orders':True,
                    'learning_rate_peak':.0001,'learning_rate_floor':.00001,'warmup_updates':50,
                    'checkpoint_every':100,'minimum_updates':400,'consecutive_passing_validations_to_stop':2},
        'checkpoint_selection':'Prefer checkpoints passing all operational targets, then lowest full-vocabulary selection cross entropy. Selection responses never enter optimizer updates.',
        'operational_targets':{'teacher_probability_rmse':.04,'min_answer_mass':.99,'absolute_parameter_errors':TOLERANCES},
        'scope':'These are newly declared repair targets, not the missing external scientific go/pivot rule.',
        'posttraining_dose_selection':'On selection rows, choose the largest rho no greater than the pretraining rho at which every one of the 23 additive directions passes answer-mass and norm gates. Fail closed if none pass.',
        'comparisons':{'norm_matched_directions':23,'final_conditions':29,
                       'original_magnitude_controls':4,'random_seeds_per_layer':1,
                       'features':[184,4237,31935,13142,20117,4992],
                       'full_feature_sweep':False},
        'frozen_policy':'Evaluate frozen model responses only after the selected adapter passes validation and all comparison directions are locked. A failed validation leaves the new frozen responses unopened.',
    })
    print(json.dumps({'rows':len(rows),'split_counts':{k:v['rows'] for k,v in validation.items()},'output':str(args.output)}))


if __name__=='__main__':main()
