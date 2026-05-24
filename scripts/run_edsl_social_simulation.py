#!/usr/bin/env python3
"""Collect a new EDSL social-simulation game run.

The input is a Python module that defines ``build_game_spec() -> GameSpec``.
The output is a normalized run folder consumed by ``run_open_sae_feature_inspection.py
--run-dir``.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from social_sim_open_sae.edsl_adapter import load_game_spec, run_game


def parse_csv_list(value: str | None) -> set[str] | None:
    """Parse comma-separated CLI values."""

    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--game-module",
        type=Path,
        required=True,
        help="Python file defining build_game_spec() -> GameSpec.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory where normalized EDSL run outputs will be written.",
    )
    parser.add_argument(
        "--model-id",
        default=None,
        help="EDSL model id. Defaults to the GameSpec default_model_id.",
    )
    parser.add_argument(
        "--service-name",
        default=None,
        help="Optional EDSL service name. Defaults to the GameSpec default_service_name.",
    )
    parser.add_argument(
        "--agents",
        type=int,
        default=None,
        help="Number of agents per condition/scenario. Defaults to the GameSpec AgentSpec count.",
    )
    parser.add_argument(
        "--conditions",
        default=None,
        help="Comma-separated condition names to run. Defaults to all conditions.",
    )
    parser.add_argument(
        "--limit-scenarios",
        type=int,
        default=None,
        help="Keep only the first N scenarios per condition for smoke tests.",
    )
    parser.add_argument(
        "--mock-model",
        action="store_true",
        help="Use EDSL's deterministic test model instead of remote model inference.",
    )
    parser.add_argument(
        "--cache",
        action="store_true",
        help="Enable EDSL cache. Default is disabled for clearer provenance.",
    )
    parser.add_argument(
        "--disable-remote-inference",
        action="store_true",
        help="Pass disable_remote_inference=True to EDSL run().",
    )
    return parser.parse_args()


def main() -> None:
    """Run an EDSL game and write normalized outputs."""

    args = parse_args()
    spec = load_game_spec(args.game_module)
    manifest = run_game(
        spec=spec,
        module_path=args.game_module.resolve(),
        output_dir=args.output_dir,
        model_id=args.model_id or spec.default_model_id,
        service_name=args.service_name if args.service_name is not None else spec.default_service_name,
        agent_count=args.agents if args.agents is not None else spec.agents.count,
        selected_conditions=parse_csv_list(args.conditions),
        limit_scenarios=args.limit_scenarios,
        mock_model=args.mock_model,
        cache=args.cache,
        disable_remote_inference=args.disable_remote_inference,
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "output_dir": str(args.output_dir),
                "game_id": manifest["game_id"],
                "response_units": manifest["response_units"],
                "behavior_summary_rows": manifest["behavior_summary_rows"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
