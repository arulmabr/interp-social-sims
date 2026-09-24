"""Extract immutable original rendered prompts, controllers and historical outcomes."""
import argparse
import ast
import csv
import json
import re
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path

from label_pilot.common import MODEL, MODEL_REVISION, SAE, SAE_REVISION, LAYER
from .common import ROOT, write, append, digest, file_hash

CONFIGS = {
    'lottery': ('safe_risky/results_20251008_225522','safe_risky','safe_risky_choice',
                ['baseline','barely_prompting','slightly_prompting','lite_steering','steering'],list(range(10,181,5))),
    'ultimatum': ('ultimatum/results_20251008_201139','ultimatum','ultimatum_response',
                 ['baseline','prompting','steering'],list(range(10,91,5))),
}


def extract_controller(value):
    if not value: return [],{}
    try: controller=json.loads(value)
    except ValueError: controller=ast.literal_eval(value)
    if not isinstance(controller,dict): raise ValueError('Unexpected controller')
    edits=[]
    for intervention in controller.get('interventions',[]):
        if intervention['mode']!='nudge': raise ValueError('Expected original additive nudge')
        for f in intervention['features']['features']:
            edits.append(dict(feature_id=int(f['index_in_sae']),delta=float(intervention['value']),
                              label=f['label'],uuid=f['uuid'],declared_max_activation_strength=f.get('max_activation_strength')))
    return edits,{'scopes':controller.get('scopes',[]),'nonzero_strength_threshold':controller.get('nonzero_strength_threshold')}


def prepare(output):
    output=Path(output)
    if output.exists(): raise FileExistsError('Plans are immutable; choose a fresh directory')
    output.mkdir(parents=True)
    rows=[];history=[];source_files={};cells=Counter();settings=defaultdict(set);controllers={}
    for game,(folder,prefix,question,conditions,values) in CONFIGS.items():
        source=ROOT.parent/'SAE/data/raw/games'/folder
        for condition in conditions:
            for value in values:
                p=source/f'{prefix}_{condition}_{value}.csv'
                originals=list(csv.DictReader(p.open(newline='')))
                if len(originals)!=40: raise ValueError(f'Expected 40 rows in {p}')
                source_files[str(p.relative_to(ROOT.parent))]=file_hash(p)
                for i,row in enumerate(originals):
                    edits,controller_meta=extract_controller(row.get('model.controller',''))
                    if bool(edits)!=('steering' in condition): raise ValueError('Controller/condition mismatch')
                    if row['model.model']!=MODEL: raise ValueError('Original model mismatch')
                    generation={k:float(row['model.'+k]) for k in ('temperature','top_p','frequency_penalty','presence_penalty')}
                    generation['max_new_tokens']=int(row['model.max_tokens'])
                    if generation!={'temperature':.5,'top_p':1.,'frequency_penalty':0.,'presence_penalty':0.,'max_new_tokens':1000}:
                        raise ValueError(f'Unexpected generation configuration: {generation}')
                    system=row['prompt.'+question+'_system_prompt'];user=row['prompt.'+question+'_user_prompt']
                    if not system or not user: raise ValueError('Missing original rendered prompts')
                    rid=f'{game}:{condition}:{value}:{i}'
                    record=dict(id=rid,game=game,condition=condition,value=value,agent_index=i,
                                source_file=str(p.relative_to(ROOT.parent)),source_row=i,
                                system_prompt=system,user_prompt=user,edits=edits,controller_metadata=controller_meta,
                                generation=generation)
                    rows.append(record);cells[(game,condition,value)]+=1
                    history.append(dict(id=rid,game=game,condition=condition,value=value,agent_index=i,
                        original_answer=row['answer.'+question],original_response=row['generated_tokens.'+question+'_generated_tokens']))
                    settings[game].add(json.dumps(generation,sort_keys=True))
                    key=f'{game}:{condition}';sig=digest([edits,controller_meta])
                    if key in controllers and controllers[key]['hash']!=sig: raise ValueError('Controller changed within condition')
                    controllers[key]=dict(hash=sig,edits=edits,metadata=controller_meta)
    # Baseline and SAE arms must have exactly the same original prompt for each trial.
    lookup={(r['game'],r['condition'],r['value'],r['agent_index']):r for r in rows}
    for row in rows:
        if not row['edits']: continue
        base=lookup[(row['game'],'baseline',row['value'],row['agent_index'])]
        for k in ('system_prompt','user_prompt'):
            if row[k]!=base[k]: raise ValueError(f'Steering prompt differs from baseline: {row["id"]}')
    with sqlite3.connect(f'file:{ROOT.parent}/label_pilot/outputs/plan-v3/catalog.sqlite?mode=ro',uri=True) as db:
        for row in rows:
            for edit in row['edits']:
                fid,uuid,label=db.execute('select feature_id,uuid,label from features where feature_id=?',(edit['feature_id'],)).fetchone()
                if uuid.replace('-','')!=edit['uuid'].replace('-','') or label!=edit['label']:
                    raise ValueError('Supplied catalog/controller identity mismatch')
    for filename,values in [('requests.jsonl',rows),('historical.jsonl',history)]:
        (output/filename).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n'for r in values))
    plan=dict(schema=1,model=MODEL,model_revision=MODEL_REVISION,sae=SAE,sae_revision=SAE_REVISION,layer=LAYER,
        model_precision='bfloat16',sae_precision='float32',batch_size=8,seed=20260924,
        edit_rule='Add supplied nudge value in raw released-SAE units; clip latent below at zero; preserve reconstruction residual.',
        hosted_equivalence='Not established: historical server-side scaling, exact checkpoint, token scope and inference backend remain unavailable.',
        scope='Last token of each forward pass, including first-answer prefill and subsequent generation.',
        response_policy='Preserve full original prompts and temperature=.5/top_p=1/max_new_tokens=1000. Parse an explicit first-line answer. One documented local repair prompt for invalid answers; original EDSL repair wording is not available.',
        quantities=dict(Counter(r['game']for r in rows)),conditions={g:c[3]for g,c in CONFIGS.items()},
        request_count=len(rows),requests_sha256=file_hash(output/'requests.jsonl'),historical_sha256=file_hash(output/'historical.jsonl'),
        source_files=source_files,controllers=controllers,
        analysis='Acceptance/risky-choice curves by offer/reward; matched local conditions; historical hosted curves shown separately. Invalid responses remain in denominator. No human-population or stable-trait inference.',
        deviations=['Public BF16 checkpoint and raw-unit additive strength are explicit local choices, not verified equivalents to the historical hosted backend.',
                    'Historical random seeds were not recorded; local batch seeds and batching are fixed and recorded.',
                    'Reprompt template explicitly documented locally; report first-attempt invalidity and repaired outcomes separately.'])
    plan['plan_hash']=digest(plan);write(output/'plan.json',plan)
    write(output/'source-audit.json',dict(requests=len(rows),historical_rows=len(history),cells=len(cells),
        all_cells_have_40=all(n==40 for n in cells.values()),steering_prompts_identical_to_baseline=True,
        original_features=[184,4237,31935],source_files=len(source_files),generation_settings={g:list(s)for g,s in settings.items()}))
    print(json.dumps(dict(output=str(output),plan_hash=plan['plan_hash'],requests=len(rows),by_game=plan['quantities']),indent=2))
    return plan


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',required=True);args=p.parse_args();prepare(args.output)
