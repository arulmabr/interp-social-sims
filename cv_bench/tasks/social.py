"""Social-domain trial generators (ICLR_PLAN.md B1).

Ultimatum responder and proposer, Dictator Game (A7), mini-ultimatum, and an
accept-bias control. Payoffs are degenerate lotteries so these trials share the
`Trial` machinery, its split assignment and its chat-template rendering with the
risk domain; canonical index 0 is always the passive option (reject, or keep
nothing extra), so a positive logit difference means more accepting.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from cv_bench.tasks.core import (
    Format, Lottery, Trial, assign_split, check_test_access, formats_for_split,
)

PIES: Tuple[float, ...] = (20.0, 100.0, 1000.0)
OFFER_FRACTIONS: Tuple[float, ...] = tuple(i / 100 for i in range(0, 105, 5))

#: The proposer's offer in the mini-ultimatum, and the alternatives it is judged
#: against. `None` means the offer was made with no alternative available.
MINI_OFFER = (8.0, 2.0)
MINI_ALTERNATIVES: Tuple[Optional[Tuple[float, float]], ...] = (
    (5.0, 5.0), (2.0, 8.0), (10.0, 0.0), None,
)


def _default_format(split: str, label_sets: Sequence[str]) -> Format:
    available = formats_for_split(split, label_sets=label_sets)
    if not available:
        raise KeyError(f"no formats available for split {split!r}")
    return available[0]


def _social_trial(family: str, params: Dict[str, float],
                  passive: float, active: float, split: str,
                  is_catch: bool = False) -> Trial:
    """A trial whose two options pay `passive` and `active` for sure."""
    canonical = (Lottery(((1.0, passive),)), Lottery(((1.0, active),)))
    # `dominant` means "a choice no preference in scope explains", not merely
    # "less money". Accepting always pays a responder at least as much as
    # rejecting, but rejecting a low offer is inequity aversion, which is the
    # preference under study — marking it dominated would score every fairness
    # driven rejection as a dominance violation. So dominance is recorded only
    # on catch trials, where by construction no preference explains the choice.
    dominant = None
    if is_catch and active != passive:
        dominant = 1 if active > passive else 0
    return Trial(
        domain="social",
        family=family,
        params=tuple(sorted(params.items())),
        canonical=canonical,
        split=split,
        frame_role="heldout",       # core frames are sure-gain risk trials only
        fmt=_default_format(split, ("accept_reject", "neutral")),
        is_catch=is_catch,
        dominant=dominant,
    )


def generate_responder(splits: Sequence[str] = ("disc", "sel", "cal"),
                       pies: Sequence[float] = PIES,
                       unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Ultimatum responder: accept the offer, or reject and both get nothing.

    Offers of at least half the pie are catch trials: rejecting one costs the
    responder money to punish a split that favours them, which no preference in
    the model's range explains.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="social.generate_responder")

    for pie in pies:
        for i, frac in enumerate(OFFER_FRACTIONS):
            split = assign_split(i)
            if split not in wanted:
                continue
            offer = float(round(pie * frac, 2))
            yield _social_trial(
                "responder", {"pie": pie, "offer": offer, "offer_frac": frac},
                passive=0.0, active=offer, split=split,
                is_catch=frac >= 0.5,
            )


def generate_proposer(splits: Sequence[str] = ("disc", "sel", "cal"),
                      pies: Sequence[float] = PIES,
                      unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Ultimatum proposer: offer this much, or keep the pie whole and risk rejection."""
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="social.generate_proposer")

    for pie in pies:
        for i, frac in enumerate(OFFER_FRACTIONS):
            split = assign_split(i)
            if split not in wanted:
                continue
            offer = float(round(pie * frac, 2))
            yield _social_trial(
                "proposer", {"pie": pie, "offer": offer, "offer_frac": frac},
                passive=pie - offer, active=offer, split=split,
            )


def generate_dictator(splits: Sequence[str] = ("disc", "sel", "cal"),
                      pies: Sequence[float] = PIES,
                      unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Dictator Game (A7): give this much, with no possibility of rejection.

    The contrast with the proposer separates fairness from fear of rejection.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="social.generate_dictator")

    for pie in pies:
        for i, frac in enumerate(OFFER_FRACTIONS):
            split = assign_split(i)
            if split not in wanted:
                continue
            give = float(round(pie * frac, 2))
            yield _social_trial(
                "dictator", {"pie": pie, "give": give, "give_frac": frac},
                passive=pie - give, active=give, split=split,
            )


def generate_mini_ultimatum(splits: Sequence[str] = ("disc", "sel", "cal"),
                            unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """The (8, 2) offer judged against what the proposer could have done instead.

    The offer is identical in every trial; only the foregone alternative moves,
    so any change in acceptance is a judgement about intention rather than about
    the amount.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="social.generate_mini_ultimatum")

    # The four alternatives are experimental *conditions*, not reward levels, so
    # they are replicated across splits rather than divided between them. Split
    # assignment by condition index would put each condition in exactly one
    # split and the no-alternative condition in the locked test split, which
    # silently deletes it and confounds condition with split.
    for split in sorted(wanted):
        for alt in MINI_ALTERNATIVES:
            params: Dict[str, float] = {
                "proposer_keeps": MINI_OFFER[0], "responder_gets": MINI_OFFER[1],
                "alt_proposer": -1.0 if alt is None else alt[0],
                "alt_responder": -1.0 if alt is None else alt[1],
                "has_alternative": 0.0 if alt is None else 1.0,
            }
            yield _social_trial("mini_ultimatum", params,
                                passive=0.0, active=MINI_OFFER[1], split=split)


def generate_accept_bias_control(splits: Sequence[str] = ("disc", "sel", "cal"),
                                 unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Accept/reject and yes/no items with an objectively correct answer.

    These carry no social content, so a shift here is a response bias and not a
    change in social preference. Every item is a catch trial.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="social.generate_accept_bias_control")

    items: List[Tuple[str, bool]] = [
        ("The number 7 is greater than the number 3.", True),
        ("The number 2 is greater than the number 9.", False),
        ("A triangle has three sides.", True),
        ("A week contains ten days.", False),
        ("Water freezes at a lower temperature than it boils.", True),
        ("The letter B comes before the letter A in the alphabet.", False),
        ("Twelve is divisible by four.", True),
        ("Fifteen is an even number.", False),
        ("A square has four sides.", True),
        ("A decade is shorter than a year.", False),
        ("The number 100 is greater than the number 10.", True),
        ("Five plus five equals eleven.", False),
        ("January comes before March.", True),
        ("The letter Z comes before the letter M in the alphabet.", False),
        ("Ten is divisible by five.", True),
        ("Twenty is smaller than seven.", False),
    ]
    for i, (claim, truth) in enumerate(items):
        split = assign_split(i)
        if split not in wanted:
            continue
        # The "accept" option is correct exactly when the claim is true, so a
        # bias toward accepting shows up as errors on the false items.
        yield _social_trial(
            "accept_bias_control",
            {"index": float(i), "truth": 1.0 if truth else 0.0},
            passive=0.0 if truth else 1.0,
            active=1.0 if truth else 0.0,
            split=split, is_catch=True,
        )


def generate_social(splits: Sequence[str] = ("disc", "sel", "cal"),
                    unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Every social trial whose split is in ``splits``, format-free."""
    for gen in (generate_responder, generate_proposer, generate_dictator):
        yield from gen(splits=splits, unlock_test=unlock_test)
    yield from generate_mini_ultimatum(splits=splits, unlock_test=unlock_test)
    yield from generate_accept_bias_control(splits=splits, unlock_test=unlock_test)
