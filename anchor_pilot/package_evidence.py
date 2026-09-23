"""Export saved scientific records for Git without weights or deployment state.

Run from the repository root. Source archives remain untouched. The export is
byte-for-byte, with source-relative paths and SHA-256 hashes in the manifest.
"""
import hashlib
import json
from pathlib import Path
import shutil


BASE = Path(__file__).resolve().parent
SOURCES = {
    'decision': 'outputs/decision-backup-20260918/outputs/decision-refined-20260918T235147Z',
    'replay': 'outputs/replay-backup-20260918/outputs/replay-20260918T052546Z',
    'repair': 'outputs/repair-backup-20260917/outputs/repair-20260917T062148Z',
    'pilot': 'outputs/full-pilot-final-backup-20260917/outputs/pilot-20260917T044718Z',
    'smoke': 'outputs/gpu-gradient-refinement-20260917',
    'smoke_initial': 'outputs/gpu-20260917T034907Z',
}
ALLOWED = {'.json', '.csv', '.md', '.png', '.pdf'}
EXCLUDED = {'environment.json'}


def main():
    destination = BASE / 'evidence'
    destination.mkdir(exist_ok=True)
    entries = {}

    def copy(source, target):
        data = source.read_bytes()
        if target.exists() and target.read_bytes() != data:
            raise RuntimeError(f'Refusing to replace a changed export: {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        entries[str(target.relative_to(destination))] = {
            'source': str(source.relative_to(BASE)),
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest(),
        }

    for phase, relative in SOURCES.items():
        source = BASE / relative
        if not source.is_dir():
            raise FileNotFoundError(source)
        for file in sorted(source.iterdir()):
            if file.is_file() and file.suffix in ALLOWED and file.name not in EXCLUDED:
                copy(file, destination / phase / file.name)
        # Archived executed code preserves the implementation used for each run.
        for subdir in ('execution_source', 'postprocessing_source', 'figures', 'refinement'):
            directory = source / subdir
            if not directory.is_dir():
                continue
            for file in sorted(directory.iterdir()):
                if file.is_file() and file.suffix in ALLOWED | {'.py'} and file.name not in EXCLUDED:
                    copy(file, destination / phase / subdir / file.name)

    for phase in ('decision', 'repair', 'replay'):
        plan = BASE / ('outputs/decision-plan-v2' if phase == 'decision' else f'outputs/{phase}-plan-v1')
        for file in sorted(plan.glob('*.json')):
            copy(file, destination / 'plans' / phase / file.name)
    for file in sorted((BASE / 'outputs').glob('decision-analysis-lock*.json')):
        copy(file, destination / 'plans' / 'decision' / file.name)
    for name in ('decision-refinement-plan-v1.json', 'fidelity_plan.json'):
        copy(BASE / 'outputs' / name, destination / 'plans' / name)
    for phase in ('design-v1', 'refinement-plan'):
        for file in sorted((BASE / 'outputs' / phase).glob('*.json')):
            copy(file, destination / 'plans' / phase / file.name)

    manifest = {
        'description': 'Byte-identical exports of saved scientific records; no new model runs.',
        'omitted': ['Model and adapter weights', 'Activation tensors and vector checkpoints',
                    'Virtual environments and caches', 'Account, billing, SSH and deployment state',
                    'Temporary logs and incomplete-run backups'],
        'files': entries,
    }
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'files': len(entries), 'megabytes': round(sum(x['bytes'] for x in entries.values()) / 1024**2, 2)}))


if __name__ == '__main__':
    main()
