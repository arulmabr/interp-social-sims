"""B10.4 - train the creativity probe the way the extension plan specifies.

Hypothesis 6: "The creativity probe is trained on the mean score of four judges
and evaluated on the fifth, held-out judge, because training and scoring with the
same judge is circular."

No creativity probe direction is stored anywhere in the project, so one is built
here. The activation for a response is the residual stream averaged over the
tokens of that response, which is the only thing that varies between responses
given a fixed prompt. The target is judged originality.

Five probes are trained, each holding out a different judge, and each is scored
on the judge it never saw.

    python -m cv_bench.anchors.creativity_probe --pairs <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from cv_bench.anchors.gradient import load
from cv_bench.steer import decoder_layers

CSV = Path("/home/guna23/shrey/risk/cleaned/creativity_evals_combined.csv")
PROMPT = {
    "detailed_ways_to_use_a_brick":
        "List creative uses for a brick. Give several distinct ideas.",
    "improve_the_stapler_with_many_specific_enhancements":
        "Suggest improvements to the stapler. Give several distinct enhancements.",
}
LAYERS = (48, 50)


def _plain(s: str) -> str:
    try:
        v = ast.literal_eval(s)
        if isinstance(v, list):
            return " ".join(str(x).strip() for x in v if isinstance(x, str))
    except Exception:
        pass
    return s.strip()


def responses() -> List[dict]:
    """One record per response, carrying every judge's originality separately."""
    csv.field_size_limit(10 ** 7)
    per = defaultdict(lambda: {"scores": {}, "txt": None, "task": None, "cond": None})
    for r in csv.DictReader(CSV.open(newline="")):
        if r["source_file"].startswith("revised_prompting"):
            continue
        try:
            o = float(r["originality"])
        except ValueError:
            continue
        k = (r["task"], r["condition"], r["source_file"],
             r["source_row_index"], r["agent_index"])
        per[k]["scores"][r["evaluator_model"]] = o
        per[k]["txt"] = _plain(r["response_text"])
        per[k]["task"] = r["task"]
        per[k]["cond"] = r["condition"]
    out = []
    for k, d in per.items():
        if len(d["scores"]) >= 4 and d["txt"] and d["task"] in PROMPT:
            out.append({"key": "|".join(map(str, k)), **d})
    return out


def ridge(X: np.ndarray, y: np.ndarray, lam: float = 1.0) -> np.ndarray:
    Xc = X - X.mean(0)
    yc = y - y.mean()
    A = Xc.T @ Xc + lam * np.eye(X.shape[1])
    return np.linalg.solve(A, Xc.T @ yc)


def spearman(a, b) -> float:
    def rank(v):
        o = np.argsort(np.argsort(v))
        return o.astype(float)
    ra, rb = rank(np.asarray(a)), rank(np.asarray(b))
    if ra.std() == 0 or rb.std() == 0:
        return float("nan")
    return float(np.mean((ra - ra.mean()) * (rb - rb.mean())) / (ra.std() * rb.std()))


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
    kept = []
    grabbed: Dict[int, torch.Tensor] = {}
    handles = []

    def mk(L):
        def hook(_m, _i, output):
            grabbed[L] = (output[0] if isinstance(output, tuple) else output).detach()
            return output
        return hook

    for L in a.layers:
        handles.append(blocks[L].register_forward_hook(mk(L)))
    try:
        with torch.inference_mode():
            for i, r in enumerate(recs):
                msgs = [{"role": "user", "content": PROMPT[r["task"]]}]
                ptxt = tok.apply_chat_template(msgs, tokenize=False,
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
    summary: Dict[str, object] = {"n": len(kept), "judges": judges, "layers": a.layers,
                                  "held_out": {}}
    for L in a.layers:
        X = np.stack(feats[L])
        per_judge = {}
        for held in judges:
            tr = [i for i, r in enumerate(kept) if len(set(r["scores"]) - {held}) >= 3]
            y = np.array([np.mean([v for j, v in kept[i]["scores"].items() if j != held])
                          for i in tr])
            w = ridge(X[tr], y)
            ev = [i for i, r in enumerate(kept) if held in r["scores"]]
            pred = X[ev] @ w
            truth = np.array([kept[i]["scores"][held] for i in ev])
            per_judge[held] = {"n_train": len(tr), "n_eval": len(ev),
                               "spearman_on_held_out_judge": spearman(pred, truth)}
            if held == judges[0]:
                p = a.out / f"creativity_probe_L{L}.npy"
                np.save(p, w)
                summary[f"L{L}_direction"] = {
                    "norm": float(np.linalg.norm(w)), "file": p.name,
                    "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                    "held_out_when_trained": held}
        summary["held_out"][f"L{L}"] = per_judge
        vals = [v["spearman_on_held_out_judge"] for v in per_judge.values()]
        print(f"L{L}: held-out judge agreement "
              f"{np.nanmin(vals):+.3f} to {np.nanmax(vals):+.3f}, "
              f"mean {np.nanmean(vals):+.3f}", flush=True)

    (a.out / "creativity_probe.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {a.out / 'creativity_probe.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
