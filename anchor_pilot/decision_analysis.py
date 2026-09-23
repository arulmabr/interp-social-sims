"""Cross-validated behavioral comparisons; inference is over economic scenarios."""
from dataclasses import asdict
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit, logit

from .cpt import Parameters, probabilities, fit
from .decision_plan import build_decision_rows, TARGETS
from .smoke import save_json


def rmse(a,b): return float(np.sqrt(np.mean((np.asarray(a)-np.asarray(b))**2)))


def shortcut_design(rows,base):
    margin=logit(np.clip(base,1e-6,1-1e-6))
    frames=np.array([[float(r['frame']==f) for f in ('gain','loss','mixed')] for r in rows])
    label=np.array([1 if r['risky_label']=='A' else -1 for r in rows])
    return np.column_stack([frames*margin[:,None],frames,label])


def fit_shortcut(rows,base,target):
    x=shortcut_design(rows,base);y=np.asarray(target)
    def objective(theta):
        z=x@theta;return np.mean(np.logaddexp(0,z)-y*z),x.T@(expit(z)-y)/len(y)
    result=minimize(objective,[1,1,1,0,0,0,0],jac=True,method='L-BFGS-B',
                    bounds=[(.05,10)]*3+[(-12,12)]*4,options={'maxiter':1200,'ftol':1e-13,'gtol':1e-8})
    return {'parameters':result.x.tolist(),'converged':bool(result.success),'loss':float(result.fun)}


def behavioral_comparison(train_rows,train_p,train_base,test_rows,test_p,test_base):
    cpt=fit(train_rows,train_p,starts=4);shortcut=fit_shortcut(train_rows,train_base,train_p)
    pc=probabilities(test_rows,cpt['parameters']);ps=expit(shortcut_design(test_rows,test_base)@shortcut['parameters'])
    return {'cpt_selection_fit':cpt,'shortcut_selection_fit':shortcut,'heldout_cpt_rmse':rmse(test_p,pc),
            'heldout_shortcut_rmse':rmse(test_p,ps),'cpt_advantage':rmse(test_p,ps)-rmse(test_p,pc),
            'effect_rmse':rmse(test_p,test_base)}


def calibration(output):
    rows=build_decision_rows();train=[r for r in rows if r['split']=='selection']
    test=[r for r in rows if r['split']=='frozen' and r['template']=='original']
    base1=probabilities(train,TARGETS['combined']);base2=probabilities(test,TARGETS['combined']);cases=[]
    for kind in ('risky_bias','label_bias','temperature','frame_bias','frame_temperature'):
        for amount in (-1.,-.5,.5,1.):
            theta=np.array([1.,1.,1.,0.,0.,0.,0.])
            if kind=='risky_bias':theta[3:6]=amount
            elif kind=='label_bias':theta[6]=amount
            elif kind=='temperature':theta[:3]=np.exp(amount)
            elif kind=='frame_bias':theta[3:6]=[amount,-amount,.5*amount]
            else:theta[:3]=np.exp([amount,-amount,.5*amount])
            p1=expit(shortcut_design(train,base1)@theta);p2=expit(shortcut_design(test,base2)@theta)
            comparison=behavioral_comparison(train,p1,base1,test,p2,base2)
            cases.append({'kind':kind,'amount':amount,'truth':'action','comparison':comparison})
    alternatives=[('neutral',TARGETS['neutral'])]
    for name,values in [('curvature',[.55,1.15]),('weighting',[.5,1.1]),('loss_aversion',[1.,3.])]:
        for value in values: alternatives.append((name+str(value),dict(TARGETS['combined'],**{name:value})))
    for name,target in alternatives:
        comparison=behavioral_comparison(train,probabilities(train,target),base1,test,probabilities(test,target),base2)
        cases.append({'kind':name,'truth':'preference','comparison':comparison})
    for case in cases:
        c=case['comparison'];case['classified_preference']=c['heldout_cpt_rmse']<=.06 and c['cpt_advantage']>=.01 and c['effect_rmse']>=.03
    null=[c for c in cases if c['truth']=='action'];alt=[c for c in cases if c['truth']=='preference']
    result={'cases':cases,'false_positives':sum(c['classified_preference'] for c in null),'null_n':len(null),
            'true_positives':sum(c['classified_preference'] for c in alt),'alternative_n':len(alt),
            'calibrated_for_neutral_combined_comparison':next(c['classified_preference'] for c in alt if c['kind']=='neutral'),
            'scope':'Deterministic probabilities and finite hand-specified shortcuts; not a population false-positive-rate guarantee.'}
    result['passed']=result['false_positives']==0 and result['calibrated_for_neutral_combined_comparison']
    save_json(output,result);return result


def grouped_rmse_interval(rows,p,target,reps=1000,seed=702):
    groups=sorted({r['economic_id'] for r in rows});indices={g:[i for i,r in enumerate(rows) if r['economic_id']==g] for g in groups}
    squared=(np.asarray(p)-np.asarray(target))**2
    rng=np.random.default_rng(seed);values=[]
    for _ in range(reps):
        ids=[i for g in rng.choice(groups,len(groups),replace=True) for i in indices[g]]
        values.append(float(np.sqrt(squared[ids].mean())))
    return np.quantile(values,[.025,.975]).tolist()


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=Path('anchor_pilot/outputs/decision-plan-v2/calibration.json'));args=parser.parse_args()
    result=calibration(args.output)
    print(json.dumps({k:v for k,v in result.items() if k!='cases'}))
