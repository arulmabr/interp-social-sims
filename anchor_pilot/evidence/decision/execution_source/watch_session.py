"""Continuously back up generated artifacts, then stop the authorized GPU pod.

Only reads named experiment outputs/logs, never model caches or environments.
Hashes remote files and verifies transferred bytes before marking backup valid.
Intended for a bounded foreground-session supervisor, not a scheduled task.
"""
import argparse
import datetime as dt
import hashlib
import io
import json
from pathlib import Path
import shlex
import subprocess
import tarfile
import time

from .remote_session import ssh_command


def remote_python(args, code, payload=None, timeout=180):
    result = subprocess.run(ssh_command(args, 'python3 -c ' + shlex.quote(code)),
                            input=json.dumps(payload).encode() if payload is not None else None,
                            capture_output=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError('Read-only remote artifact request failed')
    return result.stdout


def backup(args, previous):
    code = r'''
import hashlib,json,pathlib
root=pathlib.Path('/workspace/anchor_pilot')
files=list((root/'outputs').rglob('*'))
for pat in ('session-*.log','guard-*.log','exit-*.txt'):
    files.extend(root.glob(pat))
out={}
for p in files:
    if p.is_file() and not p.name.endswith('.tmp'):
        s=p.stat()
        out[str(p.relative_to(root))]={'size':s.st_size,'mtime_ns':s.st_mtime_ns}
print(json.dumps(out))
'''
    state = json.loads(remote_python(args, code))
    changed = [name for name, stat in state.items() if previous.get(name, {}).get('stat') != stat]
    if changed:
        # Emit manifest and file contents from the SAME in-memory byte read, so
        # live log growth cannot create a false content/hash match.
        transfer = r'''
import hashlib,io,json,pathlib,sys,tarfile,time
root=pathlib.Path('/workspace/anchor_pilot'); names=json.load(sys.stdin); hashes={}
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|gz') as archive:
    for name in names:
        p=(root/name).resolve()
        if root not in p.parents: raise RuntimeError('Artifact path outside experiment root')
        data=p.read_bytes(); hashes[name]=hashlib.sha256(data).hexdigest()
        info=tarfile.TarInfo(name); info.size=len(data); archive.addfile(info,io.BytesIO(data))
    data=json.dumps(hashes).encode(); info=tarfile.TarInfo('transfer_hashes.json');info.size=len(data)
    archive.addfile(info,io.BytesIO(data))
'''
        blob = remote_python(args, transfer, changed, timeout=600)
        with tarfile.open(fileobj=io.BytesIO(blob), mode='r:gz') as archive:
            archive.extractall(args.destination, filter='data')
        hashes = json.loads((args.destination / 'transfer_hashes.json').read_text())
        for name in changed:
            actual = hashlib.sha256((args.destination / name).read_bytes()).hexdigest()
            if actual != hashes[name]:
                raise RuntimeError('Artifact hash mismatch')
            previous[name] = {'stat': state[name], 'sha256': actual}
        (args.destination / 'verified_remote_files.json').write_text(json.dumps(previous, indent=2))
    return state, len(changed)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--host',required=True)
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--key',type=Path,default=Path('~/.ssh/runpod_codex_ed25519'))
    p.add_argument('--pod-id',required=True)
    p.add_argument('--session',required=True)
    p.add_argument('--deadline',required=True)
    p.add_argument('--destination',type=Path,required=True)
    p.add_argument('--stop-on-failure',action='store_true',
                   help='After a verified final backup, stop even if the job exits with an error')
    p.add_argument('--resume',action='store_true',help='Resume an interrupted local backup using its verified manifest')
    args=p.parse_args()
    args.destination.mkdir(parents=True,exist_ok=args.resume)
    cutoff=dt.datetime.fromisoformat(args.deadline.replace('Z','+00:00')).timestamp()-600
    manifest=args.destination/'verified_remote_files.json'
    previous=json.loads(manifest.read_text()) if args.resume and manifest.exists() else {}
    errors=0
    while True:
        try:
            state, changed=backup(args,previous)
            errors=0
            exit_name='exit-'+args.session+'.txt'
            completed=exit_name in state
            print(json.dumps({'backup_utc':dt.datetime.now(dt.timezone.utc).isoformat(),
                              'verified_files':len(previous),'new_or_changed':changed,'job_exited':completed}),flush=True)
            if completed or time.time()>=cutoff:
                # Re-copy a final snapshot before stopping transient storage.
                backup(args,previous)
                code=(args.destination/exit_name).read_text() if completed else None
                if completed and code.strip() != '0' and time.time() < cutoff and not args.stop_on_failure:
                    report={'status':'job_failed_backed_up_for_repair','exit_code':code,
                            'stop_request_confirmed':False,'guard_still_armed':True,
                            'verified_files':len(previous),'pod_id':args.pod_id}
                    (args.destination/'session_completion.json').write_text(json.dumps(report,indent=2))
                    print(json.dumps(report),flush=True)
                    return
                result=subprocess.run(ssh_command(args,'python3 /workspace/anchor_pilot/stop_guard.py --pod-id '+shlex.quote(args.pod_id)+' --stop-now'),capture_output=True,timeout=60)
                output=result.stdout.decode(errors='replace')
                stop_confirmed='"stop_requested": true' in output
                report={'status':'job_exited' if completed else 'stopped_at_backup_cutoff',
                        'exit_code':code,'stop_request_confirmed':stop_confirmed,
                        'verified_files':len(previous),'pod_id':args.pod_id}
                (args.destination/'session_completion.json').write_text(json.dumps(report,indent=2))
                print(json.dumps(report),flush=True)
                return
        except Exception as error:
            errors+=1
            print(json.dumps({'backup_error_type':type(error).__name__,'consecutive_errors':errors}),flush=True)
            if errors>=5:
                raise RuntimeError('Backup failed repeatedly; inspect the paid pod immediately')
        time.sleep(30)


if __name__=='__main__':
    main()
