"""Build collaborator release assets from local research backups, never provider state."""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import re
import tarfile

BASE = Path(__file__).resolve().parent
REPO = BASE.parent
RELEASE = BASE / 'backup_release'
TAG = 'sae-anchor-backups-2026-09-22'
URL = f'https://github.com/arulmabr/interp-social-sims/releases/download/{TAG}'
GROUPS = {
    'repair-backup-20260917': 'repair',
    'full-pilot-final-backup-20260917': 'pilot',
    'decision-backup-20260918': 'decision',
    'replay-backup-20260918': 'replay',
}
SUFFIXES = {'.pt', '.json', '.py', '.csv', '.md', '.png', '.pdf', '.sh', '.txt'}
ROOT_FILES = {'fidelity_plan.json', 'decision-refinement-plan-v1.json',
              'repair-tokenization-all-rows.json', 'repair-tokenization.json',
              'repair_diagnosis.json', 'refinement_source_hashes.json',
              'verified_artifact_hashes.json'}
SECRETS = {
    'huggingface_token': rb'\bhf_[A-Za-z0-9]{20,}\b',
    'github_token': rb'\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,})\b',
    'api_secret': rb'\b(?:sk-|rpa_)[A-Za-z0-9_-]{20,}\b',
    'private_key': rb'-----BEGIN (?:OPENSSH |RSA |EC |DSA )?PRIVATE KEY-----',
}
PRIVATE_KEYS = {'pod_id', 'podId', 'ssh_host', 'sshHost', 'publicIp', 'public_ip',
                'api_key', 'apiKey', 'hf_token', 'access_token', 'runpod_api_key'}


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def private_keys(value):
    if isinstance(value, dict):
        return [k for k, v in value.items() if k in PRIVATE_KEYS and v] + [
            k for v in value.values() for k in private_keys(v)]
    if isinstance(value, list):
        return [k for v in value for k in private_keys(v)]
    return []


def classify(relative):
    parts = relative.parts
    if '__pycache__' in parts or relative.suffix == '.pyc':
        return None, 'interpreter cache'
    if relative.suffix == '.log':
        return None, 'operational log'
    if relative.suffix not in SUFFIXES:
        return None, 'unsupported or temporary file'
    if len(parts) == 1:
        if relative.name in ROOT_FILES or relative.name.startswith('decision-analysis-lock'):
            return 'plans', None
        return None, 'account, deployment, transfer, or delivery record'
    if '-backup-' in parts[0]:
        if len(parts) < 3 or parts[1] != 'outputs':
            return None, 'provider session or transfer record'
        return GROUPS.get(parts[0], 'history'), None
    if 'fixture' in parts[0] or parts[0].startswith(('gpu-', 'cpu-')):
        return 'history', None
    if parts[0] in {'design-v1', 'refinement-plan'} or '-plan-v' in parts[0]:
        return 'plans', None
    return None, 'outside declared research backup scope'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=BASE / 'outputs/collaborator-release-v1')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    files = {}; omitted = {}; group_files = {}
    for path in sorted((BASE / 'outputs').rglob('*')):
        if not path.is_file() or args.output.resolve() in path.resolve().parents:
            continue
        relative = path.relative_to(BASE / 'outputs')
        group, reason = classify(relative)
        if reason:
            omitted[str(relative)] = reason
            continue
        if path.suffix == '.json':
            keys = private_keys(json.loads(path.read_text()))
            if keys:
                omitted[str(relative)] = 'provider/account fields: ' + ', '.join(sorted(set(keys)))
                continue
        data = path.read_bytes()
        hits = [name for name, pattern in SECRETS.items() if re.search(pattern, data)]
        if hits:
            raise RuntimeError(f'Credential-pattern review required: {relative}: {hits}')
        name = str(path.relative_to(REPO))
        files[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data), 'group': group}
        group_files.setdefault(group, []).append(path)
    common = sorted((RELEASE / 'licenses').glob('*'))
    assert len(common) == 2, 'License and NOTICE must accompany each asset'
    assets = {}
    for group, paths in sorted(group_files.items()):
        name = f'Llama-SAE-pilot-backups-{group}.tar.gz'
        output = args.output / name
        members = {}
        with output.open('wb') as raw, gzip.GzipFile(filename='', mode='wb', fileobj=raw, mtime=0, compresslevel=1) as gz:
            with tarfile.open(fileobj=gz, mode='w', format=tarfile.PAX_FORMAT) as tar:
                for path in sorted(paths + common):
                    member_name = str(path.relative_to(REPO))
                    data = path.read_bytes()
                    info = tarfile.TarInfo(member_name)
                    info.size = len(data); info.mode = 0o644; info.mtime = 0
                    tar.addfile(info, io.BytesIO(data))
                    members[member_name] = {'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}
        assets[group] = {'name': name, 'url': f'{URL}/{name}', 'sha256': sha256(output),
                         'bytes': output.stat().st_size, 'files': members}
        print(json.dumps({'group': group, 'files': len(paths), 'MiB': round(output.stat().st_size / 1024**2, 2)}), flush=True)
    manifest = {'schema_version': 1, 'release_tag': TAG, 'repository': 'arulmabr/interp-social-sims',
                'description': 'Byte-preserved research backups; excludes operational account state and logs.',
                'assets': assets,
                'coverage': {'research_files': len(files), 'tensor_files': sum(n.endswith('.pt') for n in files),
                             'original_bytes': sum(r['bytes'] for r in files.values()),
                             'omitted_files': len(omitted), 'omitted_by_reason': dict(Counter(omitted.values()))}}
    (RELEASE / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    (RELEASE / 'excluded_files.json').write_text(json.dumps(omitted, indent=2) + '\n')
    (args.output / 'SHA256SUMS').write_text(''.join(f"{a['sha256']}  {a['name']}\n" for a in assets.values()))
    print(json.dumps(manifest['coverage'], indent=2))


if __name__ == '__main__':
    main()
