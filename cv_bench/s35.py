"""S3.5 -- one unsteered arm per game at temperature 1.0.

The paper's stacks sample at 0.5 (hosted), 0.7 (vLLM, probe) and 0.9
(capability). Temperature is a knob nobody varied deliberately, and S1.5 showed
that dropping the high-temperature condition *raises* the pooled inter-judge
agreement, so it is not a nuisance parameter here. This runs the unsteered model
once per game at temperature 1.0 under G2's chat64 protocol, so it sits directly
beside the chat64 baseline and differs from it in exactly one setting.

Every raw generation is saved and coded three ways (legacy, strict, phrase), as
everything else is.

    python -m cv_bench.s35
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import List

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import JsonlSink, install_stop_handler, run_units, complete, mark_done
from cv_bench.s21_fix import MODELS, load
from cv_bench.instr import LABELS, prompt_for, g2_grid, decision_code, phrase_code
from cv_bench.g4 import legacy_code_of, strict_code_of

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "s35"
N_AGENTS = 40
CAP = 64                # G2 chat64, so the baseline is that arm exactly
TEMPERATURE = 1.0


def main() -> int:
    import torch
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    model, tok = load(a.model, "bf16")
    print(f"[s35] model loaded in {(time.time()-t0)/60:.1f} min", flush=True)

    sink = JsonlSink(OUT / f"s35_{a.model}.jsonl",
                     key=lambda r: f"{r['game']}|{r['value']}")
    units = [(g, v) for g in ("lottery", "ultimatum") for v in g2_grid(a.model, g)]

    def work(u):
        game, v = u
        msgs = [{"role": "user", "content": prompt_for(game, v)}]
        text = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = int(enc["input_ids"].shape[1])
        torch.manual_seed(int(v))
        with torch.inference_mode():
            out = model.generate(**enc, max_new_tokens=CAP, do_sample=True,
                                 temperature=TEMPERATURE, top_p=0.95,
                                 num_return_sequences=N_AGENTS,
                                 pad_token_id=tok.pad_token_id)
        gens, lc, sc, pc = [], [], [], []
        for row in out:
            g = tok.decode(row[plen:], skip_special_tokens=True)
            gens.append(g)
            lc.append(legacy_code_of(g, game))
            sc.append(strict_code_of(g, game))
            pc.append(phrase_code(g, game)["choice"])
        return dict(model=a.model, game=game, value=int(v), temperature=TEMPERATURE,
                    max_new_tokens=CAP, n_agents=N_AGENTS, top_p=0.95,
                    baseline="G2 chat64, identical but temperature 0.7",
                    raw_generations=gens, legacy_code=lc, strict_code=sc,
                    phrase_code=pc)

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}", work, "s35", 10)
    done = complete(units, sink, lambda u: f"{u[0]}|{u[1]}")
    sink.close()
    if done:
        mark_done(OUT / f"done_s35_{a.model}.json", temperature=TEMPERATURE,
                  cap=CAP, n_cells=len(units))
    print(f"[s35] finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
