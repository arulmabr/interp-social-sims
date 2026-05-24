#!/usr/bin/env python3
"""Check local prerequisites without installing packages or loading big models."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON_MIN = (3, 10)
PYTHON_MAX_EXCLUSIVE = (3, 14)
GPU_PACKAGES = [
    "torch",
    "transformers",
    "accelerate",
    "huggingface_hub",
    "safetensors",
]
LOCAL_PACKAGES = ["pandas", "numpy", "matplotlib", "edsl"]


@dataclass
class CheckResult:
    """One prerequisite check result."""

    name: str
    status: str
    detail: str
    required_for: str


def package_status(name: str) -> str:
    """Return a compact package availability string."""

    spec = importlib.util.find_spec(name)
    if spec is None:
        return "missing"
    try:
        module = __import__(name)
        version = getattr(module, "__version__", "")
    except Exception:
        version = ""
    return f"installed {version}".strip()


def command_output(command: list[str]) -> str:
    """Return command output or an empty string when unavailable."""

    try:
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
    except OSError:
        return ""
    return (result.stdout or result.stderr).strip()


def check_python() -> CheckResult:
    """Check supported Python version."""

    version = sys.version_info
    ok = PYTHON_MIN <= (version.major, version.minor) < PYTHON_MAX_EXCLUSIVE
    status = "ok" if ok else "warning"
    detail = (
        f"{platform.python_version()} at {sys.executable}; recommended "
        "range is Python 3.10-3.13"
    )
    return CheckResult("python", status, detail, "all workflows")


def check_packages(names: list[str], required_for: str) -> list[CheckResult]:
    """Check import availability for package names."""

    rows: list[CheckResult] = []
    for name in names:
        status = package_status(name)
        rows.append(
            CheckResult(
                name=f"package:{name}",
                status="ok" if status.startswith("installed") else "missing",
                detail=status,
                required_for=required_for,
            )
        )
    return rows


def check_env_var(name: str, required_for: str) -> CheckResult:
    """Check whether an environment variable is set without printing its value."""

    present = bool(os.getenv(name))
    return CheckResult(
        name=f"env:{name}",
        status="ok" if present else "missing",
        detail="set" if present else "not set",
        required_for=required_for,
    )


def check_nvidia_smi() -> CheckResult:
    """Check whether NVIDIA tooling is visible."""

    path = shutil.which("nvidia-smi")
    if path is None:
        return CheckResult(
            "nvidia-smi",
            "missing",
            "not found on PATH",
            "GPU Open-SAE inspection and live steering",
        )
    output = command_output([path, "--query-gpu=name,memory.total", "--format=csv,noheader"])
    return CheckResult(
        "nvidia-smi",
        "ok" if output else "warning",
        output or f"found at {path}, but GPU query returned no output",
        "GPU Open-SAE inspection and live steering",
    )


def check_repo_files() -> list[CheckResult]:
    """Check core release files that commands assume exist."""

    required = [
        "examples/games/safe_risky.py",
        "scripts/run_edsl_social_simulation.py",
        "scripts/run_open_sae_feature_inspection.py",
        "scripts/run_open_sae_steering_generation.py",
        "data/processed/feature_description_lookup.csv",
        "reports/RELEASE_COMPLETION_AUDIT.json",
    ]
    rows: list[CheckResult] = []
    for rel_path in required:
        path = ROOT / rel_path
        rows.append(
            CheckResult(
                name=f"file:{rel_path}",
                status="ok" if path.exists() and path.stat().st_size > 0 else "missing",
                detail=f"{path.stat().st_size} bytes" if path.exists() else "not found",
                required_for="release reproduction",
            )
        )
    return rows


def run_checks(include_gpu: bool) -> list[CheckResult]:
    """Run selected checks."""

    rows = [check_python()]
    rows.extend(check_packages(LOCAL_PACKAGES, "local EDSL/data workflows"))
    if include_gpu:
        rows.extend(check_packages(GPU_PACKAGES, "GPU Open-SAE inspection and steering"))
        rows.append(check_env_var("HF_TOKEN", "gated Meta Llama model download"))
        rows.append(check_nvidia_smi())
    rows.extend(check_repo_files())
    return rows


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpu", action="store_true", help="Also check GPU/HF prerequisites.")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of a table.")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit nonzero on missing checks. Warnings remain informational.",
    )
    return parser.parse_args()


def main() -> None:
    """Run environment checks."""

    args = parse_args()
    rows = run_checks(args.gpu)
    if args.json:
        print(json.dumps([asdict(row) for row in rows], indent=2))
    else:
        width = max(len(row.name) for row in rows)
        for row in rows:
            print(f"{row.name:<{width}}  {row.status:<7}  {row.detail}  [{row.required_for}]")
    if args.strict and any(row.status == "missing" for row in rows):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
