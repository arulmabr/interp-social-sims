"""Safe-risk lottery spec with *strengthened* prompting baselines.

This module reimplements the safe-risk lottery game from ``safe_risky.py`` to
support the reviewer-requested strong prompting baselines (few-shot and
chain-of-thought), while leaving the original game module and its archived
fixtures untouched.

Key differences from ``safe_risky.py``:

* The question is ``free_text`` rather than ``multiple_choice`` so the model can
  emit a single completion containing its reasoning followed by an explicit
  ``Final answer: ...`` line. This is canonical Wei/Kojima chain-of-thought (one
  completion, reasoning-then-answer, parsed), not an EDSL-specific two-question
  mechanism. Every condition uses this same elicitation, so differences are
  attributable to the prompting manipulation and not to MCQ-vs-free-text format.
* Few-shot demonstrations and the CoT trigger are injected through the existing
  EDSL scenario-templating mechanism (``{{ scenario.fewshot_block }}`` /
  ``{{ scenario.cot_instruction }}``), so no change to the core package is
  required.
* ``parse_behavior`` extracts the LAST ``Final answer: (safe|risky)`` marker
  (the reasoning text mentions both options, so a naive keyword search breaks).

Decoding is held constant across all conditions (no per-condition
``model_parameters``); only the prompt differs.

Conditions:
  baseline                  free-text, no demos, no CoT
  persona                   risk-seeking persona instruction (the original weak
                            prompting baseline, re-run under free-text)
  cot                       zero-shot CoT, no demos (does reasoning alone shift?)
  fewshot                   few-shot demos (risk-seeking), NO reasoning in demos
                            (isolates few-shot vs few-shot+CoT)
  fewshot_cot_dose000..100  few-shot CoT at graded risk-seeking "dose" (fraction
                            of risky exemplars). dose100 is the headline strong
                            baseline; the full family is the prompting
                            dose-response to compare against probe/SAE lambda/alpha.

Smoke test (no GPU/network):
  python scripts/run_edsl_social_simulation.py \
    --game-module examples/games/safe_risky_strong_prompting.py \
    --output-dir /tmp/srsp --mock-model --agents 2 \
    --conditions baseline,fewshot_cot_dose100 --limit-scenarios 1
"""

from __future__ import annotations

import random
import re

from social_sim_open_sae import (
    AgentSpec,
    BehaviorMetric,
    ConditionSpec,
    GameSpec,
    QuestionSpec,
)

# Reward sweep: identical to safe_risky.py (safe = 50, EV crossover at 100).
REWARD_SWEEP = list(range(10, 181, 5))

# Demonstration reward values are deliberately OFF the step-5 test grid so that
# no demonstration ever answers an exact test item (leakage control).
DEMO_REWARDS = [33, 51, 67, 99, 132, 166]

# Constant CoT trigger appended for CoT conditions (model generates its own
# reasoning; nothing about the reasoning content is hard-coded).
COT_INSTRUCTION = (
    "Think step by step about the expected value of each option and your own "
    "attitude toward risk, then decide."
)

# Persona instruction reused verbatim from the original safe_risky.py so the
# "persona" condition is a like-for-like re-run of the old weak baseline.
PERSONA_INSTRUCTION = "You are inclined to take advantageous risky opportunities."

QUESTION_TEXT = (
    "{{ scenario.fewshot_block }}"
    "You are playing a lottery game. Option safe gives 50 tokens for sure. "
    "Option risky gives {{ scenario.risky_reward }} tokens with 50 percent "
    "probability and 0 tokens otherwise. Choose one option.\n"
    "{{ scenario.cot_instruction }}\n"
    'End your response with exactly "Final answer: safe" or "Final answer: risky".'
)

_FINAL_ANSWER = re.compile(r"final\s*answer\s*[:\-]?\s*(safe|risky)", re.IGNORECASE)


def build_demo_block(risky_fraction: float, *, with_reasoning: bool, seed: int = 7) -> str:
    """Build a few-shot demonstration block.

    ``risky_fraction`` in [0, 1] is the dose: the fraction of demonstrations
    that choose the risky option. 1.0 = risk-seeking demonstrator, 0.0 =
    risk-averse, 0.5 = mildly/variably risk-inclined. Choices are shuffled
    across the (off-grid) demo rewards so the set demonstrates a graded
    propensity rather than a sharp, leak-prone switching threshold.

    ``with_reasoning`` toggles few-shot CoT (reasoning then answer) vs. plain
    few-shot (answer only).
    """

    rng = random.Random(seed)
    rewards = list(DEMO_REWARDS)
    rng.shuffle(rewards)
    k = len(rewards)
    n_risky = round(risky_fraction * k)
    choices = ["risky"] * n_risky + ["safe"] * (k - n_risky)
    rng.shuffle(choices)

    blocks = []
    for reward, choice in zip(rewards, choices):
        question = (
            f"Q: Option safe gives 50 tokens for sure. Option risky gives {reward} "
            "tokens with 50 percent probability and 0 tokens otherwise. Choose one option."
        )
        if with_reasoning:
            if choice == "risky":
                answer = (
                    f"A: A guaranteed 50 is fine, but a 50/50 shot at {reward} has enough "
                    "upside that I'd rather take the chance. Final answer: risky"
                )
            else:
                answer = (
                    f"A: A 50/50 shot at {reward} could leave me with nothing, so I'd "
                    "rather lock in the certain 50. Final answer: safe"
                )
        else:
            answer = f"A: Final answer: {choice}"
        blocks.append(f"{question}\n{answer}")

    return "Here are example responses:\n\n" + "\n\n".join(blocks) + "\n\n"


def make_scenarios(*, fewshot_block: str = "", cot_instruction: str = "") -> list[dict[str, object]]:
    """Reward sweep with per-condition few-shot / CoT injection fields.

    Every scenario carries all three templated keys (empty when unused) so the
    shared question template never references an undefined variable.
    """

    return [
        {
            "risky_reward": reward,
            "fewshot_block": fewshot_block,
            "cot_instruction": cot_instruction,
        }
        for reward in REWARD_SWEEP
    ]


def parse_behavior(unit: dict[str, object]) -> dict[str, int]:
    """Extract the risky choice from a free-text (possibly CoT) response.

    Reads the LAST ``Final answer: (safe|risky)`` marker. Falls back to the last
    bare option keyword only if no marker is present. ``parse_ok`` records
    whether the explicit marker was found.
    """

    text = str(unit.get("answer_text", "")) or str(unit.get("response_text", ""))
    matches = _FINAL_ANSWER.findall(text)
    if matches:
        return {"choice_risky": int(matches[-1].lower() == "risky"), "parse_ok": 1}

    low = text.lower()
    last_risky = low.rfind("risky")
    last_safe = low.rfind("safe")
    if last_risky == -1 and last_safe == -1:
        return {"choice_risky": 0, "parse_ok": 0}
    return {"choice_risky": int(last_risky > last_safe), "parse_ok": 0}


def build_game_spec() -> GameSpec:
    """Build the strengthened-prompting safe-risk game spec."""

    mock = "Reasoning: deterministic smoke response. Final answer: risky"

    conditions = [
        ConditionSpec(
            name="baseline",
            description="Free-text elicitation, no demonstrations, no CoT.",
            scenarios=make_scenarios(),
            value_field="risky_reward",
        ),
        ConditionSpec(
            name="persona",
            description="Risk-seeking persona instruction (original weak prompting baseline).",
            instruction=PERSONA_INSTRUCTION,
            scenarios=make_scenarios(),
            value_field="risky_reward",
        ),
        ConditionSpec(
            name="cot",
            description="Zero-shot chain-of-thought, no demonstrations.",
            scenarios=make_scenarios(cot_instruction=COT_INSTRUCTION),
            value_field="risky_reward",
        ),
        ConditionSpec(
            name="fewshot",
            description="Few-shot demonstrations (risk-seeking), no reasoning in demos.",
            scenarios=make_scenarios(
                fewshot_block=build_demo_block(1.0, with_reasoning=False),
            ),
            value_field="risky_reward",
        ),
    ]

    # Bidirectional few-shot CoT dose-response. dose100 is the headline strong
    # prompting baseline; the family traces the prompting controllability curve.
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        conditions.append(
            ConditionSpec(
                name=f"fewshot_cot_dose{int(fraction * 100):03d}",
                description=f"Few-shot CoT with {int(fraction * 100)}% risk-seeking exemplars.",
                scenarios=make_scenarios(
                    fewshot_block=build_demo_block(fraction, with_reasoning=True),
                    cot_instruction=COT_INSTRUCTION,
                ),
                value_field="risky_reward",
            )
        )

    return GameSpec(
        game_id="safe_risky_strong_prompting",
        title="Safe-Risk Lottery Game (Strong Prompting Baselines)",
        description=(
            "Safe-risk lottery with strengthened prompting baselines: few-shot and "
            "chain-of-thought, plus a bidirectional few-shot-CoT dose-response."
        ),
        agents=AgentSpec(count=40, subject_prefix="L"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="safe_risky_choice",
                question_type="free_text",
                question_text=QUESTION_TEXT,
                mock_response=mock,
            )
        ],
        conditions=conditions,
        behavior_metrics=[
            BehaviorMetric(
                name="choice_risky",
                description="1 if the model chose the risky lottery, else 0.",
            )
        ],
        behavior_parser=parse_behavior,
    )
