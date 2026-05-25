#!/usr/bin/env python3
"""Self-hosted (vLLM, full-precision) generation runner for the strong-prompting specs.

This bypasses EDSL and the hosted APIs (which only serve the FP8 "Turbo" build of
Llama-3.3-70B). It loads a strong-prompting GameSpec, rebuilds the *same* prompts
(persona + few-shot/CoT via the question's Jinja template), runs them through a
locally hosted model with vLLM (batched), and writes the *same* normalized
``response_units.csv`` / behavior outputs as the EDSL runner -- so every
downstream step (Open-SAE inspection, the dose-response analysis, the Torrance
eval) is unchanged.

Built for a RunPod 2x H100 80GB pod at bf16 (the native full precision for
Llama-3.3 -- the true non-Turbo model).

Key detail: the 40 agents per (condition, scenario) are 40 *samples*. With greedy
decoding they would be identical, so we sample at ``--temperature`` > 0 with a
distinct, reproducible per-agent seed.

Inspect prompts without a GPU first:
    python scripts/run_local_vllm_generation.py \
        --game-module games/safe_risky_strong_prompting.py \
        --output-dir /tmp/dry --dry-run --agents 2 --limit-scenarios 1
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import jinja2  # noqa: E402

from social_sim_open_sae.edsl_adapter import (  # noqa: E402  (these are stdlib-only helpers)
    behavior_rows_for_units,
    behavior_summary,
    load_game_spec,
    write_csv,
    write_jsonl,
)
from social_sim_open_sae.game_spec import GameSpec, ResponseUnit  # noqa: E402


def render_persona(spec: GameSpec, condition) -> str:
    """Render a condition's persona into a system prompt (instruction and/or traits)."""

    instruction = condition.instruction or spec.agents.instruction or ""
    traits = {**spec.agents.traits, **condition.traits}
    parts = []
    if instruction:
        parts.append(instruction)
    if traits:
        trait_text = "; ".join(str(v) for v in traits.values())
        parts.append(f"You have the following characteristics: {trait_text}.")
    return " ".join(parts).strip()


def render_question(question_text: str, scenario: dict) -> str:
    """Render the EDSL-style ``{{ scenario.* }}`` template with concrete values."""

    return jinja2.Template(question_text).render(scenario=scenario)


def stable_seed(seed_base: int, condition: str, scenario_index: int, agent_index: int) -> int:
    key = f"{seed_base}|{condition}|{scenario_index}|{agent_index}".encode("utf-8")
    return int(hashlib.md5(key).hexdigest(), 16) % (2**31)


def build_jobs(spec, *, agent_count, conditions_filter, limit_scenarios, seed_base):
    """Expand a spec into a flat list of generation jobs."""

    jobs = []
    for condition in spec.conditions:
        if conditions_filter and condition.name not in conditions_filter:
            continue
        system = render_persona(spec, condition)
        scenarios = condition.scenarios or [{}]
        if limit_scenarios is not None:
            scenarios = scenarios[:limit_scenarios]
        for scenario_index, scenario in enumerate(scenarios):
            payload = {"condition": condition.name, "scenario_index": scenario_index, **scenario}
            reward = scenario.get(condition.value_field) if condition.value_field else None
            for question in spec.questions:
                user = render_question(question.question_text, payload)
                for agent_index in range(1, agent_count + 1):
                    jobs.append(
                        {
                            "condition": condition.name,
                            "task": question.question_name,
                            "scenario_index": scenario_index,
                            "reward": reward,
                            "agent_index": agent_index,
                            "subject_id": f"{spec.agents.subject_prefix}{agent_index}",
                            "system": system,
                            "user": user,
                            "seed": stable_seed(seed_base, condition.name, scenario_index, agent_index),
                        }
                    )
    return jobs


def jobs_to_units(spec, jobs, texts) -> list[ResponseUnit]:
    units = []
    for index, (job, text) in enumerate(zip(jobs, texts)):
        text = (text or "").strip()
        unit_id = (
            f"{spec.game_id}:{job['condition']}:{job['scenario_index']}:"
            f"{job['agent_index']}:{job['task']}"
        )
        units.append(
            ResponseUnit(
                unit_id=unit_id,
                game_id=spec.game_id,
                condition=job["condition"],
                task=job["task"],
                scenario_id=str(job["scenario_index"]),
                reward=job["reward"],
                source_file="vllm_local",
                source_row_index=index,
                response_index=index + 1,
                agent_index=str(job["agent_index"]),
                agent_subject_id=job["subject_id"],
                answer_text=text,
                comment_text="",
                system_prompt=job["system"],
                user_prompt=job["user"],
                response_text=text,
            )
        )
    return units


def write_outputs(spec, units, output_dir: Path, manifest_extra: dict) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    unit_rows = [asdict(u) for u in units]
    write_csv(output_dir / "response_units.csv", unit_rows)
    write_jsonl(output_dir / "response_units.jsonl", unit_rows)

    behavior_unit_rows = behavior_rows_for_units(spec, units)
    behavior_summary_rows = behavior_summary(
        behavior_unit_rows, [metric.name for metric in spec.behavior_metrics]
    )
    if behavior_unit_rows:
        write_csv(output_dir / "behavior_units.csv", behavior_unit_rows)
    if behavior_summary_rows:
        write_csv(output_dir / "behavior_summary.csv", behavior_summary_rows)

    manifest = {
        "run_type": "vllm_local_generation",
        "game_id": spec.game_id,
        "response_units": len(units),
        "behavior_summary_rows": len(behavior_summary_rows),
        **manifest_extra,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--game-module", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    p.add_argument("--model", default="meta-llama/Llama-3.3-70B-Instruct")
    p.add_argument("--dtype", default="bfloat16", help="bfloat16 = native full precision for Llama-3.3.")
    p.add_argument("--tensor-parallel-size", type=int, default=2, help="Number of GPUs (2x80GB for bf16 70B).")
    p.add_argument("--max-model-len", type=int, default=4096)
    p.add_argument("--gpu-memory-utilization", type=float, default=0.92)
    p.add_argument("--temperature", type=float, default=0.7,
                   help="MUST be > 0 so the 40 agents differ; set to match your other runs.")
    p.add_argument("--top-p", type=float, default=1.0)
    p.add_argument("--max-tokens", type=int, default=512, help="Raise for creativity lists (e.g. 1536).")
    p.add_argument("--agents", type=int, default=None, help="Override agents/condition (default: spec count).")
    p.add_argument("--conditions", default=None, help="Comma-separated condition names (default: all).")
    p.add_argument("--limit-scenarios", type=int, default=None, help="Smoke: first N scenarios per condition.")
    p.add_argument("--seed-base", type=int, default=0)
    p.add_argument("--dry-run", action="store_true", help="Build prompts and exit (no GPU/vLLM).")
    return p.parse_args()


def main() -> None:
    args = parse_args()
    spec = load_game_spec(args.game_module)
    agent_count = args.agents if args.agents is not None else spec.agents.count
    conditions_filter = (
        {c.strip() for c in args.conditions.split(",") if c.strip()} if args.conditions else None
    )
    jobs = build_jobs(
        spec,
        agent_count=agent_count,
        conditions_filter=conditions_filter,
        limit_scenarios=args.limit_scenarios,
        seed_base=args.seed_base,
    )
    print(f"{spec.game_id}: {len(jobs)} generation jobs "
          f"({agent_count} agents x conditions x scenarios)")

    if args.dry_run:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        sample = []
        seen = set()
        for job in jobs:
            if job["condition"] in seen:
                continue
            seen.add(job["condition"])
            sample.append({k: job[k] for k in ("condition", "task", "reward", "seed", "system", "user")})
        (args.output_dir / "dry_run_prompts.json").write_text(
            json.dumps(sample, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"[dry-run] wrote {len(sample)} sample prompts (one per condition) to "
              f"{args.output_dir / 'dry_run_prompts.json'}")
        return

    from vllm import LLM, SamplingParams  # imported lazily so --dry-run needs no GPU

    llm = LLM(
        model=args.model,
        dtype=args.dtype,
        tensor_parallel_size=args.tensor_parallel_size,
        max_model_len=args.max_model_len,
        gpu_memory_utilization=args.gpu_memory_utilization,
        trust_remote_code=True,
    )
    conversations = []
    sampling_params = []
    for job in jobs:
        messages = []
        if job["system"]:
            messages.append({"role": "system", "content": job["system"]})
        messages.append({"role": "user", "content": job["user"]})
        conversations.append(messages)
        sampling_params.append(
            SamplingParams(
                temperature=args.temperature,
                top_p=args.top_p,
                max_tokens=args.max_tokens,
                seed=job["seed"],
            )
        )

    outputs = llm.chat(conversations, sampling_params)
    texts = [o.outputs[0].text for o in outputs]
    units = jobs_to_units(spec, jobs, texts)
    manifest = write_outputs(
        spec,
        units,
        args.output_dir,
        manifest_extra={
            "model": args.model,
            "dtype": args.dtype,
            "tensor_parallel_size": args.tensor_parallel_size,
            "temperature": args.temperature,
            "top_p": args.top_p,
            "max_tokens": args.max_tokens,
            "agents": agent_count,
        },
    )
    print(json.dumps({"status": "complete", "output_dir": str(args.output_dir), **manifest}, indent=2))


if __name__ == "__main__":
    main()
