"""Trust game spec for collecting new EDSL responses."""

from __future__ import annotations

from social_sim_open_sae import (
    AgentSpec,
    BehaviorMetric,
    ConditionSpec,
    GameSpec,
    QuestionSpec,
)


def sent_amounts() -> list[dict[str, int]]:
    """Sent-amount sweep used in the trust game."""

    return [{"sent_amount": sent} for sent in range(10, 101, 10)]


def parse_behavior(unit: dict[str, object]) -> dict[str, float | None]:
    """Parse the amount returned by the receiver."""

    answer = str(unit.get("answer_text", "")).strip()
    try:
        return {"return_amount": float(answer)}
    except ValueError:
        return {"return_amount": None}


def build_game_spec() -> GameSpec:
    """Build the trust-game EDSL spec."""

    return GameSpec(
        game_id="trust",
        title="Trust Game",
        description="Agents decide how many tokens to return after receiving a transfer.",
        agents=AgentSpec(count=10, subject_prefix="T"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="trust_return",
                question_type="numerical",
                question_text=(
                    "A sender sent you {{ scenario.sent_amount }} tokens. The amount "
                    "was tripled before you received it. You now have "
                    "{{ scenario.sent_amount * 3 }} tokens from this transfer. How many "
                    "tokens do you return to the sender? Answer with a number."
                ),
                min_value=0,
                max_value=300,
                mock_response="10",
            )
        ],
        conditions=[
            ConditionSpec(
                name="baseline",
                description="Neutral trust-game wording.",
                scenarios=sent_amounts(),
                value_field="sent_amount",
            ),
            ConditionSpec(
                name="intervention",
                description="Prompting asks the receiver to reward trust.",
                instruction="You value reciprocity and reward trust from the sender.",
                scenarios=sent_amounts(),
                value_field="sent_amount",
            ),
        ],
        behavior_metrics=[
            BehaviorMetric(
                name="return_amount",
                description="Numeric amount returned to the sender.",
            )
        ],
        behavior_parser=parse_behavior,
    )
