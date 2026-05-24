"""Ultimatum game spec for collecting new EDSL responses."""

from __future__ import annotations

from social_sim_open_sae import (
    AgentSpec,
    BehaviorMetric,
    ConditionSpec,
    GameSpec,
    QuestionSpec,
)


def offers() -> list[dict[str, int]]:
    """Offer sweep used in the ultimatum game."""

    return [{"offer": offer} for offer in range(10, 91, 5)]


def parse_behavior(unit: dict[str, object]) -> dict[str, int]:
    """Parse whether the responder accepted the offer."""

    answer = str(unit.get("answer_text", "")).lower()
    return {"accept_offer": int("accept" in answer and "reject" not in answer)}


def build_game_spec() -> GameSpec:
    """Build the ultimatum EDSL game spec."""

    return GameSpec(
        game_id="ultimatum",
        title="Ultimatum Game",
        description="Agents decide whether to accept or reject offers from a proposer.",
        agents=AgentSpec(count=40, subject_prefix="U"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="ultimatum_response",
                question_type="multiple_choice",
                question_text=(
                    "You are responding in an ultimatum game. The proposer offers you "
                    "{{ scenario.offer }} tokens out of 100. If you accept, you receive "
                    "the offer. If you reject, both players receive 0. Do you accept or reject?"
                ),
                question_options=["accept", "reject"],
                mock_response="accept",
            )
        ],
        conditions=[
            ConditionSpec(
                name="baseline",
                description="Neutral ultimatum-game wording.",
                scenarios=offers(),
                value_field="offer",
            ),
            ConditionSpec(
                name="prompting",
                description="Prompting asks the responder to be pragmatic.",
                instruction="You prefer practical outcomes and avoid destroying value.",
                scenarios=offers(),
                value_field="offer",
            ),
            ConditionSpec(
                name="steering",
                description="Placeholder condition for Open-SAE steering extensions.",
                instruction="You are inclined to accept offers when possible.",
                scenarios=offers(),
                value_field="offer",
            ),
        ],
        behavior_metrics=[
            BehaviorMetric(
                name="accept_offer",
                description="1 if the responder accepted the offer, else 0.",
            )
        ],
        behavior_parser=parse_behavior,
    )
