#!/usr/bin/env python3
"""Run and summarize dose-sensitive live Open-SAE steering sweeps."""

from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import run_open_sae_feature_inspection as inspection
import run_open_sae_steering_generation as steering


RUN_ROOT = ROOT / "runs" / "open_sae_dose_sweeps"
SUMMARY_DIR = RUN_ROOT / "summary"
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"
SAE_REPO = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"
HOOK = "model.layers.50"
TOP_K = 10


@dataclass(frozen=True)
class DoseSpec:
    """One dose level for one game."""

    dataset_kind: str
    dose_id: str
    dose_rank: int
    source_conditions: str
    feature_indices: tuple[int, ...]
    strengths: tuple[float, ...]
    full_units: int
    reward_cells: int
    source_dir: str
    behavior_file: str
    behavior_x: str
    behavior_y: str
    output_condition: str | None = None
    reuse_full_run: str | None = None
    reuse_smoke_run: str | None = None
    condition_cells: int = 1
    smoke_units: int = 8


DOSE_SPECS: tuple[DoseSpec, ...] = (
    DoseSpec(
        "safe_risky",
        "risk_03_01",
        1,
        "steering",
        (184, 4237),
        (0.3, 0.1),
        1400,
        35,
        "data/raw/games/safe_risky/results_20251008_225522",
        "safe_risky_behavior_summary.csv",
        "reward",
        "risky_percentage",
        output_condition="dose_risk_03_01",
    ),
    DoseSpec(
        "safe_risky",
        "risk_04_02",
        2,
        "steering",
        (184, 4237),
        (0.4, 0.2),
        1400,
        35,
        "data/raw/games/safe_risky/results_20251008_225522",
        "safe_risky_behavior_summary.csv",
        "reward",
        "risky_percentage",
        output_condition="dose_risk_04_02",
    ),
    DoseSpec(
        "safe_risky",
        "risk_05_03",
        3,
        "steering",
        (184, 4237),
        (0.5, 0.3),
        1400,
        35,
        "data/raw/games/safe_risky/results_20251008_225522",
        "safe_risky_behavior_summary.csv",
        "reward",
        "risky_percentage",
        output_condition="dose_risk_05_03",
    ),
    DoseSpec(
        "safe_risky",
        "risk_06_04",
        4,
        "lite_steering",
        (184, 4237),
        (0.6, 0.4),
        1400,
        35,
        "data/raw/games/safe_risky/results_20251008_225522",
        "safe_risky_behavior_summary.csv",
        "reward",
        "risky_percentage",
        reuse_full_run="runs/safe_risky_open_sae_steering_lite_full",
        reuse_smoke_run="runs/safe_risky_open_sae_steering_lite_smoke",
    ),
    DoseSpec(
        "safe_risky",
        "risk_07_05",
        5,
        "steering",
        (184, 4237),
        (0.7, 0.5),
        1400,
        35,
        "data/raw/games/safe_risky/results_20251008_225522",
        "safe_risky_behavior_summary.csv",
        "reward",
        "risky_percentage",
        reuse_full_run="runs/safe_risky_open_sae_steering_full",
        reuse_smoke_run="runs/safe_risky_open_sae_steering_full_smoke",
    ),
    *(
        DoseSpec(
            "ultimatum",
            f"altruism_0{rank}",
            rank,
            "steering",
            (31935,),
            (strength,),
            680,
            17,
            "data/raw/games/ultimatum/results_20251008_201139",
            "ultimatum_behavior_summary.csv",
            "offer",
            "accept_percentage",
            output_condition=f"dose_altruism_0{rank}",
            reuse_full_run="runs/ultimatum_open_sae_steering_full" if rank == 5 else None,
            reuse_smoke_run="runs/ultimatum_open_sae_steering_smoke" if rank == 5 else None,
        )
        for rank, strength in enumerate((0.1, 0.2, 0.3, 0.4, 0.5), start=1)
    ),
    DoseSpec(
        "trust",
        "trust_02_02_01_01",
        1,
        "baseline,intervention",
        (38558, 11444, 17623, 39359),
        (0.2, 0.2, 0.1, 0.1),
        200,
        20,
        "data/raw/games/trust/results",
        "trust_behavior_summary.csv",
        "sent_amount",
        "mean_return_share_of_tripled",
        condition_cells=2,
    ),
    DoseSpec(
        "trust",
        "trust_03_03_02_02",
        2,
        "baseline,intervention",
        (38558, 11444, 17623, 39359),
        (0.3, 0.3, 0.2, 0.2),
        200,
        20,
        "data/raw/games/trust/results",
        "trust_behavior_summary.csv",
        "sent_amount",
        "mean_return_share_of_tripled",
        condition_cells=2,
    ),
    DoseSpec(
        "trust",
        "trust_04_04_03_03",
        3,
        "baseline,intervention",
        (38558, 11444, 17623, 39359),
        (0.4, 0.4, 0.3, 0.3),
        200,
        20,
        "data/raw/games/trust/results",
        "trust_behavior_summary.csv",
        "sent_amount",
        "mean_return_share_of_tripled",
        reuse_full_run="runs/trust_open_sae_steering_full",
        reuse_smoke_run="runs/trust_open_sae_steering_smoke",
        condition_cells=2,
    ),
    DoseSpec(
        "trust",
        "trust_05_05_04_04",
        4,
        "baseline,intervention",
        (38558, 11444, 17623, 39359),
        (0.5, 0.5, 0.4, 0.4),
        200,
        20,
        "data/raw/games/trust/results",
        "trust_behavior_summary.csv",
        "sent_amount",
        "mean_return_share_of_tripled",
        condition_cells=2,
    ),
    DoseSpec(
        "trust",
        "trust_06_06_05_05",
        5,
        "baseline,intervention",
        (38558, 11444, 17623, 39359),
        (0.6, 0.6, 0.5, 0.5),
        200,
        20,
        "data/raw/games/trust/results",
        "trust_behavior_summary.csv",
        "sent_amount",
        "mean_return_share_of_tripled",
        condition_cells=2,
    ),
)


def rel(path: Path | str) -> str:
    path = Path(path)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_dir(spec: DoseSpec, scope: str) -> Path:
    if scope == "full" and spec.reuse_full_run:
        return ROOT / spec.reuse_full_run
    if scope == "smoke" and spec.reuse_smoke_run:
        return ROOT / spec.reuse_smoke_run
    return RUN_ROOT / scope / spec.dataset_kind / spec.dose_id


def expected_units(spec: DoseSpec, scope: str) -> int:
    return spec.smoke_units if scope == "smoke" else spec.full_units


def expected_topk_rows(spec: DoseSpec, scope: str) -> int:
    return expected_units(spec, scope) * TOP_K


def spec_rows(scope: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in DOSE_SPECS:
        path = run_dir(spec, scope)
        rows.append(
            {
                "dataset_kind": spec.dataset_kind,
                "dose_id": spec.dose_id,
                "dose_rank": spec.dose_rank,
                "source_conditions": spec.source_conditions,
                "feature_indices": ",".join(str(index) for index in spec.feature_indices),
                "input_strengths": ",".join(str(strength) for strength in spec.strengths),
                "run_path": rel(path),
                "reused_existing_run": bool(
                    (scope == "full" and spec.reuse_full_run)
                    or (scope == "smoke" and spec.reuse_smoke_run)
                ),
                "expected_units": expected_units(spec, scope),
                "expected_topk_rows": expected_topk_rows(spec, scope),
                "exists": path.exists(),
            }
        )
    return rows


def run_is_complete(spec: DoseSpec, scope: str) -> bool:
    path = run_dir(spec, scope)
    response_path = path / "response_units.csv"
    open_sae_path = path / "open_sae" / "open_sae_feature_activations.csv"
    meta_path = path / "open_sae" / "open_sae_metadata.json"
    if not (response_path.exists() and open_sae_path.exists() and meta_path.exists()):
        return False
    try:
        response_rows = len(pd.read_csv(response_path))
        topk_rows = len(pd.read_csv(open_sae_path))
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return False
    return (
        response_rows == expected_units(spec, scope)
        and topk_rows == expected_topk_rows(spec, scope)
        and metadata.get("processed_response_task_units") == expected_units(spec, scope)
        and metadata.get("special_or_control_token_topk_hits") == 0
    )


def generation_args(spec: DoseSpec, scope: str, args: argparse.Namespace) -> argparse.Namespace:
    units = expected_units(spec, scope)
    return argparse.Namespace(
        dataset_kind=spec.dataset_kind,
        run_dir=None,
        source_dir=ROOT / spec.source_dir,
        prompt_file=None,
        output_dir=run_dir(spec, scope),
        model_id=args.model_id,
        sae_repo=args.sae_repo,
        hook=args.hook,
        feature_indices=list(spec.feature_indices),
        strengths=list(spec.strengths),
        steering_mode=args.steering_mode,
        strength_calibration=args.strength_calibration,
        patch_scope=args.patch_scope,
        limit_units=units,
        expected_units=units,
        max_agents_per_cell=None,
        conditions=spec.source_conditions,
        rewards=None,
        smoke_mode=False,
        execute=True,
        progress=args.progress,
        max_new_tokens=args.max_new_tokens,
        do_sample=False,
        temperature=0.7,
        top_p=0.95,
        seed=args.seed,
        torch_dtype=args.torch_dtype,
        device_map=args.device_map,
        sae_device=args.sae_device,
        sae_filename=None,
        hf_token=args.hf_token,
        trust_remote_code=False,
        load_in_4bit=args.load_in_4bit,
        load_in_8bit=args.load_in_8bit,
        neuronpedia_model=args.neuronpedia_model,
        neuronpedia_source=args.neuronpedia_source,
        neuronpedia_timeout=args.neuronpedia_timeout,
        skip_neuronpedia_metadata=args.skip_neuronpedia_metadata,
    )


def inspection_args(spec: DoseSpec, scope: str, args: argparse.Namespace) -> argparse.Namespace:
    path = run_dir(spec, scope)
    return argparse.Namespace(
        run_dir=path,
        dataset_kind=spec.dataset_kind,
        source_dir=path,
        output_dir=path / "open_sae",
        model_id=args.model_id,
        sae_repo=args.sae_repo,
        sae_filename=None,
        hook=args.hook,
        activation_scope="all_content",
        include_system_message=False,
        include_system_in_all_content=False,
        top_k=TOP_K,
        condition_top_k=10,
        summary_top_n_per_cell=200,
        feature_aggregation="max",
        activation_threshold=0.1,
        activation_chunk_size=64,
        max_seq_len=None,
        limit_units=None,
        max_agents_per_cell=None,
        conditions=None,
        rewards=None,
        dry_run=False,
        audit_only=False,
        strict=True,
        torch_dtype=args.torch_dtype,
        device_map=args.device_map,
        sae_device=args.sae_device,
        load_in_4bit=args.load_in_4bit,
        load_in_8bit=args.load_in_8bit,
        trust_remote_code=False,
        hf_token=args.hf_token,
        skip_labels=False,
        label_workers=16,
        label_timeout=15.0,
        neuronpedia_model=args.neuronpedia_model,
        neuronpedia_source=args.neuronpedia_source,
        goodfire_log=None,
        write_full_summary=False,
        expected_units=expected_units(spec, scope),
    )


def load_shared_model_bundle(args: argparse.Namespace):
    model_args = argparse.Namespace(
        model_id=args.model_id,
        sae_repo=args.sae_repo,
        sae_filename=None,
        hook=args.hook,
        torch_dtype=args.torch_dtype,
        device_map=args.device_map,
        sae_device=args.sae_device,
        load_in_4bit=args.load_in_4bit,
        load_in_8bit=args.load_in_8bit,
        trust_remote_code=False,
        hf_token=args.hf_token,
    )
    return inspection.load_model_and_sae(model_args)


def apply_output_condition(spec: DoseSpec, prompt_records: list[dict[str, Any]]) -> None:
    if not spec.output_condition:
        return
    for record in prompt_records:
        record["source_condition"] = record.get("condition", "")
        record["condition"] = spec.output_condition


def generate_one_dose(
    spec: DoseSpec,
    scope: str,
    args: argparse.Namespace,
    loaded_model_bundle: tuple[Any, Any, Any, Any, Any, str, str],
) -> None:
    gen_args = generation_args(spec, scope, args)
    dataset_kind = steering.effective_dataset_kind(gen_args)
    feature_indices = steering.parse_feature_indices(gen_args.feature_indices)
    strengths = steering.parse_float_list(gen_args.strengths)
    steering.validate_feature_strengths(feature_indices, strengths)
    prompt_records = steering.selected_prompt_records(gen_args)
    apply_output_condition(spec, prompt_records)
    feature_metadata = steering.fetch_neuronpedia_metadata(
        feature_indices,
        neuronpedia_model=gen_args.neuronpedia_model,
        neuronpedia_source=gen_args.neuronpedia_source,
        timeout=gen_args.neuronpedia_timeout,
        skip=gen_args.skip_neuronpedia_metadata,
    )
    actual_strengths = steering.calibrated_strengths(
        strengths, feature_metadata, gen_args.strength_calibration
    )
    torch_module, tokenizer, model, hook_module, sae, sae_path, sae_device = loaded_model_bundle

    response_rows: list[dict[str, Any]] = []
    trace_rows: list[dict[str, Any]] = []
    for index, record in enumerate(prompt_records, start=1):
        response_text, trace = steering.generate_one_response(
            args=gen_args,
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
            steering.response_unit_row(
                record,
                dataset_kind=dataset_kind,
                response_text=response_text,
                output_dir=gen_args.output_dir,
                model_id=gen_args.model_id,
            )
        )
        trace["ordinal"] = index
        trace_rows.append(trace)
        if args.progress:
            print(
                json.dumps(
                    {
                        "status": "generated",
                        "scope": scope,
                        "dataset_kind": spec.dataset_kind,
                        "dose_id": spec.dose_id,
                        "ordinal": index,
                        "total": len(prompt_records),
                        "generated_tokens": trace["generated_tokens"],
                    }
                ),
                flush=True,
            )

    metadata = steering.write_execution_outputs(
        args=gen_args,
        dataset_kind=dataset_kind,
        prompt_records=prompt_records,
        response_rows=response_rows,
        trace_rows=trace_rows,
        feature_metadata=feature_metadata,
        sae_path=sae_path,
        sae_device=sae_device,
        actual_strengths=actual_strengths,
    )
    metadata.update(
        {
            "dose_sweep": True,
            "dose_id": spec.dose_id,
            "dose_rank": spec.dose_rank,
            "source_conditions": spec.source_conditions,
            "output_condition": spec.output_condition,
        }
    )
    (gen_args.output_dir / "open_sae_steering_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )


def inspect_one_dose(
    spec: DoseSpec,
    scope: str,
    args: argparse.Namespace,
    loaded_model_bundle: tuple[Any, Any, Any, Any, Any, str, str],
) -> None:
    insp_args = inspection_args(spec, scope, args)
    units, validation = inspection.load_work_units(insp_args)
    inspection.run_inference(insp_args, units, validation, loaded_model_bundle=loaded_model_bundle)


def execute_missing(args: argparse.Namespace) -> None:
    specs = [spec for spec in DOSE_SPECS if args.dataset_kind in {None, spec.dataset_kind}]
    missing = [spec for spec in specs if args.force_rerun or not run_is_complete(spec, args.scope)]
    if not missing:
        print(json.dumps({"status": "all_complete", "scope": args.scope}, indent=2))
        return
    loaded_model_bundle = load_shared_model_bundle(args)
    for spec in missing:
        if args.force_rerun or not (run_dir(spec, args.scope) / "response_units.csv").exists():
            generate_one_dose(spec, args.scope, args, loaded_model_bundle)
        inspect_one_dose(spec, args.scope, args, loaded_model_bundle)
    print(
        json.dumps(
            {
                "status": "complete",
                "scope": args.scope,
                "processed_missing_doses": [spec.dose_id for spec in missing],
            },
            indent=2,
        )
    )


def read_metadata(path: Path) -> dict[str, Any]:
    return json.loads((path / "open_sae_steering_metadata.json").read_text(encoding="utf-8"))


def read_open_sae_metadata(path: Path) -> dict[str, Any]:
    return json.loads((path / "open_sae/open_sae_metadata.json").read_text(encoding="utf-8"))


def run_index_rows(scope: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in DOSE_SPECS:
        path = run_dir(spec, scope)
        steering_meta = read_metadata(path)
        open_sae_meta = read_open_sae_metadata(path)
        response_units = pd.read_csv(path / "response_units.csv")
        activations = pd.read_csv(path / "open_sae/open_sae_feature_activations.csv")
        rows.append(
            {
                "dataset_kind": spec.dataset_kind,
                "dose_id": spec.dose_id,
                "dose_rank": spec.dose_rank,
                "source_conditions": spec.source_conditions,
                "run_path": rel(path),
                "reused_existing_run": bool(scope == "full" and spec.reuse_full_run),
                "feature_indices": ",".join(str(index) for index in spec.feature_indices),
                "input_strengths": ",".join(str(strength) for strength in spec.strengths),
                "actual_strengths": ",".join(
                    str(strength) for strength in steering_meta.get("actual_strengths", [])
                ),
                "response_units": len(response_units),
                "topk_rows": len(activations),
                "processed_response_task_units": open_sae_meta.get("processed_response_task_units"),
                "special_or_control_token_topk_hits": open_sae_meta.get(
                    "special_or_control_token_topk_hits"
                ),
            }
        )
    return rows


def add_dose_columns(frame: pd.DataFrame, spec: DoseSpec, path: Path) -> pd.DataFrame:
    output = frame.copy()
    output.insert(0, "dataset_kind", spec.dataset_kind)
    output.insert(1, "dose_id", spec.dose_id)
    output.insert(2, "dose_rank", spec.dose_rank)
    output.insert(3, "input_strengths", ",".join(str(strength) for strength in spec.strengths))
    output.insert(4, "feature_indices", ",".join(str(index) for index in spec.feature_indices))
    output.insert(5, "source_run", rel(path))
    return output


def combined_behavior(scope: str) -> pd.DataFrame:
    frames = []
    for spec in DOSE_SPECS:
        path = run_dir(spec, scope)
        frames.append(add_dose_columns(pd.read_csv(path / "open_sae" / spec.behavior_file), spec, path))
    return pd.concat(frames, ignore_index=True)


def combined_feature_summary(scope: str) -> pd.DataFrame:
    frames = []
    for spec in DOSE_SPECS:
        path = run_dir(spec, scope)
        feature_path = path / "open_sae" / "open_sae_condition_reward_top_features.csv"
        frame = pd.read_csv(feature_path)
        frame.insert(0, "summary_scope", "condition_reward")
        frames.append(add_dose_columns(frame, spec, path))
    return pd.concat(frames, ignore_index=True)


def save_behavior_plot(data: pd.DataFrame, dataset_kind: str, output_path: Path) -> None:
    specs = [spec for spec in DOSE_SPECS if spec.dataset_kind == dataset_kind]
    x_col = specs[0].behavior_x
    y_col = specs[0].behavior_y
    subset = data[data["dataset_kind"] == dataset_kind].copy()
    fig, ax = plt.subplots(figsize=(10, 6))
    if dataset_kind == "trust":
        for (dose_rank, dose_id, condition), group in subset.groupby(
            ["dose_rank", "dose_id", "condition"], dropna=False
        ):
            group = group.sort_values(x_col)
            label = f"{dose_id} / {condition}"
            ax.plot(group[x_col], group[y_col], marker="o", linewidth=1.6, label=label)
        ax.set_ylabel("Mean returned share of tripled amount")
    else:
        for (dose_rank, dose_id), group in subset.groupby(["dose_rank", "dose_id"]):
            group = group.sort_values(x_col)
            ax.plot(group[x_col], group[y_col], marker="o", linewidth=1.8, label=dose_id)
        ax.set_ylabel("Risky choice %" if dataset_kind == "safe_risky" else "Accept %")
    ax.set_xlabel(x_col.replace("_", " ").title())
    ax.set_title(f"{dataset_kind.replace('_', ' ').title()} Dose Response")
    ax.grid(alpha=0.25)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def save_feature_plot(data: pd.DataFrame, dataset_kind: str, output_path: Path) -> None:
    subset = data[(data["dataset_kind"] == dataset_kind) & (data["rank"] == 1)].copy()
    grouped = (
        subset.groupby(["dose_rank", "dose_id"], as_index=False)["mean_activation"]
        .mean()
        .sort_values("dose_rank")
    )
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.plot(grouped["dose_id"], grouped["mean_activation"], marker="o", linewidth=2)
    ax.set_xlabel("Dose")
    ax.set_ylabel("Mean rank-1 SAE activation")
    ax.set_title(f"{dataset_kind.replace('_', ' ').title()} Feature Diagnostic")
    ax.grid(alpha=0.25)
    ax.tick_params(axis="x", rotation=30)
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=200)
    plt.close(fig)


def summarize(scope: str) -> dict[str, Any]:
    SUMMARY_DIR.mkdir(parents=True, exist_ok=True)
    index = pd.DataFrame(run_index_rows(scope))
    behavior = combined_behavior(scope)
    features = combined_feature_summary(scope)
    index.to_csv(SUMMARY_DIR / "dose_sweep_run_index.csv", index=False)
    behavior.to_csv(SUMMARY_DIR / "dose_sweep_behavior_summary.csv", index=False)
    features.to_csv(SUMMARY_DIR / "dose_sweep_feature_summary.csv", index=False)
    plots = []
    for dataset_kind in ["safe_risky", "ultimatum", "trust"]:
        behavior_plot = SUMMARY_DIR / f"{dataset_kind}_dose_response_behavior.png"
        feature_plot = SUMMARY_DIR / f"{dataset_kind}_dose_feature_activation_diagnostics.png"
        save_behavior_plot(behavior, dataset_kind, behavior_plot)
        save_feature_plot(features, dataset_kind, feature_plot)
        plots.extend([rel(behavior_plot), rel(feature_plot)])
    metadata = {
        "status": "complete",
        "scope": scope,
        "dose_count": int(len(index)),
        "response_units": int(index["response_units"].sum()),
        "topk_rows": int(index["topk_rows"].sum()),
        "summary_dir": rel(SUMMARY_DIR),
        "plots": plots,
    }
    (SUMMARY_DIR / "dose_sweep_metadata.json").write_text(
        json.dumps(metadata, indent=2),
        encoding="utf-8",
    )
    return metadata


def dry_run(args: argparse.Namespace) -> None:
    rows = spec_rows(args.scope)
    missing = [row for row in rows if not run_is_complete(DOSE_SPECS[rows.index(row)], args.scope)]
    print(
        json.dumps(
            {
                "status": "dry_run",
                "scope": args.scope,
                "dose_count": len(rows),
                "missing_count": len(missing),
                "new_units_if_missing": sum(row["expected_units"] for row in missing),
                "new_topk_rows_if_missing": sum(row["expected_topk_rows"] for row in missing),
                "doses": rows,
            },
            indent=2,
        )
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--dataset-kind", choices=["safe_risky", "ultimatum", "trust"], default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--execute-missing", action="store_true")
    parser.add_argument("--summarize", action="store_true")
    parser.add_argument("--force-rerun", action="store_true")
    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--sae-repo", default=SAE_REPO)
    parser.add_argument("--hook", default=HOOK)
    parser.add_argument("--steering-mode", default="clamp_min")
    parser.add_argument("--strength-calibration", default="raw")
    parser.add_argument("--patch-scope", default="last_token")
    parser.add_argument("--max-new-tokens", type=int, default=256)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--torch-dtype", default="bfloat16")
    parser.add_argument("--device-map", default="auto")
    parser.add_argument("--sae-device", default="auto")
    parser.add_argument("--load-in-4bit", action="store_true")
    parser.add_argument("--load-in-8bit", action="store_true")
    parser.add_argument("--hf-token", default=os.environ.get("HF_TOKEN"))
    parser.add_argument("--neuronpedia-model", default=inspection.DEFAULT_NEURONPEDIA_MODEL)
    parser.add_argument("--neuronpedia-source", default=inspection.DEFAULT_NEURONPEDIA_SOURCE)
    parser.add_argument("--neuronpedia-timeout", type=float, default=10.0)
    parser.add_argument("--skip-neuronpedia-metadata", action="store_true")
    parser.add_argument("--progress", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.dry_run:
        dry_run(args)
    if args.execute_missing:
        execute_missing(args)
    if args.summarize:
        print(json.dumps(summarize(args.scope), indent=2))
    if not (args.dry_run or args.execute_missing or args.summarize):
        raise SystemExit("Pass --dry-run, --execute-missing, or --summarize.")


if __name__ == "__main__":
    main()
