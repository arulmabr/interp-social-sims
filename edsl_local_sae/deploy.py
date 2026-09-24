"""Upload, inspect and collect an EDSL diagnostic in an existing guarded session."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
import shlex
import subprocess
import tarfile

from label_pilot.access import load_credentials
from label_pilot.common import file_hash, read, write
from label_pilot.deploy import remaining, ssh_args, stop
from paper_replication.deploy import source_archive as runtime_archive

ROOT = Path(__file__).resolve().parent
REMOTE = '/workspace/sae-label-pilot'


def source_archive(plan):
    data = io.BytesIO()
    with tarfile.open(fileobj=data, mode='w:gz') as out:
        with tarfile.open(fileobj=io.BytesIO(runtime_archive(plan)), mode='r:gz') as src:
            for member in src.getmembers():
                out.addfile(member, src.extractfile(member) if member.isfile() else None)
        for pattern in ('*.py', '*.sh', '*.txt', '*.md', 'tests/*.py'):
            for path in sorted(ROOT.glob(pattern)):
                out.add(path, arcname='edsl_local_sae/'+str(path.relative_to(ROOT)))
    return data.getvalue()


def remote(session, code, payload=None, timeout=60):
    result = subprocess.run(ssh_args(session, session['provider'], 'python3 -c '+shlex.quote(code)),
                            input=json.dumps(payload).encode() if payload is not None else None,
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Remote command failed; inspect the saved pod state without printing credentials')
    return json.loads(result.stdout.decode().splitlines()[-1])


def launch(args, session):
    if session.get('launched') or not session.get('guard_pid'):
        raise ValueError('Need a fresh attached session with its shutdown guard')
    if not 600 < remaining(session) <= 7200:
        raise ValueError('Need ten minutes to two hours on the current approved session')
    if not args.run_id or not re.fullmatch('[A-Za-z0-9_-]{1,80}', args.run_id):
        raise ValueError('Invalid run ID')
    package = source_archive(args.plan)
    sha = hashlib.sha256(package).hexdigest()
    path = ROOT/'outputs/uploads'/f'{sha}.tar.gz'
    path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(package)
    subprocess.run(ssh_args(session, session['provider'], f'cd {REMOTE} && tar --no-same-owner -xzf -'),
                   input=package, check=True, timeout=60)
    from huggingface_hub import get_token
    payload = dict(run_id=args.run_id, pod_id=session['pod_id'], guard_pid=session['guard_pid'],
                   deadline=session['stop_deadline_utc'], seconds=int(remaining(session))-180,
                   hf_token=load_credentials().get('HF_TOKEN') or get_token())
    code = r'''import json,os,pathlib,subprocess,sys
p=json.load(sys.stdin);root=pathlib.Path('/workspace/sae-label-pilot');os.chdir(root)
guard=pathlib.Path('/proc')/str(p['guard_pid'])/'cmdline'
tokens=guard.read_bytes().decode().split('\0')
assert p['pod_id'] in tokens and p['deadline'] in tokens and any(t.endswith('stop_guard.py') for t in tokens)
out=root/'edsl-results'/p['run_id'];out.mkdir(parents=True,exist_ok=False)
env=dict(os.environ,HF_HOME='/workspace/hf',PYTHONUNBUFFERED='1')
if p['hf_token']:env['HF_TOKEN']=p['hf_token']
worker="import pathlib,subprocess,sys,json; rc=subprocess.call(sys.argv[2:]); pathlib.Path(sys.argv[1]).write_text(json.dumps({'exit_code':rc}))"
command=['timeout','--signal=TERM','--kill-after=30s',str(p['seconds'])+'s','bash','edsl_local_sae/bootstrap.sh',str(out/'requirements-frozen.txt'),'--plan','replication-plan','--output',str(out/'run'),'--pod-id',p['pod_id'],'--guard-pid',str(p['guard_pid']),'--deadline',p['deadline']]
with (out/'job.log').open('x') as log:
    proc=subprocess.Popen([sys.executable,'-u','-c',worker,str(out/'exit.json'),*command],stdin=subprocess.DEVNULL,stdout=log,stderr=log,env=env,start_new_session=True)
print(json.dumps({'job_pid':proc.pid,'run_id':p['run_id']}))
'''
    try:
        launched = remote(session, code, payload)
    except Exception:
        stop(session)
        raise
    session.update(launched=launched, source_archive=str(path), archive_sha256=sha)
    write(args.session, session)
    return dict(pod_id=session['pod_id'], deadline=session['stop_deadline_utc'], **launched)


def status(session):
    run_id = session['launched']['run_id']
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}', run_id):
        raise ValueError('Invalid stored run ID')
    code = 'run_id='+repr(run_id)+'\n'+r'''from pathlib import Path
import json,subprocess,re
p=Path('/workspace/sae-label-pilot/edsl-results')/run_id
out={}
for name in ('exit.json','run/run.json','run/smoke/smoke-summary.json','run/replays/progress.json'):
    f=p/name
    if f.exists():
        data=json.loads(f.read_text())
        out[name]={k:v for k,v in data.items() if k not in ('adapter_source_hashes','runtime_source_hashes')}
f=p/'job.log'
if f.exists():
    lines=f.read_text(errors='replace').splitlines()[-5:]
    out['log_tail']=[re.sub(r'(hf_[A-Za-z0-9]+|rpa_[A-Za-z0-9_-]+)', '[REDACTED]',s) for s in lines]
out['gpu']=subprocess.run(['nvidia-smi','--query-gpu=name,memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True).stdout.strip()
print(json.dumps(out))
'''
    return remote(session, code)


def collect(args, session):
    run_id = session['launched']['run_id']
    if not re.fullmatch('[A-Za-z0-9_-]{1,80}', run_id):
        raise ValueError('Invalid stored run ID')
    destination = Path(args.output); destination.mkdir(parents=True, exist_ok=False)
    archive = destination/'results.tar.gz'
    with archive.open('wb') as handle:
        subprocess.run(ssh_args(session, session['provider'], f'cd {REMOTE} && tar -czf - edsl-results/'+run_id),
                       stdout=handle, check=True, timeout=90)
    with tarfile.open(archive) as tar:
        tar.extractall(destination, filter='data')
    hashes = {str(p.relative_to(destination)):file_hash(p) for p in destination.rglob('*') if p.is_file()}
    write(destination/'sha256.json', hashes)
    result = dict(files_saved=len(hashes), destination=str(destination))
    if args.stop_after:
        result['shutdown'] = stop(session)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['launch', 'status', 'collect'])
    parser.add_argument('--session', required=True)
    parser.add_argument('--plan'); parser.add_argument('--run-id')
    parser.add_argument('--output'); parser.add_argument('--stop-after', action='store_true')
    args = parser.parse_args(); session = read(args.session)
    result = launch(args, session) if args.action == 'launch' else status(session) if args.action == 'status' else collect(args, session)
    print(json.dumps(result, indent=2))
