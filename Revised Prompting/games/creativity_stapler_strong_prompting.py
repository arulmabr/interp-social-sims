"""Product-innovation (stapler) spec with strong prompting baselines (Path A).

No public human-rated *product-improvement* dataset matches this task (the
Alternative Uses Task is about alternate uses, not improvements), so we do NOT
use few-shot exemplars here -- a deliberate, disclosed asymmetry vs. the brick
task. Strengthened prompting = persona + plan-then-list chain-of-thought.

The question stays a ``list`` so the downstream GPT-5 Torrance judge scores a
clean list; creativity is scored downstream, so no behavior parser/metrics here.

Conditions: baseline, persona, cot, persona_cot (headline).
"""

from __future__ import annotations

from social_sim_open_sae import AgentSpec, ConditionSpec, GameSpec, QuestionSpec

# Creativity persona (same trait labels as the original creativity.py).
CREATIVITY_TRAITS = {
    "trait1": "Enabling or empowering creative expression and exploration",
    "trait2": "Descriptions of creative unconventional thinking, especially thinking outside the box",
    "trait3": "Professional innovation and creative problem-solving",
}

COT_INSTRUCTION = (
    "Before answering, consider many distinct dimensions of improvement (features, "
    "materials, mechanisms, interfaces, ergonomics, manufacturing, ...); then give "
    "your most original, well-elaborated enhancements."
)

QUESTION_TEXT = (
    "Your goal is to improve the stapler. List as many specific enhancements as you "
    "can that would make it better. You may change features, materials, mechanisms, "
    "interfaces, or add/remove parts. Do not list new uses; stay focused on "
    "improvements to the object itself. For each idea, add enough detail so someone "
    "could build or test it.\n"
    "{{ scenario.cot_instruction }}"
)


def make_scenarios(*, cot_instruction: str = "") -> list[dict[str, object]]:
    """Single scenario carrying the per-condition CoT field."""

    return [{"cot_instruction": cot_instruction}]


def build_game_spec() -> GameSpec:
    """Build the strengthened-prompting stapler product-innovation spec."""

    conditions = [
        ConditionSpec(
            name="baseline",
            description="No persona, no CoT.",
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
            description="Plan-then-list chain-of-thought, no persona.",
            scenarios=make_scenarios(cot_instruction=COT_INSTRUCTION),
        ),
        ConditionSpec(
            name="persona_cot",
            description="Persona + plan-then-list CoT (headline strong baseline; no few-shot available).",
            traits=CREATIVITY_TRAITS,
            scenarios=make_scenarios(cot_instruction=COT_INSTRUCTION),
        ),
    ]

    return GameSpec(
        game_id="creativity_stapler_strong_prompting",
        title="Product Innovation: Stapler (Strong Prompting Baselines)",
        description=(
            "Improve-the-stapler task with strengthened prompting baselines "
            "(persona + plan-then-list CoT; no few-shot, since no comparable public "
            "human-rated product-improvement dataset exists)."
        ),
        agents=AgentSpec(count=40, subject_prefix="C"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="improve_the_stapler_with_many_specific_enhancements",
                question_type="list",
                question_text=QUESTION_TEXT,
                max_list_items=10,
                mock_response='["Add a staple-depth gauge window.", "Add a one-touch jam-release lever."]',
            )
        ],
        conditions=conditions,
    )
