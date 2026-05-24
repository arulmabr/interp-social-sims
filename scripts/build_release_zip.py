#!/usr/bin/env python3
"""Build a clean release zip from the current working tree.

The release zip intentionally includes generated data artifacts that may be
untracked during local preparation, while excluding source-control metadata,
Python caches, local environments, model caches, logs, and prior archives.
"""

from __future__ import annotations

import argparse
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT.parent / "social-sim-open-sae_release.zip"
SKIP_DIRS = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".venv",
    "venv",
    "hf_cache",
    "transformers_cache",
    "wandb",
}
SKIP_SUFFIXES = {".zip", ".tgz", ".tar.gz", ".pyc", ".log"}
RELEASE_RUN_DIRS = {
    "creativity_open_sae_steering_smoke",
    "creativity_open_sae_steering_40agent",
    "safe_risky_five_condition_open_sae_smoke",
}


def should_skip(path: Path, output: Path) -> bool:
    """Return true for local state that should not enter the release zip."""

    if path == output:
        return True
    rel = path.relative_to(ROOT)
    if rel.parts and rel.parts[0] == "runs":
        return len(rel.parts) < 2 or rel.parts[1] not in RELEASE_RUN_DIRS
    if any(part in SKIP_DIRS for part in rel.parts):
        return True
    return any(path.name.endswith(suffix) for suffix in SKIP_SUFFIXES)


def release_files(output: Path) -> list[Path]:
    """Return release file paths in deterministic order."""

    return [
        path
        for path in sorted(ROOT.rglob("*"))
        if path.is_file() and not should_skip(path, output)
    ]


def sha256_file(path: Path) -> str:
    """Compute a SHA-256 hash for a file."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_zip(output: Path) -> tuple[int, str]:
    """Write the release zip and return file count plus archive hash."""

    output.parent.mkdir(parents=True, exist_ok=True)
    files = release_files(output)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            archive.write(path, Path("social-sim-open-sae") / path.relative_to(ROOT))
    return len(files), sha256_file(output)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> None:
    """Build the release archive."""

    args = parse_args()
    output = args.output.resolve()
    count, digest = build_zip(output)
    print(f"wrote {output}")
    print(f"files: {count}")
    print(f"sha256: {digest}")


if __name__ == "__main__":
    main()
