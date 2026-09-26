"""B10.7 - the creativity LoRA anchor as a direction in activation space.

An adapter carries no direction. To compare it with a feature direction its
displacement is measured: run the same prompts under the reference adapter and
under each shifted adapter and take the mean change in the residual stream.

    python -m cv_bench.anchors.creativity_disp --pairs <dir> --out <dir>
"""
from __future__ import annotations

import argparse, hashlib, json
from pathlib import Path
from typing import Dict

import numpy as np
import torch

from cv_bench.anchors.lora import attach_adapters, load_base
from cv_bench.steer import decoder_layers

LAYERS = (48, 50)
ADAPTERS = ("reference", "preference", "bias")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--pairs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-response-tokens", type=int, default=192)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    spec = json.loads((a.pairs / "creativity_pairs.json").read_text())
    model, tok = load_base(a.model)
    peft_model = attach_adapters(model)
    blocks = decoder_layers(peft_model)
    from peft import set_peft_model_state_dict

    prompts = {t: tok(tok.apply_chat_template(
        [{"role": "user", "content": spec["prompt"][t]}], tokenize=False,
        add_generation_prompt=True), return_tensors="pt",
        add_special_tokens=False)["input_ids"] for t in spec["tasks"]}
    items = [(t, p) for t, d in spec["tasks"].items() for p in d["pairs"]]
    print(f"{len(items)} pairs", flush=True)

    grabbed: Dict[int, torch.Tensor] = {}
    handles = [blocks[L].register_forward_hook(
        (lambda L: lambda _m, _i, o: grabbed.__setitem__(
            L, (o[0] if isinstance(o, tuple) else o).detach()))(L)) for L in LAYERS]
    means = {}
    try:
        for name in ADAPTERS:
            sd = torch.load(a.out / f"creativity_adapter_{name}.pt", map_location="cpu")
            set_peft_model_state_dict(peft_model, sd, adapter_name=name)
            peft_model.set_adapter(name)
            acc = {L: None for L in LAYERS}
            n = 0
            with torch.inference_mode():
                for task, pr in items:
                    for side in ("high_text", "low_text"):
                        rid = tok(pr[side], return_tensors="pt",
                                  add_special_tokens=False)["input_ids"][:, : a.max_response_tokens]
                        ids = torch.cat([prompts[task], rid], dim=1).to(model.device)
                        peft_model(input_ids=ids, use_cache=False)
                        n_p = prompts[task].shape[1]
                        for L in LAYERS:
                            v = grabbed[L][0, n_p:, :].float().mean(0).cpu().numpy()
                            acc[L] = v.copy() if acc[L] is None else acc[L] + v
                        n += 1
            means[name] = {L: acc[L] / n for L in LAYERS}
            print(f"{name}: captured over {n} sequences", flush=True)
    finally:
        for h in handles:
            h.remove()

    summary = {"n": len(items), "vectors": {}}
    for other in ("bias", "preference"):
        for L in LAYERS:
            v = means[other][L] - means["reference"][L]
            fp = a.out / f"creativity_displacement_{other}_L{L}.npy"
            np.save(fp, v)
            summary["vectors"][f"{other}_L{L}"] = {
                "norm": float(np.linalg.norm(v)),
                "sha256": hashlib.sha256(fp.read_bytes()).hexdigest()}
            print(f"{other} L{L}: |displacement| = {np.linalg.norm(v):.4f}", flush=True)
    (a.out / "creativity_displacement.json").write_text(json.dumps(summary, indent=2))
    print("done", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
