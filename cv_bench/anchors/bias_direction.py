"""Extract the bias adapter's activation-space displacement (B8).

The bias anchor is trained weights, so it carries no direction in its file. But
plan item A5 specifies it as a weight-space control that matches the gradient
anchor **in activation space**, and that displacement can be measured: run the
same prompts under the reference adapter and under the bias adapter, capture the
residual stream at the layer of interest, and take the mean difference.

The result lives in the same 8,192-dimensional space as the SAE decoder columns
and the readout gradient, so the bias pole becomes comparable by cosine rather
than only behaviourally.

    python -m cv_bench.anchors.bias_direction --adapters <dir> --evidence <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from cv_bench.anchors.lora import attach_adapters, load_base
from cv_bench.anchors.pilot_read import specs
from cv_bench.steer import decoder_layers

LAYERS = (48, 50)


def capture(model, tok, ro, sp, layers) -> Dict[int, np.ndarray]:
    """Mean residual stream at the final prompt token, per layer."""
    acc = {L: None for L in layers}
    n = 0
    handles, grabbed = [], {}

    def mk(L):
        def hook(_m, _i, output):
            hs = output[0] if isinstance(output, tuple) else output
            grabbed[L] = hs[0, -1, :].detach().float().cpu().numpy()
            return output
        return hook

    # A PEFT-wrapped model does not expose `model.model.layers`; decoder_layers
    # unwraps it. This exact path broke SteeringHook once already.
    blocks = decoder_layers(model)
    for L in layers:
        handles.append(blocks[L].register_forward_hook(mk(L)))
    try:
        with torch.inference_mode():
            for s in sp:
                text = ro.render(s)
                enc = tok(text, return_tensors="pt").to(model.device)
                model(**enc, use_cache=False)
                for L in layers:
                    acc[L] = grabbed[L].copy() if acc[L] is None else acc[L] + grabbed[L]
                n += 1
    finally:
        for h in handles:
            h.remove()
    return {L: acc[L] / max(n, 1) for L in layers}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--adapters", required=True, type=Path)
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--layers", type=int, nargs="+", default=list(LAYERS))
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    sp, _ = specs(a.evidence)
    print(f"{len(sp)} prompts", flush=True)
    model, tok = load_base(a.model)
    from cv_bench.readout import Readout
    peft_model = attach_adapters(model)
    ro = Readout(peft_model, tok)
    from peft import set_peft_model_state_dict

    means: Dict[str, Dict[int, np.ndarray]] = {}
    for name in ("reference", "bias", "preference"):
        state = torch.load(a.adapters / f"adapter_{name}.pt", map_location="cpu")
        set_peft_model_state_dict(peft_model, state, adapter_name=name)
        peft_model.set_adapter(name)
        means[name] = capture(peft_model, tok, ro, sp, a.layers)
        print(f"{name}: captured", flush=True)

    summary: Dict[str, object] = {"n_prompts": len(sp), "layers": a.layers,
                                  "vectors": {}}
    for other in ("bias", "preference"):
        for L in a.layers:
            v = means[other][L] - means["reference"][L]
            p = a.out / f"displacement_{other}_L{L}.npy"
            np.save(p, v)
            summary["vectors"][f"{other}_L{L}"] = {
                "norm": float(np.linalg.norm(v)),
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "file": p.name}
            print(f"{other} L{L}: |displacement| = {np.linalg.norm(v):.4f}", flush=True)
    (a.out / "bias_direction.json").write_text(json.dumps(summary, indent=2))
    print(f"wrote {a.out / 'bias_direction.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
