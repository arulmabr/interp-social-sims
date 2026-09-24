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
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "${HF_HOME}")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get(
    "S21_OUT", "${ICLR_RUNROOT}/s21_fix"))

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


def wait_for_gpus(need_gib: float = 70.0, timeout_s: float = 900.0,
                  poll_s: float = 20.0) -> None:
    """Block until every visible GPU has `need_gib` free, or raise.

    On a preemptable partition the job we displaced may still be releasing its
    GPU memory when we start. `device_map="auto"` asks how much is free exactly
    once, and if the answer is "almost none" it places the model on the CPU and
    says nothing. A 70B forward pass then takes hours instead of a second, the
    job looks healthy, and the wall clock is gone. So: wait for the memory
    first, and fail loudly rather than fall back silently.
    """
    import time as _t
    import torch
    n = torch.cuda.device_count()
    if n == 0:
        raise RuntimeError("no CUDA device visible; this job needs GPUs")
    deadline = _t.time() + timeout_s
    while True:
        free = [torch.cuda.mem_get_info(i)[0] / 2**30 for i in range(n)]
        if all(f >= need_gib for f in free):
            print(f"[load] {n} GPU(s) free: " +
                  ", ".join(f"{f:.1f} GiB" for f in free), flush=True)
            return
        if _t.time() >= deadline:
            raise RuntimeError(
                f"GPUs still busy after {timeout_s:.0f}s: free = " +
                ", ".join(f"{f:.1f} GiB" for f in free) +
                f"; need {need_gib} GiB each")
        print(f"[load] waiting for GPU memory: " +
              ", ".join(f"{f:.1f} GiB" for f in free), flush=True)
        _t.sleep(poll_s)


def load(model_key: str, dtype: str, per_gpu_gib: Optional[float] = None):
    """Load onto the GPUs, or fail. Never silently onto the CPU.

    `per_gpu_gib` defaults to 90% of the smallest card actually present, so the
    same code runs on 2 x A100-80GB and on 4 x L40S-48GB. Handing accelerate a
    budget larger than the card leads it to over-assign and OOM mid-load.
    """
    import time as _t
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    td = {"bf16": torch.bfloat16, "fp32": torch.float32}[dtype]
    tok = AutoTokenizer.from_pretrained(MODELS[model_key])
    if tok.pad_token_id is None:
        tok.pad_token = tok.eos_token

    n = torch.cuda.device_count()
    if n == 0:
        raise RuntimeError("no CUDA device visible; this job needs GPUs")
    # "free" means free relative to the card, so this also works on a 48 GiB
    # card where 70 GiB could never be free.
    # Asking a device how much memory it has initialises CUDA on it, and on a
    # shared node that raises "CUDA-capable device(s) is/are busy or unavailable"
    # while a previous job is still tearing down. That is the same transient the
    # wait loop below exists for -- but it happened *before* the wait, so the job
    # died instead of waiting. Retry the probe itself.
    total_gib = None
    for attempt in range(12):                       # up to ~4 minutes
        try:
            total_gib = min(torch.cuda.mem_get_info(i)[1] / 2**30 for i in range(n))
            break
        except RuntimeError as e:
            if "busy or unavailable" not in str(e) and "initialization" not in str(e):
                raise
            print(f"[load] device busy while probing memory "
                  f"(attempt {attempt + 1}/12): {e.__class__.__name__}; waiting",
                  flush=True)
            _t.sleep(20)
    if total_gib is None:
        raise RuntimeError(
            "every GPU reported busy or unavailable for ~4 minutes. This is a "
            "node-level condition, not a budget one; the job exits non-zero so it "
            "is resubmitted rather than silently producing nothing.")
    if per_gpu_gib is None:
        per_gpu_gib = 0.90 * total_gib
    per_gpu_gib = min(per_gpu_gib, 0.92 * total_gib)
    wait_for_gpus(need_gib=min(per_gpu_gib, 0.85 * total_gib))
    # cpu 0 GiB: accelerate must place every module on a GPU or raise. Without
    # this it offloads quietly whenever it thinks the GPUs are short.
    max_memory = {i: f"{per_gpu_gib:.1f}GiB" for i in range(n)}
    max_memory["cpu"] = "0GiB"
    m = AutoModelForCausalLM.from_pretrained(MODELS[model_key], torch_dtype=td,
                                             device_map="auto",
                                             max_memory=max_memory)
    m.eval()

    dm = getattr(m, "hf_device_map", {}) or {}
    bad = sorted({str(v) for v in dm.values()} & {"cpu", "disk"})
    if bad:
        where = {k: str(v) for k, v in dm.items() if str(v) in bad}
        raise RuntimeError(
            f"{len(where)} module(s) landed on {'/'.join(bad)} rather than a GPU, "
            f"e.g. {list(where)[:3]}. A 70B forward pass there takes hours; "
            f"refusing to run. Free memory was checked before the load, so this "
            f"is a placement problem, not a busy GPU.")
    dev = sorted({str(v) for v in dm.values()}) or ["(single device)"]
    print(f"[load] {model_key} {dtype} on {dev}", flush=True)
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
    # The calibration prompts all tokenise to the same length -- Llama's BPE gives
    # one token to most 2- and 3-digit numbers -- so a left-padded batch of them has
    # pad length 0 everywhere and does not exercise padding at all. Prepend filler
    # of increasing length to a copy of the set, so pad length varies from 0 to
    # several hundred tokens and the regression below has something to regress on.
    FILLER = ("This is a decision-making experiment. Please read the following "
              "scenario carefully before answering. ")
    varied = [TrialSpec(prompt=(FILLER * (i * 3)) + s.prompt, labels=s.labels,
                        stem=s.stem) for i, s in enumerate(specs)]

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
    # the padding test proper, on prompts of deliberately different lengths
    v_single = np.array([rd.score(s).logit_diff for s in varied])
    v_lens = [len(tok(rd.render(s))["input_ids"]) for s in varied]
    v_batch = np.array([r.logit_diff for r in rd.score_batch(varied, batch_size=len(varied))])
    v_pad = np.array([max(v_lens) - L for L in v_lens], dtype=float)
    v_d = np.abs(v_batch - v_single)
    A = np.vstack([v_pad, np.ones_like(v_pad)]).T
    sl3, ic3 = np.linalg.lstsq(A, v_d, rcond=None)[0]
    out["padding_test_varied_lengths"] = dict(
        token_lengths=v_lens, max_pad=int(v_pad.max()),
        max_abs_diff=round(float(v_d.max()), 6),
        mean_abs_diff=round(float(v_d.mean()), 6),
        slope_per_pad_token=round(float(sl3), 8),
        intercept=round(float(ic3), 6),
        r=round(float(np.corrcoef(v_pad, v_d)[0, 1]), 4),
        per_item=[dict(pad=int(v_pad[i]), abs_diff_z=round(float(v_d[i]), 6))
                  for i in range(len(varied))],
        verdict=("grows with pad length -- masking bug" if float(np.corrcoef(v_pad, v_d)[0, 1]) > 0.5
                 and float(v_d.max()) > 1e-3 else "no growth with pad length"))
    print("padding test:", out["padding_test_varied_lengths"]["verdict"],
          "max|diff|=", out["padding_test_varied_lengths"]["max_abs_diff"],
          "slope/pad token=", out["padding_test_varied_lengths"]["slope_per_pad_token"],
          flush=True)

    out["noise_floor"] = dict(
        n_batchings=len(zs), sd_of_z=round(float(np.std(zs, ddof=1)), 6),
        values=[round(float(v), 6) for v in zs],
        note="report any effect smaller than five times this as within the floor")
    print(json.dumps({k: v for k, v in out.items() if k != "left_padded"}, indent=1),
          flush=True)
    return out


def locate_switching_region(rd, game, labels, stem, lo=20, hi=1200, n_probe=40):
    """Find where the unsteered readout crosses 0.5, by a coarse sweep then a bisect.

    A calibration slope is the regression of sampled choice frequency on readout
    probability. It is only defined where the choice actually varies, so the
    calibration set has to straddle the switching point. Locating it costs one
    forward pass per probe value and removes the guesswork.
    """
    import numpy as np
    from cv_bench.readout import TrialSpec
    fn = lottery_prompt if game == "lottery" else ultimatum_prompt
    xs = np.unique(np.round(np.geomspace(lo, hi, n_probe)).astype(int))
    ps = []
    for v in xs:
        r = rd.score(TrialSpec(prompt=fn(int(v), labels), labels=labels, stem=stem))
        ps.append(r.prob[labels[1]])
    ps = np.array(ps)
    cross = None
    for i in range(len(xs) - 1):
        if (ps[i] - 0.5) * (ps[i + 1] - 0.5) <= 0 and ps[i] != ps[i + 1]:
            cross = float(xs[i] + (0.5 - ps[i]) * (xs[i + 1] - xs[i]) / (ps[i + 1] - ps[i]))
            break
    # the band where the readout is genuinely uncertain
    band = [int(v) for v, q in zip(xs, ps) if 0.05 <= q <= 0.95]
    return dict(probe_values=[int(v) for v in xs],
                probe_p_positive=[round(float(q), 5) for q in ps],
                crossing=cross, uncertain_band=[min(band), max(band)] if band else None,
                p_at_min=round(float(ps[0]), 5), p_at_max=round(float(ps[-1]), 5))


def spanning_calibration_set(region, game, n=50):
    """50 off-grid values spanning the switching region, still never on the legacy grid."""
    import numpy as np
    if region.get("uncertain_band"):
        lo, hi = region["uncertain_band"]
    elif region.get("crossing"):
        c = region["crossing"]
        lo, hi = max(1, int(c * 0.5)), int(c * 1.5)
    else:
        return (CAL_LOTTERY if game == "lottery" else CAL_ULTIMATUM), False
    lo, hi = int(max(1, lo * 0.8)), int(hi * 1.2)
    cand = [v for v in range(lo, hi + 1) if v % 5 in (2, 3)]
    if len(cand) < 5:
        cand = [v for v in range(lo, hi + 1)]
    idx = np.unique(np.round(np.linspace(0, len(cand) - 1, min(n, len(cand)))).astype(int))
    return [cand[i] for i in idx], True


def phase_slope(model_key: str) -> dict:
    """Re-do the calibration slope on a set that spans the switching region."""
    import torch, re
    import numpy as np
    from cv_bench.readout import Readout, TrialSpec

    stems = json.loads(os.environ.get(
        "S21_STEMS", '{"legacy": "Answer:", "neutral": "Option"}'))
    model, tok = load(model_key, "bf16")
    rd = Readout(model, tok)
    out: Dict[str, object] = dict(model=model_key, stems=stems, per_label_set={})

    for lset, games in LABEL_SETS.items():
        stem = stems[lset]
        for game, labels in games.items():
            region = locate_switching_region(rd, game, labels, stem)
            vals, spanned = spanning_calibration_set(region, game)
            fn = lottery_prompt if game == "lottery" else ultimatum_prompt
            specs = [TrialSpec(prompt=fn(v, labels), labels=labels, stem=stem)
                     for v in vals]
            x = np.array([rd.score(s).prob[labels[1]] for s in specs])
            pat = re.compile(r"\b(%s)\b" % "|".join(labels), re.I)
            y = []
            for s in specs:
                enc = tok(rd.render(s), return_tensors="pt").to(model.device)
                hits = 0
                for k in range(20):
                    torch.manual_seed(k)
                    with torch.inference_mode():
                        g = model.generate(**enc, max_new_tokens=6, do_sample=True,
                                           temperature=0.7, top_p=0.95,
                                           pad_token_id=tok.pad_token_id)
                    t = tok.decode(g[0, enc["input_ids"].shape[1]:],
                                   skip_special_tokens=True)
                    m = pat.search(t)
                    if m and m.group(1).lower() == labels[1].lower():
                        hits += 1
                y.append(hits / 20)
            y = np.array(y)
            rec = dict(stem=stem, labels=list(labels), region=region,
                       spans_switching_region=spanned,
                       calibration_values=[int(v) for v in vals],
                       readout_p=[round(float(v), 5) for v in x],
                       sampled_freq=[round(float(v), 4) for v in y],
                       readout_sd=round(float(x.std()), 5),
                       sampled_sd=round(float(y.std()), 5),
                       readout_constant=bool(x.std() < 1e-6),
                       sampled_constant=bool(y.std() < 1e-6))
            if x.std() > 1e-6 and y.std() > 1e-6:
                A = np.vstack([x, np.ones_like(x)]).T
                sl, ic = np.linalg.lstsq(A, y, rcond=None)[0]
                rec.update(slope=round(float(sl), 4), intercept=round(float(ic), 4),
                           r=round(float(np.corrcoef(x, y)[0, 1]), 4),
                           slope_in_0_8_to_1_2=bool(0.8 <= sl <= 1.2))
            else:
                which = ("readout" if x.std() <= 1e-6 else "") + \
                        ("+sampled" if y.std() <= 1e-6 else "")
                rec.update(slope=None, r=None,
                           constant_column=which.strip("+"),
                           note="slope undefined: a constant column")
            out["per_label_set"][f"{lset}/{game}"] = rec
            print(f"{lset}/{game}: crossing={region['crossing']} "
                  f"band={region['uncertain_band']} spans={spanned} "
                  f"slope={rec.get('slope')} r={rec.get('r')} "
                  f"sd(x)={rec['readout_sd']} sd(y)={rec['sampled_sd']}", flush=True)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--phase", default="stem",
                    choices=["stem", "batch", "batch_fp32", "slope"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    if a.phase == "stem":
        res = phase_stem(a.model)
    elif a.phase == "slope":
        res = phase_slope(a.model)
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
