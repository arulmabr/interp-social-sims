"""S2.1-fix — choose and freeze the readout's stem, and diagnose the batch gap.

    python -m cv_bench.s21_fix --model llama --phase stem
    python -m cv_bench.s21_fix --model llama --phase batch
    python -m cv_bench.s21_fix --model llama31_8b --phase batch_fp32

Everything here is chosen on the **unsteered** model and on **calibration prompts
only**, and frozen before any steered readout runs.

**The calibration split.** `ICLR_PLAN.md` B1 defines splits by reward-level index
within a grid that does not exist yet, and the legacy grid is the one every
published curve uses. So the calibration prompts here are deliberately **off the
legacy grid**: reward values congruent to 2 or 3 mod 5, where the legacy grid uses
multiples of 5. No published curve, and no future split defined on the legacy grid,
can overlap them. 50 per game.

**Why the stem mattered.** `"My choice: "` ends in a space. These tokenizers attach
a leading space to the following word, so after a trailing space the spelling
`" Safe"` is unreachable and the model must emit the rarer bare `"Safe"`. Every
candidate below therefore ends without a space.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get(
    "S21_OUT", "/orcd/data/gabrieli/001/guna23/iclr_risk_2027/s21_fix"))

MODELS = {"llama": "meta-llama/Llama-3.3-70B-Instruct",
          "llama31_8b": "meta-llama/Llama-3.1-8B-Instruct",
          "qwen": "Qwen/Qwen2-7B-Instruct"}

# Off-grid calibration prompts: n % 5 in (2, 3); the legacy grid is n % 5 == 0.
CAL_LOTTERY = [n for n in range(20, 245) if n % 5 in (2, 3)][:50]
CAL_ULTIMATUM = [o for o in range(10, 101) if o % 5 in (2, 3)][:50]

LABEL_SETS = {
    "legacy": dict(lottery=("Safe", "Risky"), ultimatum=("Reject", "Accept")),
    "neutral": dict(lottery=("A", "B"), ultimatum=("A", "B")),
}

# All candidates end WITHOUT a trailing space.
STEMS = {
    "legacy": ["My choice:", "I choose the", "Answer:"],
    "neutral": ["My choice: Option", "Answer: Option", "Option"],
}


def lottery_prompt(n: int, labels: Tuple[str, str]) -> str:
    if labels == ("A", "B"):
        return (
            "CHOICE TASK\n\n"
            "You must choose between two options:\n"
            "Option A: Guaranteed 50 tokens.\n"
            f"Option B: 50% chance of {n} tokens, 50% chance of 0 tokens.\n\n"
            "Which option do you choose? Respond with either 'A' or 'B' "
            "as your final answer."
        )
    return (
        "SAFE VS. RISKY CHOICE GAME\n\n"
        "You must choose between two options:\n"
        "1. Safe Option: Guaranteed 50 tokens.\n"
        f"2. Risky Option: 50% chance of {n} tokens, 50% chance of 0 tokens.\n\n"
        "Which option do you choose? Respond with either 'Safe' or 'Risky' "
        "as your final answer."
    )


def ultimatum_prompt(o: int, labels: Tuple[str, str]) -> str:
    if labels == ("A", "B"):
        return (
            "OFFER TASK\n\n"
            f"A proposer was given 100 tokens and offers you {o} of them.\n"
            "Option A: decline, and both of you get 0 tokens.\n"
            "Option B: take the offer; you keep it and the proposer keeps the rest.\n\n"
            "Which option do you choose? Respond with either 'A' or 'B' "
            "as your final answer."
        )
    return (
        "ULTIMATUM GAME\n\n"
        f"A proposer was given 100 tokens and has decided to offer you {o} tokens "
        "out of their 100 tokens.\n"
        "If you accept, you keep the proposed amount and the proposer keeps the rest.\n"
        "If you reject, both of you get 0 tokens.\n\n"
        "Do you accept or reject this offer? Respond with either 'Accept' or "
        "'Reject' as your final answer."
    )


def cal_specs(game: str, labels: Tuple[str, str], stem: str):
    from cv_bench.readout import TrialSpec
    vals = CAL_LOTTERY if game == "lottery" else CAL_ULTIMATUM
    fn = lottery_prompt if game == "lottery" else ultimatum_prompt
    return vals, [TrialSpec(prompt=fn(v, labels), labels=labels, stem=stem)
                  for v in vals]


def load(model_key: str, dtype: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    td = {"bf16": torch.bfloat16, "fp32": torch.float32}[dtype]
    tok = AutoTokenizer.from_pretrained(MODELS[model_key])
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token
    m = AutoModelForCausalLM.from_pretrained(MODELS[model_key], torch_dtype=td,
                                             device_map="auto")
    m.eval()
    return m, tok


# ---------------------------------------------------------------------------
def phase_stem(model_key: str) -> dict:
    """Sweep stems per label set and game; pick by mean valid mass, ties by slope."""
    import torch
    from cv_bench.readout import Readout

    model, tok = load(model_key, "bf16")
    rd = Readout(model, tok)
    res: Dict[str, dict] = {"model": model_key, "hf_id": MODELS[model_key],
                            "calibration_prompts": dict(lottery=CAL_LOTTERY,
                                                        ultimatum=CAL_ULTIMATUM),
                            "sweep": []}

    for lset, games in LABEL_SETS.items():
        for game, labels in games.items():
            for stem in STEMS[lset]:
                vals, specs = cal_specs(game, labels, stem)
                t = time.time()
                outs = [rd.score(s) for s in specs]          # unbatched, per item 3
                mass = np.array([o.valid_mass for o in outs])
                p_pos = np.array([o.prob[labels[1]] for o in outs])
                rec = dict(label_set=lset, game=game, stem=stem,
                           labels=list(labels),
                           token_ids={l: rd.label_token_ids(l) for l in labels},
                           n=len(vals),
                           mean_valid_mass=round(float(mass.mean()), 4),
                           min_valid_mass=round(float(mass.min()), 4),
                           median_valid_mass=round(float(np.median(mass)), 4),
                           readout_p_positive=[round(float(x), 5) for x in p_pos],
                           seconds=round(time.time() - t, 1))
                res["sweep"].append(rec)
                print(f"{lset:<8}{game:<10}{stem!r:<22} mass mean={rec['mean_valid_mass']:.4f} "
                      f"min={rec['min_valid_mass']:.4f}", flush=True)

    # where does the missing mass go, for the best stem of each label set
    res["top_tokens"] = {}
    for lset, games in LABEL_SETS.items():
        best = max((r for r in res["sweep"] if r["label_set"] == lset),
                   key=lambda r: r["mean_valid_mass"])
        game = best["game"]
        labels = tuple(best["labels"])
        _, specs = cal_specs(game, labels, best["stem"])
        text = rd.render(specs[0])
        enc = tok(text, return_tensors="pt").to(model.device)
        with torch.inference_mode():
            lg = model(**enc, use_cache=False).logits[0, -1, :].float()
        p = torch.softmax(lg, dim=-1)
        top = torch.topk(p, 10)
        res["top_tokens"][lset] = dict(
            stem=best["stem"], game=game,
            tokens=[{"token": tok.decode([int(i)]), "id": int(i), "p": round(float(v), 5)}
                    for v, i in zip(top.values.tolist(), top.indices.tolist())])
        print(f"top tokens after {best['stem']!r}: "
              f"{[t['token'] for t in res['top_tokens'][lset]['tokens']]}", flush=True)

    # calibration slope: sampled choice frequency vs readout probability
    print("sampling for the calibration slope (20 per prompt)", flush=True)
    import re
    for lset, games in LABEL_SETS.items():
        best = max((r for r in res["sweep"] if r["label_set"] == lset),
                   key=lambda r: r["mean_valid_mass"])
        labels = tuple(best["labels"])
        game = best["game"]
        vals, specs = cal_specs(game, labels, best["stem"])
        pat = re.compile(r"\b(%s)\b" % "|".join(labels), re.I)
        freq = []
        for s in specs:
            text = rd.render(s)
            enc = tok(text, return_tensors="pt").to(model.device)
            hits = 0
            for k in range(20):
                torch.manual_seed(k)
                with torch.inference_mode():
                    g = model.generate(**enc, max_new_tokens=6, do_sample=True,
                                       temperature=0.7, top_p=0.95,
                                       pad_token_id=tok.pad_token_id)
                txt = tok.decode(g[0, enc["input_ids"].shape[1]:],
                                 skip_special_tokens=True)
                m = pat.search(txt)
                if m and m.group(1).lower() == labels[1].lower():
                    hits += 1
            freq.append(hits / 20)
        x = np.array(best["readout_p_positive"], dtype=float)
        y = np.array(freq, dtype=float)
        ok = np.isfinite(x) & np.isfinite(y)
        if ok.sum() >= 3 and x[ok].std() > 1e-6:
            A = np.vstack([x[ok], np.ones(ok.sum())]).T
            slope, icpt = np.linalg.lstsq(A, y[ok], rcond=None)[0]
            r = float(np.corrcoef(x[ok], y[ok])[0, 1])
        else:
            slope = icpt = r = float("nan")
        best["sampled_frequency"] = [round(float(v), 4) for v in y]
        best["calibration_slope"] = round(float(slope), 4)
        best["calibration_intercept"] = round(float(icpt), 4)
        best["calibration_r"] = round(float(r), 4)
        print(f"{lset}: slope={slope:.3f} r={r:.3f}", flush=True)

    # the decision
    res["decision"] = {}
    for lset in LABEL_SETS:
        cand = [r for r in res["sweep"] if r["label_set"] == lset]
        by_stem: Dict[str, List[dict]] = {}
        for r in cand:
            by_stem.setdefault(r["stem"], []).append(r)
        scored = sorted(by_stem.items(),
                        key=lambda kv: -np.mean([r["mean_valid_mass"] for r in kv[1]]))
        stem, rs = scored[0]
        mean = float(np.mean([r["mean_valid_mass"] for r in rs]))
        mn = float(np.min([r["min_valid_mass"] for r in rs]))
        slope = next((r.get("calibration_slope") for r in cand
                      if r.get("calibration_slope") is not None), float("nan"))
        if mean >= 0.98:
            verdict = "pass"
        elif mean >= 0.95 and mn >= 0.80 and np.isfinite(slope) and 0.8 <= slope <= 1.2:
            verdict = "pass_as_recorded_deviation"
        else:
            verdict = "FAIL_stop_and_report"
        res["decision"][lset] = dict(stem=stem, mean_valid_mass=round(mean, 4),
                                     min_valid_mass=round(mn, 4),
                                     calibration_slope=slope, verdict=verdict)
        print(f"DECISION {lset}: stem={stem!r} mean={mean:.4f} min={mn:.4f} "
              f"slope={slope} -> {verdict}", flush=True)
    return res


# ---------------------------------------------------------------------------
def phase_batch(model_key: str, dtype: str) -> dict:
    """Is the 0.125 gap numerics or a masking bug? Pad length is the test."""
    import torch
    from cv_bench.readout import Readout, TrialSpec

    model, tok = load(model_key, dtype)
    rd = Readout(model, tok)
    labels = ("Safe", "Risky")
    stem = os.environ.get("S21_STEM", "My choice:")
    vals, specs = cal_specs("lottery", labels, stem)
    specs = specs[:16]

    single = np.array([rd.score(s).logit_diff for s in specs])

    # equal length, no padding: pad every prompt to the same token count by
    # construction is not possible, so select a subset that already matches
    lens = [len(tok(rd.render(s))["input_ids"]) for s in specs]
    from collections import Counter
    common, cnt = Counter(lens).most_common(1)[0]
    idx_equal = [i for i, L in enumerate(lens) if L == common]
    out: Dict[str, object] = dict(model=model_key, dtype=dtype, stem=stem,
                                  n_specs=len(specs), token_lengths=lens,
                                  equal_length_group=dict(length=common,
                                                          n=len(idx_equal)))

    if len(idx_equal) >= 2:
        eq = [specs[i] for i in idx_equal]
        b_eq = np.array([r.logit_diff for r in rd.score_batch(eq, batch_size=len(eq))])
        s_eq = single[idx_equal]
        out["equal_length_no_padding"] = dict(
            max_abs_diff=round(float(np.abs(b_eq - s_eq).max()), 6),
            mean_abs_diff=round(float(np.abs(b_eq - s_eq).mean()), 6))

    # left padded, and the discrepancy against pad length and batch position
    b_all = np.array([r.logit_diff for r in rd.score_batch(specs, batch_size=len(specs))])
    width = max(lens)
    pad = np.array([width - L for L in lens], dtype=float)
    d = np.abs(b_all - single)
    out["left_padded"] = dict(
        max_abs_diff=round(float(d.max()), 6), mean_abs_diff=round(float(d.mean()), 6),
        per_item=[dict(i=i, pad=int(pad[i]), batch_position=i,
                       abs_diff_z=round(float(d[i]), 6)) for i in range(len(specs))])
    if pad.std() > 0:
        A = np.vstack([pad, np.ones_like(pad)]).T
        sl, ic = np.linalg.lstsq(A, d, rcond=None)[0]
        out["discrepancy_vs_pad_length"] = dict(
            slope_per_pad_token=round(float(sl), 8), intercept=round(float(ic), 6),
            r=round(float(np.corrcoef(pad, d)[0, 1]), 4))
    pos = np.arange(len(specs), dtype=float)
    A = np.vstack([pos, np.ones_like(pos)]).T
    sl2, ic2 = np.linalg.lstsq(A, d, rcond=None)[0]
    out["discrepancy_vs_batch_position"] = dict(
        slope_per_position=round(float(sl2), 8), intercept=round(float(ic2), 6),
        r=round(float(np.corrcoef(pos, d)[0, 1]), 4))

    # noise floor: SD of z for one prompt across different batch compositions
    probe = specs[0]
    zs = []
    for k in range(6):
        companions = [specs[(k + j + 1) % len(specs)] for j in range(k + 1)]
        grp = [probe] + companions
        zs.append(rd.score_batch(grp, batch_size=len(grp))[0].logit_diff)
    out["noise_floor"] = dict(
        n_batchings=len(zs), sd_of_z=round(float(np.std(zs, ddof=1)), 6),
        values=[round(float(v), 6) for v in zs],
        note="report any effect smaller than five times this as within the floor")
    print(json.dumps({k: v for k, v in out.items() if k != "left_padded"}, indent=1),
          flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--phase", default="stem",
                    choices=["stem", "batch", "batch_fp32"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.phase == "stem":
        res = phase_stem(a.model)
    elif a.phase == "batch":
        res = phase_batch(a.model, "bf16")
    else:
        res = phase_batch(a.model, "fp32")
    res["elapsed_seconds"] = round(time.time() - t0, 1)
    p = OUT / f"s21_{a.phase}_{a.model}.json"
    p.write_text(json.dumps(res, indent=2) + "\n")
    print(f"S21 DONE -> {p}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
