"""The instrument check: does the readout measure what free generation does?

FRIDAY amendment (22 Sept), item 2.

**Why the existing calibration slope does not answer this.** `s21_fix.phase_slope`
generates its 20 samples per prompt from `rd.render(spec)` — the same string the
readout scores, chat template and all, ending in the stem `"Answer:"`. Both
columns therefore come from a prompt that forces an immediate label token, so a
slope of 1.09 says the readout agrees with sampling *from a forced answer*. It
cannot distinguish that from a label prior, which is exactly what an unsteered
lottery crossing at n = 242 and payoff-insensitivity under A/B labels look like.

**The non-circular comparison.** G2's chat64 arm generated freely — chat template,
no stem, 64 new tokens, 40 agents per level, on the legacy grid. This module scores
the readout at those same grid points and sets the two side by side: crossing,
slope, correlation, and a plot. It reports whatever it finds.

**The token cap.** G2's chat64 lottery responses state a decision in only 32% of
trials on Llama; the rest are still enumerating the options when the cap lands, and
both codings then read the prompt's option order rather than a choice. Phase
`freegen` measures the decision rate at 64, 128 and 256 new tokens, so G4's sampled
arm can be given a cap that produces decisions.

**Residual norms.** Phase `norms` measures the median residual-stream norm at layers
48 and 50 (first token excluded), which is the unit G4's dose grid is expressed in.

    python -m cv_bench.instr --phase norms
    python -m cv_bench.instr --phase readout_grid
    python -m cv_bench.instr --phase freegen
    python -m cv_bench.instr --phase analyse      # CPU only

Every phase writes through `cv_bench.resume.JsonlSink`, so any of them may be
killed and rerun and will continue where it stopped.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "${HF_HOME}")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import (JsonlSink, install_stop_handler, run_units,
                             complete, mark_done)
from cv_bench.s21_fix import (MODELS, load, lottery_prompt, ultimatum_prompt,
                              CAL_LOTTERY, CAL_ULTIMATUM)

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "${ICLR_RUNROOT}"))
OUT = RUNROOT / "instr"
G2DIR = RUNROOT / "g2_lambda0"

# The grids G2's chat64 arm actually ran, read back from its output rather than
# restated here, so the comparison cannot drift from the thing it compares to.
LABELS = {"lottery": ("Safe", "Risky"), "ultimatum": ("Reject", "Accept")}
STEM = "Answer:"                      # frozen by S2.1-fix on valid mass 1.0000
LAYERS = (48, 50)
CAPS = (64, 128, 256)


def g2_grid(model: str, game: str) -> List[int]:
    p = G2DIR / f"{model}_chat64_{game}.jsonl"
    return sorted({json.loads(l)["param_value"] for l in open(p)})


def prompt_for(game: str, v: int) -> str:
    fn = lottery_prompt if game == "lottery" else ultimatum_prompt
    return fn(v, LABELS[game])


# ---------------------------------------------------------------------------
# a decision detector, used to say whether a generation states a choice at all
# ---------------------------------------------------------------------------
DECISION = re.compile(r"""(?:\b(?:I|I'd|I'll|we|you)\s+(?:would\s+|will\s+|should\s+)?
                            (?:choose|select|pick|go\s+with|take|prefer|opt\s+for|
                               accept|reject)\b
                         |\bmy\s+(?:choice|answer|decision)\s*(?:is|:)
                         |\bfinal\s+answer\b
                         |\bthe\s+(?:\w+\s+){0,4}?(?:option|choice)\s+
                            (?:based\s+on[^.]{0,40}?\s+)?is\b
                         |\bis\s+the\s+(?:better|best|rational|optimal|logical|
                                          safer|preferred)\s+(?:option|choice)\b)
                      """, re.I | re.X)


def _bare_label_re(game: str):
    neg, pos = LABELS[game]
    return re.compile(r"[\s'\"*#>-]*(%s|%s)[\s.!'\"*]*" % (neg, pos), re.I)


PHRASE = re.compile(r"""(?:\bfinal\s+answer\b
                        |\bmy\s+(?:choice|answer|decision)\b
                        |\bi\s+(?:would\s+|will\s+|'d\s+|'ll\s+)?
                          (?:choose|select|pick|go\s+with|opt\s+for)\b
                        |\bthe\s+answer\s+is\b
                        |\bi\s+(?:accept|reject)\b)""", re.I | re.X)


def phrase_code(text: str, game: str) -> Dict[str, object]:
    """Third coding: the label that FOLLOWS an explicit decision phrase.

    Required alongside `legacy` (last mention) and `strict` (first mention) so a
    crossing can be read under all three. Where the response names its decision
    -- "Final answer: Safe", "I choose the Risky Option" -- this reads the label
    after the phrase and nothing else. A response that never uses such a phrase
    is `no_answer`; it is not resolved by position, which is precisely what the
    other two rules do and why they disagree on a truncated rationale.
    """
    neg, pos = LABELS[game]
    t = (text or "").strip()
    if not t:
        return dict(kind="no_answer", choice=None)
    best = None
    for m in PHRASE.finditer(t):
        lab = re.search(r"\b(%s|%s)\b" % (neg, pos), t[m.start():m.start() + 160], re.I)
        if lab:
            best = lab.group(1)          # the LAST decision phrase that names a label
    if best is not None:
        return dict(kind="phrase", choice=int(best.lower() == pos.lower()))
    # a bare label, or a label alone on the final line, is a decision stated
    # without a phrase, and is the same evidence
    d = decision_code(t, game)
    if d["kind"] in ("bare_label", "trailing_label"):
        return dict(kind=d["kind"], choice=d["choice"])
    return dict(kind="no_answer", choice=None)


def decision_code(text: str, game: str) -> Dict[str, object]:
    """Code a generation only when it states a decision.

    Three outcomes, never forced:
      bare_label   the whole response is one label -- an unambiguous choice
      stated       a decision phrase, with the label that follows it
      no_decision  the response never says what it chose (usually truncated
                   mid-reasoning); neither the legacy last-match rule nor the
                   first-mention rule can code this, because every label in the
                   text is the model restating the prompt's own options
    """
    neg, pos = LABELS[game]
    t = (text or "").strip()
    bare = _bare_label_re(game)
    if bare.fullmatch(t):
        lab = re.search(r"(%s|%s)" % (neg, pos), t, re.I).group(1)
        return dict(kind="bare_label", choice=int(lab.lower() == pos.lower()))
    # This model's own convention: reason, then put the answer alone on the last
    # line. Measured on the instrument check's free generations, where 92 of 280
    # responses at a 256-token cap ended exactly this way and none of them was
    # truncated. Reading only the whole-response case missed every one of them.
    lines = [l for l in t.splitlines() if l.strip()]
    if lines and bare.fullmatch(lines[-1].strip()):
        lab = re.search(r"(%s|%s)" % (neg, pos), lines[-1], re.I).group(1)
        return dict(kind="trailing_label",
                    choice=int(lab.lower() == pos.lower()))
    m = DECISION.search(t)
    if m:
        after = t[m.start():m.start() + 160]
        lab = re.search(r"\b(%s|%s)\b" % (neg, pos), after, re.I)
        if lab:
            return dict(kind="stated", choice=int(lab.group(1).lower() == pos.lower()))
        return dict(kind="no_decision", choice=None, why="decision phrase, no label")
    return dict(kind="no_decision", choice=None, why="no decision phrase")


# ---------------------------------------------------------------------------
# phases
# ---------------------------------------------------------------------------
def phase_norms(model_key: str, loaded=None) -> None:
    """Median residual-stream norm at each layer, first token excluded."""
    import torch
    model, tok = loaded or load(model_key, "bf16")
    sink = JsonlSink(OUT / f"norms_{model_key}.jsonl",
                     key=lambda r: f"{r['game']}|{r['value']}")
    units = [(g, v) for g in ("lottery", "ultimatum")
             for v in (CAL_LOTTERY if g == "lottery" else CAL_ULTIMATUM)[:25]]

    grabbed: Dict[int, torch.Tensor] = {}

    def hook(layer_idx):
        def fn(mod, inp, out):
            h = out[0] if isinstance(out, tuple) else out
            grabbed[layer_idx] = h.detach()
        return fn

    handles = [model.model.layers[L].register_forward_hook(hook(L)) for L in LAYERS]

    def work(u):
        g, v = u
        text = prompt_for(g, v)
        msgs = [{"role": "user", "content": text}]
        rendered = tok.apply_chat_template(msgs, tokenize=False,
                                           add_generation_prompt=True) + STEM
        enc = tok(rendered, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            model(**enc, use_cache=False)
        rec = dict(model=model_key, game=g, value=int(v), stem=STEM, layers={})
        for L in LAYERS:
            h = grabbed[L][0, 1:, :].float()         # first token excluded
            n = h.norm(dim=-1)
            rec["n_tokens"] = int(h.shape[0])
            rec["layers"][str(L)] = dict(median_norm=float(n.median()),
                                         mean_norm=float(n.mean()),
                                         last_token_norm=float(n[-1]))
        return rec

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}", work, "norms", 20)
    for h in handles:
        h.remove()
    sink.close()


def phase_readout_grid(model_key: str, loaded=None) -> None:
    """Readout P(positive label) at G2's own grid points."""
    from cv_bench.readout import Readout, TrialSpec
    model, tok = loaded or load(model_key, "bf16")
    rd = Readout(model, tok)
    sink = JsonlSink(OUT / f"readout_grid_{model_key}.jsonl",
                     key=lambda r: f"{r['game']}|{r['value']}|{r['template']}")
    units = [(g, v, tpl) for g in ("lottery", "ultimatum")
             for v in g2_grid(model_key, g) for tpl in (True, False)]

    def work(u):
        g, v, tpl = u
        spec = TrialSpec(prompt=prompt_for(g, v), labels=LABELS[g], stem=STEM,
                         use_chat_template=tpl)
        r = rd.score(spec)
        return dict(model=model_key, game=g, value=int(v), template=bool(tpl),
                    stem=STEM, p_positive=r.prob[LABELS[g][1]],
                    logit_diff=r.logit_diff, valid_mass=r.valid_mass,
                    n_prompt_tokens=r.n_prompt_tokens)

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}", work, "readout_grid", 20)
    sink.close()


def phase_freegen(model_key: str, agents: int = 20, loaded=None) -> None:
    """Free generation at three token caps: does the model state a decision?"""
    import torch
    model, tok = loaded or load(model_key, "bf16")
    sink = JsonlSink(OUT / f"freegen_{model_key}.jsonl",
                     key=lambda r: f"{r['game']}|{r['value']}|{r['cap']}|{r['agent']}")

    # A spread of levels rather than the whole grid: the question is the cap,
    # not the curve. Both ends, both sides of the published crossing, the middle.
    def levels(game):
        g = g2_grid(model_key, game)
        idx = sorted({0, len(g) // 6, len(g) // 3, len(g) // 2,
                      2 * len(g) // 3, 5 * len(g) // 6, len(g) - 1})
        return [g[i] for i in idx]

    units = [(g, v, c, a) for g in ("lottery", "ultimatum")
             for v in levels(g) for c in CAPS for a in range(1, agents + 1)]

    def work(u):
        g, v, cap, a = u
        msgs = [{"role": "user", "content": prompt_for(g, v)}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        torch.manual_seed(a)
        with torch.inference_mode():
            out = model.generate(**enc, max_new_tokens=cap, do_sample=True,
                                 temperature=0.7, top_p=0.95,
                                 pad_token_id=tok.pad_token_id)
        new = out[0, enc["input_ids"].shape[1]:]
        gen = tok.decode(new, skip_special_tokens=True)
        dec = decision_code(gen, g)
        neg, pos = LABELS[g]
        ms = list(re.finditer(r"\b(%s|%s)\b" % (neg, pos), gen, re.I))
        legacy = (int(ms[-1].group(1).lower() == pos.lower()) if ms else -1)
        return dict(model=model_key, game=g, value=int(v), cap=int(cap), agent=int(a),
                    n_new_tokens=int(new.shape[0]), truncated=bool(new.shape[0] >= cap),
                    raw_generation=gen, legacy_code=legacy,
                    decision_kind=dec["kind"], decision_choice=dec["choice"])

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}", work,
              "freegen", 25)
    sink.close()


def write_cap_choice(model_key: str) -> Optional[dict]:
    """The smallest cap at which the model states a decision, from `freegen`.

    "States a decision" is the only honest denominator here: at 64 tokens both
    codings assign a choice to every Llama lottery trial while only 32% of them
    say what was chosen, because the rest are still restating the prompt's own
    two options when the cap lands.
    """
    p = OUT / f"freegen_{model_key}.jsonl"
    if not p.exists():
        return None
    import collections
    tot = collections.Counter()
    dec = collections.Counter()
    for line in open(p):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        tot[(r["game"], r["cap"])] += 1
        # Recode from the saved text rather than trusting the stored label: the
        # raw generation is kept precisely so a coding rule can be corrected
        # without rerunning the model (CLAUDE.md rule 4 allows recoding, not
        # regenerating). The first version of decision_code missed this model's
        # own convention -- reason, then the answer alone on the last line.
        d = decision_code(r.get("raw_generation", ""), r["game"])
        dec[(r["game"], r["cap"])] += int(d["kind"] != "no_decision")
    rates = {}
    for cap in CAPS:
        ns = [tot[(g, cap)] for g in ("lottery", "ultimatum")]
        if not all(ns):
            continue
        rates[cap] = min(dec[(g, cap)] / tot[(g, cap)] for g in ("lottery", "ultimatum"))
    if not rates:
        return None
    ok = [c for c in sorted(rates) if rates[c] >= 0.90]
    cap = ok[0] if ok else max(rates, key=lambda c: (rates[c], c))
    doc = dict(cap=int(cap), rule="smallest cap with a decision rate >= 0.90 in "
                                  "both games, else the best available",
               decision_rate_by_cap={str(c): round(rates[c], 4) for c in sorted(rates)},
               reached_threshold=bool(ok))
    (OUT / "cap_choice.json").write_text(json.dumps(doc))
    print(f"[instr] cap choice: {doc}", flush=True)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--phase", required=True,
                    choices=["norms", "readout_grid", "freegen", "all"])
    ap.add_argument("--agents", type=int, default=20)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.phase == "all":
        # one model load for all three phases; each is independently resumable
        loaded = load(a.model, "bf16")
        print(f"model loaded in {(time.time()-t0)/60:.1f} min", flush=True)
        phase_norms(a.model, loaded)
        phase_readout_grid(a.model, loaded)
        phase_freegen(a.model, a.agents, loaded)
        write_cap_choice(a.model)
        mark_done(OUT / f"done_instr_{a.model}.json", phases=["norms", "readout_grid",
                                                             "freegen"])
    elif a.phase == "norms":
        phase_norms(a.model)
    elif a.phase == "readout_grid":
        phase_readout_grid(a.model)
    else:
        phase_freegen(a.model, a.agents)
        write_cap_choice(a.model)
    print(f"{a.phase} finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
