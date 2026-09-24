"""Resumable, time-bounded activation harvest and intervention evaluation."""
import argparse
import collections
import json
import math
import time
from pathlib import Path

from .common import append, digest, file_hash, read, source_hashes, write
from .design import PERSONAS, STRONG
from .prepare import load_plan


def quantile(values, q):
    values = sorted(values)
    if not values:
        return None
    position = (len(values) - 1) * q
    lower = int(position)
    return values[lower] + (values[min(lower+1, len(values)-1)]-values[lower])*(position-lower)


def conditions(construct, candidates, calibration, doses):
    first_id = candidates[construct][0]['feature_id']
    values = [dict(id='baseline'), dict(id='zero_edit', feature_id=first_id, actual_delta=0),
              dict(id='prompt_simple', instruction=PERSONAS[construct]),
              dict(id='prompt_strong', instruction=STRONG[construct])]
    for candidate in candidates[construct]:
        fid = candidate['feature_id']
        scale = calibration['features'][str(fid)]['scale']
        if scale is None or scale <= 0:
            continue
        for dose in doses:
            name = f'f{fid}_d{dose:+g}'
            base = dict(id=name, feature_id=fid, multiplier=dose, actual_delta=dose*scale)
            values.append(base)
            values.append(dict(base, id=name+'_random', random_control=True))
    return values


def records(path):
    if not Path(path).exists():
        return []
    lines = Path(path).read_text().splitlines()
    result = []
    for n, line in enumerate(lines):
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            # Never silently lose or append after an interrupted final write.
            raise ValueError(f'Invalid JSONL at line {n+1}; preserve the file and repair its final partial record explicitly')
    return result


def calibrate(plan_hash, split, feature_ids, activation_records, scope):
    if scope not in ('user_content_prompt_max', 'final_prompt_position'):
        raise ValueError('Unsupported calibration scope')
    sampled = collections.defaultdict(list)
    for row in activation_records:
        if row['split'] != split:
            continue
        if scope == 'final_prompt_position':
            values = row['final_position']
        else:
            values = collections.defaultdict(float)
            for example in row['examples']:
                if example.get('scope') == 'user_content':
                    fid = str(example['feature_id'])
                    values[fid] = max(values[fid], example['activation'])
        for fid, value in values.items():
            if value > 0:
                sampled[str(fid)].append(value)
    return {'plan_hash': plan_hash, 'split': split, 'scope': scope, 'quantile': .95,
            'features': {str(fid): {'scale': quantile(sampled[str(fid)], .95),
                                   'positive_prompt_count': len(sampled[str(fid)])}
                         for fid in feature_ids}}


def execute(args):
    started = time.monotonic()
    plan_dir, output = Path(args.plan), Path(args.output)
    plan = load_plan(plan_dir)
    candidates = read(plan_dir / 'candidates.json')
    sources = source_hashes()
    if args.max_seconds <= 0:
        raise ValueError('Positive time limit required')
    if args.stage == 'confirm' and not args.lock:
        raise ValueError('Frozen evaluation requires a selection lock')
    if args.stage in ('screen', 'selection', 'confirm') and not args.calibration:
        raise ValueError('Run harvest first and supply its calibration file')
    if output.exists() and not args.resume:
        raise FileExistsError('Use a new directory, or --resume with identical configuration')
    output.mkdir(parents=True, exist_ok=True)
    identity = {'plan_hash': plan['plan_hash'], 'stage': args.stage, 'source_hashes': sources,
                'calibration_sha256': file_hash(args.calibration) if args.calibration else None,
                'lock_sha256': file_hash(args.lock) if args.lock else None}
    manifest_path = output / 'run.json'
    if manifest_path.exists():
        old = read(manifest_path)
        if old['identity'] != identity:
            raise ValueError('Resume configuration or source differs')
        if old['status'] == 'completed':
            return old
    elif args.resume:
        raise ValueError('No run manifest to resume')
    state = {'identity': identity, 'status': 'loading', 'new_model_runs': True,
             'scientific_use': 'engineering_only' if args.stage == 'smoke' else 'pilot',
             'max_seconds': args.max_seconds}
    write(manifest_path, state)
    calibration = None
    if args.calibration:
        calibration = read(args.calibration)
        if calibration['plan_hash'] != plan['plan_hash'] or calibration['split'] != 'discovery':
            raise ValueError('Calibration must be from this plan\'s discovery split')
        if calibration['scope'] != plan.get('calibration_scope', 'final_prompt_position'):
            raise ValueError('Calibration scope differs from the protocol')
    lock = read(args.lock) if args.lock else None
    if lock:
        expected = lock.pop('lock_hash')
        if digest(lock) != expected or lock['plan_hash'] != plan['plan_hash']:
            raise ValueError('Selection lock mismatch')
        lock['lock_hash'] = expected
        if lock.get('calibration_sha256') != identity['calibration_sha256']:
            raise ValueError('Selection lock uses different calibration')
    from .runtime import Runtime
    runtime = Runtime([f['feature_id'] for values in candidates.values() for f in values])
    state.update(status='running', runtime=runtime.metadata)
    write(manifest_path, state)
    if time.monotonic() - started >= args.max_seconds:
        state.update(status='time_limit', elapsed_seconds=time.monotonic()-started)
        write(manifest_path, state)
        return state
    split = {'harvest': 'discovery', 'smoke': 'smoke', 'screen': 'discovery',
             'selection': 'selection', 'confirm': 'frozen'}[args.stage]
    rows = read(plan_dir / f'{split}.json')
    if args.stage in ('harvest', 'smoke'):
        # Interpretation-validation examples are collected independently of the
        # discovery examples. Only discovery values set scientific-stage doses.
        harvest_rows = rows + (read(plan_dir/'selection.json') if args.stage == 'harvest' else [])
        path = output / 'activation_rows.jsonl'
        existing = records(path)
        done = {r['row_id'] for r in existing}
        for row in harvest_rows:
            if row['id'] in done:
                continue
            if time.monotonic()-started >= args.max_seconds:
                state.update(status='time_limit', elapsed_seconds=time.monotonic()-started)
                write(manifest_path, state)
                return state
            values, examples = runtime.activations(row)
            record = {'row_id': row['id'], 'scenario_id': row['scenario_id'],
                      'split': row['split'], 'final_position': values, 'examples': examples}
            append(path, record); existing.append(record)
            print(json.dumps({'stage': args.stage, 'harvested': len(existing), 'expected': len(harvest_rows)}), flush=True)
        calibration = calibrate(plan['plan_hash'], split, runtime.features, existing,
                                plan.get('calibration_scope', 'final_prompt_position'))
        write(output / 'calibration.json', calibration)
        if args.stage == 'harvest':
            state.update(status='completed', elapsed_seconds=time.monotonic()-started,
                         harvested=len(existing), uncovered_features=[k for k, v in calibration['features'].items() if v['scale'] is None])
            write(manifest_path, state)
            return state
    path = output / 'scores.jsonl'
    done = {(r['row_id'], r['condition']['id']) for r in records(path)}
    expected = 0
    for row in rows:
        available = conditions(row['construct'], candidates, calibration,
                               [.5, -.5] if args.stage == 'smoke' else plan['dose_multipliers'])
        if args.stage == 'smoke':
            available = [c for c in available if c['id'] in ('baseline', 'zero_edit', 'prompt_strong')
                         or c.get('feature_id') == candidates[row['construct']][0]['feature_id']]
        if lock:
            keep = lock['conditions'][row['construct']]
            available = [c for c in available if c['id'] in keep]
            if {c['id'] for c in available} != set(keep):
                raise ValueError('A locked condition is not executable with this calibration')
        for condition in available:
            expected += 1
            key = row['id'], condition['id']
            if key in done:
                continue
            if time.monotonic()-started >= args.max_seconds:
                state.update(status='time_limit', elapsed_seconds=time.monotonic()-started, completed=len(done))
                write(manifest_path, state)
                return state
            result = runtime.evaluate(row, condition, 32 if args.stage == 'smoke' else plan['max_new_tokens'])
            append(path, {'row_id': row['id'], 'scenario_id': row['scenario_id'],
                          'construct': row['construct'], 'split': split, 'template': row['template'],
                          'condition': condition, **result})
            done.add(key)
            print(json.dumps({'stage': args.stage, 'completed': len(done), 'last_condition': condition['id']}), flush=True)
    state.update(status='completed', completed=len(done), expected=expected,
                 elapsed_seconds=time.monotonic()-started)
    write(manifest_path, state)
    return state


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', required=True); p.add_argument('--output', required=True)
    p.add_argument('--stage', choices=['smoke', 'harvest', 'screen', 'selection', 'confirm'], required=True)
    p.add_argument('--calibration'); p.add_argument('--lock')
    p.add_argument('--max-seconds', type=int, default=3000); p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    try:
        result = execute(args)
    except Exception as error:
        manifest = Path(args.output)/'run.json'
        if manifest.exists():
            state = read(manifest)
            if state.get('status') in ('loading', 'running'):
                state.update(status='failed', error_type=type(error).__name__)
                write(manifest, state)
        raise
    print(json.dumps(result, indent=2))
    if result['status'] != 'completed':
        raise SystemExit(2)


if __name__ == '__main__':
    main()
