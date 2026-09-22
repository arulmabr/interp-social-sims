"""X1 -- build the supplement from an allow-list, and fail on a deny-list match.

The supplement is built by listing what goes in, never by excluding what should
stay out, because an exclusion list silently ships whatever it forgot. After the
allow-list selects the files, every one of them is scanned and the build
**fails** on any deny-list match.

The deny-list has two kinds of entry. Identifiers and paths that would
de-anonymise the submission, and credential shapes. A credential match is never
printed: the report names the file, the line number and the rule, and stops.
That is deliberate -- a scanner that echoes the secret it found writes it into
the build log.

    python -m cv_bench.x1_supplement --scan .          # check, build nothing
    python -m cv_bench.x1_supplement --build out.zip   # allow-list then check
"""
from __future__ import annotations

import argparse
import re
import sys
import zipfile
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

# --- what may go in -------------------------------------------------------
ALLOW = [
    "cv_bench/**/*.py", "figures/make_*.py", "figures/*.pdf",
    "paper_patches/*.md", "paper_patches/*.csv", "env/requirements-lock.txt",
    "MANIFEST.csv", "results/S/s1/*.csv",
]
# reports/, logs/ and anything with a .git path are excluded by not being here.

# --- what must not appear -------------------------------------------------
# (name, compiled pattern, whether a match may be quoted in the report)
DENY: List[Tuple[str, re.Pattern, bool]] = [
    ("username-guna23",   re.compile(r"guna23"), True),
    ("username-gunahn",   re.compile(r"gunahn"), True),
    ("username-sk1609",   re.compile(r"sk1609"), True),
    ("name-shrey",        re.compile(r"\bshrey\b", re.I), True),
    ("name-arulmabr",     re.compile(r"arulmabr"), True),
    ("pi-gabrieli",       re.compile(r"gabrieli", re.I), True),
    ("filesystem-orcd",   re.compile(r"\borcd\b", re.I), True),
    ("filesystem-hstor",  re.compile(r"hstor"), True),
    ("partition-ou_bcs",  re.compile(r"ou_bcs"), True),
    ("dataset-camcan",    re.compile(r"Cam-?CAN", re.I), True),
    ("abs-home-path",     re.compile(r"/home/"), True),
    ("email",             re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), False),
    # credential shapes -- never quoted
    ("hf-token",          re.compile(r"hf_[A-Za-z0-9]{20,}"), False),
    ("openai-key",        re.compile(r"sk-[A-Za-z0-9_-]{20,}"), False),
    ("google-key",        re.compile(r"AIza[0-9A-Za-z_-]{35}"), False),
    ("aws-key",           re.compile(r"AKIA[0-9A-Z]{16}"), False),
    ("private-key-block", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), False),
]

# Filenames that must never be inside the supplement at all, whatever they hold.
DENY_NAMES = {"working_apis", "hf_token", "hf_token.txt", ".hf_token",
              ".env", "credentials", "id_rsa"}

SKIP_SUFFIX = {".pdf", ".png", ".zip", ".pt", ".pth", ".safetensors", ".npy"}


def deny_hits(path: Path) -> List[dict]:
    """Deny-list matches in one file. A credential match is reported, not shown."""
    out: List[dict] = []
    if path.name in DENY_NAMES or any(p in DENY_NAMES for p in path.parts):
        out.append(dict(file=str(path), line=0, rule="denied-filename", quote=""))
        return out
    if path.suffix.lower() in SKIP_SUFFIX:
        return out
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return out
    for n, line in enumerate(text.splitlines(), 1):
        for name, pat, quotable in DENY:
            if pat.search(line):
                out.append(dict(file=str(path), line=n, rule=name,
                                quote=(line.strip()[:80] if quotable else
                                       "<withheld: credential shape>")))
    return out


def allow_listed(root: Path) -> List[Path]:
    seen: List[Path] = []
    for pat in ALLOW:
        for p in sorted(root.glob(pat)):
            if p.is_file() and ".git" not in p.parts:
                seen.append(p)
    return seen


def scan(paths: Iterable[Path]) -> List[dict]:
    hits: List[dict] = []
    for p in paths:
        hits.extend(deny_hits(p))
    return hits


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", default="")
    ap.add_argument("--build", default="")
    ap.add_argument("--limit", type=int, default=25)
    a = ap.parse_args()

    if a.scan:
        root = Path(a.scan).resolve()
        files = [p for p in root.rglob("*")
                 if p.is_file() and ".git" not in p.parts]
    else:
        root = ROOT
        files = allow_listed(root)
    hits = scan(files)

    by_rule: Dict[str, int] = {}
    for h in hits:
        by_rule[h["rule"]] = by_rule.get(h["rule"], 0) + 1
    print(f"x1: scanned {len(files)} files, {len(hits)} deny-list matches")
    for rule, n in sorted(by_rule.items(), key=lambda kv: -kv[1]):
        print(f"  {rule:20s} {n}")
    for h in hits[:a.limit]:
        print(f"  {h['file']}:{h['line']}  [{h['rule']}]  {h['quote']}")
    if len(hits) > a.limit:
        print(f"  ... {len(hits) - a.limit} more")

    cred = [h for h in hits if h["quote"].startswith("<withheld")
            or h["rule"] == "denied-filename"]
    if cred:
        print(f"x1: {len(cred)} CREDENTIAL-SHAPED or denied-filename matches; "
              f"the build fails on these regardless of the anonymity items")

    if a.build:
        if hits:
            print("x1: refusing to build -- fix the matches above")
            return 1
        with zipfile.ZipFile(a.build, "w", zipfile.ZIP_DEFLATED) as z:
            for p in files:
                z.write(p, p.relative_to(root))
        print(f"x1: wrote {a.build} with {len(files)} files")
    return 1 if hits else 0


if __name__ == "__main__":
    raise SystemExit(main())
