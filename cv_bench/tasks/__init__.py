"""Track B trial generators, formats and splits (ICLR_PLAN.md B1)."""

from cv_bench.tasks.core import (
    DOMAIN_LABEL_SETS, LABEL_SETS, RESPONSE_FORMATS, SPLITS, TEMPLATES,
    Format, Lottery, TestSplitLocked, Trial,
    assign_split, body_text, check_test_access, describe, expand_formats,
    formats_for_split, frame_role, instruction_text, prompt_text,
    render_raw_unsafe, statewise_dominates, to_trial_spec,
)

__all__ = [
    "DOMAIN_LABEL_SETS", "LABEL_SETS", "RESPONSE_FORMATS", "SPLITS", "TEMPLATES",
    "Format", "Lottery", "TestSplitLocked", "Trial",
    "assign_split", "body_text", "check_test_access", "describe", "expand_formats",
    "formats_for_split", "frame_role", "instruction_text", "prompt_text",
    "render_raw_unsafe", "statewise_dominates", "to_trial_spec",
]
