"""The five judges of V2: credential wiring and a one-request liveness check.

**No value from a key file is ever printed, logged, or written.** Keys are read
from `~/secrets/working_apis` at the moment they are needed, held in process
memory, and passed to the provider. The verification below reports `ok` or
`fails` and a reason *class* per judge -- never a key, never a response body.

The judge identities are V2's, read off the scoring passes rather than assumed:
claude-sonnet-4-6, deepseek-v4-pro, gemini-2.5-pro, gpt-5, kimi-k2.6.

    python -m cv_bench.judges --verify
"""
from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, Optional, Tuple

SECRETS = Path.home() / "secrets" / "working_apis"

# judge -> (key file, provider). The key file names are structural, not secret.
JUDGES: Dict[str, Tuple[str, str]] = {
    "gpt-5":             ("api_key.txt",               "openai"),
    "claude-sonnet-4-6": ("api_key_anthropic_ucb.txt", "anthropic"),
    "gemini-2.5-pro":    ("api_key_gemini.txt",        "google"),
    "deepseek-v4-pro":   ("api_key_deepseek.txt",      "deepseek"),
    "kimi-k2.6":         ("api_key_moonshot.txt",      "moonshot"),
}

ENDPOINT = {
    "openai":    "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
    "google":    "https://generativelanguage.googleapis.com/v1beta/models",
    "deepseek":  "https://api.deepseek.com/models",
    "moonshot":  "https://api.moonshot.cn/v1/models",
}


def _key(filename: str) -> Optional[str]:
    """Read a key. Returns None if absent. The value is never logged."""
    p = SECRETS / filename
    if not p.exists():
        return None
    v = p.read_text().strip()
    return v or None


def _headers(provider: str, key: str) -> Dict[str, str]:
    if provider == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    if provider == "google":
        return {"x-goog-api-key": key}
    return {"Authorization": f"Bearer {key}"}


def verify_one(judge: str, timeout: float = 20.0) -> Dict[str, str]:
    """One minimal request. Reports a class of outcome, never a key or a body."""
    filename, provider = JUDGES[judge]
    key = _key(filename)
    if key is None:
        return dict(judge=judge, status="fails", reason="no key file")
    req = urllib.request.Request(ENDPOINT[provider],
                                 headers=_headers(provider, key))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return dict(judge=judge, status=("ok" if r.status == 200 else "fails"),
                        reason=f"http {r.status}")
    except urllib.error.HTTPError as e:
        cls = {401: "auth rejected", 403: "forbidden", 404: "endpoint not found",
               429: "rate limited"}.get(e.code, f"http {e.code}")
        return dict(judge=judge, status="fails", reason=cls)
    except urllib.error.URLError as e:
        return dict(judge=judge, status="fails",
                    reason=f"network unreachable ({type(e.reason).__name__})")
    except Exception as e:
        return dict(judge=judge, status="fails", reason=type(e).__name__)


def env_for_judges() -> Dict[str, str]:
    """Credentials for the judge phase only, as an env mapping.

    Returned rather than exported globally, so the caller hands it to exactly one
    subprocess and nothing else in the session ever holds it.
    """
    env = {}
    for judge, (filename, provider) in JUDGES.items():
        k = _key(filename)
        if k is None:
            continue
        var = {"openai": "OPENAI_API_KEY", "anthropic": "ANTHROPIC_API_KEY",
               "google": "GEMINI_API_KEY", "deepseek": "DEEPSEEK_API_KEY",
               "moonshot": "MOONSHOT_API_KEY"}[provider]
        env[var] = k
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    a = ap.parse_args()
    if not a.verify:
        print("nothing to do; pass --verify")
        return 0
    print(f"{'judge':20s} {'status':7s} reason")
    n_ok = 0
    for judge in JUDGES:
        r = verify_one(judge)
        n_ok += r["status"] == "ok"
        print(f"{r['judge']:20s} {r['status']:7s} {r['reason']}")
    print(f"\n{n_ok} of {len(JUDGES)} judges reachable")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
