"""Risk-domain trial generators (ICLR_PLAN.md B1).

Families: sure-gain, sure-loss, mixed (A1), paired (A3), and the three kinds of
catch trial. The starting grid is the plan's and is finalised at B2; the legacy
cell (p = 0.5, s = 50, x = 10..240 step 5) is always present so every new result
has a cell that lines up with the published runs.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Sequence, Tuple

from cv_bench.tasks.core import (
    Format, Lottery, Trial, assign_split, check_test_access, formats_for_split,
    frame_role, statewise_dominates,
)

P_GRID: Tuple[float, ...] = (0.1, 0.25, 0.5, 0.75, 0.9)
S_GRID: Tuple[float, ...] = (20.0, 50.0, 100.0, 500.0)
N_LEVELS = 14                      # the plan allows 12-16
X_LO, X_HI = 0.3, 5.0              # multiples of s/p

#: p = 0.5, s = 50, x = 10..240 in steps of 5 (the cell every legacy curve used).
LEGACY_CELL = (0.5, 50.0)
LEGACY_X: Tuple[float, ...] = tuple(float(n) for n in range(10, 245, 5))


def x_grid(p: float, s: float, n_levels: int = N_LEVELS) -> Tuple[float, ...]:
    """A log grid of reward levels around the risk-neutral point s/p.

    Rounded to whole currency units: the prompts read naturally and the levels
    stay distinct at every (p, s) in the grid.

    Note that the plan's lower bound of 0.3 x s/p puts the bottom of the grid
    below the sure amount whenever p >= X_LO, so at p in {0.5, 0.75, 0.9} the
    lowest few levels are *statewise dominated*: the gamble cannot beat the sure
    thing. Those cells are kept, because they pin the floor of the choice curve
    and a dominated level is a legitimate extreme reward level, but they are
    flagged (`Trial.dominant` is set) so the dominated-choice rate can count
    them and the B2 estimator can weight or exclude them deliberately rather
    than by accident. See logs/B_DECISIONS.md BD5.
    """
    if (p, s) == LEGACY_CELL:
        return LEGACY_X
    centre = s / p
    out: List[float] = []
    for i in range(n_levels):
        mult = X_LO * (X_HI / X_LO) ** (i / (n_levels - 1))
        value = float(round(centre * mult))
        if value not in out:
            out.append(value)
    return tuple(out)


# --------------------------------------------------------------------------
# lottery builders
# --------------------------------------------------------------------------

def sure_gain_pair(p: float, s: float, x: float) -> Tuple[Lottery, Lottery]:
    """s for sure, versus a p chance of x and otherwise nothing."""
    safe = Lottery(((1.0, s),))
    risky = Lottery(((p, x), (1.0 - p, 0.0))) if p < 1.0 else Lottery(((1.0, x),))
    return safe, risky


def sure_loss_pair(p: float, s: float, x: float) -> Tuple[Lottery, Lottery]:
    """Lose s for sure, versus a p chance of losing x and otherwise nothing."""
    safe = Lottery(((1.0, -s),))
    risky = Lottery(((p, -x), (1.0 - p, 0.0))) if p < 1.0 else Lottery(((1.0, -x),))
    return safe, risky


def mixed_pair(gain: float, loss: float) -> Tuple[Lottery, Lottery]:
    """Nothing for sure, versus a 50/50 win of `gain` or loss of `loss` (A1)."""
    safe = Lottery(((1.0, 0.0),))
    risky = Lottery(((0.5, gain), (0.5, -loss)))
    return safe, risky


def paired_pair(m: float, d1: float, d2: float) -> Tuple[Lottery, Lottery]:
    """Two 50/50 gambles around the same mean, the second a wider spread (A3)."""
    if not d2 > d1:
        raise ValueError(f"d2 must exceed d1, got d1={d1!r}, d2={d2!r}")
    tighter = Lottery(((0.5, m + d1), (0.5, m - d1)))
    wider = Lottery(((0.5, m + d2), (0.5, m - d2)))
    return tighter, wider


# --------------------------------------------------------------------------
# generation
# --------------------------------------------------------------------------

def _default_format(split: str) -> Format:
    available = formats_for_split(split)
    if not available:
        raise KeyError(
            f"no formats available for split {split!r}"
            + (" (test templates are author-written and added at unlock)"
               if split == "test" else "")
        )
    return available[0]


def _trial(family: str, params: Dict[str, float],
           canonical: Tuple[Lottery, Lottery], split: str,
           is_catch: bool = False) -> Trial:
    a, b = canonical
    dominant: Optional[int] = None
    if statewise_dominates(a, b):
        dominant = 0
    elif statewise_dominates(b, a):
        dominant = 1
    return Trial(
        domain="risk",
        family=family,
        params=tuple(sorted(params.items())),
        canonical=canonical,
        split=split,
        frame_role=frame_role(family, params),
        fmt=_default_format(split),
        is_catch=is_catch,
        dominant=dominant,
    )


def generate_risk(splits: Sequence[str] = ("disc", "sel", "cal"),
                  p_grid: Sequence[float] = P_GRID,
                  s_grid: Sequence[float] = S_GRID,
                  families: Sequence[str] = ("sure_gain", "sure_loss", "mixed", "paired"),
                  include_catch: bool = True,
                  unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Every risk trial whose split is in ``splits``, format-free.

    Formats are added by `core.expand_formats`; yielding content once keeps the
    grid small enough to reason about and makes the split assignment auditable.
    Requesting the test split raises unless correctly unlocked.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="risk.generate_risk")

    if "sure_gain" in families:
        for p in p_grid:
            for s in s_grid:
                for i, x in enumerate(x_grid(p, s)):
                    split = assign_split(i)
                    if split in wanted:
                        yield _trial("sure_gain", {"p": p, "s": s, "x": x},
                                     sure_gain_pair(p, s, x), split)

    if "sure_loss" in families:
        for p in p_grid:
            for s in s_grid:
                for i, x in enumerate(x_grid(p, s)):
                    split = assign_split(i)
                    if split in wanted:
                        yield _trial("sure_loss", {"p": p, "s": s, "x": x},
                                     sure_loss_pair(p, s, x), split)

    if "mixed" in families:
        # 0 for sure vs 50/50 (+G, -L). L fixed by the s grid, G swept as a
        # multiple of L so the loss-aversion ratio G/L is the reward level.
        for loss in s_grid:
            ratios = [0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0]
            for i, ratio in enumerate(ratios):
                split = assign_split(i)
                if split in wanted:
                    gain = float(round(loss * ratio))
                    yield _trial("mixed", {"G": gain, "L": loss, "ratio": ratio},
                                 mixed_pair(gain, loss), split)

    if "paired" in families:
        # Same mean, two spreads, no sure option. d1 is the tighter spread.
        for m in s_grid:
            for d1_frac in (0.1, 0.25):
                d1 = float(round(m * d1_frac))
                widths = [0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0, 1.2, 1.4, 1.6]
                for i, d2_frac in enumerate(widths):
                    d2 = float(round(m * d2_frac))
                    if d2 <= d1:
                        continue
                    split = assign_split(i)
                    if split in wanted:
                        yield _trial("paired", {"m": m, "d1": d1, "d2": d2},
                                     paired_pair(m, d1, d2), split)

    if include_catch:
        yield from generate_catch(splits=splits, s_grid=s_grid, p_grid=p_grid,
                                  unlock_test=unlock_test)


def generate_catch(splits: Sequence[str] = ("disc", "sel", "cal"),
                   p_grid: Sequence[float] = P_GRID,
                   s_grid: Sequence[float] = S_GRID,
                   unlock_test: Optional[str] = None) -> Iterator[Trial]:
    """Catch trials: one option beats the other in every outcome.

    A model that picks the dominated option is not expressing a preference, so
    the dominated-choice rate is the attention floor the B2 decision rule reads.
    """
    wanted = set(splits)
    for split in sorted(wanted):
        check_test_access(split, unlock_test, caller="risk.generate_catch")

    for p in p_grid:
        for s in s_grid:
            # sure-gain with x <= s: the sure thing dominates the gamble.
            for i, frac in enumerate((0.4, 0.6, 0.8, 1.0)):
                split = assign_split(i)
                if split not in wanted:
                    continue
                x = float(round(s * frac))
                yield _trial("catch_sure_gain", {"p": p, "s": s, "x": x},
                             sure_gain_pair(p, s, x), split, is_catch=True)

            # sure-loss with x <= s: the gamble dominates the sure loss.
            for i, frac in enumerate((0.4, 0.6, 0.8, 1.0)):
                split = assign_split(i)
                if split not in wanted:
                    continue
                x = float(round(s * frac))
                yield _trial("catch_sure_loss", {"p": p, "s": s, "x": x},
                             sure_loss_pair(p, s, x), split, is_catch=True)

    # paired trials where one lottery is better in both outcomes.
    for m in s_grid:
        for i, shift in enumerate((0.1, 0.2, 0.3, 0.4)):
            split = assign_split(i)
            if split not in wanted:
                continue
            d = float(round(m * 0.2))
            bump = float(round(m * shift))
            better = Lottery(((0.5, m + d + bump), (0.5, m - d + bump)))
            worse = Lottery(((0.5, m + d), (0.5, m - d)))
            yield _trial("catch_paired", {"m": m, "d": d, "bump": bump},
                         (worse, better), split, is_catch=True)


def certainty_equivalent_prompt(trial: Trial) -> str:
    """The stated-CE question for a trial's risky option (B1).

    Greedy decoding, one number parsed, unparseable outputs counted rather than
    dropped — the counting happens in the runner, not here.
    """
    from cv_bench.tasks.core import describe
    risky = trial.canonical[1]
    return ("Consider this gamble: " + describe(risky, trial.currency) + ".\n"
            "What is the smallest sure amount you would accept instead of this "
            "gamble? Answer with a single number and nothing else.")


def recall_prompts(trial: Trial) -> Dict[str, str]:
    """Post-decision recall probes (B1): restate the reward level and the sure amount."""
    params = trial.param_dict
    out: Dict[str, str] = {}
    if "x" in params:
        out["x"] = ("In the choice you just made, what was the amount you could win or "
                    "lose if the gamble paid out? Answer with a single number.")
    if "s" in params:
        out["s"] = ("In the choice you just made, what was the amount you would receive "
                    "or lose for sure? Answer with a single number.")
    return out
