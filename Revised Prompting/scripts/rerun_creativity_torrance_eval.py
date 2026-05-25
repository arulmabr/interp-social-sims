"""Rerun Torrance-style GPT creativity evaluations over saved experiment CSVs.

This is a judge-only rerun: it reads the existing generated responses and writes
derived score artifacts into a separate output directory.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import hashlib
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE_DIR = (
    REPO_ROOT / "data" / "raw" / "creativity" / "product_innovation_20251102_202650"
)
DEFAULT_OUTPUT_DIR = (
    REPO_ROOT
    / "data"
    / "processed"
    / "creativity"
    / "torrance_gpt_eval"
)


def release_path(path: Path | str | None) -> str | None:
    """Return a metadata path without leaking local user directories."""

    if path is None:
        return None
    path = Path(path)
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        if path.is_absolute():
            return f"<external>/{path.name}"
        return path.as_posix()

CONDITIONS = {
    "baseline": "Baseline",
    "prompting": "Prompting",
    "high_temperature": "High Temp",
    "high_steering": "Steering",
}
CONDITION_COLORS = {
    "baseline": "#3498db",
    "prompting": "#e74c3c",
    "high_temperature": "#f39c12",
    "high_steering": "#2ecc71",
}
TASKS = {
    "detailed_ways_to_use_a_brick": (
        "List very detailed ways you can use a brick. Each answer should be a "
        "paragraph."
    ),
    "improve_the_stapler_with_many_specific_enhancements": (
        "Your goal is to improve the stapler. List as many specific "
        "enhancements as you can that would make it better. You may change "
        "features, materials, mechanisms, interfaces, or add/remove parts. Do "
        "not list new uses; stay focused on improvements to the object itself. "
        "For each idea, add enough detail so someone could build or test it."
    ),
}
TASK_TITLES = {
    "detailed_ways_to_use_a_brick": "Divergent Creativity Tasks",
    "improve_the_stapler_with_many_specific_enhancements": (
        "Product Innovation Tasks"
    ),
}

TORRANCE_SYSTEM_PROMPT = """You are an expert evaluator of creative responses, trained in the Torrance Tests of Creative Thinking framework. You will score a single response on four dimensions, each as an integer from 1 to 10.

Dimensions:
1. Fluency — the number of relevant, non-redundant ideas produced.
2. Flexibility — the number of distinct conceptual categories the ideas span.
3. Originality — how unusual or non-obvious the ideas are relative to common responses.
4. Elaboration — the level of detail, refinement, and specificity per idea.

Calibration anchors (apply to each dimension independently):
- 1–2: dimension is essentially absent or actively poor.
- 3–4: dimension is present but weak / minimal.
- 5–6: average; competent but unremarkable.
- 7–8: strong on this dimension.
- 9–10: exceptional; near the top of what a human creative could produce.

Rules:
- Score each dimension independently. Do not let one dimension anchor another.
- Use the full 1–10 range; do not default to the middle.
- Return integer scores only (no halves, no decimals).
- Do not penalize a response for being a list; the task asks for one.
- Do not reward verbosity that adds no new ideas or no new detail.
- Output strict JSON only. No prose, no markdown, no code fences."""

SCORE_KEYS = ("fluency", "flexibility", "originality", "elaboration")

JSON_SCHEMA_FORMAT = {
    "type": "json_schema",
    "name": "torrance_creativity_scores",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "fluency": {"type": "integer"},
            "flexibility": {"type": "integer"},
            "originality": {"type": "integer"},
            "elaboration": {"type": "integer"},
        },
        "required": list(SCORE_KEYS),
        "additionalProperties": False,
    },
}


class ApiError(RuntimeError):
    """OpenAI API call failed."""

    def __init__(self, status: int | None, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"OpenAI API error {status}: {body[:500]}")


@dataclass(frozen=True)
class EvalItem:
    """Single saved response to score."""

    eval_id: str
    task: str
    task_description: str
    condition: str
    condition_label: str
    source_file: str
    source_row_index: int
    agent_index: int | None
    subject_id: str | None
    agent_name: str | None
    response_text: str


def load_env_file(env_path: Path) -> None:
    """Load KEY=VALUE entries from .env without overwriting existing env vars."""
    if not env_path.exists():
        return

    for line in env_path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        if stripped.startswith("export "):
            stripped = stripped[len("export ") :]
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def sha256_file(path: Path) -> str:
    """Return a SHA256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_eval_items(source_dir: Path) -> list[EvalItem]:
    """Load all task responses from the four condition CSVs."""
    items: list[EvalItem] = []

    for condition, condition_label in CONDITIONS.items():
        csv_path = source_dir / f"{condition}.csv"
        if not csv_path.exists():
            raise FileNotFoundError(f"Missing source CSV: {csv_path}")

        df = pd.read_csv(csv_path)
        for task, task_description in TASKS.items():
            response_col = f"answer.{task}"
            if response_col not in df.columns:
                raise KeyError(f"Missing response column {response_col} in {csv_path}")

            for row_index, row in df.iterrows():
                agent_index = _nullable_int(row.get("agent.agent_index"))
                subject_id = _nullable_str(row.get("agent.subject_id"))
                agent_name = _nullable_str(row.get("agent.agent_name"))
                response_text = "" if pd.isna(row[response_col]) else str(row[response_col])
                eval_id = f"{condition}|{task}|{row_index}"
                items.append(
                    EvalItem(
                        eval_id=eval_id,
                        task=task,
                        task_description=task_description,
                        condition=condition,
                        condition_label=condition_label,
                        source_file=csv_path.name,
                        source_row_index=int(row_index),
                        agent_index=agent_index,
                        subject_id=subject_id,
                        agent_name=agent_name,
                        response_text=response_text,
                    )
                )

    return items


def _nullable_str(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    text = str(value)
    return text if text else None


def _nullable_int(value: Any) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)


def user_prompt(item: EvalItem) -> str:
    """Build the per-response scoring prompt."""
    return (
        f"Task:\n{item.task_description}\n\n"
        "Response to evaluate:\n"
        f"{item.response_text}\n\n"
        "Return a JSON object with exactly these integer keys: fluency, "
        "flexibility, originality, elaboration."
    )


def call_openai_responses(
    *,
    api_key: str,
    model: str,
    item: EvalItem,
    timeout: int,
    structured_output: bool = True,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Call the OpenAI Responses API using only the Python standard library."""
    payload = {
        "model": model,
        "instructions": TORRANCE_SYSTEM_PROMPT,
        "input": user_prompt(item),
        "max_output_tokens": 1000,
        "store": False,
    }
    if structured_output:
        payload["text"] = {"format": JSON_SCHEMA_FORMAT}
    if reasoning_effort:
        payload["reasoning"] = {"effort": reasoning_effort}

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/responses",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise ApiError(exc.code, error_body) from exc
    except urllib.error.URLError as exc:
        raise ApiError(None, str(exc)) from exc

    return json.loads(response_body)


def extract_output_text(response: dict[str, Any]) -> str:
    """Extract the generated text from a Responses API response."""
    if isinstance(response.get("output_text"), str):
        return response["output_text"]

    for output_item in response.get("output", []):
        for content_item in output_item.get("content", []):
            if content_item.get("type") == "output_text":
                return str(content_item.get("text", ""))
            if "text" in content_item:
                return str(content_item["text"])

    raise ValueError(f"Could not find output text in response id={response.get('id')}")


def parse_scores(raw_text: str) -> dict[str, int]:
    """Parse and validate the four Torrance scores."""
    parsed = json.loads(raw_text.strip())
    missing = [key for key in SCORE_KEYS if key not in parsed]
    if missing:
        raise ValueError(f"Missing score keys: {missing}")

    scores: dict[str, int] = {}
    for key in SCORE_KEYS:
        value = parsed[key]
        if not isinstance(value, int):
            raise ValueError(f"{key} is not an integer: {value!r}")
        if not 1 <= value <= 10:
            raise ValueError(f"{key} is outside 1-10: {value!r}")
        scores[key] = value

    return scores


def evaluate_item(
    item: EvalItem,
    *,
    api_key: str,
    model: str,
    timeout: int,
    max_attempts: int,
    plain_json_only: bool = False,
    reasoning_effort: str | None = None,
) -> dict[str, Any]:
    """Evaluate one response with retries."""
    last_error: str | None = None
    structured_attempts = 0 if plain_json_only else max_attempts
    for attempt in range(1, structured_attempts + 1):
        try:
            response = call_openai_responses(
                api_key=api_key,
                model=model,
                item=item,
                timeout=timeout,
                structured_output=True,
                reasoning_effort=reasoning_effort,
            )
            raw_text = extract_output_text(response)
            scores = parse_scores(raw_text)
            final_score = sum(scores.values()) / len(scores)
            return {
                "eval_id": item.eval_id,
                "task": item.task,
                "task_description": item.task_description,
                "condition": item.condition,
                "condition_label": item.condition_label,
                "source_file": item.source_file,
                "source_row_index": item.source_row_index,
                "agent_index": item.agent_index,
                "subject_id": item.subject_id,
                "agent_name": item.agent_name,
                "response_text": item.response_text,
                **scores,
                "final_score": final_score,
                "evaluator_model": model,
                "eval_prompt_version": "torrance_four_dimension_v1",
                "raw_evaluator_json": raw_text,
                "api_response_id": response.get("id"),
                "parse_status": "ok",
                "structured_output_mode": "json_schema",
            }
        except ApiError as exc:
            last_error = str(exc)
            if exc.status not in {408, 409, 429, 500, 502, 503, 504}:
                raise
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < max_attempts:
            time.sleep(min(2**attempt, 20))

    # Some GPT-5 calls have returned response objects without output_text when
    # strict schema mode is enabled. Keep the same rubric/model, but remove the
    # API-level schema wrapper for a final small retry window.
    plain_attempts = max_attempts if plain_json_only else 4
    for attempt in range(1, plain_attempts + 1):
        try:
            response = call_openai_responses(
                api_key=api_key,
                model=model,
                item=item,
                timeout=timeout,
                structured_output=False,
                reasoning_effort=reasoning_effort,
            )
            raw_text = extract_output_text(response)
            scores = parse_scores(raw_text)
            final_score = sum(scores.values()) / len(scores)
            return {
                "eval_id": item.eval_id,
                "task": item.task,
                "task_description": item.task_description,
                "condition": item.condition,
                "condition_label": item.condition_label,
                "source_file": item.source_file,
                "source_row_index": item.source_row_index,
                "agent_index": item.agent_index,
                "subject_id": item.subject_id,
                "agent_name": item.agent_name,
                "response_text": item.response_text,
                **scores,
                "final_score": final_score,
                "evaluator_model": model,
                "eval_prompt_version": "torrance_four_dimension_v1",
                "raw_evaluator_json": raw_text,
                "api_response_id": response.get("id"),
                "parse_status": "ok",
                "structured_output_mode": "plain_json_fallback",
            }
        except ApiError as exc:
            last_error = str(exc)
            if exc.status not in {408, 409, 429, 500, 502, 503, 504}:
                raise
        except (json.JSONDecodeError, ValueError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"

        if attempt < plain_attempts:
            time.sleep(min(2**attempt, 20))

    raise RuntimeError(
        f"Failed {item.eval_id} after {structured_attempts} structured attempts "
        f"and {plain_attempts} plain-JSON attempts: {last_error}"
    )


def choose_model(
    *,
    api_key: str,
    requested_model: str,
    fallback_models: list[str],
    timeout: int,
) -> tuple[str, list[dict[str, Any]]]:
    """Try the requested model and fallbacks with a tiny structured-output call."""
    probe = EvalItem(
        eval_id="model_preflight",
        task="model_preflight",
        task_description="List one creative use for a brick.",
        condition="preflight",
        condition_label="Preflight",
        source_file="",
        source_row_index=0,
        agent_index=None,
        subject_id=None,
        agent_name=None,
        response_text="Use a brick as a simple doorstop.",
    )
    attempts: list[dict[str, Any]] = []
    for model in [requested_model, *fallback_models]:
        try:
            response = call_openai_responses(
                api_key=api_key,
                model=model,
                item=probe,
                timeout=timeout,
            )
            raw_text = extract_output_text(response)
            parse_scores(raw_text)
            attempts.append({"model": model, "status": "ok"})
            return model, attempts
        except Exception as exc:  # noqa: BLE001 - preserve model fallback details
            attempts.append(
                {
                    "model": model,
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc)[:1000],
                }
            )

    raise RuntimeError(f"No candidate evaluator model worked: {attempts}")


def load_completed(jsonl_path: Path) -> dict[str, dict[str, Any]]:
    """Load already completed records, if this run is being resumed."""
    completed: dict[str, dict[str, Any]] = {}
    if not jsonl_path.exists():
        return completed

    with jsonl_path.open() as handle:
        for line in handle:
            if not line.strip():
                continue
            record = json.loads(line)
            if record.get("parse_status") == "ok":
                completed[str(record["eval_id"])] = record
    return completed


def write_outputs(
    *,
    records: list[dict[str, Any]],
    output_dir: Path,
) -> tuple[Path, Path, Path, list[Path]]:
    """Write CSV, JSONL, summary, and plots."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "torrance_gpt_evals.jsonl"
    csv_path = output_dir / "torrance_gpt_evals.csv"
    summary_path = output_dir / "torrance_eval_summary.csv"

    records = sorted(records, key=lambda row: (row["condition"], row["task"], row["source_row_index"]))
    with jsonl_path.open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    pd.DataFrame(records).to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)

    score_columns = [*SCORE_KEYS, "final_score"]
    df = pd.DataFrame(records)
    grouped_rows: list[dict[str, Any]] = []
    for (task, condition), group in df.groupby(["task", "condition"], sort=False):
        summary_row: dict[str, Any] = {
            "task": task,
            "condition": condition,
            "condition_label": CONDITIONS[condition],
            "n": int(len(group)),
        }
        for column in score_columns:
            summary_row[f"{column}_mean"] = float(group[column].mean())
            summary_row[f"{column}_std"] = float(group[column].std(ddof=0))
        grouped_rows.append(summary_row)
    summary_df = pd.DataFrame(grouped_rows)
    summary_df.to_csv(summary_path, index=False)

    plot_paths = make_plots(df=df, summary_df=summary_df, output_dir=output_dir)
    return csv_path, jsonl_path, summary_path, plot_paths


def make_plots(df: pd.DataFrame, summary_df: pd.DataFrame, output_dir: Path) -> list[Path]:
    """Create final-score and dimension diagnostic plots."""
    plot_paths: list[Path] = []
    condition_order = list(CONDITIONS.keys())
    labels = [CONDITIONS[key] for key in condition_order]
    colors = [CONDITION_COLORS[key] for key in condition_order]

    for task, title in TASK_TITLES.items():
        task_summary = (
            summary_df[summary_df["task"] == task]
            .set_index("condition")
            .loc[condition_order]
        )
        means = task_summary["final_score_mean"].to_list()
        stds = task_summary["final_score_std"].to_list()

        fig, ax = plt.subplots(figsize=(12, 7))
        bars = ax.bar(
            labels,
            means,
            color=colors,
            alpha=0.85,
            edgecolor="black",
            yerr=stds,
            capsize=5,
        )
        ax.set_ylabel("Creativity Score (1-10)", fontsize=12, fontweight="bold")
        ax.set_title(f"{title} - Torrance GPT Eval", fontsize=14, fontweight="bold")
        ax.set_ylim(0, 10)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        for bar, mean, std in zip(bars, means, stds):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                min(mean + std + 0.3, 9.75),
                f"{mean:.2f}±{std:.2f}",
                ha="center",
                va="bottom",
                fontweight="bold",
                fontsize=10,
            )
        fig.tight_layout()
        plot_path = output_dir / f"torrance_final_score_{task}.png"
        fig.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        plot_paths.append(plot_path)

        dim_means = task_summary[[f"{key}_mean" for key in SCORE_KEYS]]
        fig, ax = plt.subplots(figsize=(13, 7))
        x_positions = range(len(condition_order))
        width = 0.18
        offsets = [-1.5 * width, -0.5 * width, 0.5 * width, 1.5 * width]
        dim_colors = ["#4c78a8", "#f58518", "#54a24b", "#b279a2"]
        for offset, key, color in zip(offsets, SCORE_KEYS, dim_colors):
            values = dim_means[f"{key}_mean"].to_list()
            ax.bar(
                [x + offset for x in x_positions],
                values,
                width=width,
                label=key.title(),
                color=color,
                alpha=0.85,
                edgecolor="black",
                linewidth=0.5,
            )
        ax.set_xticks(list(x_positions), labels)
        ax.set_ylabel("Mean Score (1-10)", fontsize=12, fontweight="bold")
        ax.set_title(f"{title} - Torrance Dimensions", fontsize=14, fontweight="bold")
        ax.set_ylim(0, 10)
        ax.grid(axis="y", alpha=0.3, linestyle="--")
        ax.legend(frameon=False, ncols=4, loc="upper center", bbox_to_anchor=(0.5, 1.02))
        fig.tight_layout()
        plot_path = output_dir / f"torrance_dimensions_{task}.png"
        fig.savefig(plot_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
        plot_paths.append(plot_path)

    return plot_paths


def validate_records(records: list[dict[str, Any]]) -> None:
    """Validate completion criteria for the full rerun."""
    if len(records) != 320:
        raise AssertionError(f"Expected 320 judged rows, got {len(records)}")

    ids = [record["eval_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise AssertionError("Duplicate eval_id values found")

    for record in records:
        scores = [record[key] for key in SCORE_KEYS]
        if not all(isinstance(score, int) and 1 <= score <= 10 for score in scores):
            raise AssertionError(f"Invalid scores for {record['eval_id']}: {scores}")
        expected_final = sum(scores) / 4
        if abs(record["final_score"] - expected_final) > 1e-12:
            raise AssertionError(f"Bad final_score for {record['eval_id']}")


def validate_outputs(output_dir: Path, plot_paths: list[Path], summary_path: Path) -> None:
    """Validate saved output files."""
    summary_df = pd.read_csv(summary_path)
    if len(summary_df) != 8:
        raise AssertionError(f"Expected 8 summary rows, got {len(summary_df)}")

    for path in plot_paths:
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"Missing or empty plot: {path}")

    for filename in [
        "torrance_gpt_evals.csv",
        "torrance_gpt_evals.jsonl",
        "torrance_eval_summary.csv",
        "torrance_eval_metadata.json",
    ]:
        path = output_dir / filename
        if not path.exists() or path.stat().st_size == 0:
            raise AssertionError(f"Missing or empty output file: {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--notebook-copy", type=Path, default=REPO_ROOT / "creativity_torrance_test_gpt55_torrance_eval.ipynb")
    parser.add_argument("--requested-model", default="gpt-5.5")
    parser.add_argument("--fallback-models", default="gpt-5.2,gpt-5")
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--max-attempts", type=int, default=4)
    parser.add_argument("--plain-json-only", action="store_true")
    parser.add_argument("--reasoning-effort", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    load_env_file(REPO_ROOT / ".env")
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in the environment or .env")

    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    input_files = [source_dir / f"{condition}.csv" for condition in CONDITIONS]
    input_hashes_before = {path.name: sha256_file(path) for path in input_files}

    fallback_models = [
        model.strip() for model in args.fallback_models.split(",") if model.strip()
    ]
    selected_model, model_attempts = choose_model(
        api_key=api_key,
        requested_model=args.requested_model,
        fallback_models=fallback_models,
        timeout=args.timeout,
    )
    print(f"Using evaluator model: {selected_model}", flush=True)

    jsonl_path = output_dir / "torrance_gpt_evals.jsonl"
    if args.overwrite and jsonl_path.exists():
        jsonl_path.unlink()

    items = read_eval_items(source_dir)
    if args.limit is not None:
        items = items[: args.limit]

    completed = load_completed(jsonl_path)
    pending = [item for item in items if item.eval_id not in completed]
    print(
        f"Loaded {len(items)} eval items; {len(completed)} already complete; "
        f"{len(pending)} pending.",
        flush=True,
    )

    records_by_id = dict(completed)
    write_lock = threading.Lock()

    def run_and_persist(item: EvalItem) -> dict[str, Any]:
        record = evaluate_item(
            item,
            api_key=api_key,
            model=selected_model,
            timeout=args.timeout,
            max_attempts=args.max_attempts,
            plain_json_only=args.plain_json_only,
            reasoning_effort=args.reasoning_effort,
        )
        with write_lock:
            with jsonl_path.open("a") as handle:
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record

    if pending:
        completed_count = len(completed)
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as executor:
            future_to_item = {
                executor.submit(run_and_persist, item): item for item in pending
            }
            for future in concurrent.futures.as_completed(future_to_item):
                item = future_to_item[future]
                record = future.result()
                records_by_id[item.eval_id] = record
                completed_count += 1
                if completed_count % 10 == 0 or completed_count == len(items):
                    print(f"Completed {completed_count}/{len(items)}", flush=True)

    records = [records_by_id[item.eval_id] for item in items]
    if args.limit is None:
        validate_records(records)

    csv_path, jsonl_path, summary_path, plot_paths = write_outputs(
        records=records,
        output_dir=output_dir,
    )

    input_hashes_after = {path.name: sha256_file(path) for path in input_files}
    source_unchanged = input_hashes_before == input_hashes_after
    if not source_unchanged:
        raise AssertionError("Source input CSV hashes changed during evaluation")

    metadata = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_dir": release_path(source_dir),
        "output_dir": release_path(output_dir),
        "notebook_copy": release_path(args.notebook_copy),
        "requested_model": args.requested_model,
        "fallback_models": fallback_models,
        "evaluator_model": selected_model,
        "model_attempts": model_attempts,
        "eval_prompt_version": "torrance_four_dimension_v1",
        "torrance_system_prompt": TORRANCE_SYSTEM_PROMPT,
        "score_keys": list(SCORE_KEYS),
        "final_score_formula": "mean(fluency, flexibility, originality, elaboration)",
        "n_eval_rows": len(records),
        "n_summary_rows": int(len(pd.read_csv(summary_path))),
        "source_input_sha256": input_hashes_after,
        "source_inputs_unchanged": source_unchanged,
        "outputs": {
            "csv": release_path(csv_path),
            "jsonl": release_path(jsonl_path),
            "summary_csv": release_path(summary_path),
            "plots": [release_path(path) for path in plot_paths],
        },
        "openai_api": {
            "endpoint": "https://api.openai.com/v1/responses",
            "response_format": "text.format.json_schema",
        },
    }
    metadata_path = output_dir / "torrance_eval_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))

    if args.limit is None:
        validate_outputs(output_dir, plot_paths, summary_path)

    print("Wrote outputs:", flush=True)
    for path in [csv_path, jsonl_path, summary_path, metadata_path, *plot_paths]:
        print(f"  {path}", flush=True)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # noqa: BLE001 - show concise CLI failure
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
