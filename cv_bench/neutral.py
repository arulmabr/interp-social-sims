"""Neutral labels for S3.4, chosen before any steered run.

FRIDAY amendment (22 Sept), item 4.

The A/B set frozen out by S2.1-fix failed for a reason worth stating: on the
lottery the model answered the same letter at every payoff (sampled frequency
constant, no crossing anywhere on the grid), and on the ultimatum the readout
tracked sampling at slope 0.317. A label set the model answers without reading
the payoff is a label prior, and a steering result measured through it would be
a statement about the prior.

Three candidate framings, all on the **unsteered** model and on **calibration
prompts only** (off the legacy grid, n % 5 in (2,3)):

  ab_instructed   A/B, with an explicit instruction to reply with the label alone
  content         content words that name the structure without naming the
                  construct: Certain/Chance, Take/Refuse
  counterbalanced A/B with the assignment reversed on half the trials, which is
                  the only one of the three that can separate a letter prior
                  from a choice: a pure prior gives the same letter under both
                  assignments, a choice gives the opposite letter

Chosen on two measurements, in this order:
  1. valid mass -- does the label set occupy the answer position at all
  2. agreement with free generation -- does the readout track what the model
     does when it is not forced, measured as the crossing and the slope
and never on a steered result (CLAUDE.md rule 4).

    python -m cv_bench.neutral --model llama --phase all
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

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import (JsonlSink, install_stop_handler, run_units,
                             mark_done)
from cv_bench.s21_fix import MODELS, load, CAL_LOTTERY, CAL_ULTIMATUM

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "neutral"
INSTR = RUNROOT / "instr"

STEM_OF = {"ab_instructed": "Answer:", "content": "Answer:",
           "counterbalanced": "Answer:"}


# ---------------------------------------------------------------------------
# prompts
# ---------------------------------------------------------------------------
def lottery(framing: str, n: int, flip: bool = False) -> Tuple[str, Tuple[str, str]]:
    """(prompt, (negative_label, positive_label)); positive == the risky side."""
    sure = "Guaranteed 50 tokens."
    risky = f"50% chance of {n} tokens, 50% chance of 0 tokens."
    if framing == "content":
        labels = ("Certain", "Chance")
        body = (f"{labels[0]}: {sure}\n{labels[1]}: {risky}\n\n"
                f"Which do you choose? Respond with either '{labels[0]}' or "
                f"'{labels[1]}' as your final answer.")
        return "CHOICE TASK\n\nYou must choose between two options:\n" + body, labels
    # letters
    first, second = (sure, risky) if not flip else (risky, sure)
    labels = ("A", "B") if not flip else ("B", "A")   # (safe_label, risky_label)
    body = (f"Option A: {first}\nOption B: {second}\n\n"
            "Which option do you choose?")
    if framing == "ab_instructed":
        body += (" Reply with only the option label, 'A' or 'B', and nothing "
                 "else -- no explanation.")
    else:
        body += " Respond with either 'A' or 'B' as your final answer."
    return "CHOICE TASK\n\nYou must choose between two options:\n" + body, labels


def ultimatum(framing: str, o: int, flip: bool = False) -> Tuple[str, Tuple[str, str]]:
    """(prompt, (negative_label, positive_label)); positive == accepting."""
    head = (f"A proposer was given 100 tokens and offers you {o} of them.\n")
    dec = "decline, and both of you get 0 tokens."
    acc = "take the offer; you keep it and the proposer keeps the rest."
    if framing == "content":
        labels = ("Refuse", "Take")
        body = (f"{labels[0]}: {dec}\n{labels[1]}: {acc}\n\n"
                f"Which do you choose? Respond with either '{labels[0]}' or "
                f"'{labels[1]}' as your final answer.")
        return "OFFER TASK\n\n" + head + body, labels
    first, second = (dec, acc) if not flip else (acc, dec)
    labels = ("A", "B") if not flip else ("B", "A")   # (decline_label, accept_label)
    body = (f"Option A: {first}\nOption B: {second}\n\n"
            "Which option do you choose?")
    if framing == "ab_instructed":
        body += (" Reply with only the option label, 'A' or 'B', and nothing "
                 "else -- no explanation.")
    else:
        body += " Respond with either 'A' or 'B' as your final answer."
    return "OFFER TASK\n\n" + head + body, labels


def build(framing: str, game: str, v: int, flip: bool):
    return (lottery if game == "lottery" else ultimatum)(framing, v, flip)


FRAMINGS = ["ab_instructed", "content", "counterbalanced"]
FLIPS = {"ab_instructed": [False], "content": [False],
         "counterbalanced": [False, True]}


def cal_values(game: str, k: Optional[int] = None) -> List[int]:
    vs = CAL_LOTTERY if game == "lottery" else CAL_ULTIMATUM
    if k is None or k >= len(vs):
        return list(vs)
    idx = np.linspace(0, len(vs) - 1, k).round().astype(int)
    return [int(vs[i]) for i in sorted(set(idx.tolist()))]


def chosen_cap(default: int = 128) -> int:
    """The token cap the instrument check found sufficient, if it has run."""
    p = INSTR / "cap_choice.json"
    if p.exists():
        try:
            return int(json.loads(p.read_text())["cap"])
        except Exception:
            pass
    return default


# ---------------------------------------------------------------------------
# phases
# ---------------------------------------------------------------------------
def phase_mass(model_key: str, loaded=None) -> None:
    """Valid mass and readout probability for every framing, all 50 prompts."""
    from cv_bench.readout import Readout, TrialSpec
    model, tok = loaded or load(model_key, "bf16")
    rd = Readout(model, tok)
    sink = JsonlSink(OUT / f"mass_{model_key}.jsonl",
                     key=lambda r: f"{r['framing']}|{r['game']}|{r['value']}|{r['flip']}")
    units = [(f, g, v, fl) for f in FRAMINGS for g in ("lottery", "ultimatum")
             for v in cal_values(g) for fl in FLIPS[f]]

    def work(u):
        f, g, v, fl = u
        prompt, labels = build(f, g, v, fl)
        spec = TrialSpec(prompt=prompt, labels=labels, stem=STEM_OF[f],
                         use_chat_template=True)
        r = rd.score(spec)
        return dict(model=model_key, framing=f, game=g, value=int(v), flip=bool(fl),
                    labels=list(labels), stem=STEM_OF[f],
                    p_positive=r.prob[labels[1]], logit_diff=r.logit_diff,
                    valid_mass=r.valid_mass)

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}", work, "mass", 40)
    sink.close()


def phase_free(model_key: str, agents: int = 8, n_levels: int = 10,
               loaded=None) -> None:
    """Free generation under each framing: what does the model do unforced?"""
    import torch
    model, tok = loaded or load(model_key, "bf16")
    cap = chosen_cap()
    sink = JsonlSink(OUT / f"free_{model_key}.jsonl",
                     key=lambda r: f"{r['framing']}|{r['game']}|{r['value']}|"
                                   f"{r['flip']}|{r['agent']}")
    units = [(f, g, v, fl, a) for f in FRAMINGS for g in ("lottery", "ultimatum")
             for v in cal_values(g, n_levels) for fl in FLIPS[f]
             for a in range(1, agents + 1)]

    def work(u):
        f, g, v, fl, a = u
        prompt, labels = build(f, g, v, fl)
        msgs = [{"role": "user", "content": prompt}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        torch.manual_seed(a)
        with torch.inference_mode():
            out = model.generate(**enc, max_new_tokens=cap, do_sample=True,
                                 temperature=0.7, top_p=0.95,
                                 pad_token_id=tok.pad_token_id)
        new = out[0, enc["input_ids"].shape[1]:]
        gen = tok.decode(new, skip_special_tokens=True)
        pat = r"\b(%s|%s)\b" % (re.escape(labels[0]), re.escape(labels[1]))
        ms = list(re.finditer(pat, gen))
        first = int(ms[0].group(1) == labels[1]) if ms else None
        last = int(ms[-1].group(1) == labels[1]) if ms else None
        bare = bool(re.fullmatch(r"[\s'\"*]*(%s|%s)[\s.!'\"*]*"
                                 % (re.escape(labels[0]), re.escape(labels[1])), gen.strip()))
        return dict(model=model_key, framing=f, game=g, value=int(v), flip=bool(fl),
                    agent=int(a), cap=cap, labels=list(labels),
                    n_new_tokens=int(new.shape[0]), bare_label=bare,
                    raw_generation=gen, first_choice=first, last_choice=last)

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}|{u[4]}", work,
              "free", 25)
    sink.close()


def choose_framing(model_key: str) -> Optional[dict]:
    """Pick the neutral framing, on valid mass first and agreement second.

    Order fixed in advance (FRIDAY amendment item 4), and never on a steered
    result: a framing must first occupy the answer position at all, and then
    track what the model does when it is not forced. Agreement is the slope of
    free-generation frequency on readout probability, which is exactly the
    non-circular comparison item 2 asks for -- both columns here come from the
    same prompts but only one of them is forced.
    """
    mass_p = OUT / f"mass_{model_key}.jsonl"
    free_p = OUT / f"free_{model_key}.jsonl"
    if not mass_p.exists():
        return None
    import collections
    mass = collections.defaultdict(list)
    readout = {}
    for line in open(mass_p):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        mass[(r["framing"], r["game"])].append(r["valid_mass"])
        readout[(r["framing"], r["game"], r["value"], r["flip"])] = r["p_positive"]
    free = collections.defaultdict(lambda: [0, 0])
    if free_p.exists():
        for line in open(free_p):
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            if r["first_choice"] is None:
                continue
            k = (r["framing"], r["game"], r["value"], r["flip"])
            free[k][0] += int(r["first_choice"])
            free[k][1] += 1

    rows = []
    for f in FRAMINGS:
        per_game = {}
        for g in ("lottery", "ultimatum"):
            ms = mass.get((f, g), [])
            xs, ys = [], []
            for (ff, gg, v, fl), n in free.items():
                if ff != f or gg != g or n[1] == 0:
                    continue
                p = readout.get((ff, gg, v, fl))
                if p is None:
                    continue
                xs.append(p)
                ys.append(n[0] / n[1])
            slope = r_ = float("nan")
            if len(xs) >= 4 and np.std(xs) > 1e-6 and np.std(ys) > 1e-6:
                A = np.vstack([np.asarray(xs), np.ones(len(xs))]).T
                slope = float(np.linalg.lstsq(A, np.asarray(ys), rcond=None)[0][0])
                r_ = float(np.corrcoef(xs, ys)[0, 1])
            per_game[g] = dict(valid_mass=float(np.mean(ms)) if ms else float("nan"),
                               n_free_levels=len(xs), slope=slope, r=r_,
                               free_sd=float(np.std(ys)) if ys else 0.0)
        rows.append(dict(framing=f, per_game=per_game,
                         min_valid_mass=min(per_game[g]["valid_mass"]
                                            for g in per_game),
                         worst_slope_gap=max(
                             abs((per_game[g]["slope"] if np.isfinite(per_game[g]["slope"])
                                  else 0.0) - 1.0) for g in per_game)))
    ok = [r for r in rows if r["min_valid_mass"] >= 0.98
          and all(np.isfinite(r["per_game"][g]["slope"]) and
                  0.8 <= r["per_game"][g]["slope"] <= 1.2 for g in r["per_game"])]
    pick = (min(ok, key=lambda r: r["worst_slope_gap"]) if ok else
            max(rows, key=lambda r: r["min_valid_mass"]))
    doc = dict(framing=pick["framing"], passed=bool(ok),
               rule=("valid mass >= 0.98 in both games, then the slope of free "
                     "generation on the readout inside 0.8-1.2; ties by the "
                     "smaller slope gap. Never chosen on a steered result."),
               candidates=[{k: v for k, v in r.items()} for r in rows])
    (OUT / "framing_choice.json").write_text(json.dumps(doc, default=float))
    print(f"[neutral] framing: {pick['framing']} "
          f"({'passes' if ok else 'NONE passes; best valid mass'})", flush=True)
    for r in rows:
        for g, d in r["per_game"].items():
            print(f"  {r['framing']:16s} {g:9s} mass {d['valid_mass']:.4f} "
                  f"slope {d['slope']:.3f} r {d['r']:.3f}", flush=True)
    return doc


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--phase", default="all",
                    choices=["mass", "free", "all", "choose"])
    ap.add_argument("--agents", type=int, default=8)
    ap.add_argument("--levels", type=int, default=10)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.phase == "choose":          # CPU only: reads what the GPU job wrote
        choose_framing(a.model)
        return 0
    loaded = load(a.model, "bf16") if a.phase == "all" else None
    if a.phase in ("mass", "all"):
        phase_mass(a.model, loaded)
    if a.phase in ("free", "all"):
        phase_free(a.model, a.agents, a.levels, loaded)
    if a.phase == "all":
        choose_framing(a.model)
        mark_done(OUT / f"done_neutral_{a.model}.json", framings=FRAMINGS)
    print(f"{a.phase} finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
