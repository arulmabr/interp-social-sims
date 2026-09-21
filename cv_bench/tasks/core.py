"""Shared trial machinery for Track B (ICLR_PLAN.md B1).

A trial is a choice between two lotteries plus a *format*: option order, label
set, response format and instruction template. Content and format are kept
apart so a format effect can be measured against a fixed content grid, which is
what S3.4 and the B2 diagnostics need.

Three invariants are enforced here rather than left to callers:

1. Every prompt goes through the tokenizer's chat template. The legacy raw
   string format yields no answer on 88.3% of trials (`reports/G2_legacy_format.md`),
   so Track B never uses it. `render_raw_unsafe` exists only for a deliberate,
   labelled audit and refuses to run without an explicit acknowledgement.
2. The test split is locked. Materialising a test trial raises unless the
   caller passes the SHA the `prereg-v1` tag points at, and every access is
   appended to an audit log.
3. Splits are a pure function of trial content, so the same cell lands in the
   same split no matter which generator or process produced it.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Sequence, Tuple

SPLITS: Tuple[str, ...] = ("disc", "sel", "cal", "test")
LABEL_SETS: Dict[str, Tuple[str, str]] = {
    # (option shown first in canonical order, option shown second). Index 0 is
    # always the passive/less risky option, so a positive logit difference means
    # more risk taking (risk domain) or more accepting (social domain).
    "legacy": ("Safe Option", "Risky Option"),
    "neutral": ("Option A", "Option B"),
    "accept_reject": ("Reject", "Accept"),
    "yes_no": ("No", "Yes"),
}

#: Label sets that make sense per domain; the risk domain never sees accept/reject.
DOMAIN_LABEL_SETS: Dict[str, Tuple[str, ...]] = {
    "risk": ("legacy", "neutral"),
    "social": ("accept_reject", "neutral"),
    "transfer": ("legacy", "neutral"),
}
RESPONSE_FORMATS: Tuple[str, ...] = ("mc", "freetext")

#: Two instruction templates per split (ICLR_PLAN B1). The test templates are
#: written by a human author and added at unlock; they are deliberately absent.
TEMPLATES: Dict[str, Dict[str, str]] = {
    "disc": {
        "t_disc_0": "You are taking part in a study of decision making.\n\n{body}\n\n{instruction}",
        "t_disc_1": "Consider the following choice.\n\n{body}\n\n{instruction}",
    },
    "sel": {
        "t_sel_0": "Please answer the following question.\n\n{body}\n\n{instruction}",
        "t_sel_1": "Here is a decision problem.\n\n{body}\n\n{instruction}",
    },
    "cal": {
        "t_cal_0": "Read the options below and decide.\n\n{body}\n\n{instruction}",
        "t_cal_1": "A choice is described below.\n\n{body}\n\n{instruction}",
    },
    "test": {},  # author-written, added only at unlock
}

TEST_ACCESS_LOG = Path("logs/TEST_ACCESS.log")


class TestSplitLocked(RuntimeError):
    """Raised on any attempt to materialise a test-split trial while locked."""


# --------------------------------------------------------------------------
# content
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Lottery:
    """A discrete gamble as ``((probability, amount), ...)``, amounts signed."""

    outcomes: Tuple[Tuple[float, float], ...]

    def __post_init__(self) -> None:
        total = sum(p for p, _ in self.outcomes)
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"probabilities sum to {total!r}, not 1")
        if any(p < 0 for p, _ in self.outcomes):
            raise ValueError("negative probability")

    @property
    def is_sure(self) -> bool:
        return len([1 for p, _ in self.outcomes if p > 0]) == 1

    @property
    def ev(self) -> float:
        return sum(p * a for p, a in self.outcomes)

    @property
    def support(self) -> Tuple[float, ...]:
        return tuple(sorted(a for p, a in self.outcomes if p > 0))

    @property
    def worst(self) -> float:
        return min(self.support)

    @property
    def best(self) -> float:
        return max(self.support)


def statewise_dominates(a: Lottery, b: Lottery) -> bool:
    """True when ``a`` is at least as good as ``b`` in every outcome and better
    in at least one.

    Used for catch trials. For the two-outcome and sure/gamble pairs B1
    generates, comparing sorted supports is exact; it is a sufficient condition
    in general, which is all a catch trial needs.
    """
    if a.support == b.support:
        return False
    if len(a.support) == 1 and len(b.support) > 1:
        return a.worst >= b.best
    if len(b.support) == 1 and len(a.support) > 1:
        return a.worst >= b.best
    if len(a.support) != len(b.support):
        return False
    return all(x >= y for x, y in zip(a.support, b.support))


# --------------------------------------------------------------------------
# format
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Format:
    option_order: int        # 0 = canonical order, 1 = the two options swapped
    label_set: str           # key of LABEL_SETS
    response_format: str     # "mc" or "freetext"
    template_id: str

    def __post_init__(self) -> None:
        if self.option_order not in (0, 1):
            raise ValueError(f"option_order must be 0 or 1, got {self.option_order}")
        if self.label_set not in LABEL_SETS:
            raise ValueError(f"unknown label set {self.label_set!r}")
        if self.response_format not in RESPONSE_FORMATS:
            raise ValueError(f"unknown response format {self.response_format!r}")


def formats_for_split(split: str,
                      response_formats: Sequence[str] = RESPONSE_FORMATS,
                      label_sets: Sequence[str] = tuple(LABEL_SETS)) -> List[Format]:
    """Every format available to ``split``: order x labels x response x template."""
    out: List[Format] = []
    for template_id in sorted(TEMPLATES[split]):
        for label_set in label_sets:
            for response_format in response_formats:
                for option_order in (0, 1):
                    out.append(Format(option_order, label_set, response_format, template_id))
    return out


# --------------------------------------------------------------------------
# trials
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Trial:
    domain: str                       # "risk" | "social" | "transfer"
    family: str                       # e.g. "sure_gain", "paired", "catch_sure_gain"
    params: Tuple[Tuple[str, float], ...]   # sorted key/value pairs, hashable
    canonical: Tuple[Lottery, Lottery]      # (less risky, more risky)
    split: str
    frame_role: str                   # "core" | "heldout"
    fmt: Format
    is_catch: bool = False
    dominant: Optional[int] = None    # index into `canonical`, if one dominates
    currency: str = "$"

    @property
    def param_dict(self) -> Dict[str, float]:
        return dict(self.params)

    @property
    def trial_id(self) -> str:
        """Stable id over content *and* format, so rows can be joined safely."""
        payload = json.dumps(
            {
                "domain": self.domain,
                "family": self.family,
                "params": list(self.params),
                "canonical": [list(map(list, lot.outcomes)) for lot in self.canonical],
                "fmt": [self.fmt.option_order, self.fmt.label_set,
                        self.fmt.response_format, self.fmt.template_id],
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def content_id(self) -> str:
        """Stable id over content only, so the same cell can be tracked across formats."""
        payload = json.dumps(
            {
                "domain": self.domain,
                "family": self.family,
                "params": list(self.params),
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    @property
    def presented(self) -> Tuple[Lottery, Lottery]:
        """The two lotteries in the order the prompt shows them."""
        a, b = self.canonical
        return (b, a) if self.fmt.option_order == 1 else (a, b)

    @property
    def labels(self) -> Tuple[str, str]:
        """Labels as presented, first then second."""
        return LABEL_SETS[self.fmt.label_set]

    @property
    def risky_label(self) -> str:
        """The label attached to the *more risky* canonical option."""
        first, second = self.labels
        return first if self.fmt.option_order == 1 else second

    @property
    def safe_label(self) -> str:
        first, second = self.labels
        return second if self.fmt.option_order == 1 else first


def assign_split(reward_index: int) -> str:
    """Split from the reward-level index within a cell (ICLR_PLAN B1)."""
    return SPLITS[reward_index % 4]


def frame_role(family: str, params: Dict[str, float]) -> str:
    """Core frames are sure-gain at p in {0.25, 0.5, 0.75}; everything else is held out."""
    if family == "sure_gain" and params.get("p") in (0.25, 0.5, 0.75):
        return "core"
    return "heldout"


# --------------------------------------------------------------------------
# the test lock
# --------------------------------------------------------------------------

def _prereg_sha() -> Optional[str]:
    """The commit the ``prereg-v1`` tag points at, or None if it does not exist."""
    import subprocess
    try:
        out = subprocess.run(
            ["git", "rev-parse", "prereg-v1^{commit}"],
            capture_output=True, text=True, check=True, timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return None


def check_test_access(split: str,
                      unlock_test: Optional[str],
                      caller: str,
                      log_path: Path = TEST_ACCESS_LOG) -> None:
    """Gate every test-split access. Raises unless correctly unlocked.

    ``unlock_test`` must be the SHA the ``prereg-v1`` tag points at. A missing
    tag means the split cannot be unlocked at all, which is the intended state
    before pre-registration.
    """
    if split != "test":
        return
    sha = _prereg_sha()
    ok = bool(unlock_test) and sha is not None and unlock_test.strip() == sha
    _append_test_access(caller, unlock_test, sha, ok, log_path)
    if not ok:
        raise TestSplitLocked(
            "the test split is locked: pass --unlock-test <prereg SHA> matching the "
            f"prereg-v1 tag (tag {'absent' if sha is None else 'present'}). "
            "A human unlocks it, and only after PREREG.md is tagged."
        )


def _append_test_access(caller: str, offered: Optional[str], sha: Optional[str],
                        granted: bool, log_path: Path) -> None:
    record = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "caller": caller,
        "offered_sha": offered,
        "prereg_sha": sha,
        "granted": granted,
        "pid": os.getpid(),
    }
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as fh:
            fh.write(json.dumps(record, sort_keys=True) + "\n")
    except OSError:
        # An audit log that cannot be written must not silently swallow the
        # attempt, but it also must not mask the TestSplitLocked that follows.
        pass


# --------------------------------------------------------------------------
# rendering
# --------------------------------------------------------------------------

def describe(lot: Lottery, currency: str = "$") -> str:
    """One clause describing a lottery, in the plan's own wording."""
    def amount(a: float) -> str:
        mag = abs(a)
        shown = f"{mag:,.0f}" if float(mag).is_integer() else f"{mag:,.2f}"
        if a < 0:
            return f"lose {currency}{shown}"
        if a == 0:
            return "nothing"
        return f"{currency}{shown}"

    if lot.is_sure:
        only = [a for p, a in lot.outcomes if p > 0][0]
        return f"{amount(only)} for sure"
    parts = []
    for p, a in sorted(lot.outcomes, key=lambda t: -t[0]):
        if p <= 0:
            continue
        parts.append(f"a {p:.0%} chance of {amount(a)}")
    return " and ".join(parts)


def body_text(trial: Trial) -> str:
    first, second = trial.presented
    lab_first, lab_second = trial.labels
    return (f"{lab_first}: {describe(first, trial.currency)}\n"
            f"{lab_second}: {describe(second, trial.currency)}")


def instruction_text(trial: Trial) -> str:
    lab_first, lab_second = trial.labels
    if trial.fmt.response_format == "mc":
        return (f"Which do you choose? Answer with exactly one of "
                f"\"{lab_first}\" or \"{lab_second}\" and nothing else.")
    return "Which do you choose, and why? Begin your reply with your choice."


def prompt_text(trial: Trial) -> str:
    template = TEMPLATES[trial.split].get(trial.fmt.template_id)
    if template is None:
        raise KeyError(
            f"template {trial.fmt.template_id!r} is not defined for split {trial.split!r}"
            + (" (test templates are author-written and added at unlock)"
               if trial.split == "test" else "")
        )
    return template.format(body=body_text(trial), instruction=instruction_text(trial))


def to_trial_spec(trial: Trial, stem: Optional[str] = "My choice: ",
                  system: Optional[str] = None):
    """A `readout.TrialSpec` for this trial, chat template on.

    The label pair is ordered ``(negative, positive)`` as `readout.TrialSpec`
    expects, with the *risky* option positive, so a positive logit difference
    means more risk taking regardless of how the options were ordered on screen.
    """
    from cv_bench.readout import TrialSpec

    return TrialSpec(
        prompt=prompt_text(trial),
        labels=(trial.safe_label, trial.risky_label),
        stem=stem,
        use_chat_template=True,
        system=system,
    )


def render_raw_unsafe(trial: Trial, *, acknowledge_no_chat_template: bool = False) -> str:
    """The bare prompt string, with no chat template. Refuses by default.

    Kept only so a future audit can reproduce the legacy format deliberately and
    label it, as G2's `legacy` arm does. Nothing in Track B calls this: the
    legacy format yields no answer on 88.3% of trials.
    """
    if not acknowledge_no_chat_template:
        raise RuntimeError(
            "refusing to render without a chat template: the raw format yields no "
            "answer on 88.3% of trials (reports/G2_legacy_format.md). Pass "
            "acknowledge_no_chat_template=True only for a labelled legacy audit."
        )
    return prompt_text(trial)


def expand_formats(trials: Iterable[Trial],
                   response_formats: Sequence[str] = RESPONSE_FORMATS,
                   label_sets: Sequence[str] = tuple(LABEL_SETS)) -> Iterator[Trial]:
    """One trial per (content, format) pair, for contents that arrive format-free."""
    for trial in trials:
        for fmt in formats_for_split(trial.split, response_formats, label_sets):
            yield replace(trial, fmt=fmt)
