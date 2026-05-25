"""Platform-neutral game specification objects.

The EDSL runner consumes these dataclasses and writes a normalized response-unit
schema. The Open-SAE runner then reads that schema without knowing how the game
was authored.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable


BehaviorParser = Callable[[dict[str, Any]], dict[str, Any] | None]


@dataclass(frozen=True)
class QuestionSpec:
    """One EDSL question in a social-simulation game."""

    question_name: str
    question_text: str
    question_type: str = "free_text"
    question_options: list[Any] | None = None
    max_list_items: int | None = None
    min_value: int | float | None = None
    max_value: int | float | None = None
    mock_response: str | None = None


@dataclass(frozen=True)
class AgentSpec:
    """Agent-generation defaults for a game."""

    count: int = 40
    subject_prefix: str = "A"
    instruction: str = ""
    traits: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConditionSpec:
    """One experimental condition for an EDSL social simulation."""

    name: str
    description: str = ""
    instruction: str = ""
    traits: dict[str, Any] = field(default_factory=dict)
    model_parameters: dict[str, Any] = field(default_factory=dict)
    scenarios: list[dict[str, Any]] = field(default_factory=lambda: [{}])
    value_field: str | None = None


@dataclass(frozen=True)
class BehaviorMetric:
    """A numeric behavior metric derived from response units."""

    name: str
    description: str


@dataclass(frozen=True)
class GameSpec:
    """A reusable EDSL game definition."""

    game_id: str
    title: str
    description: str
    questions: list[QuestionSpec]
    conditions: list[ConditionSpec]
    agents: AgentSpec = field(default_factory=AgentSpec)
    default_model_id: str = "meta-llama/Llama-3.3-70B-Instruct"
    default_service_name: str | None = None
    behavior_metrics: list[BehaviorMetric] = field(default_factory=list)
    behavior_parser: BehaviorParser | None = None

    def condition_names(self) -> list[str]:
        """Return condition names in declared order."""

        return [condition.name for condition in self.conditions]

    def question_names(self) -> list[str]:
        """Return question names in declared order."""

        return [question.question_name for question in self.questions]


@dataclass(frozen=True)
class ResponseUnit:
    """One normalized model response unit for Open-SAE inspection."""

    unit_id: str
    game_id: str
    condition: str
    task: str
    scenario_id: str
    reward: int | None
    source_file: str
    source_row_index: int
    response_index: int
    agent_index: str
    agent_subject_id: str
    answer_text: str
    comment_text: str
    system_prompt: str
    user_prompt: str
    response_text: str
