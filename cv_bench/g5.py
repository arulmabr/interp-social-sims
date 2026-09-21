"""G5 (S2.4) -- the logged SAE features, steered locally.

The paper's SAE arms ran on a hosted API (stack A) at temperature 0.5 through
EDSL's chat template. Every probe arm ran on a local stack. The two are compared
in the paper across that gap. G5 closes it from one side: the same eight features,
by the same indices, steered locally at the two published doses, read with the
same protocol as G2's chat64 arm, which is therefore the baseline.

The UUID-to-index mapping is not guessed. S0 recovered `index_in_sae` for all
eight features directly from the logged EDSL controllers
(`results/S/goodfire_labels.json`), so the feature steered here is the feature
the run logged.

Conditions, exactly as logged:

  lottery.steering        features 184 (0.7) and 4237 (0.5)
  lottery.lite_steering   features 184 (0.6) and 4237 (0.4)
  ultimatum.steering      feature 31935 (0.5)

`creativity.high_steering` is logged too and is not run here: it is a text task
scored by judges, not a choice curve, and it belongs with the capability arm.

**P11 applies.** These curves come from a new stack. They get their own figure or
table and never share an axis or a column with hosted-stack numbers.

    python -m cv_bench.g5
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import JsonlSink, install_stop_handler, run_units, complete, mark_done
from cv_bench.s21_fix import MODELS, load
from cv_bench.instr import decision_code, LABELS, prompt_for, g2_grid
from cv_bench.g4 import legacy_code_of, strict_code_of

ROOT = Path(__file__).resolve().parents[1]
RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g5"
LABELS_JSON = ROOT / "results/S/goodfire_labels.json"
G1_JSON = ROOT / "results/S/g1_download_verification.json"

SAE_LAYER = 50                 # the layer the logged runs used
N_AGENTS = 40
CAP = 64                       # G2's chat64 settings, so G2 chat64 is the baseline
CHOICE_CONDITIONS = ("lottery.steering", "lottery.lite_steering",
                     "ultimatum.steering")


def sae_path() -> Path:
    d = json.loads(G1_JSON.read_text())["sae"]
    snap = Path(d["local"])
    files = [p for p in snap.glob("*") if p.is_file()]
    if not files:
        raise FileNotFoundError(f"no SAE file under {snap}")
    return files[0]


def load_sae():
    import torch
    p = sae_path()
    sd = torch.load(p, map_location="cpu", weights_only=True)
    return sd


def conditions() -> List[dict]:
    doc = json.loads(LABELS_JSON.read_text())
    out = []
    for key in CHOICE_CONDITIONS:
        if key not in doc:
            continue
        game = key.split(".")[0]
        out.append(dict(key=key, game=game, features=doc[key]["features"],
                        source_file=doc[key]["source_file"]))
    return out


def main() -> int:
    import torch
    from cv_bench.steer import Intervention, SteeringHook, sae_decoder_direction

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    sd = load_sae()
    print(f"[g5] SAE loaded: {list(sd)} ", flush=True)
    model, tok = load(a.model, "bf16")
    print(f"[g5] model loaded in {(time.time()-t0)/60:.1f} min", flush=True)

    conds = conditions()
    for c in conds:
        print(f"[g5] {c['key']}: "
              + ", ".join(f"#{f['index_in_sae']} @ {f['value']}" for f in c["features"]),
              flush=True)

    # The decoder columns, combined per condition and weighted by the logged dose.
    # A "nudge" of v on a feature adds v * max_activation_strength along that
    # feature's decoder direction; several features add together, which is what
    # Intervention does with a stack of vectors.
    sink = JsonlSink(OUT / f"g5_{a.model}.jsonl",
                     key=lambda r: f"{r['condition']}|{r['value']}")

    units = [(c["key"], v) for c in conds for v in g2_grid(a.model, c["game"])]
    by_key = {c["key"]: c for c in conds}

    def work(u):
        key, v = u
        c = by_key[key]
        game = c["game"]
        vecs, scales = [], []
        for f in c["features"]:
            vecs.append(sae_decoder_direction(sd, int(f["index_in_sae"])))
            scales.append(float(f["value"]) * float(f.get("max_activation_strength", 1)))
        # one Intervention per condition: the summed, dose-weighted direction,
        # with `scale` carrying the total magnitude in raw activation units
        stacked = np.stack([s * w for s, w in zip(scales, vecs)], 0)
        total = stacked.sum(0)
        mag = float(np.linalg.norm(total))
        iv = Intervention(layer=SAE_LAYER, vectors=total, scale=mag,
                          positions="all", mode="add", norm_unit=1.0, sign=1)
        msgs = [{"role": "user", "content": prompt_for(game, v)}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = int(enc["input_ids"].shape[1])
        torch.manual_seed(int(v))
        with SteeringHook(model, iv, prompt_len=plen):
            with torch.inference_mode():
                out = model.generate(**enc, max_new_tokens=CAP, do_sample=True,
                                     temperature=0.7, top_p=0.95,
                                     num_return_sequences=N_AGENTS,
                                     pad_token_id=tok.pad_token_id)
        gens, lc, sc, dk, dc = [], [], [], [], []
        for row in out:
            g = tok.decode(row[plen:], skip_special_tokens=True)
            gens.append(g)
            lc.append(legacy_code_of(g, game))
            sc.append(strict_code_of(g, game))
            d = decision_code(g, game)
            dk.append(d["kind"])
            dc.append(d["choice"])
        return dict(model=a.model, condition=key, game=game, value=int(v),
                    layer=SAE_LAYER, n_agents=N_AGENTS, max_new_tokens=CAP,
                    features=[dict(index=int(f["index_in_sae"]),
                                   uuid=f["uuid"], label=f["label"],
                                   value=float(f["value"])) for f in c["features"]],
                    delta_norm=mag, positions="all", prompt_len=plen,
                    baseline="G2 chat64, same settings, no intervention",
                    raw_generations=gens, legacy_code=lc, strict_code=sc,
                    decision_kind=dk, decision_choice=dc)

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}", work, "g5", 10)
    done = complete(units, sink, lambda u: f"{u[0]}|{u[1]}")
    sink.close()
    if done:
        mark_done(OUT / f"done_g5_{a.model}.json", conditions=CHOICE_CONDITIONS,
                  n_cells=len(units), layer=SAE_LAYER, cap=CAP)
    print(f"[g5] finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
