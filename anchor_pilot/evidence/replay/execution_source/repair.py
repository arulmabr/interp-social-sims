"""Bounded repair experiment: format calibration, stronger CPT LoRA, fresh test.

The original pilot is immutable. Frozen model responses are not read until
validation targets pass and every comparison direction and dose is locked.
"""
import argparse
from dataclasses import asdict
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import time

import numpy as np
import torch

from .core import sparse_match, unit
from .cpt import probabilities
from .design import AGENTS, digest
from .modeling import (add_lora, batched_answer_loss, batch_readout_gradients,
                       enable_lora, load_stack, prepare_inputs, restore_adapter, save_adapter)
from .pilot import evaluate, footprint, probe_direction
from .repair_design import FORMATS, MODULES, build_repair_rows, recovery_check
from .smoke import gpu_memory, save_json


def full_ce(records, target):
    p=np.clip([r['p_risky'] for r in records],1e-7,1-1e-7)
    mass=np.clip([r['answer_mass'] for r in records],1e-12,1)
    return float(np.mean(-target*np.log(p)-(1-target)*np.log1p(-p)-np.log(mass)))


def valid(records, minimum=.95, tolerance=.02):
    errors=[abs(r['actual_norm']/r['requested_norm']-1) for r in records if r.get('requested_norm',0)>0]
    return {'passed':bool(min(r['answer_mass'] for r in records)>=minimum and max(errors,default=0)<=tolerance),
            'min_answer_mass':min(r['answer_mass'] for r in records),
            'answer_mass_failure_count':sum(r['answer_mass']<minimum for r in records),
            'max_relative_norm_error':max(errors,default=None)}


def paired_batches(rows, micro_batch, accumulation, updates, seed=812):
    """Yield frame-balanced economic scenarios, each with both answer orders."""
    if micro_batch%2:raise ValueError('Micro-batch must contain paired orders')
    groups={}
    for i,row in enumerate(rows):
        if row['split']=='discovery':groups.setdefault((row['frame'],row['economic_id']),[]).append(i)
    assert all(len(indices)==2 and {rows[i]['risky_label'] for i in indices}=={'A','B'} for indices in groups.values())
    by_frame={frame:[indices for (name,_),indices in groups.items() if name==frame] for frame in ('gain','loss','mixed')}
    rng=np.random.default_rng(seed);counter=0
    for _ in range(updates):
        micros=[]
        for _ in range(accumulation):
            indices=[]
            for _ in range(micro_batch//2):
                frame=('gain','loss','mixed')[counter%3];counter+=1
                choices=by_frame[frame];indices.extend(choices[int(rng.integers(len(choices)))])
            micros.append(indices)
        yield micros


def run(args):
    torch.set_num_threads(8)
    args.output.mkdir(exist_ok=False,parents=True)
    start=time.monotonic();deadline=start+args.max_seconds
    rows=build_repair_rows(True) if args.fixture else json.loads((args.plan/'rows.json').read_text())
    plan=json.loads((args.plan/'manifest.json').read_text())
    if not args.fixture and digest(rows)!=plan['rows_sha256']:raise RuntimeError('Frozen repair design hash mismatch')
    report={'status':'started','fixture':args.fixture,'scientific_go_pivot':None,
            'frozen_responses_opened':False,'rows_sha256':digest(rows),'plan':plan,
            'source_sha256':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')},
            'started_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()}
    save_json(args.output/'rows.json',rows);save_json(args.output/'plan.json',plan)
    source=args.output/'execution_source';source.mkdir()
    for p in Path(__file__).parent.glob('*.py'):(source/p.name).write_bytes(p.read_bytes())
    def check_time(reserve=0):
        if time.monotonic()+reserve>deadline:raise TimeoutError('Repair time budget exhausted; artifacts preserved')
    def score(inputs, **kwargs):
        check_time();return evaluate(model,inputs,args.batch_size,**kwargs)
    def save_stage():save_json(args.output/'report.json',report)
    try:
        model,tokenizer,decoder,encoder,layers,features=load_stack(args.fixture,args.hf_token_name)
        selection=[i for i,r in enumerate(rows) if r['split']=='selection']
        frozen=[i for i,r in enumerate(rows) if r['split']=='frozen']
        calibration=[i for i,r in enumerate(rows) if r['split']=='discovery' and
                     (args.fixture or (r['ratio'] in (.4,1.8,3.6,6.8) and r['stake'] in (25,75)))]
        save_json(args.output/'calibration_rows.json',[rows[i] for i in calibration])
        formats=[];prepared_formats={}
        for spec in FORMATS[:1] if args.fixture else FORMATS:
            prepared=prepare_inputs(model,tokenizer,rows,spec);prepared_formats[spec['name']]=prepared
            records,_=score([prepared[i] for i in calibration])
            save_json(args.output/f'format_{spec["name"]}.json',records)
            formats.append({'spec':spec,**valid(records,.99)})
        report['format_baselines']=formats;save_stage()
        eligible=sorted([f for f in formats if f['passed'] or args.fixture],key=lambda x:x['min_answer_mass'],reverse=True)
        trials=[];chosen=None;g={};rho=None
        for candidate in eligible:
            prepared=prepared_formats[candidate['spec']['name']];subset=[prepared[i] for i in calibration]
            gradients={layer:unit(torch.cat([batch_readout_gradients(model,subset[j:j+args.batch_size],layer)
                                            for j in range(0,len(subset),args.batch_size)]).mean(0)) for layer in layers}
            for dose in ([1.] if args.fixture else plan['rho_grid_descending']):
                results=[]
                for layer,gradient in gradients.items():
                    for sign in (-1,1):
                        records,_=score(subset,direction=sign*gradient,layer=layer,rho=dose)
                        results.append({'layer':layer,'sign':sign,**valid(records)})
                trials.append({'format':candidate['spec']['name'],'rho':dose,'conditions':results})
                if all(r['passed'] for r in results) or args.fixture:
                    chosen=candidate['spec'];g=gradients;rho=dose;break
            if chosen:break
        report['format_dose_trials']=trials
        if chosen is None:
            report['status']='format_calibration_failed';return
        report.update(response_format=chosen,pretraining_rho=rho)
        prepared=prepared_formats[chosen['name']];del prepared_formats
        train_inputs=[prepared[i] for i in calibration];val_inputs=[prepared[i] for i in selection]
        val_base,_=score(val_inputs);save_json(args.output/'selection_baseline.json',val_base)
        validation=[{'condition':'baseline',**valid(val_base,.99)}]
        for layer,gradient in g.items():
            for sign in (-1,1):
                records,_=score(val_inputs,direction=sign*gradient,layer=layer,rho=rho)
                validation.append({'condition':f'gradient_l{layer}_{sign}',**valid(records)})
        report['format_validation']=validation;save_stage()
        if not all(r['passed'] for r in validation) and not args.fixture:
            report['status']='format_validation_failed';return
        # Exact zero-dose identity in the selected format and standard batch.
        before,_=score(train_inputs[:args.batch_size]);zero,_=score(train_inputs[:args.batch_size],direction=torch.zeros_like(g[layers[-1]]),layer=layers[-1],rho=0)
        report['zero_dose_exact']=all(all(a[k]==b[k] for k in ('margin','p_risky','answer_mass')) for a,b in zip(before,zero))
        if not report['zero_dose_exact']:raise RuntimeError('Zero-dose identity failed')
        config=add_lora(model,0,layers[-1],rank=2 if args.fixture else 16,target_modules=MODULES)
        trainable=[p for p in model.parameters() if p.requires_grad]
        report['trainable_parameters']=sum(p.numel() for p in trainable)
        optimizer=torch.optim.AdamW(trainable,lr=.0001,weight_decay=.01)
        target=probabilities(rows,AGENTS['combined'])
        max_updates=args.fixture_steps if args.fixture else plan['training']['max_updates']
        micro=2 if args.fixture else plan['training']['micro_batch']
        accumulation=1 if args.fixture else plan['training']['accumulation']
        cadence=1 if args.fixture else plan['training']['checkpoint_every']
        history=[];best=(2,float('inf'));best_metrics=None;best_step=None;consecutive=0
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant':False})
        for step,micros in enumerate(paired_batches(rows,micro,accumulation,max_updates),1):
            if time.monotonic()>deadline-args.reserve_seconds:break
            model.train();optimizer.zero_grad(set_to_none=True)
            warm=1 if args.fixture else min(1,step/50)
            progress=max(0,(step-50)/max(1,max_updates-50))
            lr=warm*(.00001+.00009*(1+math.cos(math.pi*progress))/2)
            for group in optimizer.param_groups:group['lr']=lr
            losses=[]
            for indices in micros:
                loss=batched_answer_loss(model,[prepared[i] for i in indices],target[indices])
                if not torch.isfinite(loss):raise RuntimeError('Nonfinite training loss')
                (loss/accumulation).backward();losses.append(float(loss.detach()))
            if step==1:
                if any(p.grad is not None for n,p in model.named_parameters() if 'lora_' not in n):raise RuntimeError('Frozen base received gradients')
                devices={str(p.device) for p in trainable}
                report['first_step_gradient_norm_by_device']={device:sum(float(p.grad.float().norm()) for p in trainable if str(p.device)==device and p.grad is not None) for device in devices}
                if not all(v>0 for v in report['first_step_gradient_norm_by_device'].values()):raise RuntimeError('An adapter partition received no gradient')
            grad=float(torch.nn.utils.clip_grad_norm_(trainable,1.))
            if not math.isfinite(grad):raise RuntimeError('Nonfinite adapter gradient')
            optimizer.step()
            row={'step':step,'loss':float(np.mean(losses)),'learning_rate':lr,'gradient_norm':grad};history.append(row)
            if step==1 or step%cadence==0 or step==max_updates:
                model.eval()
                val_scores,_=score(val_inputs);metric=recovery_check([rows[i] for i in selection],val_scores)
                ce=full_ce(val_scores,target[selection]);metric['full_vocab_ce']=ce
                audit_scores,_=score(train_inputs);train_metric=recovery_check([rows[i] for i in calibration],audit_scores)
                row.update(selection=metric,training_audit=train_metric)
                rank=(0 if metric['passed_operational_recovery_target'] else 1,ce)
                if rank<best:
                    best=rank;best_metrics=metric;best_step=step;save_adapter(model,config,args.output/'adapter')
                    save_json(args.output/'selection_best_scores.json',val_scores)
                consecutive=consecutive+1 if metric['passed_operational_recovery_target'] else 0
                save_json(args.output/'training.json',{'history':history,'best_step':best_step,'best_selection':best_metrics,
                           'training_split':'discovery only','frozen_rows_used':0})
                print(f'Repair step {step}/{max_updates}; selection RMSE={metric["teacher_probability_rmse"]:.4f}; recovered={metric["passed_operational_recovery_target"]}',flush=True)
                if step>=400 and consecutive>=2:break
        del optimizer
        if best_metrics is None:report['status']='training_window_exhausted';return
        restore_adapter(model,args.output/'adapter');model.eval().requires_grad_(False);model.gradient_checkpointing_disable()
        report.update(best_step=best_step,selected_validation=best_metrics,completed_updates=history[-1]['step'])
        if not best_metrics['passed_operational_recovery_target'] and not args.fixture:
            report['status']='validation_recovery_failed';return
        # All downstream selection still uses discovery or selection data only.
        enable_lora(model,False);_,base_hidden=score(train_inputs,layers=layers)
        enable_lora(model,True);model.eval().requires_grad_(False);_,adapted=score(train_inputs,layers=[layers[-1]])
        raw,native,info,delta=footprint(encoder,decoder,base_hidden[layers[-1]],adapted[layers[-1]],[1,3,10])
        torch.save({'delta_h':delta,'base':base_hidden[layers[-1]],'prompt_ids':[rows[i]['id'] for i in calibration]},args.output/'footprint.pt')
        enable_lora(model,False)
        directions={}
        for layer,gradient in g.items():
            for sign in (-1,1):directions[f'gradient_l{layer}_sign{sign:+d}']=(layer,sign*gradient)
            generator=torch.Generator().manual_seed(1000+layer);random=unit(torch.randn(len(gradient),generator=generator))
            for sign in (-1,1):directions[f'random_l{layer}_sign{sign:+d}']=(layer,sign*random)
        reward_labels=np.array([rows[i]['ratio']>=2.1 for i in calibration],float)
        if args.fixture:reward_labels=np.arange(len(calibration))%2
        probe,probe_info=probe_direction(base_hidden[layers[0]],reward_labels)
        for sign in (-1,1):directions[f'reward_probe_l{layers[0]}_sign{sign:+d}']=(layers[0],sign*probe)
        for feature in features:directions[f'feature_{feature}']=(layers[-1],unit(decoder[:,feature]))
        directions['creativity_triple']=(layers[-1],unit(decoder[:,features[3:]].sum(1)))
        decoded,indices,coefficients,error=sparse_match(decoder,g[layers[-1]],10)
        for sign in (-1,1):directions[f'sae_readout_k10_sign{sign:+d}']=(layers[-1],sign*unit(decoded))
        directions['mean_delta']=(layers[-1],raw)
        for k,(vector,_) in native.items():directions[f'sae_preference_k{k}']=(layers[-1],vector)
        report.update(footprint=info,reward_probe=probe_info,readout_sparse={'indices':indices,'coefficients':coefficients.tolist(),'relative_error':error})
        # Recalibrate one common norm against EVERY planned additive direction.
        dose_trials=[];common_rho=None
        for dose in ([1.] if args.fixture else [d for d in plan['rho_grid_descending'] if d<=rho]):
            diagnostics=[]
            for name,(layer,vector) in directions.items():
                scores,_=score(val_inputs,direction=vector,layer=layer,rho=dose)
                diagnostic={'condition':name,**valid(scores)};diagnostics.append(diagnostic)
                if not diagnostic['passed'] and not args.fixture:break
            dose_trials.append({'rho':dose,'conditions':diagnostics})
            if (len(diagnostics)==len(directions) and all(d['passed'] for d in diagnostics)) or args.fixture:
                common_rho=dose;break
        report['all_direction_dose_validation']=dose_trials
        if common_rho is None:report['status']='steering_calibration_failed';return
        report['common_rho']=common_rho
        report['directions']={name:{'layer':layer,'cosine_readout':float(vector@g[layer])} for name,(layer,vector) in directions.items()}
        save_json(args.output/'selection_lock.json',{**report,'locked_at_utc':dt.datetime.now(dt.timezone.utc).isoformat()})
        torch.save({name:{'layer':layer,'vector':vector} for name,(layer,vector) in directions.items()},args.output/'directions.pt')
        # First access to any frozen MODEL response is below this point.
        report['frozen_responses_opened']=True;test_inputs=[prepared[i] for i in frozen]
        save_json(args.output/'frozen_rows.json',[rows[i] for i in frozen])
        base_scores,_=score(test_inputs);save_json(args.output/'scores_baseline.json',base_scores)
        enable_lora(model,True);model.eval().requires_grad_(False)
        scores,_=score(test_inputs);save_json(args.output/'scores_lora_combined.json',scores)
        report['frozen_recovery']=recovery_check([rows[i] for i in frozen],scores)
        enable_lora(model,False);format_checks=[{'condition':'baseline',**valid(base_scores,.99)}]
        for name,(layer,vector) in directions.items():
            print('Frozen repair comparison: '+name,flush=True)
            scores,_=score(test_inputs,direction=vector,layer=layer,rho=common_rho)
            save_json(args.output/f'scores_{name}.json',scores);format_checks.append({'condition':name,**valid(scores)})
        magnitudes=[('mean_delta',raw,info['mean_delta_norm'])]
        magnitudes +=[(f'sae_preference_k{k}',vector,meta['decoded_norm']) for k,(vector,meta) in native.items()]
        for name,vector,magnitude in magnitudes:
            scores,_=score(test_inputs,direction=vector,layer=layers[-1],rho=magnitude)
            save_json(args.output/f'scores_{name}_fitted_magnitude.json',scores)
        report['frozen_format_checks']=format_checks
        report['operational_repair_passed']=bool(not args.fixture and report['frozen_recovery']['passed_operational_recovery_target'] and all(c['passed'] for c in format_checks))
        report['condition_count']=len(list(args.output.glob('scores_*.json')))
        report['status']='fixture_completed' if args.fixture else 'completed'
    except Exception as error:
        report['status']='failed_or_partial';report['error_type']=type(error).__name__;raise
    finally:
        report['elapsed_seconds']=time.monotonic()-start;report['gpu_memory']=gpu_memory();save_stage()
        print(json.dumps({'status':report['status'],'output':str(args.output),'frozen_responses_opened':report['frozen_responses_opened']}),flush=True)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan',type=Path,default=Path('anchor_pilot/outputs/repair-plan-v1'))
    p.add_argument('--output',type=Path,required=True);p.add_argument('--fixture',action='store_true')
    p.add_argument('--fixture-steps',type=int,default=4);p.add_argument('--hf-token-name')
    p.add_argument('--batch-size',type=int,default=8);p.add_argument('--max-seconds',type=int,default=6000)
    p.add_argument('--reserve-seconds',type=int,default=1800);args=p.parse_args();run(args)


if __name__=='__main__':main()
