"""Launch only on an already authorized, running pod. Arm shutdown before upload."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import tarfile

from .auth import resolve_token
from .remote_session import ssh_command
from .replay_plan import SOURCE
from .smoke import save_json


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--pod-id',required=True);p.add_argument('--session',required=True);p.add_argument('--deadline',required=True)
    p.add_argument('--key',type=Path,default=Path('~/.ssh/runpod_codex_ed25519'))
    args=p.parse_args();root=Path(__file__).parent.resolve()
    remaining=(dt.datetime.fromisoformat(args.deadline.replace('Z','+00:00'))-dt.datetime.now(dt.timezone.utc)).total_seconds()
    if not 0<remaining<=7200:raise ValueError('Deadline must be within two hours')
    if not all(c.isalnum() or c in '-_' for c in args.session):raise ValueError('Invalid session')
    guard_code=r'''
import json,pathlib,subprocess,sys
p=json.load(sys.stdin);root=pathlib.Path('/workspace/anchor_pilot');root.mkdir(parents=True,exist_ok=True)
(root/'stop_guard.py').write_text(p['source'])
command=[sys.executable,'-u',str(root/'stop_guard.py'),'--pod-id',p['pod_id']]
subprocess.run(command+['--check'],check=True)
with (root/('guard-'+p['session']+'.log')).open('x') as log:
    guard=subprocess.Popen(command+['--deadline',p['deadline']],stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'guard_pid':guard.pid,'deadline':p['deadline']}))
'''
    payload={'source':(root/'stop_guard.py').read_text(),'pod_id':args.pod_id,'session':args.session,'deadline':args.deadline}
    result=subprocess.run(ssh_command(args,'python3 -c '+shlex.quote(guard_code)),input=json.dumps(payload).encode(),capture_output=True,check=True)
    print(result.stdout.decode(),flush=True)
    files=[(f,'anchor_pilot/'+f.name) for f in root.iterdir() if f.is_file() and f.suffix in ('.py','.sh','.txt','.md')]
    files += [(root/'outputs/decision-plan-v2'/name,'anchor_pilot/outputs/decision-plan-v2/'+name) for name in ('manifest.json','rows.json','controls.json','calibration.json')]
    files += [(SOURCE/name,'anchor_pilot/replay-source/'+name) for name in ('adapter/adapter.pt','adapter/adapter_config.json','footprint.pt','sparse_geometry_diagnostic.json')]
    proc=subprocess.Popen(ssh_command(args,'cd /workspace && tar -xzf -'),stdin=subprocess.PIPE)
    try:
        with tarfile.open(fileobj=proc.stdin,mode='w|gz') as archive:
            for file,name in files:archive.add(file,arcname=name)
        proc.stdin.close()
        if proc.wait()!=0:raise RuntimeError('Source upload failed; guard remains armed')
    finally:
        if proc.poll() is None:proc.terminate()
    token=resolve_token('first-token')
    if not token:raise RuntimeError('Named model token missing')
    runner=r'''
import json,os,pathlib,subprocess,sys
p=json.load(sys.stdin);root=pathlib.Path('/workspace/anchor_pilot')
env=dict(os.environ,HF_TOKEN=p['token'],HF_HOME='/workspace/hf',PYTHONUNBUFFERED='1',ANCHOR_SESSION_DEADLINE=p['deadline'])
command='import pathlib,subprocess,sys; code=subprocess.call(["bash",sys.argv[2]]); pathlib.Path(sys.argv[1]).write_text(str(code))'
with (root/('session-'+p['session']+'.log')).open('x') as log:
    job=subprocess.Popen([sys.executable,'-u','-c',command,str(root/('exit-'+p['session']+'.txt')),str(root/'run_decision.sh')],env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'job_pid':job.pid,'session':p['session']}))
'''
    result=subprocess.run(ssh_command(args,'python3 -c '+shlex.quote(runner)),input=json.dumps({'token':token,'session':args.session,'deadline':args.deadline}).encode(),capture_output=True)
    print(result.stdout.decode().replace(token,'[REDACTED]'),flush=True)
    if result.returncode:raise RuntimeError('Remote launch failed; guard remains armed')
    save_json(root/'outputs'/('launch-'+args.session+'.json'),{'arguments':{k:str(v) for k,v in vars(args).items()},'source_hashes':{name:hashlib.sha256(file.read_bytes()).hexdigest() for file,name in files}})


if __name__=='__main__':main()
