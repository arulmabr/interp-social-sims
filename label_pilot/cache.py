"""Download pinned checkpoints durably, then stage their files for fast mmap.

Runpod FUSE-backed volumes can stall safetensors mmap loading despite fast
sequential reads. A RAM cache is temporary; /workspace remains authoritative.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import shutil
import time

from .common import MODEL, MODEL_REVISION, SAE, SAE_REVISION, SAE_FILENAME, hf_token, write


def stage(durable, snapshots, ram, reserve_bytes=8_000_000_000):
    durable, ram = Path(durable).resolve(), Path(ram)
    target = ram/'hub'
    files, links = {}, {}
    for snapshot in snapshots:
        for item in Path(snapshot).rglob('*'):
            if item.is_symlink():
                resolved = item.resolve(strict=True)
                relative = resolved.relative_to(durable)
                files[relative] = resolved
                links[item.relative_to(durable)] = os.readlink(item)
            elif item.is_file():
                files[item.relative_to(durable)] = item
    if not files:
        raise ValueError('No checkpoint files to stage')
    missing = {rel: src for rel, src in files.items()
               if not (target/rel).is_file() or (target/rel).stat().st_size != src.stat().st_size}
    required = sum(src.stat().st_size for src in missing.values())
    ram.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(ram).free < required + reserve_bytes:
        raise RuntimeError(f'RAM cache needs {required+reserve_bytes:,} free bytes; choose a pod with sufficient shared memory')
    started = time.monotonic()
    def copy(pair):
        relative, source = pair
        destination = target/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name+'.partial')
        with source.open('rb') as src, temporary.open('wb') as dst:
            shutil.copyfileobj(src, dst, 16*1024*1024)
        if temporary.stat().st_size != source.stat().st_size:
            raise RuntimeError('Incomplete cache copy')
        temporary.replace(destination)
        return source.stat().st_size
    copied = 0
    with ThreadPoolExecutor(max_workers=2) as pool:
        for future in as_completed([pool.submit(copy, item) for item in missing.items()]):
            copied += future.result()
            print(json.dumps({'cache_copied_gb': round(copied/1e9, 2),
                              'cache_required_gb': round(required/1e9, 2)}), flush=True)
    for relative, link in links.items():
        destination = target/relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.is_symlink():
            if os.readlink(destination) != link:
                raise ValueError('Existing cache link differs from pinned snapshot')
        elif destination.exists():
            raise ValueError('Expected a snapshot symlink')
        else:
            destination.symlink_to(link)
        if not destination.is_file():
            raise ValueError('Broken cache link')
    summary = {'model': MODEL, 'model_revision': MODEL_REVISION,
               'sae': SAE, 'sae_revision': SAE_REVISION,
               'files': len(files), 'copied_bytes': copied,
               'total_bytes': sum(p.stat().st_size for p in files.values()),
               'copy_seconds': time.monotonic()-started, 'cache_root': str(target)}
    write(ram/'READY', summary)
    return summary


def prepare(durable, ram):
    from huggingface_hub import snapshot_download, hf_hub_download
    durable = str(Path(durable).resolve())
    token = hf_token()
    # Restrict to configuration/tokenizer files and safetensors; do not also
    # download the repository's alternative original .pth weight distribution.
    model = snapshot_download(MODEL, revision=MODEL_REVISION, cache_dir=durable,
                              token=token, allow_patterns=['*.json', '*.safetensors', '*.model', '*.jinja'],
                              max_workers=8)
    sae = hf_hub_download(SAE, SAE_FILENAME, revision=SAE_REVISION, cache_dir=durable, token=token)
    return stage(durable, [model, Path(sae).parent], ram)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--durable', default='/workspace/hf/hub')
    parser.add_argument('--ram', default='/dev/shm/sae-hf')
    args = parser.parse_args()
    print(json.dumps(prepare(args.durable, args.ram), indent=2))


if __name__ == '__main__':
    main()
