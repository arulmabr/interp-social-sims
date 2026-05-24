#!/usr/bin/env python3
"""Smoke checks for the platform-first EDSL workflow."""

from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

EXAMPLES = {
    "creativity": ("examples/games/creativity.py", 4),
    "safe_risky": ("examples/games/safe_risky.py", 2),
    "ultimatum": ("examples/games/ultimatum.py", 2),
    "trust": ("examples/games/trust.py", 2),
}


def run(command: list[str], *, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command and raise with useful output on failure."""

    result = subprocess.run(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "Command failed:\n"
            + " ".join(command)
            + f"\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
        )
    return result


def check_docs() -> None:
    """Ensure the public docs describe the platform workflow."""

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    build_doc = (ROOT / "docs/BUILD_A_GAME.md").read_text(encoding="utf-8")
    if "building EDSL social simulations" not in readme:
        raise AssertionError("README does not foreground building EDSL social simulations")
    if "scripts/run_edsl_social_simulation.py" not in build_doc:
        raise AssertionError("BUILD_A_GAME.md is missing the EDSL collection command")
    if "scripts/run_open_sae_feature_inspection.py" not in build_doc or "--run-dir" not in build_doc:
        raise AssertionError("BUILD_A_GAME.md is missing the Open-SAE run-dir command")


def check_game_specs() -> None:
    """Load all example GameSpecs without importing EDSL."""

    from social_sim_open_sae.edsl_adapter import load_game_spec

    for game_id, (module_path, _) in EXAMPLES.items():
        spec = load_game_spec(ROOT / module_path)
        if spec.game_id != game_id:
            raise AssertionError(f"Unexpected game id for {module_path}: {spec.game_id}")
        if not spec.questions or not spec.conditions:
            raise AssertionError(f"Example spec is incomplete: {module_path}")


def check_environment_doctor() -> None:
    """Run the non-strict environment checker."""

    result = run([sys.executable, "scripts/check_environment.py", "--json"])
    payload = json.loads(result.stdout)
    names = {row["name"] for row in payload}
    for required in [
        "python",
        "package:edsl",
        "file:scripts/run_edsl_social_simulation.py",
        "file:scripts/run_open_sae_feature_inspection.py",
    ]:
        if required not in names:
            raise AssertionError(f"Environment check missing {required}")


def check_synthetic_run_dir_loader() -> None:
    """Validate the Open-SAE --run-dir dry-run path without EDSL or GPU."""

    with tempfile.TemporaryDirectory(prefix="social_sim_open_sae_run_dir_") as tmp:
        run_dir = Path(tmp)
        (run_dir / "run_manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "run_type": "edsl_social_simulation",
                    "game_id": "synthetic_game",
                    "response_units": 1,
                }
            ),
            encoding="utf-8",
        )
        with (run_dir / "response_units.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=[
                    "unit_id",
                    "game_id",
                    "condition",
                    "task",
                    "scenario_id",
                    "reward",
                    "source_file",
                    "source_row_index",
                    "response_index",
                    "agent_index",
                    "agent_subject_id",
                    "answer_text",
                    "comment_text",
                    "system_prompt",
                    "user_prompt",
                    "response_text",
                ],
            )
            writer.writeheader()
            writer.writerow(
                {
                    "unit_id": "synthetic:baseline:0:0:choice",
                    "game_id": "synthetic_game",
                    "condition": "baseline",
                    "task": "choice",
                    "scenario_id": "0",
                    "reward": "1",
                    "source_file": "edsl_results/baseline.csv",
                    "source_row_index": "0",
                    "response_index": "1",
                    "agent_index": "0",
                    "agent_subject_id": "A1",
                    "answer_text": "yes",
                    "comment_text": "",
                    "system_prompt": "",
                    "user_prompt": "Choose yes or no.",
                    "response_text": "yes",
                }
            )
        result = run(
            [
                sys.executable,
                "scripts/run_open_sae_feature_inspection.py",
                "--run-dir",
                str(run_dir),
                "--dry-run",
                "--expected-units",
                "1",
            ]
        )
        payload = json.loads(result.stdout)
        if payload["dataset_kind"] != "synthetic_game" or payload["unit_count"] != 1:
            raise AssertionError(f"Unexpected dry-run payload: {payload}")
        steering_dir = run_dir / "steering_smoke"
        steering_result = run(
            [
                sys.executable,
                "scripts/run_open_sae_steering_generation.py",
                "--run-dir",
                str(run_dir),
                "--output-dir",
                str(steering_dir),
                "--feature-indices",
                "13142,20117,4992",
                "--strengths",
                "0.3,0.3,0.3",
                "--smoke-mode",
                "--skip-neuronpedia-metadata",
                "--expected-units",
                "1",
            ]
        )
        steering_payload = json.loads(steering_result.stdout)
        if (
            steering_payload["dataset_kind"] != "synthetic_game"
            or steering_payload["selected_prompt_units"] != 1
        ):
            raise AssertionError(f"Unexpected steering smoke payload: {steering_payload}")


def check_edsl_smoke_runs() -> None:
    """Run tiny deterministic EDSL collections when requested by the environment."""

    if os.getenv("RUN_EDSL_SMOKE") != "1":
        return
    env = dict(os.environ)
    env["PYTHONPATH"] = f"{ROOT}:{env.get('PYTHONPATH', '')}".rstrip(":")
    with tempfile.TemporaryDirectory(prefix="social_sim_open_sae_edsl_") as tmp:
        base = Path(tmp)
        for game_id, (module_path, expected_units) in EXAMPLES.items():
            output_dir = base / game_id
            run(
                [
                    sys.executable,
                    "scripts/run_edsl_social_simulation.py",
                    "--game-module",
                    module_path,
                    "--output-dir",
                    str(output_dir),
                    "--mock-model",
                    "--agents",
                    "2",
                    "--conditions",
                    "baseline",
                    "--limit-scenarios",
                    "1",
                ],
                env=env,
            )
            manifest = json.loads((output_dir / "run_manifest.json").read_text(encoding="utf-8"))
            if manifest["response_units"] != expected_units:
                raise AssertionError(
                    f"{game_id} smoke produced {manifest['response_units']} units, "
                    f"expected {expected_units}"
                )
            run(
                [
                    sys.executable,
                    "scripts/run_open_sae_feature_inspection.py",
                    "--run-dir",
                    str(output_dir),
                    "--dry-run",
                    "--expected-units",
                    str(expected_units),
                ],
                env=env,
            )


def main() -> None:
    check_docs()
    check_game_specs()
    check_environment_doctor()
    check_synthetic_run_dir_loader()
    check_edsl_smoke_runs()
    print("platform smoke verification passed")


if __name__ == "__main__":
    main()
