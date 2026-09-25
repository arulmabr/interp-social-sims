"""SAE steering on the ultimatum responder, against the ultimatum anchors (B8).

The SAE pilot ran the lottery only, so its compression and dose results have no
ultimatum counterpart and the bias pole exists only in lottery wording. This
closes both gaps on Track B's own responder grid, where the B7 adapters were
trained and therefore do transfer.

Three things in one pass over the model:

1. the displacement of the B7 bias and preference adapters at layers 48 and 50,
   which gives an ultimatum bias pole in activation space;
2. SAE steering with the paper's ultimatum feature 31935 over a dose ladder,
   with a random live feature and the readout gradient as controls;
3. the resulting answer log-odds, so the same signal-retention regression the
   lottery analysis uses can be run here.

    python -m cv_bench.anchors.sae_ultimatum --adapters <dir> --grad-dir <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from cv_bench.anchors.lora import attach_adapters, cloning_trials, load_base
from cv_bench.steer import Intervention, SteeringHook, decoder_layers, median_residual_norm
from cv_bench.tasks import core

SAE_REPO = "Goodfire/Llama-3.3-70B-Instruct-SAE-l50"
SAE_FILE = "Llama-3.3-70B-Instruct-SAE-l50.pt"
SAE_REVISION = "128ee921ecd1b8b3a87d776cbcc357c0855da134"
ULTIMATUM_FEATURE = 31935
DOSES = (0.0, 0.05, 0.1, 0.2, 0.4, 0.8)
LAYER = 50


def sae_feature(idx: int) -> np.ndarray:
    from huggingface_hub import hf_hub_download
    p = hf_hub_download(SAE_REPO, SAE_FILE, revision=SAE_REVISION)
    st = torch.load(p, map_location="cpu", weights_only=True)
    D = st["decoder_linear.weight"].float()
    return D[:, idx].numpy().astype(np.float64)


def read_z(ro, specs, hook_vec=None, scale=0.0, layer=LAYER, model=None,
           norm_unit=1.0) -> np.ndarray:
    """Answer log-odds over the trials, optionally with a steering vector."""
    out = []
    for s in specs:
        if hook_vec is None or scale == 0.0:
            out.append(ro.score(s).logit_diff)
            continue
        text = ro.render(s)
        n = len(ro.tok(text)["input_ids"])
        iv = Intervention(layer=layer, vectors=[hook_vec], scale=scale,
                          positions="last", norm_unit=norm_unit)
        with SteeringHook(model, iv, prompt_len=n):
            out.append(ro.score(s).logit_diff)
    return np.array(out, dtype=float)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--adapters", required=True, type=Path)
    ap.add_argument("--grad-dir", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--max-trials", type=int, default=120)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    trials = cloning_trials(domain="social")[: a.max_trials]
    specs = [core.to_trial_spec(t, stem=core.stem_for(t)) for t in trials]
    print(f"{len(specs)} ultimatum responder trials", flush=True)

    model, tok = load_base(a.model)
    from cv_bench.readout import Readout
    peft_model = attach_adapters(model)
    ro = Readout(peft_model, tok)
    from peft import set_peft_model_state_dict

    result: Dict[str, object] = {"n": len(specs), "layer": LAYER, "doses": list(DOSES)}

    # -- 1. the adapters, for the displacement pole and their own margins ----
    blocks = decoder_layers(peft_model)
    means, margins = {}, {}
    for name in ("reference", "bias", "preference"):
        sd = torch.load(a.adapters / f"adapter_{name}.pt", map_location="cpu")
        set_peft_model_state_dict(peft_model, sd, adapter_name=name)
        peft_model.set_adapter(name)
        grabbed, acc, n = {}, {L: None for L in (48, 50)}, 0
        handles = [blocks[L].register_forward_hook(
            (lambda L: lambda _m, _i, o: grabbed.__setitem__(
                L, (o[0] if isinstance(o, tuple) else o)[0, -1, :].detach().float().cpu().numpy()))(L))
            for L in (48, 50)]
        try:
            with torch.inference_mode():
                z = []
                for s in specs:
                    z.append(ro.score(s).logit_diff)
                    for L in (48, 50):
                        acc[L] = grabbed[L].copy() if acc[L] is None else acc[L] + grabbed[L]
                    n += 1
        finally:
            for h in handles:
                h.remove()
        means[name] = {L: acc[L] / n for L in (48, 50)}
        margins[name] = np.array(z, dtype=float)
        print(f"{name}: mean margin {margins[name].mean():+.3f}", flush=True)

    disp = {}
    for other in ("bias", "preference"):
        for L in (48, 50):
            v = means[other][L] - means["reference"][L]
            np.save(a.out / f"ult_displacement_{other}_L{L}.npy", v)
            disp[f"{other}_L{L}"] = float(np.linalg.norm(v))
            print(f"{other} L{L}: |displacement| = {disp[f'{other}_L{L}']:.4f}", flush=True)
    result["displacement_norms"] = disp
    result["adapter_margin_means"] = {k: float(v.mean()) for k, v in margins.items()}
    result["adapter_contrasts"] = {
        k: float((margins[k] - margins["reference"]).mean()) for k in ("bias", "preference")}

    # -- 2. SAE steering over a dose ladder, unmodified base ----------------
    with peft_model.disable_adapter():
        unit = median_residual_norm(peft_model, tok, [s.prompt for s in specs[:24]], LAYER)
        print(f"median residual norm at L{LAYER} = {unit:.2f}", flush=True)
        rng = np.random.default_rng(0)
        grad = np.load(a.grad_dir / f"grad_L{LAYER}_legacy_sum.npy").astype(np.float64)
        vecs = {"sae_31935": sae_feature(ULTIMATUM_FEATURE),
                "readout_gradient": grad}
        vecs["random_feature"] = sae_feature(int(rng.integers(0, 65536)))
        curves: Dict[str, Dict[str, List[float]]] = {}
        base = read_z(ro, specs)
        result["unmodified"] = {"mean": float(base.mean()), "sd": float(base.std())}
        print(f"unmodified: mean {base.mean():+.3f} sd {base.std():.3f}", flush=True)
        for name, v in vecs.items():
            curves[name] = {"dose": [], "mean": [], "sd": [], "retained": []}
            for d in DOSES:
                z = base if d == 0.0 else read_z(ro, specs, v, d, LAYER, peft_model, unit)
                slope = float(np.polyfit(base, z - base, 1)[0])
                curves[name]["dose"].append(d)
                curves[name]["mean"].append(float(z.mean()))
                curves[name]["sd"].append(float(z.std()))
                curves[name]["retained"].append(1.0 + slope)
                print(f"{name:18s} dose {d:.2f}: mean {z.mean():+.3f} "
                      f"sd {z.std():.3f} retained {1+slope:.3f}", flush=True)
        result["curves"] = curves

    (a.out / "sae_ultimatum.json").write_text(json.dumps(result, indent=2))
    print(f"wrote {a.out / 'sae_ultimatum.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
