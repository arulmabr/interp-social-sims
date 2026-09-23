"""Check repair artifact integrity and split/selection invariants on saved files."""
import argparse
import hashlib
import json
from pathlib import Path

from .audit import read, scores
from .design import digest
from .smoke import save_json


def audit_run(run):
    report=read(run/'report.json');rows=read(run/'rows.json');plan=read(run/'plan.json')
    assert digest(rows)==report['rows_sha256']
    if not report['fixture']:assert digest(rows)==plan['rows_sha256']
    assert len({r['id'] for r in rows})==len(rows)
    owners={}
    for row in rows:assert owners.setdefault(row['economic_id'],row['split'])==row['split']
    assert len({r['text'] for r in rows})==len(rows)
    for name,expected in report['source_sha256'].items():
        assert hashlib.sha256((run/'execution_source'/name).read_bytes()).hexdigest()==expected,name
    calibration=read(run/'calibration_rows.json')
    assert all(r['split']=='discovery' for r in calibration)
    assert {r['id'] for r in calibration}<={r['id'] for r in rows if r['split']=='discovery'}
    if (run/'training.json').exists():
        training=read(run/'training.json')
        assert training['training_split']=='discovery only' and training['frozen_rows_used']==0
    paths=list(run.glob('scores_*.json'))
    if report['frozen_responses_opened']:
        lock=read(run/'selection_lock.json')
        assert not lock['frozen_responses_opened']
        if not report['fixture']:
            assert lock['selected_validation']['passed_operational_recovery_target']
            assert all(c['passed'] for c in lock['format_validation'])
            trial=next(t for t in lock['all_direction_dose_validation'] if t['rho']==lock['common_rho'])
            assert len(trial['conditions'])==23 and all(c['passed'] for c in trial['conditions'])
        frozen=read(run/'frozen_rows.json')
        assert frozen==[r for r in rows if r['split']=='frozen']
        details=scores(run,frozen,len(paths))
        for path in paths:
            if path.name not in ('scores_baseline.json','scores_lora_combined.json'):
                records=read(path)
                assert all(r['positions_per_prompt']==1 for r in records)
                if not path.stem.endswith('_fitted_magnitude'):
                    assert all(abs(r['requested_norm']-lock['common_rho'])<1e-5 for r in records)
        if report['status'] in ('completed','fixture_completed'):
            assert len(paths)==29==report['condition_count']
            expected=set(lock['directions'])|{'baseline','lora_combined','mean_delta_fitted_magnitude',
                'sae_preference_k1_fitted_magnitude','sae_preference_k3_fitted_magnitude','sae_preference_k10_fitted_magnitude'}
            assert set(details)==expected
    else:
        assert not paths
        details={}
    return {'status':'artifact_integrity_verified','execution_status':report['status'],
            'fixture':report['fixture'],'conditions':len(details),'details':details,
            'frozen_responses_opened':report['frozen_responses_opened'],
            'scientific_go_pivot':None,
            'meaning':'File integrity and recorded selection invariants; not independent proof of construct validity.'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',type=Path,required=True)
    p.add_argument('--backup',type=Path);args=p.parse_args()
    result=audit_run(args.run)
    if args.backup:
        manifest=read(args.backup/'verified_remote_files.json')
        for name,record in manifest.items():
            assert hashlib.sha256((args.backup/name).read_bytes()).hexdigest()==record['sha256'],name
        completion=read(args.backup/'session_completion.json')
        assert completion['stop_request_confirmed']
        result.update(remote_files_sha256_verified=len(manifest),session_completion=completion)
    result['audit_source_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    save_json(args.run/'artifact_audit.json',result)
    print(json.dumps({k:v for k,v in result.items() if k!='details'}))


if __name__=='__main__':main()
