"""Prompt audit and bounded engineering validation for EDSL + local SAE."""
import argparse
import datetime as dt
import json
import os
from pathlib import Path

from label_pilot.common import append, file_hash, read, write
from paper_replication.common import batch_seed, load_plan, make_batches, records, sources


class SyntheticRuntime:
    """Clearly marked CPU test double; never experimental evidence."""
    mock = True
    metadata = {'backend': 'synthetic_cpu_check', 'scientific_results': False}

    def __init__(self):
        self.calls = []

    def generate_batch(self, rows, seed, zero=False, max_new_tokens=None):
        self.calls.append({'ids': [r['id'] for r in rows], 'seed': seed, 'zero': zero,
                           'edits': rows[0]['edits']})
        out = []
        for row in rows:
            edited = bool(row['edits']) and not zero
            answer = ('Risky Option' if edited else 'Safe Option') if row['game'] == 'lottery' else ('Accept' if edited else 'Reject')
            out.append(dict(response=answer + '\nSynthetic adapter test; not a model result.',
                input_tokens=0, generated_tokens=0, truncated=False, seed=seed,
                batch_size=len(rows), batch_elapsed_seconds=0., trace={}))
        return out


def verify_guard(pod_id, pid, deadline):
    if not (pod_id and pid and deadline):
        raise ValueError('GPU validation requires an already approved session and its exact-pod shutdown guard')
    stop = dt.datetime.fromisoformat(deadline.replace('Z', '+00:00'))
    if stop.utcoffset() is None:
        raise ValueError('Deadline must include its timezone')
    remaining = (stop - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if not 240 < remaining <= 7200:
        raise ValueError('Need 4 minutes to 2 hours remaining on the approved session')
    args = (Path('/proc')/str(pid)/'cmdline').read_bytes().decode().split('\0')
    if not any(a.endswith('stop_guard.py') for a in args):
        raise ValueError('PID does not identify the shutdown guard')
    for flag, value in (('--pod-id', pod_id), ('--deadline', deadline)):
        if flag not in args or args[args.index(flag)+1] != value:
            raise ValueError('Shutdown guard does not match the exact pod and deadline')


def audit_prompts(rows):
    from .bridge import FixedBatch, make_job
    checked = []
    for batch, seed in make_batches(rows, 8):
        backend = FixedBatch(None, batch, seed)
        _, _, hashes = make_job(backend)
        checked.extend({'id': row['id'], 'prompt_sha256': sha} for row, sha in zip(batch, hashes))
    return dict(status='passed', checked=len(checked), mismatches=0,
        inference_calls=0, edsl_version='1.0.8', prompts=checked,
        scope='EDSL-generated system/user strings match archived strings. Hosted tokenization remains unverified.')


def same_outputs(left, right):
    return len(left) == len(right) and all(
        a['response'] == b['response'] and a['generated_tokens'] == b['generated_tokens']
        for a, b in zip(left, right))


def smoke(runtime, rows, output, before_generate=lambda: None):
    from .bridge import FixedBatch, run_batch
    checks = []
    for game, value in (('lottery', 100), ('ultimatum', 30)):
        baseline = sorted([r for r in rows if (r['game'], r['condition'], r['value']) == (game, 'baseline', value)], key=lambda r:r['agent_index'])[:8]
        steering = sorted([r for r in rows if (r['game'], r['condition'], r['value']) == (game, 'steering', value)], key=lambda r:r['agent_index'])[:8]
        if len(baseline) != 8 or len(steering) != 8:
            raise ValueError('Missing diagnostic batches')
        seed = batch_seed(game, value, 0)
        before_generate()
        direct_base = runtime.generate_batch(baseline, seed, max_new_tokens=96)
        direct_steer = None
        generated = {}
        for arm, batch, zero in (('baseline', baseline, False), ('zero_edit', steering, True), ('steering', steering, False)):
            before_generate()
            backend = FixedBatch(runtime, batch, seed, zero=zero, max_new_tokens=96,
                raw_path=output/'edsl-engineering-responses.jsonl', engineering_only=True)
            result = run_batch(backend)
            write(output/f'{game}-{arm}-edsl.json', result)
            generated[arm] = [backend.outputs[r['id']] for r in batch]
        before_generate()
        direct_steer = runtime.generate_batch(steering, seed, max_new_tokens=96)
        write(output/f'{game}-direct.json', {'baseline': direct_base, 'steering': direct_steer})
        check = dict(game=game, batch_size=8,
            edsl_vs_direct_baseline_exact=same_outputs(generated['baseline'], direct_base),
            edsl_vs_direct_steering_exact=same_outputs(generated['steering'], direct_steer),
            edsl_zero_edit_replays_baseline=same_outputs(generated['baseline'], generated['zero_edit']))
        if not getattr(runtime, 'mock', False):
            check['positive_edits_change_hidden_states'] = all(r['trace']['changed_positions'] > 0 for r in generated['steering'])
            check['trace_token_counts_exact'] = all(r['trace']['hook_calls'] == r['generated_tokens'] for arm in ('zero_edit', 'steering') for r in generated[arm])
        checks.append(check)
        if not all(value for key, value in check.items() if key not in ('game', 'batch_size')):
            raise RuntimeError('EDSL/local GPU equivalence validation failed')
    return dict(checks=checks, passed=True, edsl_responses=48, direct_responses=32,
        mock=bool(getattr(runtime, 'mock', False)), engineering_only=True,
        interpretation='Adapter validation only. Synthetic CPU replies and 96-token GPU smoke replies are not paper results.')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('mode', choices=['audit-prompts', 'mock-smoke', 'gpu-smoke'])
    p.add_argument('--plan', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path)
    p.add_argument('--pod-id'); p.add_argument('--guard-pid', type=int); p.add_argument('--deadline')
    args = p.parse_args()
    plan = load_plan(args.plan)
    rows = records(args.plan/'requests.jsonl')
    if plan['batch_size'] != 8 or len(rows) != plan['request_count']:
        raise ValueError('Unexpected frozen plan')
    if args.mode == 'gpu-smoke':
        verify_guard(args.pod_id, args.guard_pid, args.deadline)
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault('EDSL_DATABASE_PATH', str((args.output/'edsl-cache.db').resolve()))
    os.environ.setdefault('EDSL_LOG_DIR', str((args.output/'edsl-logs').resolve()))
    os.environ['EDSL_MAX_ATTEMPTS'] = '1'
    manifest = dict(status='running', mode=args.mode, engineering_only=True,
        new_scientific_trials=0, edsl_version='1.0.8', plan_hash=plan['plan_hash'],
        runtime_source_hashes=sources(), adapter_source_hashes={p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')},
        inference_dependency='Local model and released Goodfire SAE weights; no hosted Goodfire inference.',
        edsl_service_slot='test: compatibility enum for custom in-process LocalSAEModel, not a canned model',
        remote_inference=False, remote_cache=False, gpu_session_started_by_this_command=False)
    write(args.output/'run.json', manifest)
    try:
        if args.mode == 'audit-prompts':
            result = audit_prompts(rows)
            write(args.output/'prompt-audit.json', result)
            brief = {k:v for k,v in result.items() if k != 'prompts'}
        else:
            if args.mode == 'gpu-smoke':
                from paper_replication.runtime import PaperRuntime
                runtime = PaperRuntime()
                guard_check = lambda: verify_guard(args.pod_id, args.guard_pid, args.deadline)
            else:
                runtime = SyntheticRuntime()
                guard_check = lambda: None
            result = smoke(runtime, rows, args.output, before_generate=guard_check)
            write(args.output/'smoke-summary.json', result)
            brief = result
            manifest['runtime'] = runtime.metadata
        manifest.update(status='completed', summary=brief)
        write(args.output/'run.json', manifest)
        print(json.dumps(brief, indent=2))
    except Exception as error:
        manifest.update(status='failed', error_type=type(error).__name__)
        write(args.output/'run.json', manifest)
        raise


if __name__ == '__main__':
    main()
