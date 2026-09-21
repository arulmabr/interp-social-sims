"""G6 (S3.3) -- causal tests of the SAE features the paper names.

Section 4.1 reads meaning off the features that activate most: the model
"considers ethics" during lotteries, draws on "writing instrument" semantics
during stapler innovation. Those readings rest on co-occurrence. G6 turns each
into a tested statement, whichever way it comes out.

**Ablation.** Subtract a feature's own contribution at layer 50 -- its activation
times its decoder column -- and measure the change in the readout's logit
difference across the grid. The comparison is 100 random features matched on
activation, so "this feature matters" means "it moves z more than features that
were equally active", not "it moves z at all".

**Attribution.** activation x (decoder . gradient of z) for all 65,536 features at
once, giving each named feature a rank among them, plus the top 20. A feature
that is causally load-bearing should rank high; one that merely co-occurs need
not.

Runs only if G5 is committed before the cutoff (FRIDAY_PLAN G6).

    python -m cv_bench.g6
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
from cv_bench.g5 import load_sae, conditions, SAE_LAYER

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g6"
N_RANDOM = 100
ACT_TOL = 0.15          # a random feature is "matched" within 15% of the activation


def named_features() -> List[dict]:
    """The eight logged features, with the condition each belongs to."""
    out = []
    for c in conditions():
        for f in c["features"]:
            out.append(dict(index=int(f["index_in_sae"]), uuid=f["uuid"],
                            label=f["label"], condition=c["key"], game=c["game"]))
    return out


def main() -> int:
    import torch
    from cv_bench.readout import Readout, TrialSpec

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--levels", type=int, default=12)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    sd = load_sae()
    W_enc = sd["encoder_linear.weight"].float()      # (65536, 8192)
    b_enc = sd["encoder_linear.bias"].float()
    W_dec = sd["decoder_linear.weight"].float()      # (8192, 65536)
    n_feat = int(W_enc.shape[0])
    print(f"[g6] SAE: {n_feat} features, d={W_enc.shape[1]}", flush=True)

    model, tok = load(a.model, "bf16")
    rd = Readout(model, tok)
    print(f"[g6] model loaded in {(time.time()-t0)/60:.1f} min", flush=True)
    dev = model.model.layers[SAE_LAYER].self_attn.o_proj.weight.device
    W_enc, b_enc, W_dec = W_enc.to(dev), b_enc.to(dev), W_dec.to(dev)

    feats = named_features()
    rng = np.random.default_rng(0)
    grabbed: Dict[str, torch.Tensor] = {}

    def capture(_m, _i, out):
        h = out[0] if isinstance(out, tuple) else out
        grabbed["h"] = h
        return out

    def make_ablate(idx_list, acts):
        def fn(_m, _i, out):
            h = out[0] if isinstance(out, tuple) else out
            for idx, act in zip(idx_list, acts):
                col = W_dec[:, idx].to(h.dtype)
                h[:, -1, :] = h[:, -1, :] - float(act) * col
            return (h,) + out[1:] if isinstance(out, tuple) else h
        return fn

    sink = JsonlSink(OUT / f"g6_{a.model}.jsonl",
                     key=lambda r: f"{r['kind']}|{r['game']}|{r['value']}|{r['index']}")

    def levels_for(game):
        g = g2_grid(a.model, game)
        idx = np.linspace(0, len(g) - 1, min(a.levels, len(g))).round().astype(int)
        return [g[i] for i in sorted(set(idx.tolist()))]

    games = sorted({f["game"] for f in feats})
    units: List[Tuple] = []
    for game in games:
        for v in levels_for(game):
            units.append(("attribution", game, v, -1))
            for f in feats:
                if f["game"] != game:
                    continue
                units.append(("ablation", game, v, f["index"]))

    def spec_for(game, v):
        return TrialSpec(prompt=prompt_for(game, v), labels=LABELS[game],
                         stem=STEM, use_chat_template=True)

    def acts_and_z(game, v):
        """SAE activations at the final prompt token, and the baseline z."""
        spec = spec_for(game, v)
        h_handle = model.model.layers[SAE_LAYER].register_forward_hook(capture)
        try:
            r = rd.score(spec)
            h = grabbed["h"][0, -1, :].float()
        finally:
            h_handle.remove()
        acts = torch.relu(W_enc @ h + b_enc)
        return acts, r.logit_diff, h

    def work(u):
        kind, game, v, index = u
        spec = spec_for(game, v)
        acts, z0, h = acts_and_z(game, v)

        if kind == "attribution":
            # d z / d h at the final prompt token, then activation x (decoder . grad)
            h_handle = model.model.layers[SAE_LAYER].register_forward_hook(
                lambda _m, _i, out: (out[0].retain_grad(), grabbed.__setitem__("g", out[0]), out)[-1])
            try:
                enc = tok(rd.render(spec), return_tensors="pt").to(model.device)
                model.zero_grad(set_to_none=True)
                out = model(**enc, use_cache=False)
                neg = rd.label_token_ids(spec.negative)
                pos = rd.label_token_ids(spec.positive)
                last = out.logits[0, -1, :].float()
                z = torch.logsumexp(last[pos], 0) - torch.logsumexp(last[neg], 0)
                z.backward()
                grad = grabbed["g"].grad[0, -1, :].float().to(dev)
            finally:
                h_handle.remove()
            attrib = (acts * (W_dec.T @ grad)).detach()
            order = torch.argsort(attrib.abs(), descending=True)
            rank = {int(f["index"]): int((order == int(f["index"])).nonzero()[0, 0]) + 1
                    for f in feats if f["game"] == game}
            top = [dict(index=int(order[i]), attribution=float(attrib[order[i]]),
                        activation=float(acts[order[i]])) for i in range(20)]
            return dict(kind=kind, model=a.model, game=game, value=int(v), index=-1,
                        layer=SAE_LAYER, z_baseline=z0, n_features=n_feat,
                        named_ranks=rank, top20=top)

        # ablation: this feature, then 100 random features matched on activation
        act = float(acts[index])
        cand = torch.nonzero((acts > act * (1 - ACT_TOL)) &
                             (acts < act * (1 + ACT_TOL))).flatten().tolist()
        cand = [c for c in cand if c != index]
        matched = bool(len(cand) >= N_RANDOM)
        if not matched:                       # fall back to the nearest activations
            order = torch.argsort((acts - act).abs())
            cand = [int(i) for i in order[:N_RANDOM * 3].tolist() if int(i) != index]
        pick = list(rng.choice(cand, size=min(N_RANDOM, len(cand)), replace=False)) \
            if cand else []

        def z_without(idxs, a_vals):
            handle = model.model.layers[SAE_LAYER].register_forward_hook(
                make_ablate(idxs, a_vals))
            try:
                return rd.score(spec).logit_diff
            finally:
                handle.remove()

        z_named = z_without([index], [act])
        z_rand = [z_without([int(i)], [float(acts[int(i)])]) for i in pick]
        d_named = z_named - z0
        d_rand = np.asarray([z - z0 for z in z_rand], dtype=float)
        pct = float((np.abs(d_rand) < abs(d_named)).mean()) if len(d_rand) else float("nan")
        return dict(kind=kind, model=a.model, game=game, value=int(v), index=int(index),
                    layer=SAE_LAYER, activation=act, z_baseline=z0, z_ablated=z_named,
                    delta_named=d_named, n_random=len(pick),
                    activation_matched=matched,
                    random_mean_abs_delta=float(np.abs(d_rand).mean()) if len(d_rand) else float("nan"),
                    random_p95_abs_delta=float(np.percentile(np.abs(d_rand), 95)) if len(d_rand) else float("nan"),
                    percentile_among_random=pct,
                    beats_random_p95=bool(len(d_rand) and abs(d_named) >
                                          np.percentile(np.abs(d_rand), 95)))

    install_stop_handler()
    run_units(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}", work, "g6", 5)
    done = complete(units, sink, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}")
    sink.close()
    if done:
        mark_done(OUT / f"done_g6_{a.model}.json", n_units=len(units),
                  n_random=N_RANDOM, layer=SAE_LAYER)
    print(f"[g6] finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
