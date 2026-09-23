"""Layer-50 replay ablations and SAE compression of a saved preference adapter."""
import argparse
from contextlib import contextmanager
import datetime as dt
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import time

import numpy as np
import torch

from .core import hidden_of, replace_hidden
from .cpt import fit, probabilities
from .modeling import (add_lora, answer_logits, collate, enable_lora, load_stack,
                       prepare_inputs, restore_adapter, MODEL_REVISION, SAE_REVISION)
from .repair_design import MODULES
from .smoke import save_json
from .replay_plan import CONDITIONS


@contextmanager
def capture_full(model,layer):
    captured=[]
    def hook(_module,_inputs,output): captured.append(hidden_of(output).detach().clone())
    handle=model.model.layers[layer].register_forward_hook(hook)
    try: yield captured
    finally: handle.remove()


@contextmanager
def patch_full(model,layer,value,mask,replace=False):
    """Position masks are per-example; addition stays float32 until one cast."""
    def hook(_module,_inputs,output):
        hidden=hidden_of(output)
        if tuple(mask.shape)!=tuple(hidden.shape[:2]): raise ValueError('Mask/hidden shape mismatch')
        v=value.to(hidden.device)
        if v.shape!=hidden.shape and v.shape!=hidden.shape[-1:]: raise ValueError('Replay shape mismatch')
        candidate=v.to(hidden.dtype) if replace else (hidden.float()+v.float()).to(hidden.dtype)
        return replace_hidden(output,torch.where(mask.to(hidden.device).bool().unsqueeze(-1),candidate,hidden))
    handle=model.model.layers[layer].register_forward_hook(hook)
    try: yield
    finally: handle.remove()


def records(model,prepared):
    risky,safe,norm=answer_logits(model,prepared)
    margin=risky-safe; mass=(risky-norm).exp()+(safe-norm).exp()
    return [{'margin':float(m),'p_risky':float(p),'answer_mass':float(a)}
            for m,p,a in zip(margin.cpu(),margin.sigmoid().cpu(),mass.cpu())]


def encoder_delta(base,adapted,mask,decoder,encoder,chunk=128):
    """Decode differences of latents, preserving the original residual baseline."""
    w,b=encoder;out=torch.zeros_like(base,dtype=torch.float32)
    x=base[mask].float();y=adapted[mask].float();decoded=[]
    for start in range(0,len(x),chunk):
        z0=torch.relu(x[start:start+chunk]@w.T+b)
        z1=torch.relu(y[start:start+chunk]@w.T+b)
        decoded.append((z1-z0)@decoder.T)
    out[mask]=torch.cat(decoded);return out


def projection(delta,basis):
    return (delta.float()@basis)@basis.T


@torch.no_grad()
def evaluate_batch(model,prepared,layer,decoder,encoder,mean,bases):
    model.eval().requires_grad_(False);mask=collate(prepared)['attention_mask'].bool()
    enable_lora(model,False)
    with capture_full(model,layer) as b: baseline=records(model,prepared)
    enable_lora(model,True);model.requires_grad_(False)
    with capture_full(model,layer) as a: adapted_scores=records(model,prepared)
    enable_lora(model,False)
    base,adapted=b[0],a[0];mask=mask.to(base.device)
    delta=adapted.float()-base.float();final=torch.zeros_like(mask);final[:,-1]=True
    context=mask&~final
    output={'baseline':baseline,'lora':adapted_scores}
    def run(name,value,scope,replace=False):
        with patch_full(model,layer,value,scope,replace): output[name]=records(model,prepared)
    # Complete replacement includes padding states as an exact computation check.
    all_positions=torch.ones_like(mask)
    run('raw_all_replace',adapted,all_positions,True)
    run('raw_all_add',delta,all_positions)
    run('raw_final_replace',adapted,final,True)
    run('raw_context_replace',adapted,context,True)
    run('mean_final',mean,final);run('mean_final_norm1',mean/mean.norm(),final)
    encoded=encoder_delta(base,adapted,mask,decoder,encoder)
    run('sae_encoder_all',encoded,mask);run('sae_encoder_final',encoded,final)
    geometry={'raw_delta_norm_final':delta[:,-1].norm(dim=-1).cpu().tolist(),
              'encoded_relative_error_all':float((encoded[mask]-delta[mask]).norm()/delta[mask].norm()),
              'encoded_relative_error_final':float((encoded[:,-1]-delta[:,-1]).norm()/delta[:,-1].norm())}
    del encoded
    for k,basis in bases.items():
        projected=projection(delta,basis)
        run(f'sae_subspace{k}_all',projected,mask);run(f'sae_subspace{k}_final',projected,final)
        run(f'sae_mean{k}_final',projection(mean,basis),final)
        geometry[f'subspace{k}_relative_error_all']=float((projected[mask]-delta[mask]).norm()/delta[mask].norm())
        geometry[f'subspace{k}_relative_error_final']=float((projected[:,-1]-delta[:,-1]).norm()/delta[:,-1].norm())
    assert set(output)==set(CONDITIONS)
    return output,geometry


def identity_gate(scores,tolerance=1e-6):
    reference=np.array([r['p_risky'] for r in scores['lora']]);details={}
    for name in ('raw_all_replace','raw_all_add'):
        errors=np.abs(np.array([r['p_risky'] for r in scores[name]])-reference)
        details[name]={'max_probability_error':float(errors.max()),'passed':bool(errors.max()<=tolerance)}
    return {'passed':all(d['passed'] for d in details.values()),'tolerance':tolerance,'conditions':details}


def summarize(rows,scores,target):
    reference=np.array([r['p_risky'] for r in scores['lora']]);teacher=probabilities(rows,target);out={}
    for name,rs in scores.items():
        p=np.array([r['p_risky'] for r in rs]);rmse=float(np.sqrt(np.mean((p-reference)**2)))
        mass=min(r['answer_mass'] for r in rs)
        dom=[i for i,r in enumerate(rows) if r['dominant_option']]
        violations=sum((p[i]>.5)!=(rows[i]['dominant_option']=='risky') for i in dom)
        pairs={}
        for row,prob in zip(rows,p):pairs.setdefault(row['economic_id'],{})[row['risky_label']]=float(prob)
        gaps=[abs(pair['A']-pair['B']) for pair in pairs.values() if set(pair)=={'A','B'}]
        out[name]={'n':len(rs),'rmse_to_lora':rmse,'max_probability_error_to_lora':float(np.max(np.abs(p-reference))),
                   'teacher_probability_rmse':float(np.sqrt(np.mean((p-teacher)**2))),
                   'min_answer_mass':mass,'dominance_violations':int(violations),'dominance_n':len(dom),
                   'mean_answer_order_gap':float(np.mean(gaps)),'cpt_fit':fit(rows,p,starts=4),
                   'passed_provisional_reproduction':bool(rmse<=.01 and mass>=.99),
                   'frame_rmse_to_lora':{f:float(np.sqrt(np.mean((p[[i for i,r in enumerate(rows) if r['frame']==f]]-reference[[i for i,r in enumerate(rows) if r['frame']==f]])**2))) for f in ('gain','loss','mixed')}}
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--plan',type=Path,default=Path('anchor_pilot/outputs/replay-plan-v1'))
    p.add_argument('--source',type=Path,default=Path('anchor_pilot/replay-source'))
    p.add_argument('--fixture',action='store_true');p.add_argument('--batch-size',type=int,default=6)
    p.add_argument('--hf-token-name',default=None);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False);started=time.monotonic()
    plan=json.loads((args.plan/'manifest.json').read_text());rows=json.loads((args.plan/'rows.json').read_text())
    report={'status':'running','scientific_go_pivot':None,'fixture':args.fixture,'model_revision':MODEL_REVISION,'sae_revision':SAE_REVISION}
    save_json(args.output/'plan.json',plan);save_json(args.output/'rows.json',rows)
    source_dir=args.output/'execution_source';source_dir.mkdir()
    for f in Path(__file__).parent.glob('*.py'):shutil.copy2(f,source_dir/f.name)
    try:
        if not args.fixture:
            for name,expected in plan['source_hashes'].items():
                if hashlib.sha256((args.source/name).read_bytes()).hexdigest()!=expected:raise RuntimeError('Source artifact hash mismatch: '+name)
        model,tokenizer,decoder,encoder,layers,_=load_stack(args.fixture,args.hf_token_name);layer=layers[-1]
        save_json(args.output/'environment.json',{'torch':torch.__version__,
                  'packages':{n:importlib.metadata.version(n) for n in ('transformers','peft','accelerate','numpy','scipy')},
                  'gpus':[torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())],
                  'base_parameter_dtypes':sorted({str(p.dtype) for p in model.parameters()}),
                  'base_parameter_devices':sorted({str(p.device) for p in model.parameters()})})
        add_lora(model,0,layer,rank=2 if args.fixture else 16,target_modules=MODULES)
        if args.fixture:
            generator=torch.Generator().manual_seed(52)
            for name,param in model.named_parameters():
                if 'lora_B' in name:param.data.normal_(0,.07,generator=generator)
            mean=torch.randn(model.config.hidden_size,generator=generator)*.03
            indices={'10':list(range(10)),'30':list(range(30))}
        else:
            config=json.loads((args.source/'adapter/adapter_config.json').read_text())
            assert config['layers_to_transform']==list(range(51)) and config['r']==16 and set(config['target_modules'])==set(MODULES)
            restore_adapter(model,args.source/'adapter')
            mean=torch.load(args.source/'footprint.pt',map_location='cpu',weights_only=True)['delta_h'].float().mean(0)
            indices=plan['sparse_indices']
        device=next(model.model.layers[layer].parameters()).device
        decoder=decoder.to(device);encoder=tuple(x.to(device) for x in encoder);mean=mean.to(device)
        bases={k:torch.linalg.qr(decoder[:,ids],mode='reduced').Q for k,ids in indices.items()}
        save_json(args.output/'selection_lock.json',{'locked_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                  'conditions':CONDITIONS,'sparse_indices':indices,'mean_norm':float(mean.norm()),'frozen_responses_opened':False})
        torch.save({'mean':mean.cpu(),'bases':{k:v.cpu() for k,v in bases.items()}},args.output/'replay_vectors.pt')
        model.eval().requires_grad_(False)
        for split in ('selection','frozen'):
            subset=[r for r in rows if r['split']==split]
            if args.fixture:
                subset=sum(([r for r in subset if r['frame']==f][:2] for f in ('gain','loss','mixed')),[])
            prepared=prepare_inputs(model,tokenizer,subset,plan['response_format'])
            scores={name:[] for name in CONDITIONS};geometries=[]
            for start in range(0,len(subset),args.batch_size):
                result,geometry=evaluate_batch(model,prepared[start:start+args.batch_size],layer,decoder,encoder,mean,bases)
                for name in CONDITIONS:
                    scores[name].extend(result[name]);save_json(args.output/f'{split}_scores_{name}.json',scores[name])
                geometries.append({'offset':start,**geometry});save_json(args.output/f'{split}_geometry.json',geometries)
                print(json.dumps({'split':split,'completed':len(scores['baseline']),'total':len(subset),'elapsed':round(time.monotonic()-started,1)}),flush=True)
            gate=identity_gate(scores);report[split+'_identity']=gate
            save_json(args.output/f'{split}_rows.json',subset)
            if not gate['passed']:raise RuntimeError('Full-state replay identity failed; halt before further inference')
            if split=='frozen':
                report['summary']=summarize(subset,scores,plan['target'])
        report['status']='fixture_completed' if args.fixture else 'completed'
        report['condition_count']=len(CONDITIONS)
    except Exception as error:
        report['status']='failed_or_partial';report['error_type']=type(error).__name__;report['error']=str(error);raise
    finally:
        report['elapsed_seconds']=time.monotonic()-started;save_json(args.output/'report.json',report)


if __name__=='__main__':main()
