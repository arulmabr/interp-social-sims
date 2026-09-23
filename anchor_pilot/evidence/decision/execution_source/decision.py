"""Run the frozen decision protocol. No per-test adapter activations enter steering."""
import argparse
from contextlib import nullcontext, contextmanager
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import shutil
import time

import numpy as np
import torch
import torch.nn.functional as F

from .core import unit, sparse_match, hidden_of, replace_hidden
from .cpt import probabilities
from .decision_analysis import rmse
from .modeling import (load_stack,add_lora,restore_adapter,enable_lora,prepare_inputs,collate,
                       answer_logits,batch_readout_gradients,MODEL_REVISION,SAE_REVISION)
from .repair_design import MODULES
from .replay import patch_full
from .smoke import save_json


def log(event,**kwargs):print(json.dumps({'event':event,'utc':dt.datetime.now(dt.timezone.utc).isoformat(),**kwargs}),flush=True)


def mask_for(prepared,scope):
    mask=collate(prepared)['attention_mask'].bool()
    if scope=='final':mask[:,:-1]=False
    elif scope!='all':raise ValueError(scope)
    return mask


def sphere_vector(theta,basis,rho=16.):
    value=theta if basis is None else basis@theta
    return value*(rho/value.norm().clamp_min(1e-12))


@contextmanager
def traced_patch(model,layer,vector,mask,trace):
    def hook(_module,_inputs,output):
        hidden=hidden_of(output);active=mask.to(hidden.device)
        shifted=(hidden.float()+vector.to(hidden.device).float()).to(hidden.dtype)
        changed=shifted.float()-hidden.float();norms=changed.norm(dim=-1)
        requested=float(vector.norm())
        for i in range(len(hidden)):
            n=norms[i,active[i]]
            trace.append({'requested_norm_per_position':requested,'positions':int(active[i].sum()),
                          'mean_realized_norm':float(n.mean()),'total_realized_norm':float(n.square().sum().sqrt()),
                          'max_relative_norm_error':float((n/requested-1).abs().max())})
        return replace_hidden(output,torch.where(active.unsqueeze(-1),shifted,hidden))
    handle=model.model.layers[layer].register_forward_hook(hook)
    try:yield
    finally:handle.remove()


@torch.no_grad()
def evaluate(model,prepared,layer,vector=None,scope='final',batch=8):
    output=[]
    for start in range(0,len(prepared),batch):
        items=prepared[start:start+batch]
        trace=[]
        context=traced_patch(model,layer,vector,mask_for(items,scope),trace) if vector is not None else nullcontext()
        with context:r,s,n=answer_logits(model,items)
        output.extend({'p_risky':float(p),'margin':float(m),'answer_mass':float(a),
                       **({'norm':trace[i]} if trace else {})} for i,(p,m,a) in enumerate(zip((r-s).sigmoid().cpu(),(r-s).cpu(),((r-n).exp()+(s-n).exp()).cpu())))
    return output


def expected_ce(scores,target):
    p=np.clip([r['p_risky'] for r in scores],1e-8,1-1e-8)
    mass=np.clip([r['answer_mass'] for r in scores],1e-8,1.)
    return float(np.mean(-np.asarray(target)*np.log(p)-(1-np.asarray(target))*np.log1p(-p)-np.log(mass)))


def train_vector(model,prepared,selection,targets,selection_targets,layer,basis,initial,seed,steps,batch):
    generator=torch.Generator(device='cpu').manual_seed(seed)
    start=initial.clone() if basis is None else basis.T@initial
    start=start+.25*unit(torch.randn(start.shape,generator=generator)).to(start.device)
    theta=torch.nn.Parameter(start*(16/start.norm()))
    optimizer=torch.optim.Adam([theta],lr=.2/math.sqrt(theta.numel()))
    rng=np.random.default_rng(seed);best=None;history=[]
    for step in range(1,steps+1):
        indices=rng.choice(len(prepared),min(batch,len(prepared)),replace=False)
        items=[prepared[int(i)] for i in indices];vector=sphere_vector(theta,basis)
        with patch_full(model,layer,vector,mask_for(items,train_vector.scope)):
            risky,safe,normalizer=answer_logits(model,items)
            target=torch.as_tensor(targets[indices],device=risky.device,dtype=torch.float32)
            loss=(normalizer-target*risky-(1-target)*safe).mean()
        if not torch.isfinite(loss):raise RuntimeError('Nonfinite steering training loss')
        optimizer.zero_grad(set_to_none=True);loss.backward()
        if theta.grad is None or not torch.isfinite(theta.grad).all():raise RuntimeError('Missing/nonfinite steering gradient')
        optimizer.step()
        with torch.no_grad():theta.mul_(16/theta.norm())
        if step%40==0 or step==steps:
            vector=sphere_vector(theta,basis).detach()
            scores=evaluate(model,selection,layer,vector,train_vector.scope,batch)
            metric=expected_ce(scores,selection_targets)
            history.append({'step':step,'training_loss':float(loss.detach()),'selection_ce':metric,
                            'selection_rmse':rmse([r['p_risky'] for r in scores],selection_targets)})
            if best is None or metric<best[0]:best=(metric,vector.cpu().clone(),step)
            log('training_checkpoint',name=train_vector.name,**history[-1])
    return best[1],{'selected_step':best[2],'history':history,'seed':seed,'dimension':theta.numel()}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--plan',type=Path,default=Path('anchor_pilot/outputs/decision-plan-v2'))
    parser.add_argument('--source',type=Path,default=Path('anchor_pilot/replay-source'))
    parser.add_argument('--fixture',action='store_true');parser.add_argument('--resume',action='store_true')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=args.resume)
    plan=json.loads((args.plan/'manifest.json').read_text());rows=json.loads((args.plan/'rows.json').read_text())
    calibration=json.loads((args.plan/'calibration.json').read_text());assert calibration['passed']
    started=time.monotonic();report={'status':'running','fixture':args.fixture,'model_revision':MODEL_REVISION,'sae_revision':SAE_REVISION}
    save_json(args.output/'plan.json',plan);save_json(args.output/'rows.json',rows);save_json(args.output/'calibration.json',calibration)
    source=args.output/'execution_source';source.mkdir(exist_ok=True)
    for f in Path(__file__).parent.glob('*.py'):shutil.copy2(f,source/f.name)
    try:
        if not args.fixture:
            for name,sha in plan['source_hashes'].items():assert hashlib.sha256((args.source/name).read_bytes()).hexdigest()==sha,name
        model,tokenizer,decoder,encoder,layers,fixture_features=load_stack(args.fixture);layer=layers[-1]
        del encoder
        device=next(model.model.layers[layer].parameters()).device
        save_json(args.output/'environment.json',{'torch':torch.__version__,'gpus':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
                   'base_dtypes':sorted({str(p.dtype) for p in model.parameters()}),'base_devices':sorted({str(p.device) for p in model.parameters()})})
        add_lora(model,0,layer,rank=2 if args.fixture else 16,target_modules=MODULES)
        if not args.fixture:restore_adapter(model,args.source/'adapter')
        enable_lora(model,False);model.eval().requires_grad_(False)
        subsets={split:[r for r in rows if r['split']==split] for split in ('discovery','selection','frozen')}
        if args.fixture:subsets={s:rs[:4] for s,rs in subsets.items()}
        prepared={s:prepare_inputs(model,tokenizer,rs,plan['response_format']) for s,rs in subsets.items()}
        control_rows=json.loads((args.plan/'controls.json').read_text())
        if args.fixture:control_rows=control_rows[:4]
        controls=prepare_inputs(model,tokenizer,control_rows,plan['response_format']);save_json(args.output/'control_rows.json',control_rows)
        for split,rs in subsets.items():save_json(args.output/f'{split}_rows.json',rs)
        targets={name:{s:probabilities(rs,target) for s,rs in subsets.items()} for name,target in plan['targets'].items()}
        batch=16;features=fixture_features if args.fixture else plan['candidate_features']
        k=min(plan['sparse_k'],len(features));steps=2 if args.fixture else plan['updates']
        # Common baselines and the independent adapter; frozen prompts remain unread.
        for enabled,name in ((False,'baseline'),(True,'lora')):
            enable_lora(model,enabled);model.requires_grad_(False)
            for split in ('discovery','selection'):
                path=args.output/f'{split}_scores_{name}.json'
                if not path.exists():save_json(path,evaluate(model,prepared[split],layer,batch=batch))
            log('baseline_finished',name=name)
        enable_lora(model,False);model.requires_grad_(False)
        # Raw prompt gradients are averaged before normalization.
        grad_path=args.output/'readout_gradient.pt'
        if grad_path.exists():gradient=torch.load(grad_path,weights_only=True)
        else:
            chunks=[batch_readout_gradients(model,prepared['discovery'][s:s+batch],layer) for s in range(0,len(prepared['discovery']),batch)]
            gradient=torch.cat(chunks).mean(0);torch.save(gradient,grad_path)
        log('gradient_ready',norm=float(gradient.norm()))
        candidates=decoder[:,features].to(device)
        screen_path=args.output/'causal_screen.json'
        if screen_path.exists():screen=json.loads(screen_path.read_text())
        else:screen=[]
        done={(r['scope'],r['feature'],r['sign']) for r in screen}
        for scope in plan['scopes']:
            for i,feature in enumerate(features):
                for sign in (-1,1):
                    if (scope,feature,sign) in done:continue
                    scores=evaluate(model,prepared['discovery'],layer,sign*16*unit(candidates[:,i]).to(device),scope,batch)
                    entry={'scope':scope,'feature':feature,'sign':sign,
                           'cosine_to_readout':float(F.cosine_similarity(candidates[:,i].cpu(),gradient,dim=0)),
                           'target_ce':{name:expected_ce(scores,values['discovery']) for name,values in targets.items()},
                           'target_rmse':{name:rmse([r['p_risky'] for r in scores],values['discovery']) for name,values in targets.items()},
                           'scores':scores}
                    screen.append(entry);save_json(screen_path,screen)
                log('feature_screen',scope=scope,feature=feature,completed=i+1,total=len(features))
        mean=torch.randn(model.config.hidden_size) if args.fixture else torch.load(args.source/'footprint.pt',weights_only=True,map_location='cpu')['delta_h'].float().mean(0)
        mean=16*unit(mean).to(device)
        trained={};metadata={}
        for target in plan['targets']:
            for scope in plan['scopes']:
                ranking=sorted(features,key=lambda f:min(e['target_ce'][target] for e in screen if e['scope']==scope and e['feature']==f))
                ids=ranking[:k];basis=torch.linalg.qr(decoder[:,ids].to(device),mode='reduced').Q
                for method in plan['methods']:
                    for seed in plan['seeds']:
                        name=f'{target}_{method}_{scope}_seed{seed}';path=args.output/(name+'.pt')
                        if path.exists():data=torch.load(path,map_location='cpu',weights_only=True);vector=data['vector'];info=data['metadata']
                        else:
                            train_vector.scope=scope;train_vector.name=name
                            vector,info=train_vector(model,prepared['discovery'],prepared['selection'],targets[target]['discovery'],targets[target]['selection'],layer,
                                                     None if method=='dense' else basis,mean,seed,steps,plan['batch_size'])
                            info.update(target=target,scope=scope,method=method,features=ids if method!='dense' else None)
                            if method!='dense':info['decoder_coefficients']=torch.linalg.lstsq(decoder[:,ids],vector).solution.tolist()
                            torch.save({'vector':vector,'metadata':info},path)
                        trained[name]=vector;metadata[name]=info
                        for dose in plan['doses']:
                            out=args.output/f'selection_scores_{name}_rho{dose:g}.json'
                            if not out.exists():save_json(out,evaluate(model,prepared['selection'],layer,(dose/16)*vector.to(device),scope,batch))
                        log('vector_finished',name=name)
        # Select matched scope and dose JOINTLY for dense/SAE per target, using both seeds.
        # This prevents a sparse-vs-dense difference being a token or norm difference.
        lock={'locked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),'frozen_responses_opened':False,'choices':{},'training':metadata}
        for target in plan['targets']:
            choices=[]
            for scope in plan['scopes']:
                for dose in plan['doses']:
                    values=[]
                    for method in plan['methods']:
                        for seed in plan['seeds']:
                            name=f'{target}_{method}_{scope}_seed{seed}_rho{dose:g}'
                            rs=json.loads((args.output/f'selection_scores_{name}.json').read_text())
                            values.append(rmse([r['p_risky'] for r in rs],targets[target]['selection']))
                    choices.append({'scope':scope,'dose':dose,'mean_rmse':float(np.mean(values))})
            lock['choices'][target]={'selected':min(choices,key=lambda x:x['mean_rmse']),'all':choices}
        save_json(args.output/'selection_lock.json',lock)
        # SAE readout approximation is geometric by design; preference selection above is causal.
        approx,ids,coefficients,error=sparse_match(decoder,gradient,min(10,decoder.shape[0]))
        geometry={'features':ids,'coefficients':coefficients.tolist(),'relative_error':error}
        save_json(args.output/'readout_geometry.json',geometry)
        randoms={f'random{seed}':unit(torch.randn(gradient.shape,generator=torch.Generator().manual_seed(seed))) for seed in (19,41,89)}
        directions={'gradient':unit(gradient),'sae_gradient':unit(approx),**randoms}
        conditions={'baseline':(False,None,'final'),'lora':(True,None,'final')}
        for target,choice in lock['choices'].items():
            scope=choice['selected']['scope'];dose=choice['selected']['dose']
            for method in plan['methods']:
                for seed in plan['seeds']:
                    name=f'{target}_{method}_{scope}_seed{seed}'
                    conditions[name+f'_rho{dose:g}']=(False,trained[name].to(device)*(dose/16),scope)
            for name,vec in directions.items():
                conditions[f'{name}_{scope}_rho{dose:g}']=(False,vec.to(device)*dose,scope)
            conditions[f'gradient_negative_{scope}_rho{dose:g}']=(False,-directions['gradient'].to(device)*dose,scope)
        torch.save({name:{'enabled':enabled,'vector':vec.cpu() if vec is not None else None,'scope':scope} for name,(enabled,vec,scope) in conditions.items()},args.output/'locked_interventions.pt')
        for name,(enabled,vector,scope) in conditions.items():
            enable_lora(model,enabled);model.requires_grad_(False)
            for split,items in [('selection',prepared['selection']),('frozen',prepared['frozen']),('control',controls)]:
                path=args.output/f'{split}_scores_{name}.json'
                if not path.exists():save_json(path,evaluate(model,items,layer,vector,scope,batch))
            log('frozen_condition_finished',name=name)
        report.update(status='fixture_completed' if args.fixture else 'completed',conditions=list(conditions),counts={s:len(rs) for s,rs in subsets.items()})
    except Exception as error:
        report.update(status='failed_or_partial',error_type=type(error).__name__,error=str(error));raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started;save_json(args.output/'run_status.json',report)


if __name__=='__main__':main()
