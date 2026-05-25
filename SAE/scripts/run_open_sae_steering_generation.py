#!/usr/bin/env python3
"""Generate social-simulation responses with live Goodfire Open-SAE steering.

The default smoke mode validates selected prompts and steering features without
loading the model. Passing ``--execute`` runs a GPU generation job that patches
the Llama layer-50 residual stream with Goodfire's open Hugging Face SAE.

This is a transparent open-source steering implementation. It is not an exact
replica of the deprecated hosted Goodfire controller service; historical
Goodfire controller nudges are provenance for archived runs, while this script
uses explicit SAE activation edit modes documented in the metadata.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import platform
import random
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from run_open_sae_feature_inspection import (
    DEFAULT_HOOK,
    DEFAULT_MODEL_ID,
    DEFAULT_NEURONPEDIA_MODEL,
    DEFAULT_NEURONPEDIA_SOURCE,
    DEFAULT_SAE_REPO,
    default_source_dir,
    infer_run_dataset_kind,
    load_creativity_units,
    load_model_and_sae,
    load_run_dir_units,
    load_safe_risky_units,
    load_trust_units,
    load_ultimatum_units,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
KNOWN_DATASET_KINDS = {"creativity", "safe_risky", "ultimatum", "trust"}
DEFAULT_STEERING_FEATURES = [13142, 20117, 4992]
DEFAULT_STEERING_STRENGTHS = [0.3, 0.3, 0.3]
STEERING_MODES = {"clamp_min", "add_delta", "set", "nudge"}
STRENGTH_CALIBRATIONS = {
    "raw",
    "fraction_of_neuronpedia_max",
    "fraction_of_neuronpedia_default",
}


def parse_feature_indices(value: str | list[int]) -> list[int]:
    if isinstance(value, list):
        return value
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("expected at least one integer")
    try:
        return [int(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_float_list(value: str | list[float]) -> list[float]:
    if isinstance(value, list):
        return value
    items = [item.strip() for item in value.split(",") if item.strip()]
    if not items:
        raise argparse.ArgumentTypeError("expected at least one float")
    try:
        return [float(item) for item in items]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_optional_set(value: str | None) -> set[str] | None:
    if not value:
        return None
    return {part.strip() for part in value.split(",") if part.strip()}


def parse_optional_int_set(value: str | None) -> set[int] | None:
    if not value:
        return None
    return {int(part.strip()) for part in value.split(",") if part.strip()}


def relative_path(path: Path | str) -> str:
    path = Path(path)
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    return str(value)


def effective_dataset_kind(args: argparse.Namespace) -> str:
    if args.dataset_kind:
        return args.dataset_kind
    if args.run_dir:
        return infer_run_dataset_kind(args.run_dir)
    if args.prompt_file:
        return "custom"
    raise ValueError("Pass --dataset-kind, --run-dir, or --prompt-file")


def source_label(args: argparse.Namespace, dataset_kind: str) -> str:
    if args.run_dir:
        return relative_path(args.run_dir)
    if args.prompt_file:
        return relative_path(args.prompt_file)
    if args.source_dir:
        return relative_path(args.source_dir)
    if dataset_kind in KNOWN_DATASET_KINDS:
        return relative_path(default_source_dir(dataset_kind))
    return ""


def load_units(args: argparse.Namespace) -> list[Any]:
    dataset_kind = effective_dataset_kind(args)
    if args.run_dir:
        args.dataset_kind = dataset_kind
        units, _ = load_run_dir_units(args)
        return units

    if dataset_kind not in KNOWN_DATASET_KINDS:
        raise ValueError(
            f"Dataset kind {dataset_kind!r} is only valid with --run-dir or --prompt-file"
        )

    source_dir = args.source_dir or default_source_dir(dataset_kind)
    conditions = parse_optional_set(args.conditions)
    rewards = parse_optional_int_set(args.rewards)

    if dataset_kind == "creativity":
        units, _ = load_creativity_units(
            source_dir,
            strict=True,
            conditions=conditions,
            limit_units=None,
        )
    elif dataset_kind == "safe_risky":
        units, _ = load_safe_risky_units(
            source_dir,
            strict=True,
            conditions=conditions,
            rewards=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=None,
        )
    elif dataset_kind == "ultimatum":
        units, _ = load_ultimatum_units(
            source_dir,
            strict=True,
            conditions=conditions,
            offers=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=None,
        )
    elif dataset_kind == "trust":
        units, _ = load_trust_units(
            source_dir,
            strict=True,
            conditions=conditions,
            sent_amounts=rewards,
            max_agents_per_cell=args.max_agents_per_cell,
            limit_units=None,
        )
    else:
        raise ValueError(f"Unknown dataset kind: {dataset_kind}")

    if not units:
        raise ValueError("No source units selected for steering")
    return units


def limit_records_by_condition(
    records: list[dict[str, Any]], limit: int | None
) -> list[dict[str, Any]]:
    """Select a deterministic condition-balanced prefix for smoke jobs."""
    if limit is None or len(records) <= limit:
        return records

    conditions = sorted({safe_text(record.get("condition")) for record in records})
    if len(conditions) <= 1:
        return records[:limit]

    buckets: dict[str, list[dict[str, Any]]] = {condition: [] for condition in conditions}
    for record in records:
        buckets[safe_text(record.get("condition"))].append(record)

    selected: list[dict[str, Any]] = []
    while len(selected) < limit and any(buckets.values()):
        for condition in conditions:
            bucket = buckets[condition]
            if bucket:
                selected.append(bucket.pop(0))
                if len(selected) >= limit:
                    break
    return selected


def prompt_record_from_unit(unit: Any) -> dict[str, Any]:
    return {
        "unit_id": unit.unit_id,
        "game_id": unit.dataset_kind,
        "condition": unit.condition,
        "task": unit.task,
        "scenario_id": "",
        "reward": "" if unit.reward is None else unit.reward,
        "source_file": unit.source_file,
        "source_row_index": unit.source_row_index,
        "response_index": unit.response_index,
        "agent_index": unit.agent_index,
        "agent_subject_id": unit.agent_subject_id,
        "system_prompt": unit.system_prompt,
        "user_prompt": unit.user_prompt,
        "source_response_text": unit.response_text,
    }


def load_prompt_file(path: Path, limit: int | None, dataset_kind: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            record = json.loads(text)
            if "user_prompt" not in record:
                raise ValueError(f"{relative_path(path)}:{line_number} missing user_prompt")
            records.append(
                {
                    "unit_id": record.get("unit_id", f"prompt_file:{line_number}"),
                    "game_id": record.get("game_id", dataset_kind),
                    "condition": record.get("condition", ""),
                    "task": record.get("task", ""),
                    "scenario_id": record.get("scenario_id", ""),
                    "reward": record.get("reward", ""),
                    "source_file": relative_path(path),
                    "source_row_index": record.get("source_row_index", line_number - 1),
                    "response_index": record.get("response_index", line_number),
                    "agent_index": record.get("agent_index", ""),
                    "agent_subject_id": record.get("agent_subject_id", ""),
                    "system_prompt": record.get("system_prompt", ""),
                    "user_prompt": record["user_prompt"],
                    "source_response_text": record.get("response_text", ""),
                }
            )
            if limit is not None and len(records) >= limit:
                break
    if not records:
        raise ValueError(f"No prompt records found in {relative_path(path)}")
    return records


def selected_prompt_records(args: argparse.Namespace) -> list[dict[str, Any]]:
    dataset_kind = effective_dataset_kind(args)
    if args.prompt_file:
        records = load_prompt_file(args.prompt_file, args.limit_units, dataset_kind)
    else:
        records = [prompt_record_from_unit(unit) for unit in load_units(args)]
        records = limit_records_by_condition(records, args.limit_units)
    if args.expected_units is not None and len(records) != args.expected_units:
        raise ValueError(f"Found {len(records)} prompt units, expected {args.expected_units}")
    return records


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        seen: set[str] = set()
        for row in rows:
            for key in row:
                if key not in seen:
                    fieldnames.append(key)
                    seen.add(key)
    cleaned_rows = [
        {
            key: "\n".join(value.rstrip() for value in item.splitlines())
            if isinstance(item, str)
            else item
            for key, item in row.items()
        }
        for row in rows
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=fieldnames,
            extrasaction="ignore",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(cleaned_rows)


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def validate_feature_strengths(feature_indices: list[int], strengths: list[float]) -> None:
    if len(feature_indices) != len(strengths):
        raise ValueError("--feature-indices and --strengths must have the same length")
    if len(set(feature_indices)) != len(feature_indices):
        raise ValueError("--feature-indices contains duplicates")
    for feature_index in feature_indices:
        if feature_index < 0:
            raise ValueError(f"Feature index must be nonnegative: {feature_index}")


def neuronpedia_api_url(model: str, source: str, feature_index: int) -> str:
    return f"https://www.neuronpedia.org/api/feature/{model}/{source}/{feature_index}"


def fetch_neuronpedia_metadata(
    feature_indices: list[int],
    *,
    neuronpedia_model: str,
    neuronpedia_source: str,
    timeout: float,
    skip: bool,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for feature_index in feature_indices:
        url = neuronpedia_api_url(neuronpedia_model, neuronpedia_source, feature_index)
        row: dict[str, Any] = {
            "feature_index": feature_index,
            "neuronpedia_model": neuronpedia_model,
            "neuronpedia_source": neuronpedia_source,
            "neuronpedia_api_url": url,
            "feature_label": "",
            "maxActApprox": "",
            "vectorDefaultSteerStrength": "",
            "metadata_status": "skipped" if skip else "missing",
        }
        if skip:
            rows.append(row)
            continue
        try:
            with urllib.request.urlopen(url, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            row["metadata_status"] = f"error:{type(exc).__name__}"
            rows.append(row)
            continue

        explanations = payload.get("explanations") or []
        if explanations and isinstance(explanations[0], dict):
            row["feature_label"] = safe_text(explanations[0].get("description"))
        if not row["feature_label"]:
            row["feature_label"] = safe_text(payload.get("vectorLabel"))
        row["maxActApprox"] = payload.get("maxActApprox", "")
        row["vectorDefaultSteerStrength"] = payload.get("vectorDefaultSteerStrength", "")
        row["metadata_status"] = "ok"
        rows.append(row)
    return rows


def calibrated_strengths(
    raw_strengths: list[float],
    feature_metadata: list[dict[str, Any]],
    calibration: str,
) -> list[float]:
    if calibration == "raw":
        return raw_strengths
    calibrated: list[float] = []
    for raw_strength, metadata in zip(raw_strengths, feature_metadata, strict=True):
        key = (
            "maxActApprox"
            if calibration == "fraction_of_neuronpedia_max"
            else "vectorDefaultSteerStrength"
        )
        try:
            reference = float(metadata.get(key))
        except (TypeError, ValueError):
            raise ValueError(
                f"Cannot use {calibration}; missing numeric {key} for "
                f"feature {metadata.get('feature_index')}"
            ) from None
        calibrated.append(raw_strength * reference)
    return calibrated


def write_smoke_plan(args: argparse.Namespace) -> dict[str, Any]:
    dataset_kind = effective_dataset_kind(args)
    feature_indices = parse_feature_indices(args.feature_indices)
    strengths = parse_float_list(args.strengths)
    validate_feature_strengths(feature_indices, strengths)

    prompts = selected_prompt_records(args)
    feature_metadata = fetch_neuronpedia_metadata(
        feature_indices,
        neuronpedia_model=args.neuronpedia_model,
        neuronpedia_source=args.neuronpedia_source,
        timeout=args.neuronpedia_timeout,
        skip=args.skip_neuronpedia_metadata,
    )
    actual_strengths = calibrated_strengths(strengths, feature_metadata, args.strength_calibration)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    units_path = args.output_dir / "open_sae_steering_smoke_units.csv"
    plan_path = args.output_dir / "open_sae_steering_smoke_plan.json"
    metadata_path = args.output_dir / "open_sae_steering_feature_metadata.csv"
    write_csv(units_path, prompts)
    write_csv(metadata_path, feature_metadata)

    plan = {
        "status": "smoke_plan_only",
        "dataset_kind": dataset_kind,
        "selected_prompt_units": len(prompts),
        "prompt_units_csv": relative_path(units_path),
        "feature_metadata_csv": relative_path(metadata_path),
        "model_id": args.model_id,
        "sae_repo": args.sae_repo,
        "hook": args.hook,
        "steering_mode": args.steering_mode,
        "patch_scope": args.patch_scope,
        "feature_indices": feature_indices,
        "input_strengths": strengths,
        "strength_calibration": args.strength_calibration,
        "actual_strengths": actual_strengths,
        "source": source_label(args, dataset_kind),
        "conditions": args.conditions,
        "rewards": args.rewards,
        "implementation_status": (
            "Smoke mode validates selected prompts and feature metadata. "
            "Pass --execute on a GPU machine to generate steered responses."
        ),
    }
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
    return plan


def normalize_steering_mode(mode: str) -> str:
    if mode == "nudge":
        return "add_delta"
    return mode


def empty_trace(feature_indices: list[int]) -> dict[str, Any]:
    return {
        "hook_calls": 0,
        "edited_token_positions": 0,
        "features": {
            str(feature_index): {
                "feature_index": feature_index,
                "calls": 0,
                "changed_positions": 0,
                "before_max": 0.0,
                "after_max": 0.0,
                "before_sum": 0.0,
                "after_sum": 0.0,
            }
            for feature_index in feature_indices
        },
    }


def update_trace(trace: dict[str, Any], edit_rows: list[dict[str, Any]], token_count: int) -> None:
    trace["hook_calls"] += 1
    trace["edited_token_positions"] += token_count
    for edit in edit_rows:
        feature_trace = trace["features"][str(edit["feature_index"])]
        feature_trace["calls"] += 1
        feature_trace["changed_positions"] += int(edit["changed_positions"])
        feature_trace["before_max"] = max(feature_trace["before_max"], float(edit["before_max"]))
        feature_trace["after_max"] = max(feature_trace["after_max"], float(edit["after_max"]))
        feature_trace["before_sum"] += float(edit["before_mean"])
        feature_trace["after_sum"] += float(edit["after_mean"])


def finalize_trace(trace: dict[str, Any]) -> dict[str, Any]:
    features: list[dict[str, Any]] = []
    for feature_trace in trace["features"].values():
        calls = max(int(feature_trace["calls"]), 1)
        features.append(
            {
                "feature_index": int(feature_trace["feature_index"]),
                "calls": int(feature_trace["calls"]),
                "changed_positions": int(feature_trace["changed_positions"]),
                "before_max": float(feature_trace["before_max"]),
                "after_max": float(feature_trace["after_max"]),
                "before_mean_across_calls": float(feature_trace["before_sum"]) / calls,
                "after_mean_across_calls": float(feature_trace["after_sum"]) / calls,
            }
        )
    return {
        "hook_calls": int(trace["hook_calls"]),
        "edited_token_positions": int(trace["edited_token_positions"]),
        "features": features,
    }


def apply_sae_feature_edits(
    *,
    torch_module: Any,
    sae: Any,
    hidden_slice: Any,
    feature_indices: list[int],
    strengths: list[float],
    steering_mode: str,
) -> tuple[Any, list[dict[str, Any]]]:
    """Apply SAE feature edits and preserve reconstruction error."""

    sae_device = next(sae.parameters()).device
    original_device = hidden_slice.device
    original_dtype = hidden_slice.dtype
    hidden_for_sae = hidden_slice.to(device=sae_device, dtype=sae.dtype)

    features = sae.encode(hidden_for_sae)
    reconstruction = sae.decode(features)
    reconstruction_error = hidden_for_sae - reconstruction
    mode = normalize_steering_mode(steering_mode)
    edit_rows: list[dict[str, Any]] = []

    for feature_index, strength in zip(feature_indices, strengths, strict=True):
        if feature_index >= int(sae.d_hidden):
            raise ValueError(
                f"Feature index {feature_index} exceeds SAE width {int(sae.d_hidden)}"
            )
        current = features[..., feature_index]
        before = current.detach().float()
        if mode == "clamp_min":
            target = torch_module.tensor(strength, device=current.device, dtype=current.dtype)
            updated = torch_module.maximum(current, target)
        elif mode == "add_delta":
            updated = torch_module.clamp(current + strength, min=0)
        elif mode == "set":
            updated = torch_module.full_like(current, fill_value=strength)
        else:
            raise ValueError(f"Unknown steering mode: {steering_mode}")

        features[..., feature_index] = updated
        after = updated.detach().float()
        edit_rows.append(
            {
                "feature_index": feature_index,
                "strength": strength,
                "mode": mode,
                "before_max": float(before.max().item()),
                "after_max": float(after.max().item()),
                "before_mean": float(before.mean().item()),
                "after_mean": float(after.mean().item()),
                "changed_positions": int((after != before).sum().item()),
            }
        )

    steered = sae.decode(features) + reconstruction_error
    return steered.to(device=original_device, dtype=original_dtype), edit_rows


def build_steering_hook(
    *,
    torch_module: Any,
    sae: Any,
    feature_indices: list[int],
    strengths: list[float],
    steering_mode: str,
    patch_scope: str,
    trace: dict[str, Any],
):
    def hook(_module: Any, _inputs: Any, output: Any) -> Any:
        hidden = output[0] if isinstance(output, tuple) else output
        if hidden.ndim != 3:
            raise ValueError(f"Expected hidden shape [batch, seq, d_model], got {tuple(hidden.shape)}")

        if patch_scope == "all_tokens":
            hidden_slice = hidden
            target_slice = slice(None)
        elif patch_scope == "last_token":
            hidden_slice = hidden[:, -1:, :]
            target_slice = slice(-1, None)
        else:
            raise ValueError(f"Unknown patch scope: {patch_scope}")

        with torch_module.no_grad():
            steered_slice, edit_rows = apply_sae_feature_edits(
                torch_module=torch_module,
                sae=sae,
                hidden_slice=hidden_slice,
                feature_indices=feature_indices,
                strengths=strengths,
                steering_mode=steering_mode,
            )
        new_hidden = hidden.clone()
        new_hidden[:, target_slice, :] = steered_slice
        update_trace(trace, edit_rows, int(hidden_slice.shape[0] * hidden_slice.shape[1]))

        if isinstance(output, tuple):
            return (new_hidden, *output[1:])
        return new_hidden

    return hook


def set_seed(seed: int | None) -> None:
    if seed is None:
        return
    random.seed(seed)
    try:
        import numpy as np

        np.random.seed(seed)
    except ImportError:
        pass


def chat_input_ids(tokenizer: Any, torch_module: Any, record: dict[str, Any]) -> Any:
    messages: list[dict[str, str]] = []
    system_prompt = safe_text(record.get("system_prompt"))
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": safe_text(record.get("user_prompt"))})
    try:
        return tokenizer.apply_chat_template(
            messages,
            return_tensors="pt",
            add_generation_prompt=True,
        )
    except Exception:
        transcript = "\n\n".join(
            f"{message['role'].upper()}:\n{message['content']}" for message in messages
        )
        return tokenizer(transcript, return_tensors="pt", add_special_tokens=True)["input_ids"]


def generation_kwargs(args: argparse.Namespace, tokenizer: Any) -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "max_new_tokens": args.max_new_tokens,
        "do_sample": args.do_sample,
        "pad_token_id": tokenizer.pad_token_id,
        "eos_token_id": tokenizer.eos_token_id,
    }
    if args.do_sample:
        kwargs["temperature"] = args.temperature
        kwargs["top_p"] = args.top_p
    return kwargs


def generate_one_response(
    *,
    args: argparse.Namespace,
    torch_module: Any,
    tokenizer: Any,
    model: Any,
    hook_module: Any,
    sae: Any,
    record: dict[str, Any],
    feature_indices: list[int],
    strengths: list[float],
) -> tuple[str, dict[str, Any]]:
    trace = empty_trace(feature_indices)
    input_ids = chat_input_ids(tokenizer, torch_module, record)
    input_length = int(input_ids.shape[-1])
    model_device = next(model.parameters()).device
    input_ids = input_ids.to(model_device)
    attention_mask = torch_module.ones_like(input_ids, device=model_device)

    handle = hook_module.register_forward_hook(
        build_steering_hook(
            torch_module=torch_module,
            sae=sae,
            feature_indices=feature_indices,
            strengths=strengths,
            steering_mode=args.steering_mode,
            patch_scope=args.patch_scope,
            trace=trace,
        )
    )
    try:
        with torch_module.inference_mode():
            sequences = model.generate(
                input_ids=input_ids,
                attention_mask=attention_mask,
                **generation_kwargs(args, tokenizer),
            )
    finally:
        handle.remove()

    new_tokens = sequences[0, input_length:]
    response_text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    trace_payload = finalize_trace(trace)
    trace_payload.update(
        {
            "unit_id": record["unit_id"],
            "input_tokens": input_length,
            "generated_tokens": int(new_tokens.numel()),
            "generation_status": "ok" if response_text else "empty_response",
        }
    )
    return response_text, trace_payload


def first_nonempty_line(text: str) -> str:
    """Return the first substantive generated line after light answer-prefix cleanup."""

    for line in safe_text(text).splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def strip_answer_prefix(text: str) -> str:
    lowered = text.lower()
    for prefix in ("answer:", "choice:", "decision:", "return:", "response:"):
        if lowered.startswith(prefix):
            return text[len(prefix) :].strip()
    return text.strip()


def earliest_label_match(text: str, labels: list[tuple[str, list[str]]]) -> str | None:
    lowered = safe_text(text).lower()
    matches: list[tuple[int, str]] = []
    for normalized, needles in labels:
        for needle in needles:
            index = lowered.find(needle)
            if index >= 0:
                matches.append((index, normalized))
    if not matches:
        return None
    matches.sort(key=lambda item: item[0])
    return matches[0][1]


def split_generated_answer(dataset_kind: str, response_text: str) -> tuple[str, str, str]:
    """Extract the behavior answer column from free-form generated text.

    Open-SAE steering uses normal generation, not EDSL's multiple-choice parser.
    The full text remains in ``response_text`` for SAE inspection, while these
    normalized answer/comment fields keep downstream behavior plots honest.
    """

    text = safe_text(response_text).strip()
    first_line = strip_answer_prefix(first_nonempty_line(text))

    if dataset_kind == "safe_risky":
        label = earliest_label_match(
            first_line,
            [
                ("Risky Option", ["risky option", "risky"]),
                ("Safe Option", ["safe option", "safe"]),
            ],
        ) or earliest_label_match(
            text[:500],
            [
                ("Risky Option", ["risky option", "choose risky", "choose the risky"]),
                ("Safe Option", ["safe option", "choose safe", "choose the safe"]),
            ],
        )
        if label:
            return label, text, "parsed_safe_risky_label"

    if dataset_kind == "ultimatum":
        label = earliest_label_match(
            first_line,
            [("Accept", ["accept"]), ("Reject", ["reject"])],
        ) or earliest_label_match(
            text[:500],
            [
                ("Accept", ["i accept", "would accept", "choose accept"]),
                ("Reject", ["i reject", "would reject", "choose reject"]),
            ],
        )
        if label:
            return label, text, "parsed_ultimatum_label"

    if dataset_kind == "trust":
        import re

        match = re.search(r"-?\d+(?:\.\d+)?", first_line or text)
        if match:
            return match.group(0), text, "parsed_trust_numeric"

    return text, "", "unparsed_full_response_as_answer"


def response_unit_row(
    record: dict[str, Any],
    *,
    dataset_kind: str,
    response_text: str,
    output_dir: Path,
    model_id: str,
) -> dict[str, Any]:
    unit_id = safe_text(record.get("unit_id"))
    answer_text, comment_text, parse_status = split_generated_answer(dataset_kind, response_text)
    return {
        "unit_id": f"open_sae_steered:{unit_id}",
        "game_id": safe_text(record.get("game_id")) or dataset_kind,
        "condition": safe_text(record.get("condition")),
        "source_condition": safe_text(record.get("source_condition")),
        "task": safe_text(record.get("task")),
        "scenario_id": safe_text(record.get("scenario_id")),
        "reward": safe_text(record.get("reward")),
        "source_file": safe_text(record.get("source_file")),
        "source_row_index": safe_text(record.get("source_row_index")),
        "response_index": safe_text(record.get("response_index")),
        "agent_index": safe_text(record.get("agent_index")),
        "agent_subject_id": safe_text(record.get("agent_subject_id")),
        "answer_text": answer_text,
        "comment_text": comment_text,
        "system_prompt": safe_text(record.get("system_prompt")),
        "user_prompt": safe_text(record.get("user_prompt")),
        "response_text": response_text,
        "source_response_text": safe_text(record.get("source_response_text")),
        "generation_model": model_id,
        "generation_output_dir": relative_path(output_dir),
        "generated_answer_parse_status": parse_status,
    }


def write_execution_outputs(
    *,
    args: argparse.Namespace,
    dataset_kind: str,
    prompt_records: list[dict[str, Any]],
    response_rows: list[dict[str, Any]],
    trace_rows: list[dict[str, Any]],
    feature_metadata: list[dict[str, Any]],
    sae_path: str,
    sae_device: str,
    actual_strengths: list[float],
) -> dict[str, Any]:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_csv(args.output_dir / "source_prompt_units.csv", prompt_records)
    write_csv(args.output_dir / "response_units.csv", response_rows)
    write_jsonl(args.output_dir / "response_units.jsonl", response_rows)
    write_jsonl(args.output_dir / "open_sae_steering_trace.jsonl", trace_rows)
    write_csv(args.output_dir / "open_sae_steering_feature_metadata.csv", feature_metadata)

    metadata = {
        "status": "open_sae_steering_generated",
        "timestamp_utc": dt.datetime.now(dt.UTC).isoformat(),
        "script_path": relative_path(Path(__file__)),
        "dataset_kind": dataset_kind,
        "source": source_label(args, dataset_kind),
        "output_dir": relative_path(args.output_dir),
        "conditions": args.conditions,
        "rewards": args.rewards,
        "selected_prompt_units": len(prompt_records),
        "generated_response_units": len(response_rows),
        "model_id": args.model_id,
        "sae_repo": args.sae_repo,
        "sae_path": sae_path,
        "sae_device": sae_device,
        "hook": args.hook,
        "steering_mode": args.steering_mode,
        "normalized_steering_mode": normalize_steering_mode(args.steering_mode),
        "patch_scope": args.patch_scope,
        "feature_indices": parse_feature_indices(args.feature_indices),
        "input_strengths": parse_float_list(args.strengths),
        "strength_calibration": args.strength_calibration,
        "actual_strengths": actual_strengths,
        "generation": {
            "max_new_tokens": args.max_new_tokens,
            "do_sample": args.do_sample,
            "temperature": args.temperature if args.do_sample else None,
            "top_p": args.top_p if args.do_sample else None,
            "seed": args.seed,
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "torch_dtype": args.torch_dtype,
            "device_map": args.device_map,
            "load_in_4bit": args.load_in_4bit,
            "load_in_8bit": args.load_in_8bit,
        },
        "caveat": (
            "This is live open-SAE activation patching with Goodfire's released SAE. "
            "It is not guaranteed to match deprecated hosted Goodfire controller "
            "nudge calibration exactly."
        ),
    }
    (args.output_dir / "open_sae_steering_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )

    manifest = {
        "run_type": "open_sae_steering_generation",
        "game_id": dataset_kind,
        "model_id": args.model_id,
        "response_units": len(response_rows),
        "response_units_csv": "response_units.csv",
        "response_units_jsonl": "response_units.jsonl",
        "steering_metadata": "open_sae_steering_metadata.json",
        "steering_trace": "open_sae_steering_trace.jsonl",
        "created_at_utc": metadata["timestamp_utc"],
    }
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2),
        encoding="utf-8",
    )
    return metadata


def execute_generation(args: argparse.Namespace) -> dict[str, Any]:
    dataset_kind = effective_dataset_kind(args)
    args.dataset_kind = dataset_kind
    feature_indices = parse_feature_indices(args.feature_indices)
    strengths = parse_float_list(args.strengths)
    validate_feature_strengths(feature_indices, strengths)
    if args.steering_mode not in STEERING_MODES:
        raise ValueError(f"--steering-mode must be one of {sorted(STEERING_MODES)}")
    if args.strength_calibration not in STRENGTH_CALIBRATIONS:
        raise ValueError(
            f"--strength-calibration must be one of {sorted(STRENGTH_CALIBRATIONS)}"
        )

    set_seed(args.seed)
    prompt_records = selected_prompt_records(args)
    feature_metadata = fetch_neuronpedia_metadata(
        feature_indices,
        neuronpedia_model=args.neuronpedia_model,
        neuronpedia_source=args.neuronpedia_source,
        timeout=args.neuronpedia_timeout,
        skip=args.skip_neuronpedia_metadata,
    )
    actual_strengths = calibrated_strengths(strengths, feature_metadata, args.strength_calibration)

    torch_module, tokenizer, model, hook_module, sae, sae_path, sae_device = load_model_and_sae(args)
    response_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for index, record in enumerate(prompt_records, start=1):
        response_text, trace = generate_one_response(
            args=args,
            torch_module=torch_module,
            tokenizer=tokenizer,
            model=model,
            hook_module=hook_module,
            sae=sae,
            record=record,
            feature_indices=feature_indices,
            strengths=actual_strengths,
        )
        response_rows.append(
            response_unit_row(
                record,
                dataset_kind=dataset_kind,
                response_text=response_text,
                output_dir=args.output_dir,
                model_id=args.model_id,
            )
        )
        trace["ordinal"] = index
        trace_rows.append(trace)
        if args.progress:
            print(
                json.dumps(
                    {
                        "status": "generated",
                        "ordinal": index,
                        "total": len(prompt_records),
                        "unit_id": record["unit_id"],
                        "generated_tokens": trace["generated_tokens"],
                    }
                ),
                flush=True,
            )

    return write_execution_outputs(
        args=args,
        dataset_kind=dataset_kind,
        prompt_records=prompt_records,
        response_rows=response_rows,
        trace_rows=trace_rows,
        feature_metadata=feature_metadata,
        sae_path=sae_path,
        sae_device=sae_device,
        actual_strengths=actual_strengths,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dataset-kind",
        default=None,
        help=(
            "Known archived dataset kind: creativity, safe_risky, ultimatum, or trust. "
            "For --run-dir, defaults to the run manifest game_id."
        ),
    )
    parser.add_argument("--run-dir", type=Path, default=None)
    parser.add_argument("--source-dir", type=Path, default=None)
    parser.add_argument("--prompt-file", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data/processed/steering_smoke_plan",
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL_ID)
    parser.add_argument("--sae-repo", default=DEFAULT_SAE_REPO)
    parser.add_argument("--hook", default=DEFAULT_HOOK)
    parser.add_argument(
        "--feature-indices",
        type=parse_feature_indices,
        default=DEFAULT_STEERING_FEATURES,
        help="Comma-separated SAE feature indices.",
    )
    parser.add_argument(
        "--strengths",
        type=parse_float_list,
        default=DEFAULT_STEERING_STRENGTHS,
        help="Comma-separated strengths aligned to --feature-indices.",
    )
    parser.add_argument(
        "--steering-mode",
        default="clamp_min",
        choices=sorted(STEERING_MODES),
        help=(
            "clamp_min follows the Goodfire model-card pattern; add_delta is "
            "a transparent approximation of hosted 'nudge' semantics."
        ),
    )
    parser.add_argument(
        "--strength-calibration",
        default="raw",
        choices=sorted(STRENGTH_CALIBRATIONS),
        help=(
            "Use raw strengths or multiply by Neuronpedia max/default steering "
            "metadata before applying edits."
        ),
    )
    parser.add_argument(
        "--patch-scope",
        default="last_token",
        choices=["last_token", "all_tokens"],
        help="Patch only the current generation position or every token in each forward pass.",
    )
    parser.add_argument("--limit-units", type=int, default=8)
    parser.add_argument("--expected-units", type=int, default=None)
    parser.add_argument("--max-agents-per-cell", type=int, default=None)
    parser.add_argument("--conditions", default=None)
    parser.add_argument("--rewards", default=None)
    parser.add_argument("--smoke-mode", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--progress", action="store_true")

    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--do-sample", action="store_true")
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=None)

    parser.add_argument("--torch-dtype", default="bfloat16")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--sae-device", default="auto")
    parser.add_argument("--sae-filename", default=None)
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN"))
    parser.add_argument("--trust-remote-code", action="store_true")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--load-in-8bit", action="store_true")

    parser.add_argument("--neuronpedia-model", default=DEFAULT_NEURONPEDIA_MODEL)
    parser.add_argument("--neuronpedia-source", default=DEFAULT_NEURONPEDIA_SOURCE)
    parser.add_argument("--neuronpedia-timeout", type=float, default=10.0)
    parser.add_argument("--skip-neuronpedia-metadata", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.execute and args.smoke_mode:
        raise SystemExit("Use only one of --execute or --smoke-mode")
    if args.execute:
        metadata = execute_generation(args)
        print(json.dumps(metadata, indent=2))
        return
    if not args.smoke_mode:
        raise SystemExit("Pass --smoke-mode for validation or --execute for GPU generation.")
    plan = write_smoke_plan(args)
    print(json.dumps(plan, indent=2))


if __name__ == "__main__":
    main()
