"""EDSL adapter for reusable social-simulation game specs."""

from __future__ import annotations

import csv
import datetime as dt
import importlib.util
import json
import math
import re
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

from social_sim_open_sae.game_spec import (
    ConditionSpec,
    GameSpec,
    QuestionSpec,
    ResponseUnit,
)


def load_game_spec(module_path: Path) -> GameSpec:
    """Import a Python module and call its ``build_game_spec`` function."""

    module_path = module_path.resolve()
    if not module_path.exists():
        raise FileNotFoundError(module_path)
    module_name = f"social_sim_game_{module_path.stem}_{abs(hash(module_path))}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not import game module: {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    if not hasattr(module, "build_game_spec"):
        raise AttributeError(f"{module_path} must define build_game_spec()")
    game_spec = module.build_game_spec()
    if not isinstance(game_spec, GameSpec):
        raise TypeError("build_game_spec() must return social_sim_open_sae.GameSpec")
    validate_game_spec(game_spec)
    return game_spec


def validate_game_spec(spec: GameSpec) -> None:
    """Validate the parts of the spec needed for EDSL collection."""

    if not spec.game_id:
        raise ValueError("GameSpec.game_id is required")
    if not spec.questions:
        raise ValueError("GameSpec.questions must not be empty")
    if not spec.conditions:
        raise ValueError("GameSpec.conditions must not be empty")
    question_names = spec.question_names()
    if len(question_names) != len(set(question_names)):
        raise ValueError(f"Duplicate question names: {question_names}")
    condition_names = spec.condition_names()
    if len(condition_names) != len(set(condition_names)):
        raise ValueError(f"Duplicate condition names: {condition_names}")


def safe_text(value: Any) -> str:
    """Normalize CSV/EDSL values to printable text."""

    if value is None:
        return ""
    try:
        if value != value:
            return ""
    except TypeError:
        pass
    text = str(value)
    return "" if text.lower() == "nan" else text


def parse_int_or_none(value: Any) -> int | None:
    """Parse scenario value fields used as reward/offer/sent amounts."""

    text = safe_text(value)
    if not text:
        return None
    try:
        parsed = float(text)
    except ValueError:
        return None
    if math.isnan(parsed):
        return None
    return int(parsed)


def slug(text: str) -> str:
    """Make a compact id-safe slug."""

    return re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower() or "value"


def import_edsl() -> dict[str, Any]:
    """Import EDSL lazily so docs and non-EDSL checks can run without it."""

    try:
        from edsl import (  # type: ignore
            Agent,
            AgentList,
            Model,
            QuestionFreeText,
            QuestionList,
            QuestionMultipleChoice,
            QuestionNumerical,
            Scenario,
            ScenarioList,
            Survey,
        )
    except ImportError as exc:
        raise SystemExit(
            "EDSL is required to collect new social-simulation data. Install it with "
            "`pip install edsl` or, when developing beside the EDSL checkout, "
            "`pip install -e ../edsl`."
        ) from exc
    return {
        "Agent": Agent,
        "AgentList": AgentList,
        "Model": Model,
        "QuestionFreeText": QuestionFreeText,
        "QuestionList": QuestionList,
        "QuestionMultipleChoice": QuestionMultipleChoice,
        "QuestionNumerical": QuestionNumerical,
        "Scenario": Scenario,
        "ScenarioList": ScenarioList,
        "Survey": Survey,
    }


def build_question(question: QuestionSpec, edsl: dict[str, Any]) -> Any:
    """Build an EDSL question object from a QuestionSpec."""

    common = {
        "question_name": question.question_name,
        "question_text": question.question_text,
    }
    if question.question_type == "free_text":
        return edsl["QuestionFreeText"](**common)
    if question.question_type == "list":
        kwargs = dict(common)
        if question.max_list_items is not None:
            kwargs["max_list_items"] = question.max_list_items
        return edsl["QuestionList"](**kwargs)
    if question.question_type == "multiple_choice":
        if question.question_options is None:
            raise ValueError(f"{question.question_name} needs question_options")
        return edsl["QuestionMultipleChoice"](
            **common,
            question_options=question.question_options,
        )
    if question.question_type == "numerical":
        kwargs = dict(common)
        if question.min_value is not None:
            kwargs["min_value"] = question.min_value
        if question.max_value is not None:
            kwargs["max_value"] = question.max_value
        return edsl["QuestionNumerical"](**kwargs)
    raise ValueError(f"Unsupported question_type: {question.question_type}")


def default_mock_response(question: QuestionSpec) -> str:
    """Return a deterministic response compatible with the question type."""

    if question.mock_response is not None:
        return question.mock_response
    if question.question_type == "list":
        return '["deterministic idea one", "deterministic idea two"]'
    if question.question_type == "multiple_choice":
        if question.question_options:
            return str(question.question_options[0])
        return "option"
    if question.question_type == "numerical":
        return str(question.min_value if question.min_value is not None else 0)
    return "deterministic response"


def build_mock_model(spec: GameSpec, edsl: dict[str, Any]) -> Any:
    """Build EDSL's deterministic test model for no-network smoke runs."""

    responses = [default_mock_response(question) for question in spec.questions]
    state = {"calls": 0}

    def deterministic_response(user_prompt: str, system_prompt: str, files_list: Any) -> str:
        index = state["calls"] % len(responses)
        state["calls"] += 1
        return responses[index]

    return edsl["Model"]("test", func=deterministic_response)


def build_model(
    spec: GameSpec,
    condition: ConditionSpec,
    edsl: dict[str, Any],
    *,
    model_id: str,
    service_name: str | None,
    mock_model: bool,
) -> Any:
    """Build an EDSL model for one condition."""

    if mock_model:
        return build_mock_model(spec, edsl)
    kwargs = dict(condition.model_parameters)
    if service_name:
        kwargs["service_name"] = service_name
    return edsl["Model"](model_id, **kwargs)


def build_agents(
    spec: GameSpec,
    condition: ConditionSpec,
    edsl: dict[str, Any],
    *,
    agent_count: int,
) -> Any:
    """Build condition-specific EDSL agents."""

    agents = []
    for index in range(1, agent_count + 1):
        traits = {
            **spec.agents.traits,
            **condition.traits,
            "agent_index": index,
            "subject_id": f"{spec.agents.subject_prefix}{index}",
        }
        instruction = condition.instruction or spec.agents.instruction
        agents.append(
            edsl["Agent"](
                name=f"{condition.name}_agent_{index}",
                traits=traits,
                instruction=instruction,
            )
        )
    return edsl["AgentList"](agents)


def build_scenarios(
    condition: ConditionSpec,
    edsl: dict[str, Any],
    *,
    limit_scenarios: int | None,
) -> Any:
    """Build EDSL scenarios for a condition."""

    scenario_dicts = condition.scenarios or [{}]
    if limit_scenarios is not None:
        scenario_dicts = scenario_dicts[:limit_scenarios]
    scenarios = []
    for index, scenario in enumerate(scenario_dicts):
        payload = {
            "condition": condition.name,
            "scenario_index": index,
            **scenario,
        }
        if condition.value_field and condition.value_field in scenario:
            payload["reward"] = scenario[condition.value_field]
        scenarios.append(edsl["Scenario"](payload))
    return edsl["ScenarioList"](scenarios)


def select_conditions(spec: GameSpec, names: set[str] | None) -> list[ConditionSpec]:
    """Return selected conditions in spec order."""

    if names is None:
        return spec.conditions
    unknown = sorted(names - set(spec.condition_names()))
    if unknown:
        raise ValueError(f"Unknown conditions for {spec.game_id}: {unknown}")
    return [condition for condition in spec.conditions if condition.name in names]


def results_to_frame(results: Any, csv_path: Path) -> Any:
    """Persist EDSL results to CSV and read them back with pandas."""

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(str(csv_path))
    try:
        import pandas as pd
    except ImportError as exc:
        raise SystemExit("pandas is required to normalize EDSL result CSVs") from exc
    return pd.read_csv(csv_path)


def row_value(row: Any, key: str) -> Any:
    """Read a DataFrame row key without assuming it exists."""

    return row[key] if key in row else None


def normalize_results(
    *,
    spec: GameSpec,
    condition: ConditionSpec,
    frame: Any,
    source_file: str,
) -> list[ResponseUnit]:
    """Convert one condition's EDSL result frame to response units."""

    units: list[ResponseUnit] = []
    for row_index, row in frame.iterrows():
        scenario_index = safe_text(row_value(row, "scenario.scenario_index")) or str(row_index)
        reward = parse_int_or_none(row_value(row, "scenario.reward"))
        agent_index = safe_text(row_value(row, "agent.agent_index")) or str(row_index + 1)
        agent_subject_id = safe_text(row_value(row, "agent.subject_id")) or agent_index
        for question in spec.questions:
            answer_text = safe_text(row_value(row, f"answer.{question.question_name}"))
            unit_id = (
                f"{spec.game_id}:{condition.name}:{scenario_index}:"
                f"{agent_index}:{question.question_name}"
            )
            units.append(
                ResponseUnit(
                    unit_id=unit_id,
                    game_id=spec.game_id,
                    condition=condition.name,
                    task=question.question_name,
                    scenario_id=scenario_index,
                    reward=reward,
                    source_file=source_file,
                    source_row_index=int(row_index),
                    response_index=len(units) + 1,
                    agent_index=agent_index,
                    agent_subject_id=agent_subject_id,
                    answer_text=answer_text,
                    comment_text=safe_text(row_value(row, f"comment.{question.question_name}_comment")),
                    system_prompt=safe_text(row_value(row, f"prompt.{question.question_name}_system_prompt")),
                    user_prompt=safe_text(row_value(row, f"prompt.{question.question_name}_user_prompt")),
                    response_text=safe_text(
                        row_value(row, f"generated_tokens.{question.question_name}_generated_tokens")
                    )
                    or answer_text,
                )
            )
    return units


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write dictionaries to CSV."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write dictionaries to JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def behavior_rows_for_units(spec: GameSpec, units: list[ResponseUnit]) -> list[dict[str, Any]]:
    """Run the game-defined behavior parser over response units."""

    if spec.behavior_parser is None:
        return []
    rows: list[dict[str, Any]] = []
    for unit in units:
        unit_row = asdict(unit)
        parsed = spec.behavior_parser(unit_row)
        if not parsed:
            continue
        rows.append({**unit_row, **parsed})
    return rows


def behavior_summary(behavior_rows: list[dict[str, Any]], metric_names: list[str]) -> list[dict[str, Any]]:
    """Summarize numeric behavior metrics by task/condition/reward."""

    groups: dict[tuple[str, str, int | None, str], list[float]] = {}
    for row in behavior_rows:
        for metric_name in metric_names:
            value = row.get(metric_name)
            if value is None or value == "":
                continue
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                continue
            key = (row["task"], row["condition"], row.get("reward"), metric_name)
            groups.setdefault(key, []).append(numeric)

    summary_rows: list[dict[str, Any]] = []
    for (task, condition, reward, metric_name), values in sorted(
        groups.items(),
        key=lambda item: (item[0][0], item[0][1], item[0][2] if item[0][2] is not None else -1, item[0][3]),
    ):
        summary_rows.append(
            {
                "task": task,
                "condition": condition,
                "reward": reward,
                "metric": metric_name,
                "mean": sum(values) / len(values),
                "count": len(values),
            }
        )
    return summary_rows


def write_behavior_plot(output_dir: Path, spec: GameSpec, summary_rows: list[dict[str, Any]]) -> list[str]:
    """Write a small behavior diagnostic plot when numeric metrics exist."""

    if not summary_rows:
        return []
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        return []
    metric = summary_rows[0]["metric"]
    fig, ax = plt.subplots(figsize=(7.5, 4.8))
    by_condition: dict[str, list[dict[str, Any]]] = {}
    for row in summary_rows:
        if row["metric"] == metric:
            by_condition.setdefault(row["condition"], []).append(row)
    for condition, rows in by_condition.items():
        rows = sorted(rows, key=lambda row: row["reward"] if row["reward"] is not None else 0)
        xs = [row["reward"] if row["reward"] is not None else index for index, row in enumerate(rows)]
        ys = [row["mean"] for row in rows]
        ax.plot(xs, ys, marker="o", label=condition)
    ax.set_title(f"{spec.title}: {metric}")
    ax.set_xlabel("Scenario value")
    ax.set_ylabel(metric)
    ax.legend()
    fig.tight_layout()
    path = output_dir / "behavior_summary.png"
    fig.savefig(path, dpi=180)
    plt.close(fig)
    return [str(path)]


def run_game(
    *,
    spec: GameSpec,
    module_path: Path,
    output_dir: Path,
    model_id: str,
    service_name: str | None,
    agent_count: int,
    selected_conditions: set[str] | None,
    limit_scenarios: int | None,
    mock_model: bool,
    cache: bool,
    disable_remote_inference: bool,
) -> dict[str, Any]:
    """Collect an EDSL social-simulation run and write normalized outputs."""

    edsl = import_edsl()
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "edsl_results"
    conditions = select_conditions(spec, selected_conditions)
    questions = [build_question(question, edsl) for question in spec.questions]
    survey = edsl["Survey"](questions)

    all_units: list[ResponseUnit] = []
    condition_outputs: list[dict[str, Any]] = []
    for condition in conditions:
        agents = build_agents(spec, condition, edsl, agent_count=agent_count)
        scenarios = build_scenarios(condition, edsl, limit_scenarios=limit_scenarios)
        model = build_model(
            spec,
            condition,
            edsl,
            model_id=model_id,
            service_name=service_name,
            mock_model=mock_model,
        )
        results = (
            survey.by(scenarios)
            .by(agents)
            .by(model)
            .run(
                cache=cache,
                # Don't let a single transient error (e.g. a provider 429) abort
                # a large multi-thousand-call sweep; failed cells are simply
                # skipped and can be re-run.
                stop_on_exception=False,
                disable_remote_inference=disable_remote_inference or mock_model,
            )
        )
        source_file = f"{slug(condition.name)}.csv"
        frame = results_to_frame(results, raw_dir / source_file)
        units = normalize_results(
            spec=spec,
            condition=condition,
            frame=frame,
            source_file=str(Path("edsl_results") / source_file),
        )
        all_units.extend(units)
        condition_outputs.append(
            {
                "condition": condition.name,
                "source_file": str(Path("edsl_results") / source_file),
                "result_rows": int(len(frame)),
                "response_units": len(units),
            }
        )

    unit_rows = [asdict(unit) for unit in all_units]
    write_csv(output_dir / "response_units.csv", unit_rows)
    write_jsonl(output_dir / "response_units.jsonl", unit_rows)

    behavior_unit_rows = behavior_rows_for_units(spec, all_units)
    behavior_summary_rows = behavior_summary(
        behavior_unit_rows,
        [metric.name for metric in spec.behavior_metrics],
    )
    plot_paths = write_behavior_plot(output_dir, spec, behavior_summary_rows)
    if behavior_unit_rows:
        write_csv(output_dir / "behavior_units.csv", behavior_unit_rows)
    if behavior_summary_rows:
        write_csv(output_dir / "behavior_summary.csv", behavior_summary_rows)

    manifest = {
        "schema_version": 1,
        "run_type": "edsl_social_simulation",
        "game_id": spec.game_id,
        "title": spec.title,
        "description": spec.description,
        "game_module": str(module_path),
        "timestamp_utc": dt.datetime.now(dt.timezone.utc).isoformat(),
        "model_id": "test" if mock_model else model_id,
        "service_name": None if mock_model else service_name,
        "mock_model": mock_model,
        "agent_count": agent_count,
        "limit_scenarios": limit_scenarios,
        "conditions": [asdict(condition) for condition in conditions],
        "questions": [asdict(question) for question in spec.questions],
        "condition_outputs": condition_outputs,
        "response_units": len(all_units),
        "behavior_unit_rows": len(behavior_unit_rows),
        "behavior_summary_rows": len(behavior_summary_rows),
        "plots": plot_paths,
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return manifest
