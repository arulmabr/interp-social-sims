"""Divergent-creativity (brick) spec with strong prompting baselines (Path A).

Few-shot exemplars are HUMAN Alternative Uses Task responses for "brick",
selected by HUMAN originality ratings from the Ocsai dataset (MIT; Organisciak
et al. 2023). Selecting exemplars by human ratings keeps exemplar selection
independent of the GPT-5 Torrance judge used downstream, which avoids the
selection/evaluation circularity. (Re)build the exemplars with:

    python scripts/build_brick_exemplars.py

The question stays a ``list`` so the downstream GPT-5 Torrance judge scores a
clean list. "CoT" for an open-ended list task is a *plan-then-list* instruction
(consider many categories first), which guides breadth without breaking the list
output format. Creativity is scored downstream (Torrance judge), so this spec
defines no behavior parser/metrics.

Conditions: baseline, persona, cot, fewshot, fewshot_cot (headline).
"""

from __future__ import annotations

import json
from pathlib import Path

from social_sim_open_sae import AgentSpec, ConditionSpec, GameSpec, QuestionSpec

EXEMPLARS_PATH = Path(__file__).resolve().parents[1] / "data" / "brick_exemplars.json"

# Creativity persona (same trait labels as the original creativity.py).
CREATIVITY_TRAITS = {
    "trait1": "Enabling or empowering creative expression and exploration",
    "trait2": "Descriptions of creative unconventional thinking, especially thinking outside the box",
    "trait3": "Professional innovation and creative problem-solving",
}

COT_INSTRUCTION = (
    "Before answering, consider many distinct categories of use (construction, art, "
    "recreation, household, education, ...); then give your most original, "
    "well-elaborated ideas."
)


def build_fewshot_block(k: int = 6) -> str:
    """Format the top-k human-rated brick exemplars into a prompt block."""

    if not EXEMPLARS_PATH.exists():
        raise FileNotFoundError(
            f"{EXEMPLARS_PATH} not found. Run: python scripts/build_brick_exemplars.py"
        )
    data = json.loads(EXEMPLARS_PATH.read_text(encoding="utf-8"))
    items = "\n".join(f'- "{ex["response"]}"' for ex in data["exemplars"][:k])
    return (
        "Here are examples of creative uses other people generated for a brick "
        "(for inspiration only; do NOT reuse them):\n" + items + "\n\n"
    )


QUESTION_TEXT = (
    "{{ scenario.fewshot_block }}"
    "List very detailed ways you can use a brick. Each answer should be a paragraph.\n"
    "{{ scenario.cot_instruction }}"
)


def make_scenarios(*, fewshot_block: str = "", cot_instruction: str = "") -> list[dict[str, object]]:
    """Single scenario carrying the per-condition injection fields."""

    return [{"fewshot_block": fewshot_block, "cot_instruction": cot_instruction}]


def build_game_spec() -> GameSpec:
    """Build the strengthened-prompting brick creativity spec."""

    fewshot = build_fewshot_block()
    conditions = [
        ConditionSpec(
            name="baseline",
            description="No demonstrations, no CoT.",
            scenarios=make_scenarios(),
        ),
        ConditionSpec(
            name="persona",
            description="Creativity persona traits (original weak prompting baseline).",
            traits=CREATIVITY_TRAITS,
            scenarios=make_scenarios(),
        ),
        ConditionSpec(
            name="cot",
            description="Plan-then-list chain-of-thought, no demonstrations.",
            scenarios=make_scenarios(cot_instruction=COT_INSTRUCTION),
        ),
        ConditionSpec(
            name="fewshot",
            description="Few-shot human AUT exemplars, no CoT.",
            scenarios=make_scenarios(fewshot_block=fewshot),
        ),
        ConditionSpec(
            name="fewshot_cot",
            description="Few-shot human AUT exemplars + plan-then-list CoT (headline strong baseline).",
            scenarios=make_scenarios(fewshot_block=fewshot, cot_instruction=COT_INSTRUCTION),
        ),
    ]

    return GameSpec(
        game_id="creativity_brick_strong_prompting",
        title="Divergent Creativity: Brick (Strong Prompting Baselines)",
        description=(
            "Alternative-uses-of-a-brick task with strengthened prompting baselines; "
            "few-shot exemplars are human AUT responses selected by human originality "
            "(Ocsai, MIT)."
        ),
        agents=AgentSpec(count=40, subject_prefix="C"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="detailed_ways_to_use_a_brick",
                question_type="list",
                question_text=QUESTION_TEXT,
                max_list_items=10,
                mock_response='["Crush it into powder to use as a pigment.", "Hollow it out as a planter."]',
            )
        ],
        conditions=conditions,
    )
