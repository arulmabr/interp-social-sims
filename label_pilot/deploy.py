"""Runpod smoke deployment, exact-session shutdown and artifact collection.

Creation is an explicit CLI action. No credentials are included in source
archives, public arguments, manifests or printed API responses.
"""
import argparse
import datetime as dt
import io
import json
import os
import re
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time

from .access import check, load_credentials, runpod_request
from .common import file_hash, read, write
from .prepare import load_plan

ROOT = Path(__file__).parent.resolve()
REMOTE = '/workspace/sae-label-pilot'


def now():
    return dt.datetime.now(dt.timezone.utc)


def remaining(session):
    return (dt.datetime.fromisoformat(session['stop_deadline_utc']) - now()).total_seconds()


def safe_pod(pod):
    return {k: pod.get(k) for k in ('id', 'name', 'desiredStatus', 'gpuCount', 'publicIp',
                                    'portMappings', 'costPerHr', 'adjustedCostPerHr')}


def uses_account_api(session):
    # Console sessions deliberately use their verified SSH endpoint and the
    # pod-scoped shutdown credential, even if an unrelated/invalid account key
    # happens to exist in the local credential file.
    return session.get('origin') != 'console_deployment' and bool(load_credentials().get('RUNPOD_API_KEY'))


def stop(session):
    if not uses_account_api(session):
        command = f'cd {REMOTE} && python3 stop_guard.py --pod-id ' + shlex.quote(session['pod_id']) + ' --stop-now'
        result = subprocess.run(ssh_args(session, session['provider'], command), capture_output=True)
        if result.returncode:
            raise RuntimeError('Pod-scoped SSH shutdown failed; stop this pod in the Runpod console')
        return {'stop_requested': True, 'pod_id': session['pod_id'], 'via': 'pod_scoped_guard'}
    runpod_request('POST', f"pods/{session['pod_id']}/stop")
    pod = runpod_request('GET', f"pods/{session['pod_id']}")
    return {'stop_requested': True, 'pod': safe_pod(pod)}


def watch(session_file):
    # A separate process survives the launcher, but remote guard is also required
    # before inference because this laptop may sleep or lose its connection.
    session = read(session_file)
    while remaining(session) > 0:
        time.sleep(max(0, min(20, remaining(session))))
    for attempt in range(10):
        try:
            result = stop(session)
            write(Path(session_file).with_suffix('.stop.json'), result)
            return result
        except Exception:
            time.sleep(10)
    raise RuntimeError('Provider stop could not be confirmed; inspect this exact pod immediately')


def create(args):
    if args.hours <= 0 or args.hours > 2 or args.budget <= 0 or args.budget > 25:
        raise ValueError('Initial deployment is bounded to at most two hours and $25')
    session_file = Path(args.session)
    if session_file.exists():
        raise FileExistsError('Choose a new session file')
    key = Path(args.key).expanduser()
    public_key = key.with_suffix(key.suffix + '.pub')
    if not key.is_file() or not public_key.is_file():
        raise FileNotFoundError('An existing SSH key pair is required')
    status = check()
    if not status.get('model_download_access') or not status['credential_presence']['RUNPOD_API_KEY']:
        raise RuntimeError('Configure working Runpod and model-download access before renting')
    payload = read(ROOT/'config/runpod.json')
    payload['env'] = {'PUBLIC_KEY': public_key.read_text().strip()}
    # Start deadline before POST so it includes provisioning and cold setup.
    started = now()
    pod = runpod_request('POST', 'pods', payload)
    pod_id = pod['id']
    price = float(pod.get('adjustedCostPerHr') or pod.get('costPerHr') or 0)
    # Conservative extra $0.25/hr covers this small volume/container allocation.
    billed_rate = price + .25
    if not price or price > args.max_hourly:
        emergency = {'pod_id': pod_id}
        session_file.parent.mkdir(parents=True, exist_ok=True)
        write(session_file, dict(emergency, status='price_rejected', provider= safe_pod(pod)))
        stop(emergency)
        raise RuntimeError('Returned price unavailable or above limit; requested stop for the new pod')
    seconds = min(args.hours*3600, args.budget/billed_rate*3600)
    session = {'pod_id': pod_id, 'name': payload['name'], 'created_utc': started.isoformat(),
               'stop_deadline_utc': (started + dt.timedelta(seconds=seconds)).isoformat(),
               'budget_usd': args.budget, 'provider_hourly_rate': price,
               'hourly_allowance': billed_rate, 'key_path': str(key), 'provider': safe_pod(pod),
               'storage_note': 'Stopping ends GPU rental; the retained volume continues storage billing.'}
    write(session_file, session)
    try:
        with session_file.with_suffix('.watch.log').open('x') as log:
            watcher = subprocess.Popen([sys.executable, '-m', 'label_pilot.deploy', 'watch',
                                        '--session', str(session_file.resolve())],
                                       cwd=ROOT.parent, stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=log, start_new_session=True)
        session['local_watch_pid'] = watcher.pid
        write(session_file, session)
    except Exception:
        stop(session)
        raise
    return session


def ssh_args(session, pod, command):
    port = (pod.get('portMappings') or {}).get('22')
    host = pod.get('publicIp')
    if not host or not port:
        raise RuntimeError('Pod direct SSH endpoint is not ready; rerun launch after provisioning')
    return ['ssh', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=15',
            '-o', 'StrictHostKeyChecking=accept-new', '-i', session['key_path'],
            '-p', str(port), 'root@'+host, command]


def source_archive(plan_path, calibration=None, lock=None):
    plan_path = Path(plan_path)
    load_plan(plan_path)
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:gz') as archive:
        for pattern in ('*.py', '*.sh', '*.txt', 'tests/*.py', 'config/*.json'):
            for file in sorted(ROOT.glob(pattern)):
                archive.add(file, arcname='label_pilot/'+str(file.relative_to(ROOT)))
        for file in sorted(plan_path.glob('*.json')):
            archive.add(file, arcname='plan/'+file.name)
        for file, name in ((calibration, 'calibration.json'), (lock, 'selection_lock.json')):
            if file:
                archive.add(file, arcname='inputs/'+name)
    return stream.getvalue()


def arm_guard(session, pod):
    """Install a standalone guard before uploading the experiment or credentials."""
    subprocess.run(ssh_args(session, pod, f'mkdir -p {REMOTE} && cat > {REMOTE}/stop_guard.py'),
                   input=(ROOT/'stop_guard.py').read_bytes(), check=True)
    remote = '''import json,pathlib,subprocess,sys
p=json.load(sys.stdin); root=pathlib.Path('/workspace/sae-label-pilot')
guard=[sys.executable,'-u',str(root/'stop_guard.py'),'--pod-id',p['pod_id']]
subprocess.run(guard+['--check'],check=True)
with (root/'guard.log').open('a') as log:
    proc=subprocess.Popen(guard+['--deadline',p['stop_deadline_utc']],stdin=subprocess.DEVNULL,
                          stdout=log,stderr=log,start_new_session=True)
print(json.dumps({'guard_pid':proc.pid}))
'''
    result = subprocess.run(ssh_args(session, pod, 'python3 -c '+shlex.quote(remote)),
                            input=json.dumps({k: session[k] for k in ('pod_id','stop_deadline_utc')}).encode(),
                            capture_output=True)
    if result.returncode:
        stop(session)
        raise RuntimeError('Remote shutdown guard failed verification; requested pod stop')
    return json.loads(result.stdout.decode().splitlines()[-1])


def launch(args):
    session = read(args.session)
    if remaining(session) < 120 or remaining(session) > 7200:
        raise ValueError('Need between two minutes and two hours remaining in the session')
    if session.get('launched'):
        raise ValueError('This session already launched; collect its results')
    run_id = args.run_id or args.stage
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,80}', run_id):
        raise ValueError('Run ID must contain only letters, numbers, underscore or hyphen')
    pod = (runpod_request('GET', f"pods/{session['pod_id']}") if uses_account_api(session)
           else session['provider'])
    if args.stage in ('screen','selection','confirm') and not args.calibration:
        raise ValueError('This stage requires --calibration')
    if args.stage == 'confirm' and not args.lock:
        raise ValueError('Confirmation requires --lock')
    if not session.get('guard_pid'):
        session.update(arm_guard(session, pod))
        write(args.session, session)
    package = source_archive(args.plan, args.calibration, args.lock)
    package_hash = __import__('hashlib').sha256(package).hexdigest()
    archive_path = ROOT/'outputs/uploads'/f'{package_hash}.tar.gz'
    archive_path.parent.mkdir(parents=True, exist_ok=True)
    archive_path.write_bytes(package)
    upload = ssh_args(session, pod, f'mkdir -p {REMOTE} && cd {REMOTE} && tar --no-same-owner -xzf -')
    subprocess.run(upload, input=package, check=True)
    credentials = load_credentials()
    from huggingface_hub import get_token
    token = credentials.get('HF_TOKEN') or get_token()
    remote = r'''
import json,os,pathlib,subprocess,sys,time
p=json.load(sys.stdin); root=pathlib.Path('/workspace/sae-label-pilot'); os.chdir(root)
out=root/'results'/p['run_id'];out.mkdir(parents=True,exist_ok=True)
if (out/'run').exists() and not p['resume']: raise RuntimeError('Existing run requires explicit resume')
(out/'exit.json').unlink(missing_ok=True)
env=dict(os.environ,HF_HOME='/workspace/hf',PYTHONUNBUFFERED='1')
if p['hf_token']: env['HF_TOKEN']=p['hf_token']
worker="""import pathlib,subprocess,sys
path=pathlib.Path(sys.argv[1])
rc=subprocess.call(sys.argv[2:])
path.write_text(__import__('json').dumps({'exit_code':rc}))
"""
command=['timeout','--signal=TERM','--kill-after=30s',str(p['seconds'])+'s','bash','label_pilot/bootstrap.sh',
         '--plan','plan','--stage',p['stage'],'--output',str(out/'run'),'--max-seconds',str(max(30,p['seconds']-90))]
if p['resume']: command += ['--resume']
if p['calibration']: command += ['--calibration','inputs/calibration.json']
if p['lock']: command += ['--lock','inputs/selection_lock.json']
with (out/'job.log').open('a') as log:
    job=subprocess.Popen([sys.executable,'-u','-c',worker,str(out/'exit.json'),*command],stdin=subprocess.DEVNULL,
                         stdout=log,stderr=log,env=env,start_new_session=True)
print(json.dumps({'job_pid':job.pid,'stage':p['stage'],'run_id':p['run_id']}))
'''
    payload = {'pod_id': session['pod_id'], 'deadline': session['stop_deadline_utc'],
               'hf_token': token, 'seconds': int(remaining(session))-60,
               'stage': args.stage, 'run_id': run_id, 'resume': args.resume,
               'calibration': bool(args.calibration), 'lock': bool(args.lock)}
    result = subprocess.run(ssh_args(session, pod, 'python3 -c '+shlex.quote(remote)),
                            input=json.dumps(payload).encode(), capture_output=True)
    if result.returncode:
        # Do not print raw provider/container output that could include env data.
        stop(session)
        raise RuntimeError('Remote guard or bootstrap failed; requested stop for this pod')
    launched = json.loads(result.stdout.decode().splitlines()[-1])
    session.update(launched=launched, archive_sha256=package_hash, source_archive=str(archive_path))
    write(args.session, session)
    return {'pod_id': session['pod_id'], 'deadline': session['stop_deadline_utc'], **launched}


def collect(args):
    session = read(args.session)
    pod = (runpod_request('GET', f"pods/{session['pod_id']}") if uses_account_api(session)
           else session['provider'])
    destination = Path(args.output)
    destination.mkdir(parents=True, exist_ok=False)
    command = f'cd {REMOTE} && tar -czf - results'
    archive_path = destination/'results.tar.gz'
    with archive_path.open('wb') as handle:
        subprocess.run(ssh_args(session, pod, command), stdout=handle, check=True)
    with tarfile.open(archive_path) as archive:
        archive.extractall(destination, filter='data')
    hashes = {str(p.relative_to(destination)): file_hash(p) for p in destination.rglob('*') if p.is_file()}
    write(destination/'sha256.json', hashes)
    result = {'files_saved': len(hashes), 'destination': str(destination)}
    if args.stop_after:
        result['shutdown'] = stop(session)
    return result


def attach(args):
    """Register a pod deployed in the browser; no account API key is needed."""
    if not all((args.host, args.port, args.pod_id, args.deadline, args.rate)):
        raise ValueError('Attach requires --host, --port, --pod-id, --deadline, --rate')
    if not 0 < args.budget <= 25:
        raise ValueError('Initial session budget must be between zero and $25')
    if not Path(args.key).expanduser().is_file():
        raise FileNotFoundError('Existing private SSH key required')
    session = {'pod_id': args.pod_id, 'key_path': str(Path(args.key).expanduser()),
               'stop_deadline_utc': dt.datetime.fromisoformat(args.deadline.replace('Z','+00:00')).isoformat(),
               'provider_hourly_rate': args.rate, 'budget_usd': args.budget,
               'provider': {'id': args.pod_id, 'publicIp': args.host, 'portMappings': {'22': args.port}},
               'created_utc': now().isoformat(), 'origin': 'console_deployment'}
    seconds = remaining(session)
    if not 0 < seconds <= 7200 or args.rate <= 0 or args.rate > args.max_hourly or (args.rate+.25)*seconds/3600 > args.budget:
        raise ValueError('Attached session exceeds the two-hour, price or budget bound')
    if Path(args.session).exists():
        raise FileExistsError('Choose a new session file')
    # Check exact pod identity without returning its environment or secrets.
    # Non-login SSH shells do not necessarily inherit the container environment.
    verify = ('from pathlib import Path; '
              'print(next((v.split(b"=",1)[1].decode() for v in '
              'Path("/proc/1/environ").read_bytes().split(b"\\0") '
              'if v.startswith(b"RUNPOD_POD_ID=")), ""))')
    result = subprocess.run(ssh_args(session, session['provider'], 'python3 -c '+shlex.quote(verify)),
                            capture_output=True, check=True)
    if result.stdout.decode().strip() != args.pod_id:
        raise RuntimeError('SSH destination pod identity mismatch')
    write(args.session, session)
    session.update(arm_guard(session, session['provider']))
    write(args.session, session)
    return session


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['create', 'attach', 'launch', 'collect', 'stop', 'status', 'watch'])
    p.add_argument('--session', required=True)
    p.add_argument('--key', default='~/.ssh/runpod_ssp')
    p.add_argument('--hours', type=float, default=2); p.add_argument('--budget', type=float, default=25)
    p.add_argument('--max-hourly', type=float, default=9.5)
    p.add_argument('--plan'); p.add_argument('--output'); p.add_argument('--stop-after', action='store_true')
    p.add_argument('--host'); p.add_argument('--port', type=int); p.add_argument('--pod-id')
    p.add_argument('--deadline'); p.add_argument('--rate', type=float)
    p.add_argument('--stage', choices=['smoke','harvest','screen','selection','confirm'], default='smoke')
    p.add_argument('--calibration'); p.add_argument('--lock')
    p.add_argument('--run-id'); p.add_argument('--resume', action='store_true')
    args = p.parse_args()
    if args.action == 'create': result = create(args)
    elif args.action == 'attach': result = attach(args)
    elif args.action == 'launch':
        if not args.plan: p.error('--plan is required')
        result = launch(args)
    elif args.action == 'collect':
        if not args.output: p.error('--output is required')
        result = collect(args)
    elif args.action == 'stop': result = stop(read(args.session))
    elif args.action == 'watch': result = watch(args.session)
    else:
        session = read(args.session)
        if uses_account_api(session):
            result = safe_pod(runpod_request('GET', f"pods/{session['pod_id']}"))
        else:
            result = dict(session['provider'], note='Saved endpoint only; inspect live status in the Runpod console')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
