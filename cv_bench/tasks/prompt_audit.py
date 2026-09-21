"""Render every prompt cell type verbatim, for author review (item 1).

Writes `reports/B_PROMPT_AUDIT.md`: for each trial family and each
(label set x option order x response format x template), two rendered prompts
exactly as the model sees them after the chat template, followed by the stem and
the exact token ids the readout scores for each label.

The point is that the prompts are checked as *text*, not as code. Two bugs got
through every earlier test because the tests compared the implementation with
itself: option order relabelled the options instead of reordering them, and the
neutral labels shared their first token so z was identically zero. Both are
obvious on sight in a rendered prompt.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")

from cv_bench.tasks import core, risk, social, transfer

MODEL = "meta-llama/Llama-3.1-8B-Instruct"

FAMILY_ORDER = [
    "sure_gain", "sure_loss", "mixed", "paired",
    "catch_sure_gain", "catch_sure_loss", "catch_paired",
    "responder", "proposer", "dictator", "mini_ultimatum", "accept_bias_control",
    "holt_laury", "gneezy_potters", "eckel_grossman",
]


def all_trials() -> List[core.Trial]:
    out = list(core.expand_formats(list(risk.generate_risk())))
    out += list(core.expand_formats(list(social.generate_social())))
    out += list(core.expand_formats(list(transfer.generate_transfer("unmodified"))))
    return out


def cells(trials: Sequence[core.Trial]) -> "OrderedDict[Tuple, List[core.Trial]]":
    """(family, label set, order, response format, template) -> trials."""
    out: "OrderedDict[Tuple, List[core.Trial]]" = OrderedDict()
    for t in sorted(trials, key=lambda x: (FAMILY_ORDER.index(x.family)
                                           if x.family in FAMILY_ORDER else 99,
                                           x.fmt.label_set, x.fmt.option_order,
                                           x.fmt.response_format, x.fmt.template_id,
                                           x.trial_id)):
        key = (t.family, t.fmt.label_set, t.fmt.option_order,
               t.fmt.response_format, t.fmt.template_id)
        out.setdefault(key, []).append(t)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, default=Path("reports/B_PROMPT_AUDIT.md"))
    ap.add_argument("--per-cell", type=int, default=2)
    args = ap.parse_args(argv)

    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(MODEL)

    class _RO:                      # render + token ids without loading a model
        def __init__(self, tok): self.tok = tok
        def render(self, spec):
            if spec.stem is None:
                return spec.prompt
            msgs = ([{"role": "system", "content": spec.system}] if spec.system else [])
            msgs.append({"role": "user", "content": spec.prompt})
            return tok.apply_chat_template(msgs, tokenize=False,
                                           add_generation_prompt=True) + spec.stem
        def ids(self, label):
            return sorted({tok.encode(v, add_special_tokens=False)[0]
                           for v in (label, " " + label)})

    ro = _RO(tok)
    grouped = cells(all_trials())

    L: List[str] = []
    L.append("# B_PROMPT_AUDIT.md — every prompt cell, rendered verbatim\n")
    L.append(f"Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} "
             f"with `{MODEL}`'s chat template and tokenizer.\n")
    L.append("**An author replies \"audit ok\" before B1 is rebuilt.**\n")
    L.append("## What changed since the last build, and why\n")
    L.append("| item | was | now | source |")
    L.append("|---|---|---|---|")
    L.append("| legacy labels | `Safe Option` / `Risky Option` | **`Safe` / `Risky`** | `ICLR_PLAN.md:153` |")
    L.append("| neutral labels | `Option A` / `Option B` | **`A` / `B`** | `ICLR_PLAN.md:153` |")
    L.append("| currency | `$` | **`tokens`** | `Probes/tasks/prompts.py` |")
    L.append("| legacy cell | 10..240, 47 levels | **20..240, 45 levels** | `Probes/config.py:91` |")
    L.append("| option order | swapped the **labels** | **reorders the lines only** | BD28 |")
    L.append("| neutral stem | `Answer: Option` workaround | **`Answer:`** | no longer needed |")
    L.append("")
    L.append("`ICLR_PLAN.md` B1 states the legacy cell as \"10...240 in steps of 5\"; the "
             "published grid in `Probes/config.py` is `range(20, 245, 5)`. The code follows "
             "the paper. **This discrepancy is for the authors.**\n")
    L.append(f"{len(grouped)} distinct cell types.\n")

    label_ids: Dict[str, List[int]] = {}
    for (neg, pos) in core.LABEL_SETS.values():
        for lab in (neg, pos):
            label_ids[lab] = ro.ids(lab)
    L.append("## Token ids the readout scores\n")
    L.append("| label set | negative (safe/reject) | ids | positive (risky/accept) | ids | collide? |")
    L.append("|---|---|---|---|---|---|")
    for name, (neg, pos) in core.LABEL_SETS.items():
        a, b = label_ids[neg], label_ids[pos]
        clash = "**YES — z would be identically zero**" if set(a) & set(b) else "no"
        L.append(f"| {name} | `{neg}` | {a} | `{pos}` | {b} | {clash} |")
    L.append("")

    current = None
    for key, ts in grouped.items():
        family, label_set, order, rf, template = key
        if family != current:
            L.append(f"\n---\n\n# Family: `{family}`\n")
            current = family
        L.append(f"### `{label_set}` · order {order} · {rf} · `{template}`\n")
        spec0 = core.to_trial_spec(ts[0], stem=core.stem_for(ts[0]))
        L.append(f"Stem: `{core.stem_for(ts[0])}` — readout scores "
                 f"`{spec0.negative}` {label_ids.get(spec0.negative)} as negative, "
                 f"`{spec0.positive}` {label_ids.get(spec0.positive)} as positive.\n")
        for t in ts[:args.per_cell]:
            spec = core.to_trial_spec(t, stem=core.stem_for(t))
            L.append(f"<details><summary>{t.trial_id} — {dict(t.params)}</summary>\n")
            L.append("```")
            L.append(ro.render(spec))
            L.append("```")
            L.append("</details>\n")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(L) + "\n")
    print(f"wrote {args.out} — {len(grouped)} cell types, "
          f"{sum(min(len(v), args.per_cell) for v in grouped.values())} prompts")
    return 0


if __name__ == "__main__":
    sys.exit(main())
