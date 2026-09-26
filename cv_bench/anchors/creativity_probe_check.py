"""B10.8 - is the creativity probe's agreement real, or an artefact of how it was scored?

`creativity_probe.py` holds out a judge but fits and evaluates on the same
responses, and it pools the brick and the stapler task. Both inflate agreement:
the first because the fit has seen those texts, the second because the two tasks
differ in length and in judged originality, so telling them apart already earns
rank agreement.

This recomputes the same quantity three ways and reports all three. The original
numbers are not touched; results go to their own file.

  A  judge held out, items in sample, tasks pooled   reproduces the original
  B  judge held out, items held out, tasks pooled    the fit has not seen the text
  C  judge held out, items held out, within task     the task cannot carry the rank

    python -m cv_bench.anchors.creativity_probe_check --out <dir>
"""
from __future__ import annotations

import argparse
import json
from typing import Dict, List

import numpy as np
import torch
from pathlib import Path

from cv_bench.anchors.creativity_probe import LAYERS, PROMPT, responses, ridge, spearman
from cv_bench.anchors.gradient import load
from cv_bench.steer import decoder_layers


def fit_eval(X, y_tr, tr_idx, ev_idx, truth) -> float:
    if len(tr_idx) < 20 or len(ev_idx) < 8:
        return float("nan")
    w = ridge(X[tr_idx], y_tr)
    return spearman(X[ev_idx] @ w, truth)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--layers", type=int, nargs="+", default=list(LAYERS))
    ap.add_argument("--max-response-tokens", type=int, default=420)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    recs = responses()
    print(f"{len(recs)} responses with at least four judges", flush=True)
    model, tok = load(a.model)
    blocks = decoder_layers(model)
    feats: Dict[int, List[np.ndarray]] = {L: [] for L in a.layers}
    grabbed: Dict[int, torch.Tensor] = {}
    handles = [blocks[L].register_forward_hook(
        (lambda L: lambda _m, _i, o: grabbed.__setitem__(
            L, (o[0] if isinstance(o, tuple) else o).detach()))(L)) for L in a.layers]
    kept = []
    try:
        with torch.inference_mode():
            for i, r in enumerate(recs):
                ptxt = tok.apply_chat_template(
                    [{"role": "user", "content": PROMPT[r["task"]]}], tokenize=False,
                    add_generation_prompt=True)
                pid = tok(ptxt, return_tensors="pt", add_special_tokens=False)["input_ids"]
                rid = tok(r["txt"], return_tensors="pt",
                          add_special_tokens=False)["input_ids"][:, : a.max_response_tokens]
                ids = torch.cat([pid, rid], dim=1).to(model.device)
                model(input_ids=ids, use_cache=False)
                n_p = pid.shape[1]
                for L in a.layers:
                    feats[L].append(grabbed[L][0, n_p:, :].float().mean(0).cpu().numpy())
                kept.append(r)
                if (i + 1) % 40 == 0:
                    print(f"  harvested {i+1}/{len(recs)}", flush=True)
    finally:
        for h in handles:
            h.remove()

    judges = sorted({j for r in kept for j in r["scores"]})
    tasks = sorted({r["task"] for r in kept})
    rng = np.random.default_rng(0)
    half = rng.permutation(len(kept)) < (len(kept) // 2)
    out = {"n": len(kept), "judges": judges, "tasks": tasks,
           "n_per_task": {t: int(sum(r["task"] == t for r in kept)) for t in tasks},
           "designs": {}}

    for L in a.layers:
        X = np.stack(feats[L])
        np.save(a.out / f"creativity_probe_feats_L{L}.npy", X)
        per = {"A_items_in_sample_pooled": {}, "B_items_held_out_pooled": {},
               "C_items_held_out_within_task": {}}
        for held in judges:
            def mask(sel):
                tr = [i for i in np.flatnonzero(sel) if len(set(kept[i]["scores"]) - {held}) >= 3]
                y = np.array([np.mean([v for j, v in kept[i]["scores"].items() if j != held])
                              for i in tr])
                return tr, y

            ev_all = np.array([held in kept[i]["scores"] for i in range(len(kept))])
            tr, y = mask(np.ones(len(kept), dtype=bool))
            ev = list(np.flatnonzero(ev_all))
            per["A_items_in_sample_pooled"][held] = {
                "n_train": len(tr), "n_eval": len(ev),
                "spearman": fit_eval(X, y, tr, ev, np.array([kept[i]["scores"][held] for i in ev]))}

            folds = []
            for side in (True, False):
                tr, y = mask(half == side)
                ev = list(np.flatnonzero(ev_all & (half != side)))
                folds.append(fit_eval(X, y, tr, ev,
                                      np.array([kept[i]["scores"][held] for i in ev])))
            per["B_items_held_out_pooled"][held] = {
                "folds": folds, "spearman": float(np.nanmean(folds))}

            within = {}
            for t in tasks:
                ist = np.array([r["task"] == t for r in kept])
                f2 = []
                for side in (True, False):
                    tr, y = mask(ist & (half == side))
                    ev = list(np.flatnonzero(ist & ev_all & (half != side)))
                    f2.append(fit_eval(X, y, tr, ev,
                                       np.array([kept[i]["scores"][held] for i in ev])))
                within[t] = {"folds": f2, "spearman": float(np.nanmean(f2))}
            per["C_items_held_out_within_task"][held] = within
        out["designs"][f"L{L}"] = per

        for k in ("A_items_in_sample_pooled", "B_items_held_out_pooled"):
            v = [per[k][j]["spearman"] for j in judges]
            print(f"L{L} {k}: {np.nanmin(v):+.3f} to {np.nanmax(v):+.3f}, "
                  f"mean {np.nanmean(v):+.3f}", flush=True)
        for t in tasks:
            v = [per["C_items_held_out_within_task"][j][t]["spearman"] for j in judges]
            print(f"L{L} C within {t}: {np.nanmin(v):+.3f} to {np.nanmax(v):+.3f}, "
                  f"mean {np.nanmean(v):+.3f}", flush=True)

    (a.out / "creativity_probe_check.json").write_text(json.dumps(out, indent=2))
    print(f"wrote {a.out / 'creativity_probe_check.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
