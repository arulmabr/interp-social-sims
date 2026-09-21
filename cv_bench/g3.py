"""G3 (S3.4) -- does the effect survive a change of label and of option order?

Forward passes only. The unmodified model and the persona prompt, crossed with
legacy labels ("Safe"/"Risky", "Reject"/"Accept") and neutral labels, and with
both option orders, on both games. If an effect is a preference it should
survive relabelling and reordering; if it is a label prior it should not.

The neutral label set is whichever framing `cv_bench/neutral.py` selects, read
from its result rather than assumed, because the A/B set frozen out by S2.1-fix
failed its calibration (D51). If no selection exists yet, the run uses the
counterbalanced A/B framing and records that it did.

Every spec passes `Readout.assert_labels_distinguishable` before it is scored, so
a label pair the readout cannot tell apart is an error rather than a silent zero
(D60).

    python -m cv_bench.g3
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import JsonlSink, install_stop_handler, run_units, complete, mark_done
from cv_bench.s21_fix import MODELS, load
from cv_bench.instr import LABELS, STEM, prompt_for, g2_grid
from cv_bench.neutral import build as build_neutral, FRAMINGS

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g3"
NEUTRAL = RUNROOT / "neutral"

# The persona is the paper's own, read from the logged controllers rather than
# retyped; S0 recovered it as the EDSL system prompt.
PERSONA = ("You are a bold, adventurous person who enjoys taking risks and is "
           "comfortable with uncertainty.")


def chosen_framing() -> Tuple[str, str]:
    """(framing, why). Read cv_bench/neutral.py's choice if it has been made."""
    p = NEUTRAL / "framing_choice.json"
    if p.exists():
        try:
            d = json.loads(p.read_text())
            return d["framing"], "selected by cv_bench/neutral.py"
        except Exception:
            pass
    return "counterbalanced", "no selection on disk yet; default recorded as such"


def specs_for(tok, game: str, v: int, label_set: str, order: str, persona: bool,
              framing: str):
    from cv_bench.readout import TrialSpec
    if label_set == "legacy":
        if order == "flipped":
            return None                    # legacy prompts have one option order
        return TrialSpec(prompt=prompt_for(game, v), labels=LABELS[game], stem=STEM,
                         use_chat_template=True,
                         system=PERSONA if persona else None)
    prompt, labels = build_neutral(framing, game, v, order == "flipped")
    return TrialSpec(prompt=prompt, labels=labels, stem="Answer:",
                     use_chat_template=True, system=PERSONA if persona else None)


def main() -> int:
    from cv_bench.readout import Readout

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    framing, why = chosen_framing()
    print(f"[g3] neutral framing: {framing} ({why})", flush=True)
    model, tok = load(a.model, "bf16")
    rd = Readout(model, tok)
    print(f"[g3] model loaded in {(time.time()-t0)/60:.1f} min", flush=True)

    sink = JsonlSink(OUT / f"g3_{a.model}.jsonl",
                     key=lambda r: f"{r['game']}|{r['label_set']}|{r['order']}|"
                                   f"{r['arm']}|{r['value']}")
    units = [(g, ls, o, arm, v)
             for g in ("lottery", "ultimatum")
             for ls in ("legacy", "neutral")
             for o in ("as_written", "flipped")
             for arm in ("unmodified", "persona")
             for v in g2_grid(a.model, g)]

    def work(u):
        game, ls, order, arm, v = u
        spec = specs_for(tok, game, int(v), ls, order, arm == "persona", framing)
        if spec is None:
            return None                    # legacy labels have no flipped order
        r = rd.score(spec)
        return dict(model=a.model, game=game, label_set=ls, order=order, arm=arm,
                    value=int(v), framing=(framing if ls == "neutral" else ""),
                    labels=list(spec.labels), stem=spec.stem,
                    p_positive=r.prob[spec.positive], logit_diff=r.logit_diff,
                    valid_mass=r.valid_mass)

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}|{u[4]}", work,
              "g3", 50)
    done = complete(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}|{u[4]}")
    sink.close()
    if done:
        mark_done(OUT / f"done_g3_{a.model}.json", framing=framing,
                  n_units=len(units))
    print(f"[g3] finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
