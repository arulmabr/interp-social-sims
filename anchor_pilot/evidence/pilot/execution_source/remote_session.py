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
    files += [package / 'outputs' / 'design-v1' / name for name in ('manifest.json', 'rows.json')]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for file in files:
            archive.add(file, arcname='anchor_pilot/' + str(file.relative_to(package)))
    subprocess.run(ssh_command(args, 'mkdir -p /workspace && cd /workspace && tar -xzf -'), input=stream.getvalue(), check=True)
    token = resolve_token(args.hf_token_name)
    if not token:
        raise RuntimeError('Named model credential missing')
    payload = {'hf_token': token, 'deadline': args.deadline, 'pod_id': args.pod_id, 'session': args.session}
    # Token travels over encrypted SSH stdin, not a shell argument or token file.
    remote = r'''
import json, os, pathlib, subprocess, sys
p = json.load(sys.stdin)
root = pathlib.Path('/workspace/anchor_pilot')
env = dict(os.environ, HF_TOKEN=p['hf_token'], HF_HOME='/workspace/hf', PYTHONUNBUFFERED='1')
guard = [sys.executable, '-u', str(root / 'stop_guard.py'), '--pod-id', p['pod_id']]
subprocess.run(guard + ['--check'], check=True, env=env)
with (root / ('guard-' + p['session'] + '.log')).open('x') as log:
    proc = subprocess.Popen(guard + ['--deadline', p['deadline']], stdin=subprocess.DEVNULL,
                            stdout=log, stderr=log, env=env, start_new_session=True)
runner = 'import pathlib,subprocess,sys; code=subprocess.call(["bash","/workspace/anchor_pilot/run_pilot.sh"]); pathlib.Path(sys.argv[1]).write_text(str(code))'
exit_file = root / ('exit-' + p['session'] + '.txt')
with (root / ('session-' + p['session'] + '.log')).open('x') as log:
    job = subprocess.Popen([sys.executable, '-u', '-c', runner, str(exit_file)], stdin=subprocess.DEVNULL,
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
    p.add_argument('action', choices=['launch', 'collect'])
    p.add_argument('--host', required=True)
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--key', type=Path, default=Path('~/.ssh/runpod_codex_ed25519'))
    p.add_argument('--pod-id', default='9xc474y2j2oumc')
    p.add_argument('--hf-token-name', default='first-token')
    p.add_argument('--session')
    p.add_argument('--deadline')
    p.add_argument('--destination', type=Path)
    args = p.parse_args()
    if args.action == 'launch':
        if not args.session or not args.deadline or not all(c.isalnum() or c in '-_' for c in args.session):
            p.error('Launch requires an alphanumeric session name and absolute UTC deadline')
        launch(args)
    else:
        if not args.destination:
            p.error('Collect requires a new destination directory')
        collect(args)


if __name__ == '__main__':
    main()
