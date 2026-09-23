"""Download, verify, and restore released research backups without starting a GPU."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile
from urllib.request import urlopen

BASE = Path(__file__).resolve().parent


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def restore(archive, specification, destination, verify_only=False):
    if archive.stat().st_size != specification['bytes'] or digest(archive) != specification['sha256']:
        raise ValueError('Archive checksum/size mismatch: ' + archive.name)
    destination = destination.resolve()
    expected = specification['files']; seen = set(); restored = skipped = 0
    # Never use extractall: only regular, explicitly manifested files may be written.
    with tarfile.open(archive, mode='r:gz') as tar:
        for member in tar:
            name = member.name; relative = PurePosixPath(name)
            if (name not in expected or name in seen or not member.isfile() or
                    relative.is_absolute() or '..' in relative.parts or '\\' in name):
                raise ValueError('Unexpected or unsafe archive member: ' + name)
            target = destination.joinpath(*relative.parts)
            if target.resolve() != target.absolute():
                raise ValueError('Refusing a path containing a symbolic link: ' + name)
            if not target.resolve().is_relative_to(destination):
                raise ValueError('Path escapes destination: ' + name)
            metadata = expected[name]
            if member.size != metadata['bytes']:
                raise ValueError('Member size mismatch: ' + name)
            seen.add(name)
            source = tar.extractfile(member)
            # Spool before replacing anything, so incomplete or corrupt files never land.
            with tempfile.SpooledTemporaryFile(max_size=8 * 1024 * 1024) as tmp:
                h = hashlib.sha256()
                with source:
                    for chunk in iter(lambda: source.read(1024 * 1024), b''):
                        h.update(chunk); tmp.write(chunk)
                if h.hexdigest() != metadata['sha256']:
                    raise ValueError('Member checksum mismatch: ' + name)
                if verify_only:
                    continue
                if target.exists():
                    if not target.is_file() or digest(target) != metadata['sha256']:
                        raise FileExistsError('Refusing to overwrite a different local file: ' + name)
                    skipped += 1
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                tmp.seek(0)
                with target.open('xb') as output:
                    shutil.copyfileobj(tmp, output)
                restored += 1
    if seen != set(expected):
        raise ValueError('Missing archive members')
    return {'verified': len(seen), 'restored': restored, 'already_present': skipped}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--groups', nargs='+', help='Default: every group; use repair replay decision plans for the latest work')
    parser.add_argument('--destination', type=Path, default=BASE.parent, help='Repository root or an empty restore directory')
    parser.add_argument('--archive-dir', type=Path, help='Use already downloaded assets instead of the network')
    parser.add_argument('--verify-only', action='store_true', help='Check all archive members without restoring')
    args = parser.parse_args()
    manifest = json.loads((BASE / 'backup_release/manifest.json').read_text())
    groups = args.groups or list(manifest['assets'])
    unknown = set(groups) - set(manifest['assets'])
    if unknown:
        parser.error('Unknown groups: ' + ', '.join(sorted(unknown)))
    args.destination.mkdir(parents=True, exist_ok=True)
    for group in dict.fromkeys(groups):
        asset = manifest['assets'][group]
        with tempfile.TemporaryDirectory(prefix='sae-backup-download-') as temporary:
            archive = (args.archive_dir or Path(temporary)) / asset['name']
            if not args.archive_dir:
                print(f"Downloading {group}: {asset['bytes'] / 1024**2:.1f} MiB", flush=True)
                with urlopen(asset['url'], timeout=60) as response, archive.open('wb') as output:
                    shutil.copyfileobj(response, output)
            result = restore(archive, asset, args.destination, args.verify_only)
            print(json.dumps({'group': group, **result}), flush=True)


if __name__ == '__main__':
    main()
