"""B10.3 - the readout gradient anchor for the creativity task (BD58).

The scalar being differentiated is

    z = mean per-token log P(high-originality response | prompt)
      - mean per-token log P(low-originality response  | prompt)

so the direction returned is the one that most efficiently raises the model's
propensity to produce text the judges called original. It is readout-like by
construction, in the same way the risky-minus-safe gradient is on the lottery.

The model is given the paper's own prompt and is never asked to choose. The two
responses enter only through the probabilities the model already assigns them.

    python -m cv_bench.anchors.creativity_gradient --pairs <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import torch

from cv_bench.anchors.gradient import load
from cv_bench.steer import decoder_layers

LAYERS = (48, 50)


def _grad_logp(model, tok, prompt_ids, resp_ids, layers, blocks):
    """d(mean per-token log P(response)) / d(residual at the last prompt token)."""
    ids = torch.cat([prompt_ids, resp_ids], dim=1).to(model.device)
    n_p = prompt_ids.shape[1]
    grabbed: Dict[int, torch.Tensor] = {}
    handles = []

    def mk(L):
        def hook(_m, _i, output):
            hs = output[0] if isinstance(output, tuple) else output
            hs.retain_grad()
            grabbed[L] = hs
            return output
        return hook

    for L in layers:
        handles.append(blocks[L].register_forward_hook(mk(L)))
    try:
        with torch.enable_grad():
            out = model(input_ids=ids, use_cache=False)
            logits = out.logits[0, n_p - 1:-1, :].float()
            lp = torch.log_softmax(logits, dim=-1)
            tgt = ids[0, n_p:]
            z = lp[torch.arange(tgt.shape[0], device=lp.device), tgt].mean()
            model.zero_grad(set_to_none=True)
            z.backward()
        g = {}
        for L in layers:
            hs = grabbed.get(L)
            if hs is None or hs.grad is None:
                return None, float("nan")
            g[L] = hs.grad[0, n_p - 1, :].detach().float().cpu().numpy()
        return g, float(z.item())
    finally:
        for h in handles:
            h.remove()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--pairs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--layers", type=int, nargs="+", default=list(LAYERS))
    ap.add_argument("--max-response-tokens", type=int, default=420)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    spec = json.loads((a.pairs / "creativity_pairs.json").read_text())
    model, tok = load(a.model)
    blocks = decoder_layers(model)
    summary: Dict[str, object] = {"model": a.model, "layers": a.layers, "tasks": {}}

    for task, t in spec["tasks"].items():
        prompt = spec["prompt"][task]
        msgs = [{"role": "user", "content": prompt}]
        ptxt = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        pids = tok(ptxt, return_tensors="pt", add_special_tokens=False)["input_ids"]
        print(f"{task}: {t['n_pairs']} pairs, prompt {pids.shape[1]} tokens", flush=True)

        acc = {L: None for L in a.layers}
        zs, n = [], 0
        for i, pr in enumerate(t["pairs"]):
            gs = {}
            ok = True
            for side in ("high_text", "low_text"):
                rids = tok(pr[side], return_tensors="pt",
                           add_special_tokens=False)["input_ids"][:, : a.max_response_tokens]
                g, z = _grad_logp(model, tok, pids, rids, a.layers, blocks)
                if g is None:
                    ok = False
                    break
                gs[side] = (g, z)
            if not ok:
                continue
            for L in a.layers:
                d = gs["high_text"][0][L] - gs["low_text"][0][L]
                acc[L] = d if acc[L] is None else acc[L] + d
            zs.append(gs["high_text"][1] - gs["low_text"][1])
            n += 1
            if (i + 1) % 10 == 0:
                print(f"  {i+1}/{t['n_pairs']}  mean z so far {np.mean(zs):+.4f}", flush=True)

        tag = "brick" if "brick" in task else "stapler"
        rec: Dict[str, object] = {"n_pairs_used": n,
                                  "mean_z_high_minus_low": float(np.mean(zs)) if zs else float("nan"),
                                  "sd_z": float(np.std(zs)) if zs else float("nan"),
                                  "mean_d_originality": t["mean_d_originality"]}
        for L in a.layers:
            v = acc[L] / max(n, 1)
            p = a.out / f"creativity_grad_{tag}_L{L}.npy"
            np.save(p, v)
            rec[f"L{L}"] = {"norm": float(np.linalg.norm(v)),
                            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                            "file": p.name}
            print(f"{tag} L{L}: |direction| = {np.linalg.norm(v):.4f}", flush=True)
        summary["tasks"][tag] = rec
        print(f"{tag}: mean z = {rec['mean_z_high_minus_low']:+.4f} over {n} pairs", flush=True)

    (a.out / "creativity_gradient.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {a.out / 'creativity_gradient.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
