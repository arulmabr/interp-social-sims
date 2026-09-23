"""Verify the final local backup and saved score invariants without model queries."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.special import expit

from .design import digest
from .smoke import save_json


def read(path):
    return json.loads(path.read_text())


def scores(directory, rows, expected, skip=()):
    paths = [p for p in directory.glob('scores_*.json') if p.stem not in skip]
    assert len(paths) == expected, (len(paths), expected)
    details = {}
    for path in paths:
        records = read(path)
        assert len(records) == len(rows), path.name
        values = np.array([[r[k] for k in ('margin', 'p_risky', 'answer_mass')] for r in records])
        assert np.isfinite(values).all(), path.name
        assert ((values[:, 1] >= 0) & (values[:, 1] <= 1)).all(), path.name
        assert ((values[:, 2] >= 0) & (values[:, 2] <= 1.0001)).all(), path.name
        assert np.max(np.abs(expit(values[:, 0])-values[:, 1])) < 1e-7, path.name
        patched = [r for r in records if 'actual_norm' in r]
        if patched:
            assert len(patched) == len(rows)
            assert all(r.get('positions_per_prompt') in (None, 1) and r['requested_norm'] > 0 for r in patched)
            assert all(np.isfinite(r['actual_norm']) and r['actual_norm'] > 0 for r in patched)
        details[path.stem.removeprefix('scores_')] = {
            'rows': len(records), 'invalid_answer_mass_count': int((values[:, 2] < .95).sum()),
            'max_relative_norm_error': max(abs(r['actual_norm']/r['requested_norm']-1) for r in patched) if patched else None,
        }
    return details


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--backup', type=Path, required=True)
    p.add_argument('--run', type=Path, required=True)
    args = p.parse_args()
    completion = read(args.backup / 'session_completion.json')
    assert completion['exit_code'].strip() == '0'
    assert completion['stop_request_confirmed'], 'GPU stop not confirmed'
    manifest = read(args.backup / 'verified_remote_files.json')
    for relative, record in manifest.items():
        assert hashlib.sha256((args.backup / relative).read_bytes()).hexdigest() == record['sha256'], relative
    report, rows = read(args.run / 'report.json'), read(args.run / 'rows.json')
    assert report['status'] == 'gpu_execution_complete_analysis_pending'
    assert report['token_scope'] == 'final prompt token only'
    assert digest(rows) == report['runtime_rows_sha256'] == report['design_sha256']
    assert len({r['id'] for r in rows}) == len(rows)
    groups = {}
    for row in rows:
        groups.setdefault(row['economic_id'], set()).add(row['split'])
    assert all(len(splits) == 1 for splits in groups.values())
    main_details = scores(args.run, rows, 101)
    fresh = read(args.run / 'refinement/rows.json')
    fresh_report = read(args.run / 'refinement/report.json')
    assert fresh_report['status'] == 'completed'
    assert digest(fresh) == fresh_report['rows_sha256']
    assert not {r['text'] for r in rows} & {r['text'] for r in fresh}
    assert read(args.run / 'refinement/selection_lock.json')['fresh_evaluation_seen'] is False
    fresh_details = scores(args.run / 'refinement', fresh, 11, ('scores_old_grid_development',))
    # The extra old-grid measurement is explicitly development-only.
    assert len(read(args.run / 'refinement/scores_old_grid_development.json')) == len(rows)
    outcome = {'status': 'artifact_integrity_verified', 'remote_files_sha256_verified': len(manifest),
               'main_conditions': len(main_details), 'main_rows_per_condition': len(rows),
               'fresh_conditions': len(fresh_details), 'fresh_rows_per_condition': len(fresh),
               'new_prompt_overlap_with_original': 0,
               'main': main_details, 'fresh': fresh_details,
               'scientific_pass': None, 'reason': 'Integrity checks do not establish preference-anchor validity.'}
    save_json(args.run / 'artifact_audit.json', outcome)
    print(json.dumps({k: v for k, v in outcome.items() if k not in ('main', 'fresh')}))


if __name__ == '__main__':
    main()
