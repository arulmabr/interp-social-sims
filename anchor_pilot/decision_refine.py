"""Selection-only optimization refinement, declared before any frozen results are read."""
import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import numpy as np
import torch

from .core import sparse_match,unit
from .cpt import probabilities
from .decision import evaluate,expected_ce,mask_for,sphere_vector,log
from .decision_analysis import rmse
from .modeling import load_stack,add_lora,restore_adapter,enable_lora,prepare_inputs,answer_logits,MODEL_REVISION,SAE_REVISION
from .repair_design import MODULES
from .replay import patch_full
from .smoke import save_json


def refine_vector(model,discovery,selection,target,target_selection,layer,scope,basis,initial,seed,steps=480,batch=8):
    start=initial.to(next(model.model.layers[layer].parameters()).device)
    theta=torch.nn.Parameter((start if basis is None else basis.T@start).clone())
    optimizer=torch.optim.Adam([theta],lr=.2/math.sqrt(theta.numel()))
    rng=np.random.default_rng(seed+1000)
    original=sphere_vector(theta,basis).detach()
    scores=evaluate(model,selection,layer,original,scope,batch=16)
    best=(expected_ce(scores,target_selection),original.cpu().clone(),0)
    history=[{'step':0,'selection_ce':best[0],'selection_rmse':rmse([r['p_risky'] for r in scores],target_selection)}]
    for step in range(1,steps+1):
        ids=rng.choice(len(discovery),min(batch,len(discovery)),replace=False)
        items=[discovery[int(i)] for i in ids]
        with patch_full(model,layer,sphere_vector(theta,basis),mask_for(items,scope)):
            r,s,n=answer_logits(model,items);q=torch.as_tensor(target[ids],device=r.device,dtype=torch.float32)
            loss=(n-q*r-(1-q)*s).mean()
        optimizer.zero_grad(set_to_none=True);loss.backward()
        if theta.grad is None or not torch.isfinite(theta.grad).all():raise RuntimeError('Invalid refinement gradient')
        optimizer.step()
        with torch.no_grad():theta.mul_(16/theta.norm())
        if step%80==0 or step==steps:
            vector=sphere_vector(theta,basis).detach();scores=evaluate(model,selection,layer,vector,scope,batch=16)
            ce=expected_ce(scores,target_selection)
            history.append({'step':step,'selection_ce':ce,'selection_rmse':rmse([r['p_risky'] for r in scores],target_selection),'training_loss':float(loss.detach())})
            if ce<best[0]:best=(ce,vector.cpu().clone(),step)
            log('refinement_checkpoint',name=refine_vector.name,**history[-1])
    return best[1],{'selected_refinement_step':best[2],'refinement_history':history,'extra_updates':steps}


def main():
    p=argparse.ArgumentParser();p.add_argument('--stage1',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source',type=Path,default=Path('anchor_pilot/replay-source'));p.add_argument('--fixture',action='store_true');args=p.parse_args()
    root=args.output;root.mkdir(parents=True,exist_ok=False);read=lambda name:json.loads((args.stage1/name).read_text())
    plan=read('plan.json');lock1=read('selection_lock.json');started=time.monotonic()
    amendment=json.loads(Path('anchor_pilot/outputs/decision-refinement-plan-v1.json').read_text())
    report={'status':'running','fixture':args.fixture,'stage1':str(args.stage1),'model_revision':MODEL_REVISION,'sae_revision':SAE_REVISION}
    # Deliberately copy only development scores, vectors and static inputs. No stage-one frozen scores are read.
    for file in args.stage1.iterdir():
        if file.is_file() and (file.name in ('plan.json','rows.json','calibration.json','causal_screen.json','readout_gradient.pt','control_rows.json','readout_geometry.json') or
                              file.name.endswith('_rows.json') or file.name.startswith(('selection_scores_','discovery_scores_'))):shutil.copy2(file,root/file.name)
    save_json(root/'refinement_plan.json',amendment);save_json(root/'stage1_selection_lock.json',lock1)
    execution=root/'execution_source';execution.mkdir()
    for file in Path(__file__).parent.glob('*.py'):shutil.copy2(file,execution/file.name)
    try:
        if not args.fixture:
            for name,sha in plan['source_hashes'].items():assert hashlib.sha256((args.source/name).read_bytes()).hexdigest()==sha
        model,tok,decoder,encoder,layers,_=load_stack(args.fixture);del encoder;layer=layers[-1]
        device=next(model.model.layers[layer].parameters()).device
        add_lora(model,0,layer,rank=2 if args.fixture else 16,target_modules=MODULES)
        if not args.fixture:restore_adapter(model,args.source/'adapter')
        enable_lora(model,False);model.eval().requires_grad_(False)
        rows={s:read(s+'_rows.json') for s in ('discovery','selection','frozen')}
        inputs={s:prepare_inputs(model,tok,rs,plan['response_format']) for s,rs in rows.items()}
        control_rows=read('control_rows.json');control_inputs=prepare_inputs(model,tok,control_rows,plan['response_format'])
        trained={};metadata=dict(lock1['training']);choices={}
        for target,truth in plan['targets'].items():
            scope=lock1['choices'][target]['selected']['scope']
            q=probabilities(rows['discovery'],truth);qs=probabilities(rows['selection'],truth)
            for method in plan['methods']:
                for seed in plan['seeds']:
                    name=f'{target}_{method}_{scope}_seed{seed}'
                    old=torch.load(args.stage1/(name+'.pt'),map_location='cpu',weights_only=True)
                    ids=old['metadata']['features'];basis=None if method=='dense' else torch.linalg.qr(decoder[:,ids].to(device),mode='reduced').Q
                    refine_vector.name=name
                    vector,refinement=refine_vector(model,inputs['discovery'],inputs['selection'],q,qs,layer,scope,basis,old['vector'],seed,
                                                    steps=2 if args.fixture else amendment['extra_updates'],batch=plan['batch_size'])
                    info=dict(old['metadata'],**refinement)
                    if method!='dense':info['decoder_coefficients']=torch.linalg.lstsq(decoder[:,ids],vector).solution.tolist()
                    metadata[name]=info;trained[name]=vector
                    torch.save({'vector':vector,'metadata':info},root/(name+'.pt'))
                    for dose in plan['doses']:
                        save_json(root/f'selection_scores_{name}_rho{dose:g}.json',evaluate(model,inputs['selection'],layer,vector.to(device)*(dose/16),scope,batch=16))
                    log('refined_vector_finished',name=name)
            trials=[]
            for dose in plan['doses']:
                errors=[]
                for method in plan['methods']:
                    for seed in plan['seeds']:
                        name=f'{target}_{method}_{scope}_seed{seed}_rho{dose:g}'
                        scores=json.loads((root/f'selection_scores_{name}.json').read_text())
                        errors.append(rmse([s['p_risky'] for s in scores],qs))
                trials.append({'scope':scope,'dose':dose,'mean_rmse':float(np.mean(errors))})
            choices[target]={'selected':min(trials,key=lambda c:c['mean_rmse']),'all':trials}
        lock={'locked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'frozen_responses_opened':False,'choices':choices,'training':metadata,
              'stage1_frozen_results_used':False,'refinement_plan':amendment}
        save_json(root/'selection_lock.json',lock)
        gradient=torch.load(args.stage1/'readout_gradient.pt',weights_only=True)
        approx,ids,coefficients,error=sparse_match(decoder,gradient,min(10,decoder.shape[0]))
        save_json(root/'readout_geometry.json',{'features':ids,'coefficients':coefficients.tolist(),'relative_error':error})
        directions={'gradient':unit(gradient),'gradient_negative':-unit(gradient),'sae_gradient':unit(approx),
                    **{f'random{seed}':unit(torch.randn(gradient.shape,generator=torch.Generator().manual_seed(seed))) for seed in (19,41,89)}}
        conditions={'baseline':(False,None,'final'),'lora':(True,None,'final')}
        for target,choice in choices.items():
            scope=choice['selected']['scope'];dose=choice['selected']['dose']
            for method in plan['methods']:
                for seed in plan['seeds']:
                    name=f'{target}_{method}_{scope}_seed{seed}';conditions[name+f'_rho{dose:g}']=(False,trained[name].to(device)*(dose/16),scope)
            for name,vector in directions.items():conditions[f'{name}_{scope}_rho{dose:g}']=(False,vector.to(device)*dose,scope)
        # Fixed low-dose readout calibration was also declared before frozen inspection.
        for scope in plan['scopes']:
            for dose in (1.,4.):
                for name in ('gradient','gradient_negative','sae_gradient'):
                    conditions[f'{name}_{scope}_rho{dose:g}']=(False,directions[name].to(device)*dose,scope)
        torch.save({n:{'enabled':enabled,'vector':v.cpu() if v is not None else None,'scope':scope} for n,(enabled,v,scope) in conditions.items()},root/'locked_interventions.pt')
        for name,(enabled,vector,scope) in conditions.items():
            enable_lora(model,enabled);model.requires_grad_(False)
            for split,items in [('discovery',inputs['discovery']),('selection',inputs['selection']),('frozen',inputs['frozen']),('control',control_inputs)]:
                save_json(root/f'{split}_scores_{name}.json',evaluate(model,items,layer,vector,scope,batch=16))
            log('refined_frozen_condition_finished',name=name)
        report.update(status='fixture_completed' if args.fixture else 'completed',conditions=list(conditions),counts={s:len(rs) for s,rs in rows.items()},refined_vectors=len(trained))
    except Exception as error:
        report.update(status='failed_or_partial',error_type=type(error).__name__,error=str(error));raise
    finally:report['elapsed_seconds']=time.monotonic()-started;save_json(root/'run_status.json',report)


if __name__=='__main__':main()
