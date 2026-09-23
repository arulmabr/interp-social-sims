"""Verify exported hashes, prompt counts and recorded probability errors on CPU.

This checks saved outputs; it does not retrain models or rerun the fitted
behavioral-model comparison and bootstrap. No credentials or GPU are required.
"""
import hashlib
import json
from pathlib import Path

import numpy as np

from .cpt import probabilities


ROOT = Path(__file__).resolve().parent / 'evidence'


def read(root, filename):
    return json.loads((root / filename).read_text())


def rmse(first, second):
    return float(np.sqrt(np.mean((np.asarray(first) - np.asarray(second)) ** 2)))


def main():
    manifest = read(ROOT, 'manifest.json')
    for name, expected in manifest['files'].items():
        path = (ROOT / name).resolve()
        assert path.is_relative_to(ROOT.resolve()), name
        data = path.read_bytes()
        assert len(data) == expected['bytes'], name
        assert hashlib.sha256(data).hexdigest() == expected['sha256'], name

    decision = ROOT / 'decision'
    status, plan, analysis = (read(decision, name) for name in
                              ('run_status.json', 'plan.json', 'decision_analysis.json'))
    assert status['status'] == 'completed' and not status['fixture']
    assert len(status['conditions']) == 28
    for split, count in [('discovery', 216), ('selection', 96), ('frozen', 432)]:
        rows = read(decision, f'{split}_rows.json')
        assert len(rows) == count and len({r['id'] for r in rows}) == count
    frozen = read(decision, 'frozen_rows.json')
    for name in status['conditions']:
        for split, count in [('frozen', 432), ('selection', 96), ('control', 48)]:
            scores = read(decision, f'{split}_scores_{name}.json')
            assert len(scores) == count, (name, split)
            assert all(np.isfinite(s['p_risky']) and 0 <= s['p_risky'] <= 1 for s in scores)
        scores = read(decision, f'frozen_scores_{name}.json')
        for template in ('original', 'transfer'):
            ids = [i for i, r in enumerate(frozen) if r['template'] == template]
            rows = [frozen[i] for i in ids]
            values = [scores[i]['p_risky'] for i in ids]
            for target, parameters in plan['targets'].items():
                actual = rmse(values, probabilities(rows, parameters))
                recorded = analysis['conditions'][name]['templates'][template]['targets'][target]['teacher_rmse']
                assert abs(actual - recorded) < 1e-10, (name, template, target)
    assert analysis['verdict'] == 'INCONCLUSIVE_EVALUATION_OR_ANCHOR_TRANSFER'
    for method in ('dense', 'sae10'):
        assert analysis['methods'][method]['total_cells'] == 8
        assert analysis['methods'][method]['passed_cells'] == 0

    replay = ROOT / 'replay'
    report, plan = read(replay, 'report.json'), read(replay, 'plan.json')
    rows = read(replay, 'frozen_rows.json')
    assert len(rows) == 540 and len(report['summary']) == 16
    teacher = probabilities(rows, plan['target'])
    reference = np.array([r['p_risky'] for r in read(replay, 'frozen_scores_lora.json')])
    for name, saved in report['summary'].items():
        scores = read(replay, f'frozen_scores_{name}.json')
        assert len(scores) == len(rows)
        values = np.array([s['p_risky'] for s in scores])
        assert abs(rmse(values, reference) - saved['rmse_to_lora']) < 1e-10, name
        assert abs(rmse(values, teacher) - saved['teacher_probability_rmse']) < 1e-10, name
        if name in ('raw_all_replace', 'raw_all_add'):
            assert np.array_equal(values, reference), name
    print(json.dumps({'hashes_verified': len(manifest['files']),
                      'decision_conditions_verified': 28, 'replay_conditions_verified': 16,
                      'full_state_replay_exact': True, 'new_model_runs': False}, indent=2))


if __name__ == '__main__':
    main()
