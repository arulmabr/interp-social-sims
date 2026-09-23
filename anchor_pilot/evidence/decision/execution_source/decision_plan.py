"""A bounded, predeclared comparison of constant residual and sparse SAE steering."""
import argparse
from dataclasses import asdict
import datetime as dt
import hashlib
import json
from pathlib import Path

from .cpt import Parameters, fit, identifiability, probabilities
from .design import render, describe, digest
from .repair_design import SYSTEM
from .replay_plan import SOURCE
from .smoke import save_json

TARGETS = {'combined': asdict(Parameters()), 'neutral': asdict(Parameters(1.,1.,1.,3.,0.))}
SCOPES = ['final', 'all']
DOSES = [1., 4., 16.]
SEEDS = [31, 73]


def render_transfer(row):
    options = {row['risky_label']:row['risky'], row['safe_label']:row['safe']}
    return ('Consider changes in a token account. The current balance is the zero reference; '
            'the account can cover every possible loss. Select your preferred offer.\n' +
            '\n'.join(f'{label}) {describe(options[label])}.' for label in 'AB') +
            '\nWhich offer do you take? Reply A or B only.')


def build_decision_rows():
    rows=[]
    specs={'discovery':([.15,.5,.85],[30.,70.],[.3,.7,1.3,2.3,4.3,7.3]),
           'selection':([.2,.65],[40.,60.],[.5,1.5,3.5,6.5]),
           'frozen':([.18,.42,.78],[35.,65.],[.38,.88,1.68,2.88,4.88,7.88])}
    for split,(ps,stakes,ratios) in specs.items():
        for frame in ('gain','loss','mixed'):
            for probability in ps:
                for stake in stakes:
                    for index,ratio in enumerate(ratios):
                        reward=round(stake*ratio,6)
                        if frame=='gain': risky,safe=[[reward,probability],[0.,1-probability]],[[stake,1.]]
                        elif frame=='loss': risky,safe=[[-reward,probability],[0.,1-probability]],[[-stake,1.]]
                        else: risky,safe=[[reward,probability],[-stake,1-probability]],[[0.,1.]]
                        grid=f'{frame}_p{probability:g}_s{stake:g}'
                        economic=f'decision_{split}_{grid}_r{index}'
                        dom='safe' if max(x for x,_ in risky)<safe[0][0] else 'risky' if min(x for x,_ in risky)>safe[0][0] else None
                        for template in (['original','transfer'] if split=='frozen' else ['original']):
                            for label in 'AB':
                                r={'id':economic+'_'+template+'_'+label,'economic_id':economic,
                                   'grid_id':grid,'frame':frame,'split':split,'template':template,
                                   'probability':probability,'stake':stake,'reward':reward,'ratio':ratio,
                                   'risky':risky,'safe':safe,'risky_label':label,'safe_label':'B' if label=='A' else 'A',
                                   'dominant_option':dom}
                                r['text']=render(r) if template=='original' else render_transfer(r)
                                rows.append(r)
    return rows


def comprehension_rows():
    rows=[]
    for i,(a,b) in enumerate([(7,13),(28,19),(42,42),(9,4),(18,21),(31,24),(6,16),(15,15)]):
        for order in (0,1):
            for task in ('arithmetic','probability','dominance'):
                correct=(a+b) if task=='arithmetic' else max(a,b)
                wrong=correct+3 if task=='arithmetic' else min(a,b)-3
                vals=[correct,wrong] if order==0 else [wrong,correct]
                if task=='arithmetic': text=f'What is {a} + {b}?\nA: {vals[0]}\nB: {vals[1]}'
                elif task=='probability': text=f'Which probability is larger?\nA: {vals[0]}%\nB: {vals[1]}%'
                else: text=f'Which certain token change leaves a larger balance?\nA: gain {vals[0]} tokens\nB: gain {vals[1]} tokens'
                rows.append({'id':f'control_{task}_{i}_{order}','text':text+'\nAnswer A or B only.',
                             'risky_label':'A' if order==0 else 'B','safe_label':'B' if order==0 else 'A','task':task})
    return rows


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path('anchor_pilot/outputs/decision-plan-v1'));args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);rows=build_decision_rows()
    # Frozen economic inputs and both renderings are new, including all preceding runs.
    texts={r['text'] for r in rows if r['split']=='frozen'}
    for file in Path('anchor_pilot/outputs').rglob('*rows.json'):
        if 'decision' in str(file):continue
        try: previous=json.loads(file.read_text())
        except ValueError:continue
        if isinstance(previous,list): assert not texts & {r.get('text') for r in previous if isinstance(r,dict)},str(file)
    geometry=json.loads((SOURCE/'sparse_geometry_diagnostic.json').read_text())
    candidates=list(dict.fromkeys(geometry['methods']['30']['indices']+[184,4237,31935,13142,20117,4992,47380]))
    checks={}
    for split in ('discovery','selection','frozen'):
        rs=[r for r in rows if r['split']==split and r['template']=='original']
        checks[split]={'n':len(rs),'identification':identifiability(rs),'recovery':{}}
        assert checks[split]['identification']['rank']==5
        for name,target in TARGETS.items():
            recovered=fit(rs,probabilities(rs,target),starts=4)
            assert max(abs(recovered['parameters'][k]-v) for k,v in target.items())<1e-3
            checks[split]['recovery'][name]=recovered
    hashes={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in ('adapter/adapter.pt','adapter/adapter_config.json','footprint.pt','sparse_geometry_diagnostic.json')}
    manifest={'declared_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'rows_sha256':digest(rows),
              'source_hashes':hashes,'targets':TARGETS,'checks':checks,'candidate_features':candidates,
              'response_format':{'name':'system_letter','system':SYSTEM},'layer':50,'scopes':SCOPES,'doses':DOSES,'seeds':SEEDS,
              'sparse_k':10,'methods':['dense','sae10'],'updates':160,'batch_size':8,'learning_rate':.2,
              'screen':'Each feature, both signs, norm 16, final and all positions; rank by full-grid discovery expected answer CE for each planted target. No attribution ranking.',
              'training':'Frozen base; learn one prompt-independent vector per target, scope, method and seed. Same norm-16 sphere and optimizer budget. SAE uses QR basis of ten causally ranked decoder columns. Base-model intervention; no adapted test states.',
              'selection':'For each target jointly choose one shared scope and dose minimizing mean selection teacher RMSE across both methods and seeds; retain both independent fits for frozen evaluation. Dose grid 1,4,16. No frozen tuning.',
              'controls':'Base; saved combined LoRA; raw mean discovery gradient at 50; SAE gradient approximation; three seeded random directions. All controls in both scopes at matched selected doses. Separate arithmetic/probability/dominance questions.',
              'rule':{'teacher_rmse':.06,'heldout_cpt_rmse':.06,'min_answer_mass':.99,'max_mean_order_gap':.05,
                      'max_control_accuracy_drop':.05,'max_dominance_rate':.05,'min_shortcut_rmse_advantage':.01,'max_mean_relative_norm_error':.05,
                      'max_preference_parameter_errors':{'curvature':.12,'weighting':.12,'loss_aversion':.25},
                      'repetitions':'Both seeds, both templates, and both targets must pass for a robust method-level positive.',
                      'interpretation':'Operational scope-specific decision, not the unavailable collaborator go/pivot rule; no proof of universal SAE inability.'},
              'shortcut_models':'Nested risky/A-label offsets, temperature, frame offsets and frame temperatures fitted on selection, compared on frozen predictions; known synthetic action nulls and CPT alternatives calibrate the rule before GPU.',
              'stopping':'No larger sweep. LoRA transfer failure or failed rule calibration => evaluation/generalization inconclusive. Dense passes and SAE fails => pivot tested sparse recipe. Both fail with LoRA passing => pivot constant-vector intervention. Both pass => proceed to confirmatory study.',
              'limits':'One base model/SAE/layer and one LoRA training seed. Two planted vectors do not replace a neutral CPT LoRA. Negative results concern this candidate set, budget, optimization and constant-vector format.'}
    save_json(args.output/'manifest.json',manifest);save_json(args.output/'rows.json',rows);save_json(args.output/'controls.json',comprehension_rows())
    print(json.dumps({'output':str(args.output),'counts':{s:sum(r['split']==s for r in rows) for s in checks},'features':len(candidates)}))


if __name__=='__main__':main()
