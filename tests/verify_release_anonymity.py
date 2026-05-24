#!/usr/bin/env python3
"""Check that public release files do not include accidental private context."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {".git", "__pycache__", ".pytest_cache"}
SKIP_SUFFIXES = {".png", ".zip", ".pyc", ".log"}
AUTHOR_ALLOWED_FILES = {Path("CITATION.cff"), Path("LICENSE")}

PRIVATE_PATTERNS = {
    "local_users_path": re.compile(re.escape("/" + "Users" + "/"), re.IGNORECASE),
    "local_username": re.compile(r"\bUsers/" + "ar" + "ul" + r"\b", re.IGNORECASE),
    "collaborator_g": re.compile(r"\b" + "gav" + "eal" + r"\b", re.IGNORECASE),
    "collaborator_s": re.compile(r"\b" + "shr" + "eyas" + r"\b", re.IGNORECASE),
    "messaging_app": re.compile("Whats" + "App", re.IGNORECASE),
    "chat_draft_path": re.compile("slack" + "_" + "drafts", re.IGNORECASE),
    "literal_hf_token": re.compile(r"\bhf_[A-Za-z0-9]{20,}\b"),
    "literal_openai_key": re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b"),
}

AUTHOR_PATTERNS = {
    "author_given_name": re.compile(r"\b" + "Ar" + "ul" + r"\b", re.IGNORECASE),
    "author_family_name": re.compile(r"\b" + "Mur" + "ugan" + r"\b", re.IGNORECASE),
}


def iter_text_files() -> list[Path]:
    """Return UTF-8 text files that are relevant to the release."""

    paths: list[Path] = []
    for path in ROOT.rglob("*"):
        rel = path.relative_to(ROOT)
        if not path.is_file() or any(part in SKIP_PARTS for part in rel.parts):
            continue
        if any(path.name.endswith(suffix) for suffix in SKIP_SUFFIXES):
            continue
        try:
            path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        paths.append(path)
    return paths


def main() -> None:
    """Run the anonymity scan."""

    hits: list[str] = []
    for path in iter_text_files():
        rel = path.relative_to(ROOT)
        text = path.read_text(encoding="utf-8")
        for name, pattern in PRIVATE_PATTERNS.items():
            for match in pattern.finditer(text):
                line = text.count("\n", 0, match.start()) + 1
                hits.append(f"{rel}:{line}:{name}")
        if rel not in AUTHOR_ALLOWED_FILES:
            for name, pattern in AUTHOR_PATTERNS.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    hits.append(f"{rel}:{line}:{name}")
    if hits:
        raise AssertionError("Release anonymity scan failed:\n" + "\n".join(hits[:100]))
    print("release anonymity scan passed")


if __name__ == "__main__":
    main()
