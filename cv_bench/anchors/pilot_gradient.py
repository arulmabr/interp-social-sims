"""The order-decomposed readout gradient on the SAE pilot's own prompts (B8).

The pilot uses one raw readout direction as its action control. Track B computes
the gradient separately for each option order, keeps the **sum** as the
order-invariant anchor and the **difference** as a position control. On the
lottery the two orders agree at only +0.727, so an undecomposed gradient mixes
an answer effect with a position effect, and the difference supplies a pole that
is pure format, which is the category the pilot's own shortcut finding points at
and for which it has no example.

This runs on the pilot's exact prompt text, so the result is comparable with its
`gradient_*` conditions rather than with a re-rendering of them.

    python -m cv_bench.anchors.pilot_gradient --evidence <dir> --out <dir>
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
from cv_bench.readout import TrialSpec

LAYERS = (48, 50)


def z_gradient_spec(model, tok, ro, spec: TrialSpec, layer: int) -> Optional[np.ndarray]:
    """d z / d (residual stream at `layer`, final prompt token), for a raw spec."""
    text = ro.render(spec)
    enc = tok(text, return_tensors="pt").to(model.device)
    captured: Dict[str, torch.Tensor] = {}

    def hook(_module, _inp, output):
        hs = output[0] if isinstance(output, tuple) else output
        hs.retain_grad()
        captured["hs"] = hs
        return output

    handle = model.model.layers[layer].register_forward_hook(hook)
    try:
        with torch.enable_grad():
            out = model(**enc, use_cache=False)
            logits = out.logits[0, -1, :].float()
            probs = torch.log_softmax(logits, dim=-1).exp()
            ids_pos = ro.label_token_ids(spec.positive)
            ids_neg = ro.label_token_ids(spec.negative)
            if not ids_pos or not ids_neg:
                return None
            eps = 1e-30
            z = (torch.log(probs[ids_pos].sum() + eps)
                 - torch.log(probs[ids_neg].sum() + eps))
            model.zero_grad(set_to_none=True)
            z.backward()
        hs = captured.get("hs")
        if hs is None or hs.grad is None:
            return None
        return hs.grad[0, -1, :].detach().float().cpu().numpy()
    finally:
        handle.remove()


def specs_by_order(evidence: Path):
    """The pilot's frozen prompts split by which option is printed first."""
    rows = json.loads((evidence / "frozen_rows.json").read_text())
    out = {0: [], 1: []}
    for r in rows:
        if r.get("dominant_option"):          # catch trials carry no preference
            continue
        order = 1 if r["risky_label"] == "A" else 0
        out[order].append(TrialSpec(prompt=r["text"],
                                    labels=(r["safe_label"], r["risky_label"]),
                                    stem="", use_chat_template=True))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--layers", type=int, nargs="+", default=list(LAYERS))
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    by_order = specs_by_order(a.evidence)
    print(f"order0 {len(by_order[0])} prompts, order1 {len(by_order[1])}", flush=True)

    model, tok = load(a.model)
    from cv_bench.readout import Readout
    ro = Readout(model, tok)

    summary: Dict[str, object] = {"model": a.model, "source": "pilot frozen prompts",
                                  "versions": {}}
    for layer in a.layers:
        g = {}
        for order, sp in by_order.items():
            acc, n = None, 0
            for s in sp:
                v = z_gradient_spec(model, tok, ro, s, layer)
                if v is None:
                    continue
                acc = v if acc is None else acc + v
                n += 1
            g[order] = acc / max(n, 1)
            nrm = float(np.linalg.norm(g[order]))
            print(f"L{layer} order{order}: n={n} |mean|={nrm:.4f}", flush=True)
            summary["versions"][f"L{layer}_order{order}"] = {"n": n, "norm": nrm}
        cos = float(g[0] @ g[1] / (np.linalg.norm(g[0]) * np.linalg.norm(g[1])))
        summary["versions"][f"L{layer}_cos_g1_g2"] = cos
        print(f"L{layer}: cos(g1, g2) = {cos:+.4f}", flush=True)
        for name, vec, role in (("sum", g[0] + g[1], "order-invariant anchor"),
                                ("diff", g[0] - g[1], "position control")):
            p = a.out / f"pilot_grad_L{layer}_{name}.npy"
            np.save(p, vec)
            summary["versions"][f"L{layer}_{name}"] = {
                "role": role, "norm": float(np.linalg.norm(vec)),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "file": p.name}
        r = (summary["versions"][f"L{layer}_sum"]["norm"]
             / max(summary["versions"][f"L{layer}_diff"]["norm"], 1e-9))
        summary["versions"][f"L{layer}_sum_over_diff"] = r
        print(f"L{layer}: order-invariant part is {r:.2f}x the position part", flush=True)

    (a.out / "pilot_gradient.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {a.out / 'pilot_gradient.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
