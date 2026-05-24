"""Safe-risk lottery game spec for collecting new EDSL responses."""

from __future__ import annotations

from social_sim_open_sae import (
    AgentSpec,
    BehaviorMetric,
    ConditionSpec,
    GameSpec,
    QuestionSpec,
)


def risky_rewards() -> list[dict[str, int]]:
    """Reward sweep used in the safe-risk game."""

    return [{"risky_reward": reward} for reward in range(80, 181, 5)]


def parse_behavior(unit: dict[str, object]) -> dict[str, int]:
    """Parse whether the response chose the risky option."""

    answer = str(unit.get("answer_text", "")).lower()
    return {"choice_risky": int("risky" in answer and "safe" not in answer)}


def build_game_spec() -> GameSpec:
    """Build the safe-risk EDSL game spec."""

    return GameSpec(
        game_id="safe_risky",
        title="Safe-Risk Lottery Game",
        description="Agents choose between a sure safe reward and a risky lottery.",
        agents=AgentSpec(count=40, subject_prefix="L"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="safe_risky_choice",
                question_type="multiple_choice",
                question_text=(
                    "You are playing a lottery game. Option safe gives 100 tokens for "
                    "sure. Option risky gives {{ scenario.risky_reward }} tokens with "
                    "50 percent probability and 0 tokens otherwise. Choose one option."
                ),
                question_options=["safe", "risky"],
                mock_response="safe",
            )
        ],
        conditions=[
            ConditionSpec(
                name="baseline",
                description="Neutral lottery wording.",
                scenarios=risky_rewards(),
                value_field="risky_reward",
            ),
            ConditionSpec(
                name="prompting",
                description="Prompting encourages risk-seeking.",
                instruction="You are inclined to take advantageous risky opportunities.",
                scenarios=risky_rewards(),
                value_field="risky_reward",
            ),
            ConditionSpec(
                name="steering",
                description="Placeholder condition for Open-SAE steering extensions.",
                instruction="You are strongly inclined to choose the risky option.",
                scenarios=risky_rewards(),
                value_field="risky_reward",
            ),
        ],
        behavior_metrics=[
            BehaviorMetric(
                name="choice_risky",
                description="1 if the model chose the risky lottery, else 0.",
            )
        ],
        behavior_parser=parse_behavior,
    )
