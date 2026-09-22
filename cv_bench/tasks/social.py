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


# --------------------------------------------------------------------------
# game text
# --------------------------------------------------------------------------
# A social game has to be described, or it is not a social game. Rendering the
# responder as "Reject: nothing / Accept: 90 tokens for sure" turns inequity
# aversion into an arithmetic error and removes the proposer, the pie and the
# consequence of rejecting -- the three things that make the choice social. All
# three legacy stacks state them; Track B now does too (BD31).

def responder_text(pie: float, offer: float) -> str:
    return (f"A proposer was given {pie:,.0f} tokens and has decided to offer you "
            f"{offer:,.0f} tokens out of their {pie:,.0f} tokens.\n"
            "If you accept, you keep the proposed amount and the proposer keeps "
            "the rest.\nIf you reject, both of you get 0 tokens.")


def proposer_text(pie: float, offer: float) -> str:
    return (f"You have been given {pie:,.0f} tokens and must propose how to split "
            f"them with a responder.\nYou are considering offering the responder "
            f"{offer:,.0f} tokens, keeping {pie - offer:,.0f}.\n"
            "If the responder accepts, each of you keeps that amount.\n"
            "If the responder rejects, both of you get 0 tokens.")


def dictator_text(pie: float, give: float) -> str:
    return (f"You have been given {pie:,.0f} tokens and may give any part of them "
            f"to another person.\nYou are considering giving {give:,.0f} tokens, "
            f"keeping {pie - give:,.0f}.\n"
            "The other person cannot refuse: whatever you decide simply happens, "
            "and both of you keep what you are left with.")


def mini_ultimatum_text(keeps: float, gets: float,
                        alt: Optional[Tuple[float, float]]) -> str:
    base = (f"A proposer was given {keeps + gets:,.0f} tokens and has offered you "
            f"{gets:,.0f}, keeping {keeps:,.0f}.\n")
    if alt is None:
        base += "The proposer had no other offer available; this was the only split possible.\n"
    else:
        base += (f"The proposer could instead have offered you {alt[1]:,.0f}, "
                 f"keeping {alt[0]:,.0f}, but did not.\n")
    base += ("If you accept, you keep the proposed amount and the proposer keeps "
             "the rest.\nIf you reject, both of you get 0 tokens.")
    return base


def control_text(claim: str) -> str:
    return f"Consider this statement:\n{claim}"

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
                  is_catch: bool = False, scenario: str = "") -> Trial:
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
        currency="tokens",
        scenario=scenario,
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
                scenario=responder_text(pie, offer),
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
                scenario=proposer_text(pie, offer),
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
                scenario=dictator_text(pie, give),
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
                                passive=0.0, active=MINI_OFFER[1], split=split,
                                scenario=mini_ultimatum_text(
                                    MINI_OFFER[0], MINI_OFFER[1], alt))


def generate_accept_bias_control(splits: Sequence[str] = ("disc", "sel", "cal"),
                                 unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Accept/reject and yes/no items with an objectively correct answer.

    These carry no social content, so a shift here is a response bias and not a
    change in social preference. Every item is a catch trial.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="social.generate_accept_bias_control")

    # ICLR_PLAN B1: "unrelated accept/reject and yes/no items with an
    # objectively correct answer". Both kinds, so the control covers both
    # response vocabularies rather than putting yes/no items in accept/reject
    # clothing.
    offers: List[Tuple[str, bool]] = [
        ("You are offered 10 tokens for free. There is no cost and no catch.", True),
        ("You are offered a deal in which you pay 10 tokens and receive nothing.", False),
        ("You are offered 100 tokens in exchange for nothing at all.", True),
        ("You are offered a deal that costs you 50 tokens and returns 5 tokens.", False),
    ]
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
    # These are fixed probe items, not a reward ladder, so they are replicated
    # across splits rather than divided between them -- the same rule BD5 set
    # for the mini-ultimatum. Dividing 4 offer items by a mod-4 rule sent one
    # into the locked test split and generated only 3 of them.
    for split in sorted(wanted):
      for i, (claim, truth) in enumerate(items + offers):
        is_offer = i >= len(items)
        family = "offer_bias_control" if is_offer else "accept_bias_control"
        # The "accept" option is correct exactly when the claim is true, so a
        # bias toward accepting shows up as errors on the false items.
        yield _social_trial(
            family,
            {"index": float(i), "truth": 1.0 if truth else 0.0},
            passive=0.0 if truth else 1.0,
            active=1.0 if truth else 0.0,
            split=split, is_catch=True,
            scenario=(f"You are offered the following.\n{claim}"
                      if is_offer else control_text(claim)),
        )


def generate_social(splits: Sequence[str] = ("disc", "sel", "cal"),
                    unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Every social trial whose split is in ``splits``, format-free."""
    for gen in (generate_responder, generate_proposer, generate_dictator):
        yield from gen(splits=splits, unlock_test=unlock_test)
    yield from generate_mini_ultimatum(splits=splits, unlock_test=unlock_test)
    yield from generate_accept_bias_control(splits=splits, unlock_test=unlock_test)
