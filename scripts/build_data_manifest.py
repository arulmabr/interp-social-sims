#!/usr/bin/env python3
"""Build a SHA-256 manifest for release files."""

from __future__ import annotations

import argparse
import csv
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "DATA_MANIFEST.tsv"
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


def file_sha256(path: Path) -> str:
    """Hash a file without loading it all into memory."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def should_skip(path: Path, output: Path) -> bool:
    """Return true when a path is local state rather than release content."""

    if path == output:
        return True
    rel = path.relative_to(ROOT)
    if rel.parts and rel.parts[0] == "runs":
        return len(rel.parts) < 2 or rel.parts[1] not in RELEASE_RUN_DIRS
    if any(part in SKIP_DIRS for part in rel.parts):
        return True
    name = path.name
    return any(name.endswith(suffix) for suffix in SKIP_SUFFIXES)


def build_rows(output: Path) -> list[dict[str, str | int]]:
    """Collect manifest rows."""

    rows: list[dict[str, str | int]] = []
    for path in sorted(ROOT.rglob("*")):
        if not path.is_file() or should_skip(path, output):
            continue
        rel = path.relative_to(ROOT).as_posix()
        rows.append(
            {
                "path": rel,
                "bytes": path.stat().st_size,
                "sha256": file_sha256(path),
            }
        )
    return rows


def write_manifest(output: Path, rows: list[dict[str, str | int]]) -> None:
    """Write rows as a tab-separated manifest."""

    with output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "bytes", "sha256"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify the existing manifest is current without rewriting it.",
    )
    return parser.parse_args()


def main() -> None:
    """Build or check the manifest."""

    args = parse_args()
    output = args.output.resolve()
    rows = build_rows(output)
    if args.check:
        import io

        buffer = io.StringIO()
        writer = csv.DictWriter(
            buffer,
            fieldnames=["path", "bytes", "sha256"],
            delimiter="\t",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)
        expected = buffer.getvalue()
        actual = output.read_text(encoding="utf-8") if output.exists() else ""
        if actual != expected:
            raise AssertionError(f"{output} is not current; run scripts/build_data_manifest.py")
        print(f"data manifest check passed ({len(rows)} files)")
        return
    write_manifest(output, rows)
    print(f"wrote {output} with {len(rows)} files")


if __name__ == "__main__":
    main()
