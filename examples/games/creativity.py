"""Creativity game spec for collecting new EDSL responses."""

from __future__ import annotations

from social_sim_open_sae import AgentSpec, ConditionSpec, GameSpec, QuestionSpec


CREATIVITY_TRAITS = {
    "trait1": "Enabling or empowering creative expression and exploration",
    "trait2": "Descriptions of creative unconventional thinking, especially thinking outside the box",
    "trait3": "Professional innovation and creative problem-solving",
}


def build_game_spec() -> GameSpec:
    """Build the creativity-task EDSL game spec."""

    return GameSpec(
        game_id="creativity",
        title="Creativity Product Innovation Tasks",
        description="Two divergent/product-innovation tasks collected through EDSL.",
        agents=AgentSpec(count=40, subject_prefix="C"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="detailed_ways_to_use_a_brick",
                question_type="list",
                question_text=(
                    "List very detailed ways you can use a brick. Each answer should be "
                    "a paragraph."
                ),
                max_list_items=10,
                mock_response='["Use it as a compact doorstop.", "Use it as a heat-retaining garden marker."]',
            ),
            QuestionSpec(
                question_name="improve_the_stapler_with_many_specific_enhancements",
                question_type="list",
                question_text=(
                    "Your goal is to improve the stapler. List as many specific "
                    "enhancements as you can that would make it better. You may change "
                    "features, materials, mechanisms, interfaces, or add/remove parts. "
                    "Do not list new uses; stay focused on improvements to the object "
                    "itself. For each idea, add enough detail so someone could build or "
                    "test it."
                ),
                max_list_items=10,
                mock_response='["Add a visible staple-depth guide.", "Add a jam-release lever."]',
            ),
        ],
        conditions=[
            ConditionSpec(name="baseline", description="No added creativity framing."),
            ConditionSpec(
                name="prompting",
                description="Agent traits encourage creative thinking.",
                traits=CREATIVITY_TRAITS,
            ),
            ConditionSpec(
                name="high_temperature",
                description="Higher-temperature model sampling.",
                model_parameters={"temperature": 1.0},
            ),
        ],
    )
