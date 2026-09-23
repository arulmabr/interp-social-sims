"""Freeze a diagnostic replay experiment; no new adapter training or feature search."""
import argparse
import copy
import datetime as dt
import hashlib
import json
from pathlib import Path

from .cpt import fit, identifiability, probabilities
from .design import AGENTS, build_rows, digest, render
from .repair_design import build_repair_rows, SYSTEM
from .smoke import save_json
from dataclasses import asdict

SOURCE = Path('anchor_pilot/outputs/repair-backup-20260917/outputs/repair-20260917T062148Z')
RATIOS = [.47, 1.13, 1.93, 3.07, 4.93, 7.73]
CONDITIONS = ['baseline', 'lora', 'raw_all_replace', 'raw_all_add',
              'raw_final_replace', 'raw_context_replace', 'mean_final', 'mean_final_norm1',
              'sae_encoder_all', 'sae_encoder_final', 'sae_subspace10_all',
              'sae_subspace10_final', 'sae_subspace30_all', 'sae_subspace30_final',
              'sae_mean10_final', 'sae_mean30_final']


def build_replay_rows():
    repair = build_repair_rows()
    development = [copy.deepcopy(r) for r in repair if r['split']=='selection'
                   and r['stake']==25 and r['probability'] in (.1,.5,.9)
                   and r['ratio'] in (.95,4.15)]
    frozen=[]
    old_ratios=sorted({r['ratio'] for r in repair if r['split']=='frozen'})
    for old in repair:
        if old['split']!='frozen': continue
        r=copy.deepcopy(old);ratio=RATIOS[old_ratios.index(r['ratio'])]
        reward=round(r['stake']*ratio,6)
        r.update(ratio=ratio,reward=reward,id=r['id'].replace('repair_','replay_'),
                 economic_id=r['economic_id'].replace('repair_','replay_'))
        r['risky'][0][0]=-reward if r['frame']=='loss' else reward
        r['dominant_option']='safe' if max(x for x,_ in r['risky'])<r['safe'][0][0] else 'risky' if min(x for x,_ in r['risky'])>r['safe'][0][0] else None
        r['text']=render(r);frozen.append(r)
    # Exclude every recorded old prompt, including the refinement grids.
    old_text={r['text'] for r in build_rows()+repair}
    for path in Path('anchor_pilot/outputs').rglob('*rows.json'):
        if 'replay' in str(path): continue
        try:
            data=json.loads(path.read_text())
            if isinstance(data,list): old_text.update(r['text'] for r in data if isinstance(r,dict) and 'text' in r)
        except (ValueError,KeyError): pass
    assert not {r['text'] for r in frozen}&old_text
    assert len(frozen)==540 and len(development)==36
    return development,frozen


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('anchor_pilot/outputs/replay-plan-v1'))
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    development,frozen=build_replay_rows();truth=asdict(AGENTS['combined'])
    target=probabilities(frozen,truth);recovery=fit(frozen,target);rank=identifiability(frozen)
    assert rank['rank']==5 and max(abs(recovery['parameters'][k]-v) for k,v in truth.items())<1e-4
    paths=['adapter/adapter.pt','adapter/adapter_config.json','footprint.pt','sparse_geometry_diagnostic.json']
    source_hashes={name:hashlib.sha256((SOURCE/name).read_bytes()).hexdigest() for name in paths}
    geometry=json.loads((SOURCE/'sparse_geometry_diagnostic.json').read_text())
    manifest={'declared_at_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
              'source_run':str(SOURCE),'source_hashes':source_hashes,
              'development_rows':36,'frozen_rows':540,'rows_sha256':digest(development+frozen),
              'frozen_ratios':RATIOS,'conditions':CONDITIONS,'target':truth,
              'response_format':{'name':'system_letter','system':SYSTEM},
              'layer':50,'layer_indexing':'zero-based block output',
              'adapter':'saved repair checkpoint 700; rank16; blocks0-50 only; no retraining',
              'sparse_indices':{k:geometry['methods'][k]['indices'] for k in ('10','30')},
              'feature_selection':'Previously saved OMP fit to discovery mean only; fixed before new responses. Not causal selection.',
              'primary_metrics':['RMSE against full LoRA probabilities','RMSE against planted CPT probabilities',
                                 'maximum absolute probability difference','answer mass','CPT parameter recovery'],
              'engineering_gate':{'all_replace_max_probability_error':1e-6,'all_add_max_probability_error':1e-6},
              'provisional_reproduction_target':{'rmse_against_lora':.01,'min_answer_mass':.99},
              'threshold_scope':'New operational diagnostics, not the external scientific go/pivot rule.',
              'oracle_warning':'All prompt-specific raw and SAE replays require adapted states for that same prompt; they are representation diagnostics, not stand-alone steering.',
              'dose_policy':'Preserve original changes; mean norm1 is a separately named strength control. No amplitude tuning.',
              'frozen_policy':'Lock all methods and targets before GPU work; validate engineering identity on 36 development prompts before opening 540 new frozen responses.',
              'synthetic_recovery':recovery,'identifiability':rank,'scientific_go_pivot':None}
    save_json(args.output/'manifest.json',manifest);save_json(args.output/'rows.json',development+frozen)
    print(json.dumps({'output':str(args.output),'development':len(development),'frozen':len(frozen)}))


if __name__=='__main__':main()
