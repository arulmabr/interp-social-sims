"""Upload only pinned source and request inputs; reuse verified, time-bounded pod sessions."""
import argparse
import io
import json
import re
import shlex
import subprocess
import tarfile
from pathlib import Path

from label_pilot.access import load_credentials
from label_pilot.deploy import ssh_args,remaining,arm_guard,stop
from .common import ROOT,read,write,load_plan,file_hash


def source_archive(plan_dir):
    plan_dir=Path(plan_dir);load_plan(plan_dir);buffer=io.BytesIO()
    with tarfile.open(fileobj=buffer,mode='w:gz')as tar:
        for folder in (ROOT,ROOT.parent/'label_pilot'):
            for pattern in ('*.py','*.sh','*.txt','tests/*.py','config/*.json'):
                for path in sorted(folder.glob(pattern)):
                    tar.add(path,arcname=str(path.relative_to(ROOT.parent)))
        for name in ('plan.json','requests.jsonl'):
            tar.add(plan_dir/name,arcname='replication-plan/'+name)
    return buffer.getvalue()


def launch(args):
    session=read(args.session)
    if session.get('launched'):raise ValueError('Session already launched')
    seconds=int(remaining(session))-60
    if not 180<seconds<=7200:raise ValueError('A fresh bounded session is required')
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',args.run_id):raise ValueError('Invalid run ID')
    if not session.get('guard_pid'):
        session.update(arm_guard(session,session['provider']));write(args.session,session)
    package=source_archive(args.plan)
    import hashlib
    sha=hashlib.sha256(package).hexdigest();archive=ROOT/'outputs/uploads'/f'{sha}.tar.gz'
    archive.parent.mkdir(parents=True,exist_ok=True);archive.write_bytes(package)
    subprocess.run(ssh_args(session,session['provider'],'cd /workspace/sae-label-pilot && tar --no-same-owner -xzf -'),input=package,check=True)
    code='''import json,os,pathlib,subprocess,sys
p=json.load(sys.stdin);root=pathlib.Path('/workspace/sae-label-pilot');os.chdir(root)
out=root/'replication-results'/p['run_id'];out.mkdir(parents=True,exist_ok=True)
if (out/'run').exists() and not p['resume']:raise RuntimeError('Existing output requires resume')
(out/'exit.json').unlink(missing_ok=True)
env=dict(os.environ,HF_HOME='/workspace/hf',PYTHONUNBUFFERED='1')
if p['hf_token']:env['HF_TOKEN']=p['hf_token']
worker="import pathlib,subprocess,sys,json; rc=subprocess.call(sys.argv[2:]); pathlib.Path(sys.argv[1]).write_text(json.dumps({'exit_code':rc}))"
command=['timeout','--signal=TERM','--kill-after=30s',str(p['seconds'])+'s','bash','paper_replication/bootstrap.sh','--plan','replication-plan','--output',str(out/'run'),'--max-seconds',str(p['seconds']-90),'--deadline',p['deadline']]
if p['resume']:command+=['--resume']
if p['smoke_only']:command+=['--smoke-only']
with(out/'job.log').open('a')as log:
 job=subprocess.Popen([sys.executable,'-u','-c',worker,str(out/'exit.json'),*command],stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env,start_new_session=True)
print(json.dumps({'job_pid':job.pid,'run_id':p['run_id']}))
'''
    from huggingface_hub import get_token
    payload=dict(run_id=args.run_id,seconds=seconds,deadline=session['stop_deadline_utc'],resume=args.resume,smoke_only=args.smoke_only,
                 hf_token=load_credentials().get('HF_TOKEN')or get_token())
    result=subprocess.run(ssh_args(session,session['provider'],'python3 -c '+shlex.quote(code)),input=json.dumps(payload).encode(),capture_output=True)
    if result.returncode:
        stop(session);raise RuntimeError('Launch failed; pod stop requested')
    launched=json.loads(result.stdout.decode().splitlines()[-1]);session.update(launched=launched,source_archive=str(archive),archive_sha256=sha)
    write(args.session,session);return dict(pod_id=session['pod_id'],deadline=session['stop_deadline_utc'],**launched)


def status(args):
    session=read(args.session);run_id=session['launched']['run_id']
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}',run_id):raise ValueError('Invalid stored run ID')
    code='run_id='+repr(run_id)+'\n'+'''from pathlib import Path
import json,subprocess
p=Path('/workspace/sae-label-pilot/replication-results')/run_id
out={}
for name in ('exit.json','run/run.json','run/smoke-summary.json'):
 f=p/name
 if f.exists():
  v=json.loads(f.read_text());out[name]={k:x for k,x in v.items()if k not in ('identity','checks')}
f=p/'job.log'
if f.exists():out['log_tail']=f.read_text(errors='replace').splitlines()[-10:]
out['gpu']=subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()
print(json.dumps(out))
'''
    result=subprocess.run(ssh_args(session,session['provider'],'python3 -'),input=code.encode(),capture_output=True,timeout=45)
    text=(result.stdout+result.stderr).decode(errors='replace')
    for value in load_credentials().values():
        if value:text=text.replace(value,'[REDACTED]')
    if result.returncode:raise RuntimeError('Remote status unavailable')
    return json.loads(text)


def collect(args):
    session=read(args.session);destination=Path(args.output);destination.mkdir(parents=True,exist_ok=False)
    archive=destination/'results.tar.gz'
    with archive.open('wb')as f:
        subprocess.run(ssh_args(session,session['provider'],'cd /workspace/sae-label-pilot && tar -czf - replication-results'),stdout=f,check=True)
    with tarfile.open(archive)as tar:tar.extractall(destination,filter='data')
    hashes={str(p.relative_to(destination)):file_hash(p)for p in destination.rglob('*')if p.is_file()};write(destination/'sha256.json',hashes)
    result=dict(files_saved=len(hashes),destination=str(destination))
    if args.stop_after:result['shutdown']=stop(session)
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['launch','status','collect']);p.add_argument('--session',required=True)
    p.add_argument('--plan');p.add_argument('--run-id');p.add_argument('--resume',action='store_true');p.add_argument('--smoke-only',action='store_true')
    p.add_argument('--output');p.add_argument('--stop-after',action='store_true');a=p.parse_args()
    if a.action=='launch':result=launch(a)
    elif a.action=='status':result=status(a)
    else:result=collect(a)
    print(json.dumps(result,indent=2))
