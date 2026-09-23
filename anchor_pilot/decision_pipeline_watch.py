"""Back up stage one, launch the predeclared refinement, and stop after final backup."""
import argparse
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from .auth import resolve_token
from .watch_session import backup,remote_python


def main():
    p=argparse.ArgumentParser();p.add_argument('--host',required=True);p.add_argument('--port',type=int,required=True)
    p.add_argument('--pod-id',required=True);p.add_argument('--session',required=True);p.add_argument('--deadline',required=True)
    p.add_argument('--key',type=Path,default=Path('~/.ssh/runpod_codex_ed25519'));p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--stage1',required=True);args=p.parse_args()
    manifest=args.destination/'verified_remote_files.json';previous=json.loads(manifest.read_text())
    # Reconcile any file whose copy was interrupted while handing over supervision.
    previous={n:v for n,v in previous.items() if (args.destination/n).exists() and hashlib.sha256((args.destination/n).read_bytes()).hexdigest()==v['sha256']}
    deadline=dt.datetime.fromisoformat(args.deadline).timestamp();errors=0
    while True:
        try:
            state,changed=backup(args,previous);errors=0
            print(json.dumps({'stage':'initial','verified_files':len(previous),'changed':changed,'utc':dt.datetime.now(dt.timezone.utc).isoformat()}),flush=True)
            if 'exit-'+args.session+'.txt' in state:break
        except Exception as error:
            errors+=1;print(json.dumps({'backup_error_type':type(error).__name__,'consecutive_errors':errors}),flush=True)
            if errors>=5:raise
        if time.time()>deadline-3000:raise RuntimeError('Insufficient time for refinement; independent guard remains armed')
        time.sleep(30)
    code=(args.destination/('exit-'+args.session+'.txt')).read_text().strip()
    if code!='0':raise RuntimeError('Initial stage failed; backed up, guard remains armed')
    if deadline-time.time()<2700:raise RuntimeError('Insufficient time for complete refinement')
    session=args.session+'-refine';output='anchor_pilot/outputs/decision-refined-'+dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    runner=r'''
import json,os,pathlib,subprocess,sys,time,datetime
p=json.load(sys.stdin);root=pathlib.Path('/workspace/anchor_pilot')
env=dict(os.environ,HF_TOKEN=p['token'],HF_HOME='/workspace/hf',PYTHONUNBUFFERED='1',OMP_NUM_THREADS='8',TOKENIZERS_PARALLELISM='false')
remaining=int(datetime.datetime.fromisoformat(p['deadline']).timestamp()-time.time()-720)
supervisor='import pathlib,subprocess,sys; code=subprocess.call(sys.argv[2:]); pathlib.Path(sys.argv[1]).write_text(str(code))'
command=[str(root/'.venv/bin/python'),'-u','-c',supervisor,str(root/('exit-'+p['session']+'.txt')),'timeout','--signal=TERM','--kill-after=30s',str(remaining)+'s',str(root/'.venv/bin/python'),'-u','-m','anchor_pilot.decision_refine','--stage1',p['stage1'],'--output',p['output']]
with (root/('session-'+p['session']+'.log')).open('x') as log:
    process=subprocess.Popen(command,cwd='/workspace',env=env,stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'session':p['session'],'pid':process.pid,'output':p['output']}))
'''
    result=json.loads(remote_python(args,runner,{'token':resolve_token('first-token'),'deadline':args.deadline,'session':session,'stage1':args.stage1,'output':output}))
    (args.destination/'refinement_launch.json').write_text(json.dumps(result,indent=2));print(json.dumps(result),flush=True)
    command=[sys.executable,'-u','-m','anchor_pilot.watch_session','--host',args.host,'--port',str(args.port),'--pod-id',args.pod_id,
             '--session',session,'--deadline',args.deadline,'--key',str(args.key),'--destination',str(args.destination),'--resume','--stop-on-failure']
    subprocess.run(command,check=True)


if __name__=='__main__':main()
