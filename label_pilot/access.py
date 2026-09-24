"""Local credentials and read-only service checks. Never prints token values."""
import argparse
import getpass
import json
import os
import stat
import urllib.error
import urllib.request
from pathlib import Path

from .common import MODEL, MODEL_REVISION, SAE, SAE_REVISION, SAE_FILENAME, hf_token

DEFAULT_CREDENTIALS = Path(__file__).parent / '.credentials.json'


def load_credentials(path=None):
    path = Path(path or DEFAULT_CREDENTIALS)
    values = {}
    if path.exists():
        if stat.S_IMODE(path.stat().st_mode) & 0o077:
            raise PermissionError('Credential file must be private: chmod 600 on the file')
        values = json.loads(path.read_text())
    return {key: os.environ.get(key) or values.get(key) for key in ('RUNPOD_API_KEY', 'HF_TOKEN')}


def configure(path):
    values = load_credentials(path)
    for key in ('RUNPOD_API_KEY', 'HF_TOKEN'):
        value = getpass.getpass(f'{key} (hidden input; Enter preserves existing value): ').strip()
        if value:
            values[key] = value
    path = Path(path)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w') as handle:
        json.dump(values, handle)
    os.chmod(path, 0o600)
    print(json.dumps({'saved': str(path), 'permissions': '0600',
                      'configured': {k: bool(v) for k, v in values.items()}}))


def runpod_request(method, endpoint, payload=None, credentials=None):
    key = (credentials or load_credentials()).get('RUNPOD_API_KEY')
    if not key:
        raise RuntimeError('Runpod API credential is not configured')
    request = urllib.request.Request('https://rest.runpod.io/v1/' + endpoint.lstrip('/'),
                                     method=method, headers={'Authorization': 'Bearer '+key,
                                                             'Content-Type': 'application/json'},
                                     data=json.dumps(payload).encode() if payload is not None else None)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            data = response.read()
            return json.loads(data) if data else {}
    except urllib.error.HTTPError as error:
        # Avoid propagating a response that might echo credentials/env values.
        raise RuntimeError(f'Runpod API returned HTTP {error.code}') from None


def check(credentials=None, check_runpod=True):
    credentials = credentials or load_credentials()
    result = {'credential_presence': {k: bool(v) for k, v in credentials.items()}}
    if check_runpod and credentials.get('RUNPOD_API_KEY'):
        pods = runpod_request('GET', 'pods', credentials=credentials)
        if not isinstance(pods, list):
            raise ValueError('Unexpected Runpod pod-list response')
        result['pods'] = [{k: pod.get(k) for k in ('id', 'name', 'desiredStatus', 'gpuCount', 'costPerHr',
                                                  'adjustedCostPerHr', 'publicIp', 'portMappings')}
                          for pod in pods]
    from huggingface_hub import hf_hub_download, hf_hub_url, get_hf_file_metadata
    token = credentials.get('HF_TOKEN') or hf_token()
    try:
        filename = hf_hub_download(MODEL, 'model.safetensors.index.json', revision=MODEL_REVISION, token=token)
        shard = next(iter(json.loads(Path(filename).read_text())['weight_map'].values()))
        get_hf_file_metadata(hf_hub_url(MODEL, shard, revision=MODEL_REVISION), token=token)
        get_hf_file_metadata(hf_hub_url(SAE, SAE_FILENAME, revision=SAE_REVISION), token=token)
        result['model_download_access'] = True
    except Exception as error:
        result['model_download_access'] = False
        result['model_access_error'] = {'type': type(error).__name__,
                                        'http_status': getattr(getattr(error, 'response', None), 'status_code', None)}
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['configure', 'check'])
    p.add_argument('--credentials', type=Path, default=DEFAULT_CREDENTIALS)
    p.add_argument('--model-only', action='store_true')
    args = p.parse_args()
    if args.action == 'configure':
        configure(args.credentials)
    else:
        result = check(load_credentials(args.credentials), not args.model_only)
        print(json.dumps(result, indent=2))
        if not result['model_download_access']:
            raise SystemExit(2)


if __name__ == '__main__':
    main()
