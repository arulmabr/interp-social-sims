"""Compare real GPU diagnostic replays against saved direct-local responses."""
import argparse
from collections import defaultdict
from pathlib import Path

from label_pilot.common import read, write
from paper_replication.common import parse_answer, records
from .session import CELLS


def analyze(run, previous, historical, output):
    run, previous, output = Path(run), Path(previous), Path(output)
    manifest = read(run/'run.json')
    if manifest.get('mock') is not False or manifest.get('status') != 'completed':
        raise ValueError('Only a complete real GPU run can generate an experimental comparison')
    if manifest.get('full_length_replays') != 320 or not manifest.get('smoke_passed'):
        raise ValueError('Expected successful GPU gate and all 320 diagnostic replays')
    old_manifest = read(previous/'run.json')
    if manifest['runtime_source_hashes'] != old_manifest['identity']['source_hashes']:
        raise ValueError('Direct-local comparison used different runtime source')
    if manifest['plan_hash'] != old_manifest['identity']['plan_hash']:
        raise ValueError('Direct-local comparison used a different plan')
    smoke = read(run/'smoke/smoke-summary.json')
    if smoke.get('mock') is not False or not smoke.get('passed'):
        raise ValueError('Missing real GPU smoke validation')
    protocol = read(run/'protocol.json')
    expected = set(protocol['trial_ids'])
    current = records(run/'replays/responses.jsonl')
    old = {r['id']:r for r in records(previous/'responses.jsonl')}
    if len(current) != 320 or len({r['id'] for r in current}) != 320 or {r['id'] for r in current} != expected:
        raise ValueError('Missing, duplicate or extra replay trials')
    by_cell = defaultdict(list)
    comparisons = []
    for row in current:
        prior = old[row['id']]
        if row.get('mock') is not False or row.get('zero_edit') is not False or row['max_new_tokens'] != 1000:
            raise ValueError('Unexpected replay mode or generation cap')
        if row['seed'] != prior['seed'] or row['batch_size'] != prior['batch_size']:
            raise ValueError('Sampling seed or fixed batch size changed')
        if prior.get('repair'):
            raise ValueError('Prior response was repaired and cannot be compared as a single generation')
        parsed = parse_answer(row['game'], row['response'])
        if parsed != row['parse'] or not parsed['valid']:
            raise ValueError('Invalid or inconsistent parsed answer')
        if row['condition'] == 'steering':
            trace = row['trace']
            if trace['hook_calls'] != row['generated_tokens'] or trace['changed_positions'] <= 0:
                raise ValueError('Steering trace does not support the requested intervention')
        elif row['requested_edits'] or row['trace']:
            raise ValueError('Baseline unexpectedly has steering edits')
        comparison = dict(id=row['id'], game=row['game'], value=row['value'], condition=row['condition'],
                          exact_text=row['response']==prior['response'],
                          exact_generated_tokens=row['generated_tokens']==prior['generated_tokens'],
                          exact_input_tokens=row['input_tokens']==prior['input_tokens'],
                          same_choice=parsed['answer']==prior['final_parse']['answer'],
                          local_target=prior['final_parse']['target'], edsl_target=parsed['target'],
                          truncated=row['truncated'])
        comparisons.append(comparison)
        by_cell[(row['game'],row['value'],row['condition'])].append(comparison)
    archived = {(r['game'],r['value'],r['condition']):r for r in read(historical)['historical_curves']}
    cells = []
    for game, value in CELLS:
        for condition in ('baseline','steering'):
            entries = by_cell[(game,value,condition)]
            if len(entries) != 40:
                raise ValueError('Incomplete cell')
            cells.append(dict(game=game,value=value,condition=condition,n=40,
                              original_target=archived[(game,value,condition)]['target_count'],
                              previous_local_target=sum(r['local_target'] for r in entries),
                              edsl_local_target=sum(r['edsl_target'] for r in entries),
                              same_choices=sum(r['same_choice'] for r in entries),
                              exact_texts=sum(r['exact_text'] for r in entries)))
    result = dict(status='passed', real_gpu=True, independent_new_trials=0, replayed_trials=320,
                  exact_texts=sum(r['exact_text'] for r in comparisons),
                  exact_generated_token_counts=sum(r['exact_generated_tokens'] for r in comparisons),
                  exact_input_token_counts=sum(r['exact_input_tokens'] for r in comparisons),
                  same_choices=sum(r['same_choice'] for r in comparisons),
                  truncated=sum(r['truncated'] for r in comparisons),
                  runtime=manifest['runtime'], versions=manifest['versions'],
                  same_session_smoke=smoke, cells=cells, comparisons=comparisons,
                  interpretation='Fixed-seed diagnostic replays of selected discrepancy cells. Do not pool with previous data or treat as independent efficacy evidence.')
    output.mkdir(parents=True,exist_ok=False)
    write(output/'comparison.json', result)
    lines = ['# EDSL + local SAE: GPU validation results', '',
             f"EDSL and the previous direct-local run produced the same choices in **{result['same_choices']}/320** diagnostic replays, and identical response text in **{result['exact_texts']}/320**.", '',
             'The GPU smoke checks passed for both games: EDSL/direct baseline and steering output matched exactly; zero-edit steering replayed baseline; positive edits changed hidden states; trace counts matched generated-token counts.', '',
             '| Game and setting | Original hosted baseline → steering | Previous local baseline → steering | EDSL local baseline → steering |',
             '|---|---:|---:|---:|']
    for game,value in CELLS:
        base = next(c for c in cells if (c['game'],c['value'],c['condition'])==(game,value,'baseline'))
        steer = next(c for c in cells if (c['game'],c['value'],c['condition'])==(game,value,'steering'))
        values = ['%s/40 → %s/40'%(base[k],steer[k]) for k in ('original_target','previous_local_target','edsl_local_target')]
        lines.append('| '+game+' '+str(value)+' | '+' | '.join(values)+' |')
    lines += ['', 'Lottery counts mean choosing the risky option. Ultimatum counts mean accepting the offer; acceptance alone does not establish an altruism mechanism.', '',
              'These settings were selected because earlier runs showed discrepancies. The agents and random seeds were reused. These 320 responses are diagnostic replays, not 320 new independent observations.', '',
              f"Truncated full-length responses: {result['truncated']}/320. Invalid answers: 0/320. No answer repairs or cache reuse were permitted.", '',
              '## What this means', '']
    if result['same_choices'] == 320:
        lines += ['Adding EDSL did not change the observed local choices in these tested cells. It therefore did not recover the historical hosted effects. The remaining discrepancy needs investigation in model/backend configuration and/or the hosted steering implementation, rather than assuming that using EDSL alone fixes it.']
    else:
        lines += ['Some cross-session local choices changed. The within-session smoke checks passed, but the cross-session difference needs investigation before attributing it to EDSL or interpreting a change in effect size.']
    lines += ['', 'The pipeline uses the released Goodfire SAE weights and labels with local model inference and local steering. It does not require hosted Goodfire inference. The historical EDSL version and complete hosted backend/steering configuration remain unverified.', '',
              'The manuscript and prior experiment source are unchanged. Raw EDSL results, generated responses, traces, pinned versions and source hashes are retained in the collected run directory.', '']
    (output/'RESULTS_FOR_REVIEW.md').write_text('\n'.join(lines))
    return {k:v for k,v in result.items() if k not in ('comparisons','cells','runtime','versions','same_session_smoke')}


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--previous', required=True)
    parser.add_argument('--historical', required=True)
    parser.add_argument('--output', required=True)
    args=parser.parse_args()
    print(__import__('json').dumps(analyze(args.run,args.previous,args.historical,args.output),indent=2))
