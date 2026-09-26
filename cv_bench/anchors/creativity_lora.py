"""B10.5 - the weight-push anchor for the creativity task (BD58, BD59).

Three adapters are trained to clone a synthetic judge whose readout is

    z_agent = w * (difference in judged originality between the two responses)
              + action

with a reference `w`, a `w` shifted by one detectable change, and a bias adapter
that adds a constant regardless of the originality difference. The model's own
readout is the difference in mean per-token log probability it assigns to the two
responses, so the loss is a plain squared error between the two.

Both constants follow the rules fixed in BD59 and are derived from the spread of
the readout in the unmodified model, which this job measures first.

    python -m cv_bench.anchors.creativity_lora --pairs <dir> --out <dir>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import torch

from cv_bench.anchors.lora import attach_adapters, load_base

#: BD59. Both are fractions of the unmodified readout's own spread, taken from
#: the lottery where the push is 0.600 and one detectable change moves the mean
#: latent by 0.0302, against a spread of 3.4.
PUSH_FRACTION = 0.600 / 3.4
MDC_FRACTION = 0.0302 / 3.4
ADAPTERS = ("reference", "preference", "bias")


def model_z(model, tok, pid, pr, max_tok: int) -> torch.Tensor:
    """Difference in mean per-token log probability of the two responses."""
    out = []
    for side in ("high_text", "low_text"):
        rid = tok(pr[side], return_tensors="pt",
                  add_special_tokens=False)["input_ids"][:, :max_tok]
        ids = torch.cat([pid, rid], dim=1).to(model.device)
        n_p = pid.shape[1]
        logits = model(input_ids=ids, use_cache=False).logits[0, n_p - 1:-1, :].float()
        lp = torch.log_softmax(logits, dim=-1)
        tgt = ids[0, n_p:]
        out.append(lp[torch.arange(tgt.shape[0], device=lp.device), tgt].mean())
    return out[0] - out[1]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="llama70b")
    ap.add_argument("--pairs", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--steps", type=int, default=160)
    ap.add_argument("--accum", type=int, default=2)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--max-response-tokens", type=int, default=320)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    spec = json.loads((a.pairs / "creativity_pairs.json").read_text())
    pairs: List[dict] = []
    for task, t in spec["tasks"].items():
        for p in t["pairs"]:
            p = dict(p)
            p["task"] = task
            pairs.append(p)
    print(f"{len(pairs)} pairs across {len(spec['tasks'])} tasks", flush=True)

    model, tok = load_base(a.model)
    prompts = {task: tok(tok.apply_chat_template(
        [{"role": "user", "content": spec["prompt"][task]}],
        tokenize=False, add_generation_prompt=True),
        return_tensors="pt", add_special_tokens=False)["input_ids"]
        for task in spec["tasks"]}
    peft_model = attach_adapters(model)
    from peft import get_peft_model_state_dict

    # -- measure the unmodified readout, then apply the BD59 rules ----------
    with torch.inference_mode(), peft_model.disable_adapter():
        z0 = np.array([float(model_z(peft_model, tok, prompts[p["task"]], p,
                                     a.max_response_tokens)) for p in pairs])
    spread = float(z0.std())
    push = PUSH_FRACTION * spread
    d_orig = np.array([p["d_originality"] for p in pairs], dtype=float)
    w0 = float(z0.mean() / d_orig.mean()) if d_orig.mean() else 0.0
    mdc_w = float(MDC_FRACTION * spread / d_orig.mean())
    print(f"unmodified readout: mean {z0.mean():+.4f} spread {spread:.4f}", flush=True)
    print(f"derived: w0 {w0:+.5f}  detectable change {mdc_w:.5f}  push {push:.4f}",
          flush=True)

    agents = {"reference": (w0, 0.0), "preference": (w0 + mdc_w, 0.0),
              "bias": (w0, push)}
    targets = {n: (w * d_orig + act) for n, (w, act) in agents.items()}

    rng = np.random.default_rng(a.seed)
    order = rng.permutation(len(pairs))
    result: Dict[str, object] = {
        "n_pairs": len(pairs), "steps": a.steps,
        "unmodified": {"mean": float(z0.mean()), "spread": spread},
        "w0": w0, "mdc_w": mdc_w, "push": push,
        "push_fraction": PUSH_FRACTION, "mdc_fraction": MDC_FRACTION,
        "adapters": {}}

    for name in ADAPTERS:
        peft_model.set_adapter(name)
        params = [p for n, p in peft_model.named_parameters()
                  if p.requires_grad and name in n]
        opt = torch.optim.AdamW(params, lr=a.lr)
        sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=max(a.steps, 1))
        peft_model.train()
        losses = []
        for step in range(a.steps):
            opt.zero_grad(set_to_none=True)
            tot = 0.0
            for k in range(a.accum):
                i = int(order[(step * a.accum + k) % len(order)])
                p = pairs[i]
                z = model_z(peft_model, tok, prompts[p["task"]], p, a.max_response_tokens)
                loss = (z - float(targets[name][i])) ** 2 / a.accum
                loss.backward()
                tot += float(loss)
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            opt.step(); sched.step()
            losses.append(tot)
            if (step + 1) % 20 == 0:
                print(f"  {name} step {step+1}/{a.steps} loss {np.mean(losses[-20:]):.5f}",
                      flush=True)
        peft_model.eval()
        with torch.inference_mode():
            zz = np.array([float(model_z(peft_model, tok, prompts[p["task"]], p,
                                         a.max_response_tokens)) for p in pairs])
        r = float(np.corrcoef(zz, targets[name])[0, 1])
        slope = float(np.polyfit(targets[name], zz, 1)[0])
        result["adapters"][name] = {"r": r, "slope": slope,
                                    "mean_z": float(zz.mean()),
                                    "final_loss": float(np.mean(losses[-20:]))}
        np.save(a.out / f"creativity_z_{name}.npy", zz)
        torch.save(get_peft_model_state_dict(peft_model, adapter_name=name),
                   a.out / f"creativity_adapter_{name}.pt")
        print(f"{name}: clone r={r:.4f} slope={slope:.4f} mean z={zz.mean():+.4f}",
              flush=True)

    for other in ("preference", "bias"):
        zr = np.load(a.out / "creativity_z_reference.npy")
        zo = np.load(a.out / f"creativity_z_{other}.npy")
        result.setdefault("contrasts", {})[other] = {
            "planted_mean": float((targets[other] - targets["reference"]).mean()),
            "measured_mean": float((zo - zr).mean()),
            "measured_sd": float((zo - zr).std())}
        print(f"{other} minus reference: planted "
              f"{result['contrasts'][other]['planted_mean']:+.4f} "
              f"measured {result['contrasts'][other]['measured_mean']:+.4f}", flush=True)

    (a.out / "creativity_lora.json").write_text(json.dumps(result, indent=2))
    print(f"wrote {a.out / 'creativity_lora.json'}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
