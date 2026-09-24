"""Report generated local curves separately from archived hosted responses."""
import argparse
import math
from collections import defaultdict,Counter
from pathlib import Path

from .common import read,write,records,parse_answer,load_plan


def wilson(successes,n):
    if not n:return [None,None]
    z=1.959963984540054;p=successes/n;d=1+z*z/n
    center=(p+z*z/(2*n))/d;radius=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,center-radius),min(1,center+radius)]


def curves(rows,historical=False):
    grouped=defaultdict(list)
    for r in rows:grouped[(r['game'],r['condition'],r['value'])].append(r)
    out=[]
    for (game,condition,value),group in sorted(grouped.items()):
        values=[parse_answer(game,r['original_answer'])if historical else r['final_parse']for r in group]
        valid=sum(v['valid']for v in values);positive=sum(v['target']==1 for v in values)
        n=len(group)
        out.append(dict(game=game,condition=condition,value=value,n=n,valid=valid,invalid=n-valid,
            target_count=positive,target_rate_all=positive/n,target_rate_valid=positive/valid if valid else None,
            descriptive_wilson_95=wilson(positive,n),
            first_attempt_invalid=0 if historical else sum(not r['first_attempt_parse']['valid']for r in group),
            truncated=0 if historical else sum(r.get('repair',r)['truncated']if r.get('repair')else r['truncated']for r in group)))
    baseline={(r['game'],r['value']):r for r in out if r['condition']=='baseline'}
    for r in out:
        base=baseline.get((r['game'],r['value']))
        r['change_from_same_backend_baseline']=r['target_rate_all']-base['target_rate_all']if base else None
    return out


def analyze(plan_dir,run_dir,output):
    plan_dir,run_dir,output=map(Path,(plan_dir,run_dir,output));output.mkdir(parents=True,exist_ok=True)
    plan=load_plan(plan_dir);manifest=read(run_dir/'run.json')
    if manifest['identity']['plan_hash']!=plan['plan_hash']:raise ValueError('Plan mismatch')
    new=records(run_dir/'responses.jsonl');old=records(plan_dir/'historical.jsonl')
    if len({r['id']for r in new})!=len(new):raise ValueError('Duplicate output IDs')
    local=curves(new);historical=curves(old,True)
    hmap={(r['game'],r['condition'],r['value']):r for r in historical}
    comparisons=[]
    for r in local:
        h=hmap[(r['game'],r['condition'],r['value'])]
        if r['n']==40:
            comparisons.append(dict(game=r['game'],condition=r['condition'],value=r['value'],
                local_rate=r['target_rate_all'],historical_rate=h['target_rate_all'],difference=r['target_rate_all']-h['target_rate_all'],
                local_effect=r['change_from_same_backend_baseline'],historical_effect=h['change_from_same_backend_baseline']))
    value=dict(plan_hash=plan['plan_hash'],run_status=manifest['status'],completed=len(new),expected=plan['request_count'],
        complete=manifest['status']=='completed'and len(new)==plan['request_count'],local_curves=local,historical_curves=historical,
        comparisons=comparisons,interpretation='Descriptive local replication. Historical hosted and local raw-unit additive implementations are not verified equivalents. Intervals describe model samples conditional on these prompts; they are not human-population intervals.')
    write(output/'comparison.json',value)
    lines=['# Lottery and ultimatum local replication — author review','',
           f'Status: **{manifest["status"]}**. Generated {len(new):,}/{plan["request_count"]:,} responses.','',
           '**The manuscript has not been changed.** These are new local generations, compared with separately labeled historical Goodfire-hosted responses.','',
           'Original rendered prompts and temperature 0.5 are retained. Feature nudges use raw released-SAE units, with last-token additive edits and BF16 model inference. Exact hosted scaling and backend equivalence have not been established.','',
           '## Matched local results','',
           'Target means Risky Option for lottery and Accept for ultimatum. Rates include invalid responses in the denominator; invalids are also reported separately. Difference is relative to the local baseline at the same reward/offer.','',
           '| Game | Condition | Reward/offer | Responses | Target rate | Change vs local baseline | Invalid final | Invalid first attempt |',
           '|---|---|---:|---:|---:|---:|---:|---:|']
    for r in local:
        diff=r['change_from_same_backend_baseline'];d='—'if diff is None else f'{diff:+.3f}'
        lines.append(f'| {r["game"]} | {r["condition"]} | {r["value"]} | {r["n"]} | {r["target_rate_all"]:.3f} | {d} | {r["invalid"]} | {r["first_attempt_invalid"]} |')
    lines+=['','Full historical/local curves, descriptive intervals and per-cell comparisons are in `comparison.json`. A historical numerical match should not be manufactured by tuning against the test curves.','',
            'The 40 agents per cell are model trials, not independent human participants. Rationale and vocabulary changes alone do not establish risk preference or altruism. Complete response text and intervention traces are retained in the raw records.','']
    (output/'RESULTS_FOR_REVIEW.md').write_text('\n'.join(lines))
    return value


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--run',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();x=analyze(a.plan,a.run,a.output);print({k:x[k]for k in ('run_status','completed','expected','complete')})
