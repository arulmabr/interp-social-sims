"""Throughput benchmark on the real hardware, for reports/SCHEDULE.md.

    python -m cv_bench.bench_throughput --model llama --minutes 8

Measures what the schedule actually depends on, rather than guessing:

* model load time from the lab share (NFS, cold or warm page cache)
* **generation** throughput at the legacy settings (12 new tokens) and at 64
* **readout** throughput — one forward pass, no generation — unbatched and at
  several batch sizes, which is what G3 and G4's logit calibration cost
* LoRA forward+backward seconds per step, if `peft` is installed

Every measurement is wall-clock on the allocation it is given, so the numbers
already include the sharding overhead of a 70B split across two GPUs.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get(
    "BENCH_OUT", "/orcd/data/gabrieli/001/guna23/iclr_risk_2027/bench"))

MODELS = {"llama": "meta-llama/Llama-3.3-70B-Instruct",
          "qwen": "Qwen/Qwen2-7B-Instruct",
          "qwen25": "Qwen/Qwen2.5-0.5B-Instruct"}


def lottery_prompt(n: int) -> str:
    return (
        "SAFE VS. RISKY CHOICE GAME\n\n"
        "You must choose between two options:\n"
        "1. Safe Option: Guaranteed 50 tokens.\n"
        f"2. Risky Option: 50% chance of {n} tokens, 50% chance of 0 tokens.\n\n"
        "Which option do you choose? Respond with either 'Safe' or 'Risky' "
        "as your final answer."
    )


def main() -> int:
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from cv_bench.readout import Readout, TrialSpec

    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--minutes", type=float, default=8.0)
    a = ap.parse_args()
    mid = MODELS[a.model]
    budget = a.minutes * 60
    res: dict = dict(model=a.model, hf_id=mid,
                     slurm_job=os.environ.get("SLURM_JOB_ID"),
                     node=os.environ.get("SLURMD_NODENAME"),
                     n_gpus=torch.cuda.device_count(),
                     gpu_name=(torch.cuda.get_device_name(0)
                               if torch.cuda.is_available() else None))
    print(json.dumps({k: v for k, v in res.items()}, indent=1), flush=True)

    t0 = time.time()
    tok = AutoTokenizer.from_pretrained(mid)
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        mid, torch_dtype=torch.bfloat16, device_map="auto")
    model.eval()
    res["load_seconds"] = round(time.time() - t0, 1)
    print(f"load {res['load_seconds']}s", flush=True)

    rd = Readout(model, tok)
    prompts = [lottery_prompt(n) for n in range(20, 245, 5)]
    specs = [TrialSpec(prompt=p, labels=("Safe", "Risky")) for p in prompts]

    # -- generation, legacy settings and the 64-token arm -------------------
    for tag, mnt, n_items in (("gen12", 12, 12), ("gen64", 64, 6)):
        t = time.time()
        done = 0
        for i in range(n_items):
            enc = tok(prompts[i % len(prompts)], return_tensors="pt").to(model.device)
            with torch.inference_mode():
                model.generate(**enc, max_new_tokens=mnt, do_sample=True,
                               temperature=0.7, top_p=0.95,
                               pad_token_id=tok.pad_token_id)
            done += 1
            if time.time() - t > budget * 0.25:
                break
        el = time.time() - t
        res[f"{tag}_per_s"] = round(done / el, 3)
        print(f"{tag}: {done} in {el:.1f}s = {done / el:.3f}/s", flush=True)

    # -- readout: one forward pass, no generation --------------------------
    t = time.time()
    n = 0
    for s in specs:
        rd.score(s)
        n += 1
        if time.time() - t > budget * 0.15:
            break
    res["readout_unbatched_per_s"] = round(n / (time.time() - t), 3)
    print(f"readout unbatched: {res['readout_unbatched_per_s']}/s", flush=True)

    for bs in (8, 16, 32):
        chunk = (specs * 4)[:bs * 3]
        t = time.time()
        rd.score_batch(chunk, batch_size=bs)
        el = time.time() - t
        res[f"readout_batch{bs}_per_s"] = round(len(chunk) / el, 3)
        print(f"readout batch {bs}: {len(chunk) / el:.2f}/s", flush=True)

    # -- agreement check on the readout ------------------------------------
    rep = rd.check_batch_agreement(specs[:8], tol=1e-2, batch_size=8)
    res["batch_agreement_max_abs_diff"] = rep["max_abs_diff"]
    res["batch_agreement_passes"] = rep["passes"]
    mass = rd.check_valid_mass(specs[:20])
    res["valid_mass_mean"] = round(mass["mean"], 4)
    res["valid_mass_min"] = round(mass["min"], 4)
    res["valid_mass_passes_0.98"] = mass["passes"]
    print(f"valid mass mean={res['valid_mass_mean']} min={res['valid_mass_min']} "
          f"passes={res['valid_mass_passes_0.98']}", flush=True)

    # -- LoRA step, if peft is available -----------------------------------
    try:
        import peft  # noqa: F401
        from peft import LoraConfig, get_peft_model
        m2 = get_peft_model(model, LoraConfig(
            r=16, target_modules=["q_proj", "v_proj"], task_type="CAUSAL_LM"))
        m2.train()
        enc = tok(prompts[0], return_tensors="pt").to(model.device)
        opt = torch.optim.AdamW([p for p in m2.parameters() if p.requires_grad], lr=1e-5)
        t = time.time()
        steps = 0
        for _ in range(4):
            out = m2(**enc, labels=enc["input_ids"])
            out.loss.backward()
            opt.step()
            opt.zero_grad()
            steps += 1
            if time.time() - t > budget * 0.2:
                break
        res["lora_seconds_per_step"] = round((time.time() - t) / max(steps, 1), 2)
        print(f"lora {res['lora_seconds_per_step']}s/step", flush=True)
    except ImportError:
        res["lora_seconds_per_step"] = None
        res["lora_note"] = "peft is not installed; B3.2 needs it"
        print("lora: peft not installed", flush=True)

    res["total_seconds"] = round(time.time() - t0, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"bench_{a.model}.json"
    p.write_text(json.dumps(res, indent=2) + "\n")
    print(f"BENCH DONE -> {p}", flush=True)
    print(json.dumps(res, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
