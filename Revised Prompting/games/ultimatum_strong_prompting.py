"""Ultimatum spec with *strengthened* prompting baselines.

Mirror of ``safe_risky_strong_prompting.py`` for the ultimatum game; see that
module's docstring for the full design rationale (canonical single-completion
few-shot/CoT injected via scenario templating, free-text elicitation shared
across all conditions, decoding held constant, original ``ultimatum.py`` left
untouched).

Disposition: the dose is the fraction of *accepting* exemplars. dose100 =
maximally accepting (altruistic/pragmatic: accept even low offers, matching the
paper's altruism condition); dose000 = maximally rejecting (spiteful: reject
even generous offers). dose100 is the headline strong prompting baseline; the
full family is the prompting dose-response to compare against probe/SAE steering.

Conditions:
  baseline                  free-text, no demos, no CoT
  persona                   accept-leaning persona instruction (original weak
                            prompting baseline, re-run under free-text)
  cot                       zero-shot CoT, no demos
  fewshot                   few-shot demos (accept-leaning), NO reasoning in demos
  fewshot_cot_dose000..100  few-shot CoT at graded acceptance dose

Smoke test (no GPU/network):
  python scripts/run_edsl_social_simulation.py \
    --game-module examples/games/ultimatum_strong_prompting.py \
    --output-dir /tmp/usp --mock-model --agents 2 \
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

# Offer sweep: identical to ultimatum.py (offers out of 100, fair split = 50).
OFFER_SWEEP = list(range(10, 91, 5))

# Demonstration offers are OFF the step-5 test grid so no demo answers an exact
# test item (leakage control).
DEMO_OFFERS = [13, 27, 41, 58, 72, 86]

COT_INSTRUCTION = (
    "Think step by step about what you gain from accepting versus rejecting and "
    "how fair the split is, then decide."
)

# Reused verbatim from the original ultimatum.py so "persona" is a like-for-like
# re-run of the old weak baseline.
PERSONA_INSTRUCTION = "You prefer practical outcomes and avoid destroying value."

QUESTION_TEXT = (
    "{{ scenario.fewshot_block }}"
    "You are responding in an ultimatum game. The proposer offers you "
    "{{ scenario.offer }} tokens out of 100. If you accept, you receive the "
    "offer. If you reject, both players receive 0. Do you accept or reject?\n"
    "{{ scenario.cot_instruction }}\n"
    'End your response with exactly "Final answer: accept" or "Final answer: reject".'
)

_FINAL_ANSWER = re.compile(r"final\s*answer\s*[:\-]?\s*(accept|reject)", re.IGNORECASE)


def build_demo_block(accept_fraction: float, *, with_reasoning: bool, seed: int = 7) -> str:
    """Build a few-shot demonstration block.

    ``accept_fraction`` in [0, 1] is the dose: the fraction of demonstrations
    that accept the offer. 1.0 = always-accept (altruistic/pragmatic), 0.0 =
    always-reject (spiteful), 0.5 = mixed. Choices are shuffled across the
    (off-grid) demo offers so the set demonstrates a graded propensity rather
    than a sharp, leak-prone acceptance threshold.

    ``with_reasoning`` toggles few-shot CoT (reasoning then answer) vs. plain
    few-shot (answer only).
    """

    rng = random.Random(seed)
    offers = list(DEMO_OFFERS)
    rng.shuffle(offers)
    k = len(offers)
    n_accept = round(accept_fraction * k)
    choices = ["accept"] * n_accept + ["reject"] * (k - n_accept)
    rng.shuffle(choices)

    blocks = []
    for offer, choice in zip(offers, choices):
        question = (
            "Q: The proposer offers you "
            f"{offer} tokens out of 100. If you accept, you receive the offer. "
            "If you reject, both players receive 0. Do you accept or reject?"
        )
        if with_reasoning:
            if choice == "accept":
                answer = (
                    f"A: {offer} out of 100 isn't a lot, but taking it beats walking "
                    "away with nothing. Final answer: accept"
                )
            else:
                answer = (
                    f"A: {offer} out of 100 is a lopsided split; I'd rather we both get "
                    "nothing than reward an unfair offer. Final answer: reject"
                )
        else:
            answer = f"A: Final answer: {choice}"
        blocks.append(f"{question}\n{answer}")

    return "Here are example responses:\n\n" + "\n\n".join(blocks) + "\n\n"


def make_scenarios(*, fewshot_block: str = "", cot_instruction: str = "") -> list[dict[str, object]]:
    """Offer sweep with per-condition few-shot / CoT injection fields."""

    return [
        {
            "offer": offer,
            "fewshot_block": fewshot_block,
            "cot_instruction": cot_instruction,
        }
        for offer in OFFER_SWEEP
    ]


def parse_behavior(unit: dict[str, object]) -> dict[str, int]:
    """Extract the accept/reject choice from a free-text (possibly CoT) response.

    Reads the LAST ``Final answer: (accept|reject)`` marker; falls back to the
    last bare keyword only if no marker is present.
    """

    text = str(unit.get("answer_text", "")) or str(unit.get("response_text", ""))
    matches = _FINAL_ANSWER.findall(text)
    if matches:
        return {"accept_offer": int(matches[-1].lower() == "accept"), "parse_ok": 1}

    low = text.lower()
    last_accept = low.rfind("accept")
    last_reject = low.rfind("reject")
    if last_accept == -1 and last_reject == -1:
        return {"accept_offer": 0, "parse_ok": 0}
    return {"accept_offer": int(last_accept > last_reject), "parse_ok": 0}


def build_game_spec() -> GameSpec:
    """Build the strengthened-prompting ultimatum game spec."""

    mock = "Reasoning: deterministic smoke response. Final answer: accept"

    conditions = [
        ConditionSpec(
            name="baseline",
            description="Free-text elicitation, no demonstrations, no CoT.",
            scenarios=make_scenarios(),
            value_field="offer",
        ),
        ConditionSpec(
            name="persona",
            description="Accept-leaning persona instruction (original weak prompting baseline).",
            instruction=PERSONA_INSTRUCTION,
            scenarios=make_scenarios(),
            value_field="offer",
        ),
        ConditionSpec(
            name="cot",
            description="Zero-shot chain-of-thought, no demonstrations.",
            scenarios=make_scenarios(cot_instruction=COT_INSTRUCTION),
            value_field="offer",
        ),
        ConditionSpec(
            name="fewshot",
            description="Few-shot demonstrations (accept-leaning), no reasoning in demos.",
            scenarios=make_scenarios(
                fewshot_block=build_demo_block(1.0, with_reasoning=False),
            ),
            value_field="offer",
        ),
    ]

    # Bidirectional few-shot CoT dose-response. dose100 (always accept) is the
    # headline altruistic strong baseline; the family traces controllability.
    for fraction in (0.0, 0.25, 0.5, 0.75, 1.0):
        conditions.append(
            ConditionSpec(
                name=f"fewshot_cot_dose{int(fraction * 100):03d}",
                description=f"Few-shot CoT with {int(fraction * 100)}% accepting exemplars.",
                scenarios=make_scenarios(
                    fewshot_block=build_demo_block(fraction, with_reasoning=True),
                    cot_instruction=COT_INSTRUCTION,
                ),
                value_field="offer",
            )
        )

    return GameSpec(
        game_id="ultimatum_strong_prompting",
        title="Ultimatum Game (Strong Prompting Baselines)",
        description=(
            "Ultimatum game with strengthened prompting baselines: few-shot and "
            "chain-of-thought, plus a bidirectional few-shot-CoT acceptance dose-response."
        ),
        agents=AgentSpec(count=40, subject_prefix="U"),
        default_model_id="meta-llama/Llama-3.3-70B-Instruct",
        questions=[
            QuestionSpec(
                question_name="ultimatum_response",
                question_type="free_text",
                question_text=QUESTION_TEXT,
                mock_response=mock,
            )
        ],
        conditions=conditions,
        behavior_metrics=[
            BehaviorMetric(
                name="accept_offer",
                description="1 if the responder accepted the offer, else 0.",
            )
        ],
        behavior_parser=parse_behavior,
    )
