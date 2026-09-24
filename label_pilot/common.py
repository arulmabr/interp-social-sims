"""Pinned configuration and small, credential-free artifact helpers."""
import hashlib
import json
import os
from pathlib import Path

MODEL = 'meta-llama/Llama-3.3-70B-Instruct'
MODEL_REVISION = '6f6073b423013f6a7d4d9f39144961bfbfbc386b'
SAE = 'Goodfire/Llama-3.3-70B-Instruct-SAE-l50'
SAE_REVISION = '128ee921ecd1b8b3a87d776cbcc357c0855da134'
SAE_FILENAME = 'Llama-3.3-70B-Instruct-SAE-l50.pt'
LAYER = 50


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                     allow_nan=False).encode()).hexdigest()


def file_hash(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temp.replace(path)


def append(path, value):
    with Path(path).open('a') as handle:
        handle.write(json.dumps(value, ensure_ascii=False, allow_nan=False) + '\n')
        handle.flush()
        os.fsync(handle.fileno())


def source_hashes():
    return {p.name: file_hash(p) for p in sorted(Path(__file__).parent.glob('*.py'))}


def hf_token():
    # Standard HF login is also supported by huggingface_hub when this is None.
    return os.environ.get('HF_TOKEN') or os.environ.get('HUGGING_FACE_HUB_TOKEN')
