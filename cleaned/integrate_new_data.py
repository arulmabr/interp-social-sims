"""
integrate_new_data.py
=====================

One-shot integration script. Appends two new generations of data into the
consolidated CSVs that already live in this folder, **without deleting** any
rows that were there before:

1.  Revised-Prompting behavioural data (lottery + ultimatum).
    Source:  ``Revised Prompting/runs_fp16/runs/{safe_risky_full,ultimatum_full}/behavior_units.csv``
    New ``treatment_condition`` values appended to
    ``behavioral_games_combined.csv``:
        baseline_rp, cot, fewshot, persona,
        fewshot_cot_dose000 / 025 / 050 / 075 / 100
    The revised-prompting *baseline* is appended under the distinct name
    ``baseline_rp`` so that the existing plotting code (which filters by
    ``treatment_condition == 'baseline'``) continues to see only the original
    Goodfire rows — the two runs use different inference stacks (Goodfire vs.
    local vLLM at fp16) and should not be silently averaged together. The
    ``source_file`` of the new rows is the run's ``game_id`` (e.g.
    ``safe_risky_strong_prompting``), so they are also distinguishable on
    provenance.

2.  Multi-judge creativity evals (5 judges: GPT-5, Claude Sonnet 4.6,
    Gemini 2.5 Pro, Kimi K2.6, DeepSeek V4 Pro).
    Source:  ``Probes/runs/mj_creativity_extra/multi_judge_scores.jsonl``
                + the matching responses in ``input.jsonl``
    New ``evaluator_model`` values appended to
    ``creativity_evals_combined.csv``: all 5 judges (the existing 320 rows
    are the older single-judge GPT-5 eval and are left untouched).
    New ``condition`` values appended: ``cot``, ``fewshot``, ``fewshot_cot``,
    ``persona``, ``persona_cot`` (in addition to the previous baseline /
    prompting / high_temperature / high_steering).

    Naming rule that mirrors the behavioural integration above: rows whose
    ``_source_figure`` is ``revised_prompting_brick`` or ``_stapler`` have
    their ``baseline`` re-tagged as ``baseline_rp``, because they are a
    different generation run (local vLLM @ fp16) than the original
    ``open_sae_creativity`` baseline (Goodfire SAE-steering pipeline). Rows
    whose ``_source_figure`` is ``open_sae_creativity`` *do* keep
    ``condition='baseline'`` — those are simply re-scoring the original
    responses with the 5-judge rubric and are distinguishable from the
    320 existing rows by ``evaluator_model`` or ``eval_prompt_version``.

Run from the repo root **or** from ``cleaned/``:

    python3 cleaned/integrate_new_data.py

Idempotent: rows already present (matched by a stable composite key) are
skipped, so re-running the script does not duplicate data.
"""
from __future__ import annotations

import json
import os
from collections import defaultdict
from typing import Dict, List

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, ".."))

BEHAVIORAL_CSV = os.path.join(HERE, "behavioral_games_combined.csv")
CREATIVITY_CSV = os.path.join(HERE, "creativity_evals_combined.csv")

RP_RUNS = os.path.join(REPO, "Revised Prompting", "runs_fp16", "runs")
SR_NEW = os.path.join(RP_RUNS, "safe_risky_full", "behavior_units.csv")
ULT_NEW = os.path.join(RP_RUNS, "ultimatum_full", "behavior_units.csv")

MJ_DIR = os.path.join(REPO, "Probes", "runs", "mj_creativity_extra")
MJ_SCORES = os.path.join(MJ_DIR, "multi_judge_scores.jsonl")
MJ_INPUT = os.path.join(MJ_DIR, "input.jsonl")


# ---------------------------------------------------------------------------
# 1) Behavioural revised-prompting integration
# ---------------------------------------------------------------------------
def _map_safe_risky_choice(v) -> object:
    """Map 0/1 + the original textual answer to canonical ``Safe Option`` /
    ``Risky Option`` strings the cleaned CSV uses."""
    if pd.isna(v):
        return np.nan
    if v == 1:
        return "Risky Option"
    if v == 0:
        return "Safe Option"
    return np.nan


def _map_ultimatum_choice(v) -> object:
    if pd.isna(v):
        return np.nan
    if v == 1:
        return "Accept"
    if v == 0:
        return "Reject"
    return np.nan


def build_behavioral_rows(src_csv: str, game: str) -> pd.DataFrame:
    """Project a revised-prompting behavior_units.csv into the schema used by
    behavioral_games_combined.csv. Unknown columns become NaN."""
    raw = pd.read_csv(src_csv, low_memory=False)
    n = len(raw)

    if game == "lottery":
        sys_p = "prompt.safe_risky_choice_system_prompt"
        usr_p = "prompt.safe_risky_choice_user_prompt"
        gen_t = "generated_tokens.safe_risky_choice_generated_tokens"
        com_t = "comment.safe_risky_choice_comment"
        val_t = "validated.safe_risky_choice_validated"
        ans_col = "answer.safe_risky_choice"
        ans_vals = raw["choice_risky"].apply(_map_safe_risky_choice)
        ult_ans = pd.Series([np.nan] * n)
    elif game == "ultimatum":
        sys_p = "prompt.ultimatum_response_system_prompt"
        usr_p = "prompt.ultimatum_response_user_prompt"
        gen_t = "generated_tokens.ultimatum_response_generated_tokens"
        com_t = "comment.ultimatum_response_comment"
        val_t = "validated.ultimatum_response_validated"
        ans_col = "answer.ultimatum_response"
        ans_vals = raw["accept_offer"].apply(_map_ultimatum_choice)
        ult_ans = ans_vals
    else:
        raise ValueError(game)

    # Re-tag the revised-prompting baseline so it does not collide with the
    # Goodfire baseline already in the CSV (see module docstring).
    new_condition = raw["condition"].replace({"baseline": "baseline_rp"})

    out = pd.DataFrame({
        "game": game,
        "treatment_condition": new_condition,
        "offer_amount": raw["reward"],
        # Encode the run identity in source_file so revised-prompting baseline
        # rows are distinguishable from the original Goodfire baseline rows.
        "source_file": raw["game_id"],
        "answer.safe_risky_choice": ans_vals if game == "lottery" else np.nan,
        "scenario.scenario_index": raw["scenario_id"],
        "agent.subject_id": raw["agent_subject_id"],
        "agent.agent_name": raw["agent_index"].apply(lambda i: f"Agent_{int(i)}"),
        "agent.agent_index": raw["agent_index"].astype(int) - 1,
        "model.model": "meta-llama/Llama-3.3-70B-Instruct",
        "model.inference_service": "vllm_local",
        "model.temperature": 0.7,
        "model.top_p": 1.0,
        "model.max_tokens": 512,
        "iteration.iteration": raw["response_index"].astype(int) - 1,
        sys_p: raw["system_prompt"],
        usr_p: raw["user_prompt"],
        gen_t: raw["response_text"],
        com_t: raw["comment_text"],
        val_t: raw["parse_ok"],
        ans_col: ans_vals,
        "answer.ultimatum_response": ult_ans if game == "ultimatum" else np.nan,
    })
    return out


def append_behavioral_new() -> Dict[str, int]:
    print(f"Reading {BEHAVIORAL_CSV}")
    base = pd.read_csv(BEHAVIORAL_CSV, low_memory=False)
    base_cols = list(base.columns)
    n_before = len(base)
    print(f"  rows before: {n_before}")

    print("Loading revised-prompting behavioural CSVs")
    lottery_new = build_behavioral_rows(SR_NEW, "lottery")
    ult_new = build_behavioral_rows(ULT_NEW, "ultimatum")
    print(f"  lottery (revised): {len(lottery_new)}, ultimatum (revised): {len(ult_new)}")

    new = pd.concat([lottery_new, ult_new], ignore_index=True)

    # Conform to the existing schema (preserve column order). Any column the
    # revised data does not have stays NaN.
    for c in base_cols:
        if c not in new.columns:
            new[c] = np.nan
    new = new[base_cols]

    # Dedup key — append-only: do not re-add rows that already match in
    # (source_file, treatment_condition, offer_amount, agent.agent_index,
    #  iteration.iteration). The revised-prompting source_file values
    # (``safe_risky_strong_prompting`` / ``ultimatum_strong_prompting``) do not
    # collide with the Goodfire CSV names, so this is purely a self-dedup
    # for repeat runs of this script.
    keycols = ["source_file", "treatment_condition", "offer_amount",
               "agent.agent_index", "iteration.iteration"]
    existing_keys = set(map(tuple, base[keycols].astype(str).values.tolist()))
    new_keys = list(map(tuple, new[keycols].astype(str).values.tolist()))
    keep_mask = [k not in existing_keys for k in new_keys]
    n_dup = sum(1 for x in keep_mask if not x)
    new_to_add = new[keep_mask].copy()
    print(f"  filtered {n_dup} rows already present, {len(new_to_add)} new rows to append")

    out = pd.concat([base, new_to_add], ignore_index=True)
    out.to_csv(BEHAVIORAL_CSV, index=False)
    print(f"  wrote {BEHAVIORAL_CSV}  (rows: {n_before} -> {len(out)})")
    return {"before": n_before, "after": len(out), "added": int(len(new_to_add)),
            "skipped_dup": int(n_dup)}


# ---------------------------------------------------------------------------
# 2) Multi-judge creativity integration
# ---------------------------------------------------------------------------
TASK_DESCRIPTIONS = {
    "detailed_ways_to_use_a_brick":
        "List very detailed ways you can use a brick. Each answer should be a paragraph.",
    "improve_the_stapler_with_many_specific_enhancements":
        "List many specific enhancements that could improve the stapler. Each answer should be a paragraph.",
}
CONDITION_LABEL = {
    "baseline": "Baseline",
    "baseline_rp": "Baseline (Revised Prompting)",
    "prompting": "Prompting",
    "high_temperature": "High Temperature",
    "high_steering": "Steering",
    "persona": "Persona",
    "cot": "CoT",
    "fewshot": "Few-shot",
    "fewshot_cot": "Few-shot + CoT",
    "persona_cot": "Persona + CoT",
}


def _agent_idx_from_id(s) -> object:
    if not isinstance(s, str):
        return np.nan
    if s.startswith("agent_"):
        try:
            return int(s.split("_", 1)[1]) - 1
        except Exception:
            return np.nan
    return np.nan


def load_mj_responses() -> Dict[str, str]:
    """Return row_id -> response text. row_id is constructed the same way the
    scores JSONL stores it: ``{_source_figure}|{model}|{task}|{object}|{condition}|{agent_id}``."""
    mapping: Dict[str, str] = {}
    with open(MJ_INPUT) as f:
        for line in f:
            r = json.loads(line)
            row_id = "|".join([
                str(r.get("_source_figure", "unknown")),
                str(r.get("model") or "unknown"),
                str(r.get("task", "unknown")),
                str(r.get("object", "unknown")),
                str(r.get("condition") or r.get("target_creativity_score") or "unknown"),
                str(r.get("agent_id", "unknown")),
            ])
            mapping[row_id] = r.get("response", "")
    return mapping


def append_multi_judge_creativity() -> Dict[str, int]:
    print(f"\nReading {CREATIVITY_CSV}")
    base = pd.read_csv(CREATIVITY_CSV, low_memory=False)
    base_cols = list(base.columns)
    n_before = len(base)
    print(f"  rows before: {n_before}")

    print("Loading multi_judge_scores.jsonl + input.jsonl")
    responses = load_mj_responses()
    rows: List[dict] = []
    with open(MJ_SCORES) as f:
        for line in f:
            r = json.loads(line)
            sf = r.get("_source_figure")
            judge = r.get("judge_name") or r.get("judge_model_id")
            cond = r.get("target_creativity_score") or r.get("condition")
            # Re-tag the revised-prompting baseline so it does not collide with
            # the open_sae_creativity baseline (different generation pipeline).
            if cond == "baseline" and sf in {"revised_prompting_brick",
                                              "revised_prompting_stapler"}:
                cond = "baseline_rp"
            agent_id = r.get("agent_id")
            row_id = r.get("row_id") or "|".join([
                str(sf), str(r.get("model") or "unknown"),
                str(r.get("task", "unknown")), str(r.get("object", "unknown")),
                str(cond), str(agent_id),
            ])
            prompt_id = r.get("prompt_id") or {
                "brick": "detailed_ways_to_use_a_brick",
                "stapler": "improve_the_stapler_with_many_specific_enhancements",
            }.get(r.get("object"))
            scores = r.get("scores") or {}
            rows.append({
                "eval_id": f"mj|{row_id}|{judge}",
                "task": prompt_id,
                "task_description": TASK_DESCRIPTIONS.get(prompt_id, np.nan),
                "condition": cond,
                "condition_label": CONDITION_LABEL.get(cond, str(cond).title() if cond else np.nan),
                "source_file": sf,
                "source_row_index": r.get("blind_order_idx"),
                "agent_index": _agent_idx_from_id(agent_id),
                "subject_id": agent_id,
                "agent_name": agent_id,
                "response_text": responses.get(row_id, np.nan),
                "fluency": scores.get("fluency"),
                "flexibility": scores.get("flexibility"),
                "originality": scores.get("originality"),
                "elaboration": scores.get("elaboration"),
                "final_score": r.get("creativity_score"),
                "evaluator_model": judge,
                "eval_prompt_version": "torrance_four_dimension_length_controlled_v1",
                "raw_evaluator_json": json.dumps(scores) if scores else np.nan,
                "api_response_id": np.nan,
                "parse_status": "ok",
                "structured_output_mode": np.nan,
            })
    new = pd.DataFrame(rows)
    print(f"  multi-judge rows produced: {len(new)}")

    # Dedup key — append-only: do not re-add rows already in the CSV.
    # The existing 320 GPT-5 rows have eval_prompt_version='torrance_four_dimension_v1',
    # while the new ones are 'torrance_four_dimension_length_controlled_v1', so
    # they never collide; this guard exists for re-runs of this script.
    keycols = ["task", "condition", "source_file", "subject_id",
               "evaluator_model", "eval_prompt_version"]
    for c in keycols:
        if c not in base.columns:
            base[c] = np.nan
    existing_keys = set(map(tuple, base[keycols].astype(str).values.tolist()))
    new_keys = list(map(tuple, new[keycols].astype(str).values.tolist()))
    keep_mask = [k not in existing_keys for k in new_keys]
    n_dup = sum(1 for x in keep_mask if not x)
    new_to_add = new[keep_mask].copy()
    for c in base_cols:
        if c not in new_to_add.columns:
            new_to_add[c] = np.nan
    new_to_add = new_to_add[base_cols]
    print(f"  filtered {n_dup} rows already present, {len(new_to_add)} new rows to append")

    out = pd.concat([base, new_to_add], ignore_index=True)
    out.to_csv(CREATIVITY_CSV, index=False)
    print(f"  wrote {CREATIVITY_CSV}  (rows: {n_before} -> {len(out)})")
    return {"before": n_before, "after": len(out), "added": int(len(new_to_add)),
            "skipped_dup": int(n_dup)}


def main():
    stats = {
        "behavioral": append_behavioral_new(),
        "creativity_multi_judge": append_multi_judge_creativity(),
    }
    print("\nIntegration summary:")
    for k, v in stats.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
