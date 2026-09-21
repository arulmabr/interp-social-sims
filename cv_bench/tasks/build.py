"""Materialise the Track B trial set (ICLR_PLAN.md B1).

Writes one JSONL row per (content, format) pair. The `prompt` field is the
*user turn*: the chat template is applied at model time by `readout.Readout`,
which `core.to_trial_spec` always asks for. No raw-format prompt is ever
written (logs/B_DECISIONS.md BD4).

CPU only. Run as a Slurm job, never on the login node.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List

from cv_bench.tasks import core, risk, social, transfer

DEFAULT_SHARE = Path("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB")


def git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"],
                             capture_output=True, text=True, check=True, timeout=10)
        return out.stdout.strip()
    except Exception:
        return "nogit"


def row(trial: core.Trial) -> Dict[str, object]:
    first, second = trial.presented
    lab_first, lab_second = trial.labels
    return {
        "trial_id": trial.trial_id,
        "content_id": trial.content_id,
        "domain": trial.domain,
        "family": trial.family,
        "split": trial.split,
        "frame_role": trial.frame_role,
        "params": trial.param_dict,
        "option_order": trial.fmt.option_order,
        "label_set": trial.fmt.label_set,
        "response_format": trial.fmt.response_format,
        "template_id": trial.fmt.template_id,
        "label_first": lab_first,
        "label_second": lab_second,
        "safe_label": trial.safe_label,
        "risky_label": trial.risky_label,
        "text_first": core.describe(first, trial.currency),
        "text_second": core.describe(second, trial.currency),
        "ev_first": first.ev,
        "ev_second": second.ev,
        "is_catch": trial.is_catch,
        "dominant": trial.dominant,
        "prompt": core.prompt_text(trial),
        "use_chat_template": True,
    }


def content_trials(splits) -> List[core.Trial]:
    out = list(risk.generate_risk(splits=splits))
    out += list(social.generate_social(splits=splits))
    # The transfer battery is never used for selection or calibration (A11).
    transfer_splits = tuple(s for s in splits if s not in ("sel", "cal"))
    if transfer_splits:
        out += list(transfer.generate_transfer("unmodified", splits=transfer_splits))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--splits", nargs="+", default=["disc", "sel", "cal"])
    ap.add_argument("--out", type=Path, default=None,
                    help="output directory (default: the lab share, timestamped)")
    ap.add_argument("--unlock-test", default=None,
                    help="SHA of the prereg-v1 tag; required for the test split")
    args = ap.parse_args(argv)

    if "test" in args.splits:
        # Fail loudly and early rather than part way through a write.
        core.check_test_access("test", args.unlock_test, caller="tasks.build")

    sha = git_sha()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out or (DEFAULT_SHARE / "b1_trials" / f"{stamp}_{sha}")
    out_dir.mkdir(parents=True, exist_ok=True)

    contents = content_trials(tuple(args.splits))
    path = out_dir / "trials.jsonl"
    digest = hashlib.sha256()
    n = 0
    counts: Counter = Counter()
    with path.open("w") as fh:
        for trial in core.expand_formats(contents):
            line = json.dumps(row(trial), sort_keys=True, separators=(",", ":"))
            fh.write(line + "\n")
            digest.update((line + "\n").encode())
            counts[(trial.domain, trial.split)] += 1
            n += 1

    summary = {
        "utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "git_sha": sha,
        "splits": list(args.splits),
        "n_content_trials": len(contents),
        "n_rows": n,
        "sha256": digest.hexdigest(),
        "by_domain": dict(Counter(t.domain for t in contents)),
        "by_split": dict(Counter(t.split for t in contents)),
        "by_family": dict(Counter(t.family for t in contents)),
        "by_frame_role": dict(Counter(t.frame_role for t in contents)),
        "n_catch_content": sum(t.is_catch for t in contents),
        "n_dominated_content": sum(t.dominant is not None for t in contents),
        "rows_by_domain_split": {f"{d}/{s}": c for (d, s), c in sorted(counts.items())},
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")

    # A test row must never appear in the output, whatever the arguments were.
    assert not any(k.endswith("/test") for k in summary["rows_by_domain_split"]), \
        "test-split rows reached the output"

    print(json.dumps(summary, indent=2, sort_keys=True))
    print(f"\nwrote {n:,} rows to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
