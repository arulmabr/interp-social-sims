"""Resumable original-protocol replication; smoke precedes any full generation."""
import argparse
import copy
import json
import time
from pathlib import Path

from .common import load_plan,records,read,write,append,file_hash,sources,make_batches,parse_answer,batch_seed


def smoke(runtime,rows,output):
    checks=[];examples=[]
    for game,value in [('lottery',100),('ultimatum',30)]:
        baseline=[r for r in rows if r['game']==game and r['condition']=='baseline'and r['value']==value][:8]
        steered=[r for r in rows if r['game']==game and r['condition']=='steering'and r['value']==value][:8]
        seed=batch_seed(game,value,0)
        b=runtime.generate_batch(baseline,seed,max_new_tokens=96)
        z=runtime.generate_batch(steered,seed,zero=True,max_new_tokens=96)
        s=runtime.generate_batch(steered,seed,max_new_tokens=96)
        for row,base,zero,edited in zip(baseline,b,z,s):
            exact=base['response']==zero['response']and base['generated_tokens']==zero['generated_tokens']
            trace_exact=all(result['trace']['hook_calls']==result['generated_tokens']for result in (zero,edited))
            checks.append(dict(game=game,id=row['id'],zero_exact=exact,positive_displacement=edited['trace']['changed_positions']>0,trace_token_count_exact=trace_exact))
            for condition,result in [('baseline',base),('zero_edit',zero),('steering',edited)]:
                examples.append(dict(id=row['id'],game=game,condition=condition,**result,parsed=parse_answer(game,result['response'])))
        if not all(c['zero_exact']and c['positive_displacement']and c['trace_token_count_exact']for c in checks):
            raise RuntimeError('GPU validation failed; full run is not permitted')
    for r in examples:append(output/'smoke-responses.jsonl',r)
    times={}
    for game in ('lottery','ultimatum'):
        batches=[r for r in examples if r['game']==game and r['condition']=='steering']
        times[game]=dict(batch_seconds=batches[0]['batch_elapsed_seconds'],batch_size=len(batches),
                         generated_tokens=sum(r['generated_tokens']for r in batches))
    report=dict(zero_edit_checks=len(checks),zero_edit_exact=all(c['zero_exact']for c in checks),
                positive_edits_with_displacement=sum(c['positive_displacement']for c in checks),
                trace_token_counts_exact=all(c['trace_token_count_exact']for c in checks),
                checks=checks,batch_timings=times,engineering_only=True)
    write(output/'smoke-summary.json',report)
    return report


def execute(args):
    started=time.monotonic();plan=load_plan(args.plan);rows=records(Path(args.plan)/'requests.jsonl')
    if len(rows)!=plan['request_count']:raise ValueError('Request count mismatch')
    output=Path(args.output);identity=dict(plan_hash=plan['plan_hash'],source_hashes=sources(),batch_size=plan['batch_size'])
    if output.exists():
        if not args.resume:raise FileExistsError('Output exists; explicit identical resume is required')
        old=read(output/'run.json')
        if old['identity']!=identity:raise ValueError('Resume identity mismatch')
        if old['status']=='completed':return old
    else:output.mkdir(parents=True)
    manifest=dict(identity=identity,status='loading',expected=len(rows),elapsed_seconds=0,scientific_use='transparent_local_replication_not_verified_hosted_equivalence')
    write(output/'run.json',manifest)
    from .runtime import PaperRuntime
    runtime=PaperRuntime();manifest.update(status='smoke',runtime=runtime.metadata);write(output/'run.json',manifest)
    if not (output/'smoke-summary.json').exists():smoke(runtime,rows,output)
    check=read(output/'smoke-summary.json')
    if not check['zero_edit_exact']or check['positive_edits_with_displacement']!=16 or not check['trace_token_counts_exact']:raise ValueError('Missing valid smoke')
    if args.smoke_only:
        manifest.update(status='smoke_completed',elapsed_seconds=time.monotonic()-started);write(output/'run.json',manifest);return manifest
    path=output/'responses.jsonl';existing=records(path);done={r['id']for r in existing}
    if len(done)!=len(existing):raise ValueError('Duplicate responses')
    expected_ids={r['id']for r in rows}
    if not done<=expected_ids:raise ValueError('Unexpected existing response IDs')
    manifest.update(status='running',completed=len(done));write(output/'run.json',manifest)
    for batch,seed in make_batches(rows,plan['batch_size']):
        if all(r['id']in done for r in batch):continue
        if time.monotonic()-started>args.max_seconds-180:
            manifest.update(status='time_limit',completed=len(done),elapsed_seconds=time.monotonic()-started);write(output/'run.json',manifest);return manifest
        outputs=runtime.generate_batch(batch,seed)
        invalid=[i for i,(r,result)in enumerate(zip(batch,outputs))if not parse_answer(r['game'],result['response'])['valid']]
        repaired={}
        if invalid:
            attempts=runtime.generate_batch([batch[i]for i in invalid],seed+1,
                                           repair_responses=[outputs[i]['response']for i in invalid])
            repaired=dict(zip(invalid,attempts))
        for i,(row,result)in enumerate(zip(batch,outputs)):
            if row['id']in done:continue
            first=parse_answer(row['game'],result['response'])
            final=repaired.get(i,result)
            record={k:row[k]for k in ('id','game','condition','value','agent_index')}
            record.update(result,first_attempt_parse=first,repair=repaired.get(i),final_parse=parse_answer(row['game'],final['response']))
            append(path,record);done.add(row['id'])
        manifest.update(status='running',completed=len(done),elapsed_seconds=time.monotonic()-started,
                        last_batch=dict(game=batch[0]['game'],condition=batch[0]['condition'],value=batch[0]['value']))
        write(output/'run.json',manifest)
        print(json.dumps({k:manifest[k]for k in ('status','completed','expected','elapsed_seconds','last_batch')}),flush=True)
    if done!=expected_ids:raise ValueError('Incomplete response set')
    manifest.update(status='completed',completed=len(done),elapsed_seconds=time.monotonic()-started,responses_sha256=file_hash(path))
    write(output/'run.json',manifest);return manifest


def main():
    p=argparse.ArgumentParser();p.add_argument('--plan',required=True);p.add_argument('--output',required=True)
    p.add_argument('--max-seconds',type=int,default=6600);p.add_argument('--resume',action='store_true');p.add_argument('--smoke-only',action='store_true')
    p.add_argument('--deadline',help='Absolute UTC provider-stop deadline, including bootstrap time')
    args=p.parse_args()
    if args.deadline:
        import datetime as dt
        remaining=(dt.datetime.fromisoformat(args.deadline.replace('Z','+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()
        # Recalculate after bootstrap so migration/cache preparation cannot
        # extend the run. Together with execute's batch reserve, this leaves
        # approximately four minutes to collect results before provider stop.
        args.max_seconds=min(args.max_seconds,max(0,int(remaining)-60))
    try:result=execute(args)
    except Exception as error:
        path=Path(args.output)/'run.json'
        if path.exists():
            state=read(path);state.update(status='failed',error_type=type(error).__name__);write(path,state)
        raise
    print(json.dumps(result,indent=2))
    if result['status']not in ('completed','smoke_completed'):raise SystemExit(2)


if __name__=='__main__':main()
