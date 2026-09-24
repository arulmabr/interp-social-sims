"""Read Track B's trained anchors on the SAE pilot's own frozen prompts (B8).

The pilot has a preference anchor and a readout gradient but **no planted
bias**, so when its SAE vectors look shortcut-like there is no calibrated
example of a shortcut to compare them against. Track B's bias adapter is
exactly that: a weight-space change that is a constant push and nothing else.

This reads the three existing adapters on the pilot's 432 frozen prompts, in
the pilot's own prompt wording and its own logit-margin units, so its
conditions and these anchors sit on one scale. No adapter is trained here and
no pilot file is written.

    python -m cv_bench.anchors.pilot_read --adapters <dir> --evidence <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from cv_bench.anchors.lora import ADAPTERS, attach_adapters, load_base
from cv_bench.readout import TrialSpec


def specs(evidence: Path) -> tuple[List[TrialSpec], List[Dict]]:
    rows = json.loads((evidence / "frozen_rows.json").read_text())
    out = []
    for r in rows:
        # positive is the gamble, matching the pilot's `margin` sign.
        out.append(TrialSpec(prompt=r["text"],
                             labels=(r["safe_label"], r["risky_label"]),
                             stem="", use_chat_template=True))
    return out, rows


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--adapters", required=True, type=Path)
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--batch", type=int, default=8)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    sp, rows = specs(a.evidence)
    print(f"{len(sp)} pilot frozen prompts", flush=True)
    for name in ADAPTERS:
        if not (a.adapters / f"adapter_{name}.pt").exists():
            raise SystemExit(f"missing adapter_{name}.pt in {a.adapters}")

    model, tok = load_base(a.model)
    from cv_bench.readout import Readout
    peft_model = attach_adapters(model)
    ro = Readout(peft_model, tok)
    from peft import set_peft_model_state_dict

    result: Dict[str, List[float]] = {}
    # The unmodified model first, with every adapter scaled out.
    with peft_model.disable_adapter():
        res = ro.score_batch(sp, batch_size=a.batch)
        result["unmodified"] = [float(r.logit_diff) for r in res]
        print(f"unmodified: mean margin {np.mean(result['unmodified']):+.3f}", flush=True)

    for name in ADAPTERS:
        state = torch.load(a.adapters / f"adapter_{name}.pt", map_location="cpu")
        set_peft_model_state_dict(peft_model, state, adapter_name=name)
        peft_model.set_adapter(name)
        res = ro.score_batch(sp, batch_size=a.batch)
        result[name] = [float(r.logit_diff) for r in res]
        print(f"{name}: mean margin {np.mean(result[name]):+.3f}", flush=True)

    payload = {"n": len(sp), "adapters": result,
               "row_ids": [r["id"] for r in rows]}
    (a.out / "pilot_anchor_margins.json").write_text(json.dumps(payload))
    print(f"wrote {a.out / 'pilot_anchor_margins.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
