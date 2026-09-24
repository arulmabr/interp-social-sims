"""GPU adapter gate followed by a fixed diagnostic replay of discrepant cells.

These are repeated prompts and seeds, not new independent scientific trials.
"""
import argparse
import datetime as dt
from importlib.metadata import version
import os
from pathlib import Path
import platform

from label_pilot.common import MODEL, MODEL_REVISION, SAE, SAE_REVISION, file_hash, write
from paper_replication.common import load_plan, make_batches, records, sources
from .check import SyntheticRuntime, smoke, verify_guard

CELLS = (('lottery', 115), ('lottery', 125), ('ultimatum', 35), ('ultimatum', 40))


def select_rows(rows):
    selected = [r for r in rows if (r['game'], r['value']) in CELLS
                and r['condition'] in ('baseline', 'steering')]
    for game, value in CELLS:
        for condition in ('baseline', 'steering'):
            cell = [r for r in selected if (r['game'], r['value'], r['condition']) == (game, value, condition)]
            if len(cell) != 40 or sorted(r['agent_index'] for r in cell) != list(range(40)):
                raise ValueError('Diagnostic replay requires all 40 original agents per cell')
    return selected


def run_replays(runtime, selected, output, before_generate):
    from .bridge import FixedBatch, run_batch
    completed = 0
    for index, (batch, seed) in enumerate(make_batches(selected, 8)):
        before_generate()
        backend = FixedBatch(runtime, batch, seed, raw_path=output/'responses.jsonl', engineering_only=True)
        result = run_batch(backend)
        write(output/f'edsl-batch-{index:03d}.json', result)
        completed += len(batch)
        progress = dict(completed=completed, planned=len(selected), last_batch=index,
                        game=batch[0]['game'], value=batch[0]['value'], condition=batch[0]['condition'])
        write(output/'progress.json', progress)
        print(__import__('json').dumps(progress), flush=True)
    return completed


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--plan', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--mock', action='store_true')
    p.add_argument('--pod-id'); p.add_argument('--guard-pid', type=int); p.add_argument('--deadline')
    args = p.parse_args()
    plan = load_plan(args.plan)
    rows = records(args.plan/'requests.jsonl')
    if plan['batch_size'] != 8 or len(rows) != plan['request_count']:
        raise ValueError('Unexpected frozen plan')
    selected = select_rows(rows)
    guard = (lambda: None) if args.mock else lambda: verify_guard(args.pod_id, args.guard_pid, args.deadline)
    guard()
    args.output.mkdir(parents=True, exist_ok=False)
    os.environ['EDSL_DATABASE_PATH'] = str((args.output/'edsl-cache.db').resolve())
    os.environ['EDSL_LOG_DIR'] = str((args.output/'edsl-logs').resolve())
    os.environ['EDSL_MAX_ATTEMPTS'] = '1'
    protocol = dict(plan_hash=plan['plan_hash'], selected_cells=CELLS,
                    selection_reason='Previously observed baseline discrepancies and steering effects; diagnostic selection before this session, not an unbiased new efficacy estimate.',
                    trial_ids=[r['id'] for r in selected], paired_seeds='Original fixed eight-agent batches and recorded seed function',
                    generation=selected[0]['generation'], repeats_of_prior_trials=True,
                    invalid_answer_policy='Preserve the entire raw batch and stop visibly; no repair or additional samples.',
                    engineering_only=True, additional_independent_scientific_trials=0)
    write(args.output/'protocol.json', protocol)
    manifest = dict(status='starting', started_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                    mock=args.mock, engineering_only=True, additional_independent_scientific_trials=0,
                    plan_hash=plan['plan_hash'], protocol_sha256=file_hash(args.output/'protocol.json'),
                    model=MODEL, model_revision=MODEL_REVISION, sae=SAE, sae_revision=SAE_REVISION,
                    runtime_source_hashes=sources(),
                    adapter_source_hashes={p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')},
                    versions={'python':platform.python_version(), **{n:version(n) for n in ('edsl',)}},
                    remote_inference=False, remote_cache=False, api_proxy=False,
                    planned_short_smoke_responses=80, planned_full_length_replays=320,
                    pod_id=args.pod_id, stop_deadline_utc=args.deadline)
    write(args.output/'run.json', manifest)
    try:
        if args.mock:
            runtime = SyntheticRuntime()
        else:
            from paper_replication.runtime import PaperRuntime
            runtime = PaperRuntime()
            manifest['versions'].update({n:version(n) for n in ('torch', 'transformers', 'accelerate', 'huggingface-hub')})
        manifest.update(status='smoke', runtime=runtime.metadata)
        write(args.output/'run.json', manifest)
        smoke_path = args.output/'smoke'; smoke_path.mkdir()
        result = smoke(runtime, rows, smoke_path, before_generate=guard)
        write(smoke_path/'smoke-summary.json', result)
        manifest.update(status='replaying', smoke_passed=True)
        write(args.output/'run.json', manifest)
        replay_path = args.output/'replays'; replay_path.mkdir()
        completed = run_replays(runtime, selected, replay_path, guard)
        manifest.update(status='completed', full_length_replays=completed,
                        completed_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    except Exception as error:
        manifest.update(status='failed', error_type=type(error).__name__)
        raise
    finally:
        write(args.output/'run.json', manifest)


if __name__ == '__main__':
    main()
