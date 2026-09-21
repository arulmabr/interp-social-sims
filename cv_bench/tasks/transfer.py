"""Transfer battery (ICLR_PLAN.md B1, A11): Holt-Laury, Gneezy-Potters, Eckel-Grossman.

These are standard elicitation instruments from the experimental-economics
literature. They exist to test whether a direction found on the project's own
trials moves behaviour on instruments it was never fitted to, so the plan says
they are **never used for selection or calibration**. That is enforced here:
asking for the `sel` or `cal` split raises.
"""

from __future__ import annotations

from typing import Dict, Iterator, Optional, Sequence, Tuple

from cv_bench.tasks.core import (
    Format, Lottery, Trial, check_test_access, check_transfer_access,
    formats_for_split,
)


class TransferMisuse(RuntimeError):
    """Raised when the transfer battery is asked for a selection split."""


# Each instrument is a fixed, standard ladder that is only interpretable whole:
# Holt-Laury's switching point needs all ten decisions. So an instrument is
# replicated in full within each requested split rather than divided across
# splits by item index, which would leave three of ten decisions per split and
# no switching point to find. See logs/B_DECISIONS.md BD5.


#: Holt-Laury: ten paired choices, safe (2.00, 1.60) against risky (3.85, 0.10),
#: with the probability of the better outcome rising from 0.1 to 1.0.
HL_SAFE = (2.00, 1.60)
HL_RISKY = (3.85, 0.10)
HL_PROBS: Tuple[float, ...] = tuple(round(0.1 * i, 1) for i in range(1, 11))

#: Gneezy-Potters: invest part of a 100 endowment; the investment returns 2.5x
#: with probability 0.5 and nothing otherwise.
GP_ENDOWMENT = 100.0
GP_MULTIPLIER = 2.5
GP_LEVELS: Tuple[float, ...] = tuple(float(x) for x in range(10, 110, 10))

#: Eckel-Grossman: a menu of 50/50 gambles of rising risk and return, presented
#: as choices between adjacent menu items.
EG_MENU: Tuple[Tuple[float, float], ...] = (
    (28.0, 28.0), (24.0, 36.0), (20.0, 44.0), (16.0, 52.0), (12.0, 60.0), (2.0, 70.0),
)


def _guard(splits: Sequence[str], unlock_test: Optional[str], caller: str,
           role: str) -> set:
    # Evaluation-only: the unmodified model and the anchors may run now, every
    # intervention family waits for B9's committed predictions.
    check_transfer_access(role, caller)
    wanted = set(splits)
    forbidden = wanted & {"sel", "cal"}
    if forbidden:
        raise TransferMisuse(
            f"the transfer battery may never be used for selection or calibration "
            f"(ICLR_PLAN.md B1, A11); refusing split(s) {sorted(forbidden)}. "
            f"Generate it on 'disc', or on 'test' after unlock, and report it as transfer."
        )
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller=caller)
    return wanted


def _default_format(split: str) -> Format:
    available = formats_for_split(split, label_sets=("legacy", "neutral"))
    if not available:
        raise KeyError(f"no formats available for split {split!r}")
    return available[0]


def _trial(family: str, params: Dict[str, float],
           canonical: Tuple[Lottery, Lottery], split: str) -> Trial:
    return Trial(
        domain="transfer",
        family=family,
        params=tuple(sorted(params.items())),
        canonical=canonical,
        split=split,
        frame_role="heldout",
        fmt=_default_format(split),
        is_catch=False,
        dominant=None,
    )


def generate_holt_laury(role: str,
                            splits: Sequence[str] = ("disc",),
                            unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Ten paired choices; the switching point is the risk-aversion measure."""
    wanted = _guard(splits, unlock_test, "transfer.generate_holt_laury", role)
    for split in sorted(wanted):
      for i, p in enumerate(HL_PROBS):
        safe = Lottery(((p, HL_SAFE[0]), (1.0 - p, HL_SAFE[1]))) if p < 1.0 \
            else Lottery(((1.0, HL_SAFE[0]),))
        risky = Lottery(((p, HL_RISKY[0]), (1.0 - p, HL_RISKY[1]))) if p < 1.0 \
            else Lottery(((1.0, HL_RISKY[0]),))
        yield _trial("holt_laury", {"p": p, "decision": float(i + 1)},
                     (safe, risky), split)


def generate_gneezy_potters(role: str,
                                splits: Sequence[str] = ("disc",),
                                unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Invest part of an endowment at a 50% chance of a 2.5x return."""
    wanted = _guard(splits, unlock_test, "transfer.generate_gneezy_potters", role)
    for split in sorted(wanted):
      for i, invest in enumerate(GP_LEVELS):
        keep = Lottery(((1.0, GP_ENDOWMENT),))
        won = GP_ENDOWMENT - invest + GP_MULTIPLIER * invest
        lost = GP_ENDOWMENT - invest
        risky = Lottery(((0.5, won), (0.5, lost)))
        yield _trial("gneezy_potters",
                     {"invest": invest, "endowment": GP_ENDOWMENT,
                      "multiplier": GP_MULTIPLIER},
                     (keep, risky), split)


def generate_eckel_grossman(role: str,
                                splits: Sequence[str] = ("disc",),
                                unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Choices between adjacent rungs of a menu of 50/50 gambles."""
    wanted = _guard(splits, unlock_test, "transfer.generate_eckel_grossman", role)
    for split in sorted(wanted):
      for i in range(len(EG_MENU) - 1):
        lo_a, hi_a = EG_MENU[i]
        lo_b, hi_b = EG_MENU[i + 1]
        tighter = Lottery(((0.5, lo_a), (0.5, hi_a)))
        wider = Lottery(((0.5, lo_b), (0.5, hi_b)))
        yield _trial("eckel_grossman",
                     {"rung": float(i + 1), "low_a": lo_a, "high_a": hi_a,
                      "low_b": lo_b, "high_b": hi_b},
                     (tighter, wider), split)


def generate_transfer(role: str,
                      splits: Sequence[str] = ("disc",),
                      unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """The whole battery. Defaults to `disc`; `sel` and `cal` are refused.

    ``role`` is required and has no default: a caller must say who is about to
    look at the battery, because it is evaluation-only until B9's predictions
    are committed. Pass "unmodified" or "anchor" before then.
    """
    yield from generate_holt_laury(role, splits, unlock_test)
    yield from generate_gneezy_potters(role, splits, unlock_test)
    yield from generate_eckel_grossman(role, splits, unlock_test)
