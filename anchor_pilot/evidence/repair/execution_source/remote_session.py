"""Authorized Runpod session launch/collection via SSH; never prints secrets.

This does not deploy or start a pod. Call only AFTER the separate paid restart
approval. The operator supplies the live SSH endpoint and absolute stop time.
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

from .auth import resolve_token


def ssh_command(args, command):
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15', '-i', str(args.key.expanduser()),
            '-p', str(args.port), 'root@' + args.host, command]


def launch(args):
    deadline = dt.datetime.fromisoformat(args.deadline.replace('Z', '+00:00'))
    remaining = (deadline - dt.datetime.now(dt.timezone.utc)).total_seconds()
    if not 0 < remaining <= 7200:
        raise ValueError('The absolute stop time must be in the next two hours')
    package = Path(__file__).resolve().parent
    files = [p for p in package.iterdir() if p.is_file() and p.suffix in ('.py', '.sh', '.txt', '.md')]
    design = 'repair-plan-v1' if args.runner == 'run_repair.sh' else 'design-v1'
    files += [package / 'outputs' / design / name for name in ('manifest.json', 'rows.json')]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for file in files:
            archive.add(file, arcname='anchor_pilot/' + str(file.relative_to(package)))
    subprocess.run(ssh_command(args, 'mkdir -p /workspace && cd /workspace && tar -xzf -'), input=stream.getvalue(), check=True)
    token = resolve_token(args.hf_token_name)
    if not token:
        raise RuntimeError('Named model credential missing')
    payload = {'hf_token': token, 'deadline': args.deadline, 'pod_id': args.pod_id,
               'session': args.session, 'runner': args.runner}
    # Token travels over encrypted SSH stdin, not a shell argument or token file.
    remote = r'''
import json, os, pathlib, subprocess, sys
p = json.load(sys.stdin)
root = pathlib.Path('/workspace/anchor_pilot')
env = dict(os.environ, HF_TOKEN=p['hf_token'], HF_HOME='/workspace/hf', PYTHONUNBUFFERED='1',
           ANCHOR_SESSION_DEADLINE=p['deadline'])
guard = [sys.executable, '-u', str(root / 'stop_guard.py'), '--pod-id', p['pod_id']]
subprocess.run(guard + ['--check'], check=True, env=env)
with (root / ('guard-' + p['session'] + '.log')).open('x') as log:
    proc = subprocess.Popen(guard + ['--deadline', p['deadline']], stdin=subprocess.DEVNULL,
                            stdout=log, stderr=log, env=env, start_new_session=True)
if p['runner'] not in ('run_pilot.sh', 'run_repair.sh'): raise ValueError('Unsupported runner')
runner = 'import pathlib,subprocess,sys; code=subprocess.call(["bash",sys.argv[2]]); pathlib.Path(sys.argv[1]).write_text(str(code))'
exit_file = root / ('exit-' + p['session'] + '.txt')
with (root / ('session-' + p['session'] + '.log')).open('x') as log:
    job = subprocess.Popen([sys.executable, '-u', '-c', runner, str(exit_file), str(root / p['runner'])], stdin=subprocess.DEVNULL,
                           stdout=log, stderr=log, env=env, start_new_session=True)
print(json.dumps({'guard_pid': proc.pid, 'job_pid': job.pid, 'session': p['session'], 'deadline': p['deadline']}))
'''
    result = subprocess.run(ssh_command(args, 'python3 -c ' + shlex.quote(remote)),
                            input=json.dumps(payload).encode(), capture_output=True)
    # Defensive redaction before exposing bootstrap errors from remote libraries.
    print(result.stdout.decode(errors='replace').replace(token, '[REDACTED]'))
    if result.returncode:
        print(result.stderr.decode(errors='replace').replace(token, '[REDACTED]'))
        raise RuntimeError('Remote bootstrap failed; inspect pod and stop it if needed')
    source_hashes = {str(p.relative_to(package)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
    safe = {k: str(v) if isinstance(v, Path) else v for k, v in vars(args).items()}
    (package / 'outputs' / f'launch-{args.session}.json').write_text(json.dumps({'arguments': safe, 'source_hashes': source_hashes}, indent=2))


def launch_fidelity(args):
    package = Path(__file__).resolve().parent
    # Keep the running main experiment's source files intact.
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        files = [package / (args.completion_module.rsplit('.', 1)[-1] + '.py')]
        files += list((package / 'outputs/refinement-plan').glob('*.json')) if args.completion_module.endswith('.refine') else [package / 'outputs/fidelity_plan.json']
        for file in files:
            archive.add(file, arcname='anchor_pilot/' + str(file.relative_to(package)))
    subprocess.run(ssh_command(args, 'cd /workspace && tar -xzf -'), input=stream.getvalue(), check=True)
    token = resolve_token(args.hf_token_name)
    payload = {'hf_token': token, 'session': args.session, 'after': args.after_session, 'module': args.completion_module}
    remote = r'''
import json,os,pathlib,subprocess,sys
p=json.load(sys.stdin);root=pathlib.Path('/workspace/anchor_pilot')
env=dict(os.environ,HF_TOKEN=p['hf_token'],HF_HOME='/workspace/hf',PYTHONUNBUFFERED='1')
runner=''' + repr('''import pathlib,subprocess,sys,time
root=pathlib.Path('/workspace/anchor_pilot');source=root/('exit-'+sys.argv[1]+'.txt');destination=root/('exit-'+sys.argv[2]+'.txt')
while not source.exists(): time.sleep(5)
code=int(source.read_text())
if code==0: code=subprocess.call(['/workspace/anchor_pilot/.venv/bin/python','-u','-m',sys.argv[3]],cwd='/workspace')
destination.write_text(str(code))
''') + r'''
with (root/('session-'+p['session']+'.log')).open('x') as log:
    job=subprocess.Popen([sys.executable,'-u','-c',runner,p['after'],p['session'],p['module']],env=env,
                          stdin=subprocess.DEVNULL,stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'job_pid':job.pid,'session':p['session'],'after_session':p['after']}))
'''
    result = subprocess.run(ssh_command(args, 'python3 -c ' + shlex.quote(remote)),
                            input=json.dumps(payload).encode(), capture_output=True)
    print(result.stdout.decode(errors='replace').replace(token, '[REDACTED]'))
    if result.returncode:
        print(result.stderr.decode(errors='replace').replace(token, '[REDACTED]'))
        raise RuntimeError('Fidelity supervisor failed to launch')


def collect(args):
    # Read-only transfer: package experiment outputs/logs and adapters, excluding
    # the model cache, venv, process environment, and any credential stores.
    remote = r'''
import io, pathlib, sys, tarfile
root = pathlib.Path('/workspace/anchor_pilot')
with tarfile.open(fileobj=sys.stdout.buffer, mode='w|gz') as archive:
    archive.add(root / 'outputs', arcname='outputs')
    for pattern in ('session-*.log', 'guard-*.log', 'exit-*.txt'):
        for file in root.glob(pattern):
            archive.add(file, arcname=file.name)
'''
    destination = args.destination
    destination.mkdir(parents=True, exist_ok=False)
    tar_path = destination / 'remote-artifacts.tar.gz'
    with tar_path.open('wb') as handle:
        subprocess.run(ssh_command(args, 'python3 -c ' + shlex.quote(remote)), stdout=handle, check=True)
    with tarfile.open(tar_path, 'r:gz') as archive:
        archive.extractall(destination, filter='data')
    hashes = {str(p.relative_to(destination)): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in destination.rglob('*') if p.is_file()}
    (destination / 'sha256.json').write_text(json.dumps(hashes, indent=2))
    print(json.dumps({'destination': str(destination), 'files': len(hashes), 'archive_sha256': hashes['remote-artifacts.tar.gz']}))


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['launch', 'collect', 'fidelity'])
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--key', type=Path, default=Path('~/.ssh/runpod_codex_ed25519'))
    p.add_argument('--pod-id', default='9xc474y2j2oumc')
    p.add_argument('--hf-token-name', default='first-token')
    p.add_argument('--session')
    p.add_argument('--deadline')
    p.add_argument('--runner', choices=['run_pilot.sh', 'run_repair.sh'], default='run_pilot.sh')
    p.add_argument('--after-session')
    p.add_argument('--completion-module', choices=['anchor_pilot.fidelity', 'anchor_pilot.refine'], default='anchor_pilot.fidelity')
    p.add_argument('--destination', type=Path)
    args = p.parse_args()
    if args.action == 'launch':
        if not args.session or not args.deadline or not all(c.isalnum() or c in '-_' for c in args.session):
            p.error('Launch requires an alphanumeric session name and absolute UTC deadline')
        launch(args)
    elif args.action == 'fidelity':
        if not args.after_session or not args.session:
            p.error('Fidelity needs session and after-session names')
        launch_fidelity(args)
    else:
        if not args.destination:
            p.error('Collect requires a new destination directory')
        collect(args)


if __name__ == '__main__':
    main()
