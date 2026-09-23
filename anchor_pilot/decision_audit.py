"""Verify provenance, split isolation, matched norms, and delivered local artifacts."""
import argparse
import hashlib
import json
from pathlib import Path
import torch

from .design import digest
from .smoke import save_json


def main():
    p=argparse.ArgumentParser();p.add_argument('root',type=Path);p.add_argument('--backup',type=Path,required=True);args=p.parse_args()
    root=args.root;read=lambda name:json.loads((root/name).read_text())
    plan=read('plan.json');assert digest(read('rows.json'))==plan['rows_sha256']
    lock=read('selection_lock.json');assert lock['frozen_responses_opened'] is False
    status=read('run_status.json');assert status['status']=='completed'
    vectors=torch.load(root/'locked_interventions.pt',map_location='cpu',weights_only=True)
    checks={}
    for target,choice in lock['choices'].items():
        c=choice['selected'];names=[n for n in vectors if n.startswith(target+'_')]
        assert len(names)==4
        for n in names:
            v=vectors[n];assert v['scope']==c['scope'] and abs(float(v['vector'].norm())-c['dose'])<1e-4
        checks[target]={'scope':c['scope'],'dose':c['dose'],'conditions':names}
    for info in lock['training'].values():
        assert info['selected_step'] in (40,80,120,160)
        assert len(info['history'])==4
        if info['method']=='sae10':assert len(info['features'])==10 and len(set(info['features']))==10
    assert len(lock['training'])==16
    refinement=None
    if 'refinement_plan' in lock:
        refined=[info for info in lock['training'].values() if 'extra_updates' in info]
        assert len(refined)==8
        for info in refined:
            assert info['extra_updates']==480
            assert [x['step'] for x in info['refinement_history']]==[0,80,160,240,320,400,480]
            assert info['selected_refinement_step'] in [0,80,160,240,320,400,480]
        assert lock['stage1_frozen_results_used'] is False
        refinement={'vectors':8,'extra_updates_per_vector':480,'stage1_frozen_scores_used':False}
    backup=json.loads((args.backup/'verified_remote_files.json').read_text());verified=0
    # Mutable session log may have a later snapshot; verify the saved snapshot against its manifest.
    for name,entry in backup.items():
        assert hashlib.sha256((args.backup/name).read_bytes()).hexdigest()==entry['sha256'],name
        verified+=1
    completion=json.loads((args.backup/'session_completion.json').read_text())
    assert completion['stop_request_confirmed'] and completion['exit_code'].strip()=='0'
    source_hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (root/'execution_source').glob('*.py')}
    report={'status':'verified','matched_comparisons':checks,'trained_vectors':16,'frozen_conditions':len(status['conditions']),
            'frozen_rows_per_condition':432,'remote_files_sha256_verified':verified,'provider_stop_confirmed':True,
            'source_hashes':source_hashes,'protocol_rows_hash_verified':True,'refinement':refinement}
    save_json(root/'delivery_audit.json',report);print(json.dumps({k:v for k,v in report.items() if k!='source_hashes'},indent=2))


if __name__=='__main__':main()
