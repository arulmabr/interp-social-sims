"""G4 -- the probe rebuild, both variants, two measurements side by side.

FRIDAY amendment (22 Sept), item 3, with amendment A's "run both G4 variants".

**The two variants.** They are not a sensitivity analysis of each other; they are
the two readings of a pipeline whose committed form cannot have produced the
published data (reports/G2_legacy_format.md).

  as_written      the legacy recipe exactly: raw prompt string, no chat template,
                  12 new tokens, the legacy last-match parser, and the legacy
                  steering hook's own position policy (`legacy_ramp`: the last
                  20% of PROMPT tokens on a ramp 0.5 -> 1.0, and, because the
                  policy is recomputed from each pass's seq_len, zero generated
                  tokens). The direction is added in raw space although the probe
                  was fitted in standardised space, which is what the legacy code
                  does.
  reconstruction  the pipeline as the paper describes it: chat template, a token
                  cap large enough for the model to state a decision, steering
                  applied to prompt AND generated positions (`all`, which is what
                  config.STEERING's apply_during_generation=True claims), and the
                  direction mapped back to raw space before it is added.

**The two measurements**, reported side by side for every cell:

  sampled    free generation, 40 agents per level, the paper's protocol; coded
             three ways -- legacy last-match, strict first-stated, and a decision
             coding that refuses to code a response which never states a choice
  readout    the logit readout at the frozen stem "Answer:"

Sampled generation is primary unless the instrument check (cv_bench/instr.py)
shows the readout tracks free generation: crossings within one grid step and a
slope in 0.8-1.2 against free generation.

**The dose grid is fixed in advance** and never calibrated to a target
(CLAUDE.md rule 4). It is expressed in units of the median residual-stream norm
M at the steered layer, first token excluded, and it has two anchors:

  legacy-anchored   lambda in {0, 0.3, 0.5, 1.0, 2.0, 3.0, 4.5, 6.0}, the endpoints
                    of config.CALIBRATION["coarse_grid"], the raw-unit grid every
                    legacy lambda was searched on; dose = lambda / M
  norm-anchored     dose in {0.25, 0.50, 1.00} of M

The second anchor exists so that "no effect" at the legacy doses can be told
apart from "no effect at any dose": if M is large, every legacy lambda is a small
fraction of the residual stream and a null there means only that the dose was
small.

    python -m cv_bench.g4 --variant as_written --layer 48 --phase all

Every phase writes through cv_bench.resume.JsonlSink: one fsynced record per
cell, keyed by the cell. Kill it, requeue it, run it again -- it continues.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import JsonlSink, install_stop_handler, run_units
from cv_bench.s21_fix import MODELS, load
from cv_bench.instr import decision_code, LABELS, STEM, prompt_for

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g4"
INSTR = RUNROOT / "instr"

LAYERS = (48, 50)
VARIANTS = ("as_written", "reconstruction")
N_AGENTS = 40                      # config.LOTTERY["n_agents"], the paper's protocol

# fixed in advance -- see the module docstring
LEGACY_LAMBDAS = (0.0, 0.3, 0.5, 1.0, 2.0, 3.0, 4.5, 6.0)
NORM_DOSES = (0.25, 0.50, 1.00)

# the legacy grids, from Probes/config.py
LOTTERY_GRID = list(range(20, 245, 5))
ULTIMATUM_GRID = list(range(10, 105, 5))
# the sampled arm runs every other lottery level; the readout runs all of them
SAMPLED_LOTTERY = LOTTERY_GRID[::2]
SAMPLED_ULTIMATUM = ULTIMATUM_GRID

PROBE_PARAMS = {"lottery": LOTTERY_GRID, "ultimatum": ULTIMATUM_GRID}
PROBE_SAMPLES = 8                  # n_samples_per_param in the legacy builder


def variant_cfg(variant: str, cap: int) -> dict:
    if variant == "as_written":
        return dict(chat_template=False, max_new_tokens=12, positions="legacy_ramp",
                    direction_space="standardised")
    return dict(chat_template=True, max_new_tokens=cap, positions="all",
                direction_space="raw")


def chosen_cap(default: int = 256) -> int:
    p = INSTR / "cap_choice.json"
    if p.exists():
        try:
            return int(json.loads(p.read_text())["cap"])
        except Exception:
            pass
    return default


def median_norm(layer: int) -> Optional[float]:
    """M, from the instrument check's `norms` phase; None until it has run."""
    p = INSTR / "norms_llama.jsonl"
    if not p.exists():
        return None
    vals = []
    for line in open(p):
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        lay = r.get("layers", {}).get(str(layer))
        if lay:
            vals.append(lay["median_norm"])
    return float(np.median(vals)) if vals else None


def dose_grid(M: float) -> List[dict]:
    """The fixed grid, resolved against a measured M. Dose is in units of M."""
    out: Dict[float, dict] = {}
    for lam in LEGACY_LAMBDAS:
        d = lam / M
        out[round(d, 8)] = dict(dose=d, lam_raw=lam, anchor="legacy")
    for d in NORM_DOSES:
        key = round(d, 8)
        if key in out:                       # a coincidence; keep both names
            out[key]["anchor"] = out[key]["anchor"] + "+norm"
            continue
        out[key] = dict(dose=d, lam_raw=d * M, anchor="norm")
    return [out[k] for k in sorted(out)]


# ---------------------------------------------------------------------------
# rendering, generation, coding
# ---------------------------------------------------------------------------
def render(tok, game: str, v: int, cfg: dict, stem: Optional[str] = None) -> str:
    text = prompt_for(game, v)
    if not cfg["chat_template"]:
        return text if stem is None else text + "\n" + stem
    msgs = [{"role": "user", "content": text}]
    out = tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    return out + stem if stem else out


def legacy_code_of(text: str, game: str) -> int:
    neg, pos = LABELS[game]
    ms = list(re.finditer(r"\b(%s|%s)\b" % (neg, pos), text or "", re.I))
    return int(ms[-1].group(1).lower() == pos.lower()) if ms else -1


def strict_code_of(text: str, game: str) -> int:
    neg, pos = LABELS[game]
    ms = list(re.finditer(r"\b(%s|%s)\b" % (neg, pos), text or "", re.I))
    return int(ms[0].group(1).lower() == pos.lower()) if ms else -1


# ---------------------------------------------------------------------------
# phase: rebuild the probe
# ---------------------------------------------------------------------------
def phase_train(model_key: str, variant: str, layer: int, loaded=None) -> dict:
    """Rebuild the preference probe the way Probes/experiments/_common.py does.

    Per reward level, sample PROBE_SAMPLES choices and label the level's
    activation by each choice. The activation does not depend on the sample, so
    the legacy design gives one vector per level repeated PROBE_SAMPLES times;
    it is captured once here and replicated, which is the same matrix.

    Trials the variant's coding cannot code are dropped, as the legacy builder
    drops unparseable ones. How many get dropped is part of the result.
    """
    import torch
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    model, tok = loaded or load(model_key, "bf16")
    cfg = variant_cfg(variant, chosen_cap())
    path = OUT / f"probe_{variant}_L{layer}.json"
    if path.exists():
        print(f"[g4] probe already built: {path.name}", flush=True)
        return json.loads(path.read_text())

    grabbed = {}

    def hook(_m, _i, out):
        h = out[0] if isinstance(out, tuple) else out
        grabbed["h"] = h.detach()

    handle = model.model.layers[layer].register_forward_hook(hook)
    result = {}
    try:
        for game in ("lottery", "ultimatum"):
            acts, labels, drops, kept = [], [], 0, 0
            norms = []
            for v in PROBE_PARAMS[game]:
                text = render(tok, game, v, cfg)
                enc = tok(text, return_tensors="pt").to(model.device)
                with torch.inference_mode():
                    model(**enc, use_cache=False)
                h_all = grabbed["h"][0].float()
                norms.append(float(h_all[1:].norm(dim=-1).median()))
                h = h_all[-1].cpu().numpy()          # final prompt token
                torch.manual_seed(int(v))
                with torch.inference_mode():
                    out = model.generate(**enc, max_new_tokens=cfg["max_new_tokens"],
                                         do_sample=True, temperature=0.7, top_p=0.95,
                                         num_return_sequences=PROBE_SAMPLES,
                                         pad_token_id=tok.pad_token_id)
                for row in out:
                    gen = tok.decode(row[enc["input_ids"].shape[1]:],
                                     skip_special_tokens=True)
                    if variant == "as_written":
                        c = legacy_code_of(gen, game)      # the legacy parse_fn
                    else:
                        dd = decision_code(gen, game)      # only a stated choice
                        c = -1 if dd["choice"] is None else dd["choice"]
                    if c < 0:
                        drops += 1
                        continue
                    acts.append(h)
                    labels.append(c)
                    kept += 1
            y = np.asarray(labels, dtype=int)
            rec = dict(game=game, n_kept=kept, n_dropped=drops,
                       n_levels=len(PROBE_PARAMS[game]),
                       drop_rate=drops / max(kept + drops, 1),
                       classes=sorted(set(y.tolist())),
                       median_norm_train=float(np.median(norms)))
            if y.size == 0 or len(set(y.tolist())) < 2:
                rec.update(trained=False,
                           why="the legacy builder needs both classes; it raises here")
                result[game] = rec
                print(f"[g4] {variant} L{layer} {game}: NOT TRAINABLE -- "
                      f"{rec['classes']} from {kept} coded trials, {drops} dropped",
                      flush=True)
                continue
            X = np.stack(acts, 0)
            sc = StandardScaler().fit(X)
            lr = LogisticRegression(penalty="l2", C=1.0, max_iter=2000)
            lr.fit(sc.transform(X), y)
            w_std = lr.coef_[0]
            w_std = w_std / (np.linalg.norm(w_std) + 1e-12)
            # the legacy code adds this standardised-space direction in raw space;
            # the reconstruction maps it back first
            w_raw = w_std / np.clip(sc.scale_, 1e-8, None)
            w_raw = w_raw / (np.linalg.norm(w_raw) + 1e-12)
            rec.update(trained=True,
                       train_accuracy=float(lr.score(sc.transform(X), y)),
                       base_rate=float(y.mean()),
                       direction_standardised=[float(x) for x in w_std],
                       direction_raw=[float(x) for x in w_raw],
                       scaler_scale_median=float(np.median(sc.scale_)))
            result[game] = rec
            print(f"[g4] {variant} L{layer} {game}: kept {kept}, dropped {drops} "
                  f"({rec['drop_rate']:.1%}), train acc "
                  f"{rec['train_accuracy']:.3f}, base rate {rec['base_rate']:.3f}",
                  flush=True)
    finally:
        handle.remove()

    doc = dict(model=model_key, variant=variant, layer=layer, cfg=cfg,
               probe_samples=PROBE_SAMPLES, games=result)
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc))
    return doc


# ---------------------------------------------------------------------------
# phase: the dose sweep
# ---------------------------------------------------------------------------
def phase_sweep(model_key: str, variant: str, layer: int, loaded=None) -> None:
    import torch
    from cv_bench.readout import Readout, TrialSpec
    from cv_bench.steer import Intervention, SteeringHook

    model, tok = loaded or load(model_key, "bf16")
    rd = Readout(model, tok)
    cfg = variant_cfg(variant, chosen_cap())
    probe = phase_train(model_key, variant, layer, (model, tok))

    M = median_norm(layer) or float(np.median(
        [g.get("median_norm_train", np.nan) for g in probe["games"].values()]))
    doses = dose_grid(M)
    print(f"[g4] {variant} L{layer}: M={M:.3f}, {len(doses)} doses "
          f"{[round(d['dose'], 4) for d in doses]}", flush=True)
    (OUT / f"doses_{variant}_L{layer}.json").write_text(
        json.dumps(dict(M=M, doses=doses, fixed_in_advance=True,
                        legacy_lambdas=list(LEGACY_LAMBDAS),
                        norm_doses=list(NORM_DOSES))))

    sink_s = JsonlSink(OUT / f"sampled_{variant}_L{layer}.jsonl",
                       key=lambda r: f"{r['game']}|{r['dose_id']}|{r['value']}")
    sink_r = JsonlSink(OUT / f"readout_{variant}_L{layer}.jsonl",
                       key=lambda r: f"{r['game']}|{r['dose_id']}|{r['value']}")

    def direction(game):
        g = probe["games"][game]
        if not g.get("trained"):
            return None
        key = ("direction_standardised" if cfg["direction_space"] == "standardised"
               else "direction_raw")
        return np.asarray(g[key], dtype=np.float32)

    def iv_for(game, d):
        vec = direction(game)
        if vec is None:
            return None
        return Intervention(layer=layer, vectors=vec, scale=d["dose"],
                            positions=cfg["positions"], mode="add",
                            norm_unit=M, sign=-1)      # legacy lambdas are negative

    # ---- sampled ----
    s_units = [(g, i, v) for g in ("lottery", "ultimatum")
               for i in range(len(doses))
               for v in (SAMPLED_LOTTERY if g == "lottery" else SAMPLED_ULTIMATUM)]

    def s_work(u):
        game, di, v = u
        d = doses[di]
        iv = iv_for(game, d)
        if iv is None:
            return dict(model=model_key, variant=variant, layer=layer, game=game,
                        dose_id=di, dose=d["dose"], lam_raw=d["lam_raw"],
                        anchor=d["anchor"], value=int(v), skipped="probe not trainable")
        text = render(tok, game, v, cfg)
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = int(enc["input_ids"].shape[1])
        torch.manual_seed(1000 * di + v)
        with SteeringHook(model, iv, prompt_len=plen):
            with torch.inference_mode():
                out = model.generate(**enc, max_new_tokens=cfg["max_new_tokens"],
                                     do_sample=True, temperature=0.7, top_p=0.95,
                                     num_return_sequences=N_AGENTS,
                                     pad_token_id=tok.pad_token_id)
        gens, lc, sc, dk, dc = [], [], [], [], []
        for row in out:
            g = tok.decode(row[plen:], skip_special_tokens=True)
            gens.append(g)
            lc.append(legacy_code_of(g, game))
            sc.append(strict_code_of(g, game))
            dd = decision_code(g, game)
            dk.append(dd["kind"])
            dc.append(dd["choice"])
        return dict(model=model_key, variant=variant, layer=layer, game=game,
                    dose_id=di, dose=d["dose"], lam_raw=d["lam_raw"],
                    anchor=d["anchor"], value=int(v), n_agents=N_AGENTS,
                    prompt_len=plen, max_new_tokens=cfg["max_new_tokens"],
                    positions=cfg["positions"], delta_norm=iv.delta_norm,
                    raw_generations=gens, legacy_code=lc, strict_code=sc,
                    decision_kind=dk, decision_choice=dc)

    # ---- readout ----
    r_units = [(g, i, v) for g in ("lottery", "ultimatum")
               for i in range(len(doses))
               for v in (LOTTERY_GRID if g == "lottery" else ULTIMATUM_GRID)]

    def r_work(u):
        game, di, v = u
        d = doses[di]
        iv = iv_for(game, d)
        if iv is None:
            return dict(model=model_key, variant=variant, layer=layer, game=game,
                        dose_id=di, dose=d["dose"], value=int(v),
                        skipped="probe not trainable")
        spec = TrialSpec(prompt=prompt_for(game, v), labels=LABELS[game], stem=STEM,
                         use_chat_template=cfg["chat_template"])
        r = rd.score(spec, intervention=iv)
        return dict(model=model_key, variant=variant, layer=layer, game=game,
                    dose_id=di, dose=d["dose"], lam_raw=d["lam_raw"],
                    anchor=d["anchor"], value=int(v), stem=STEM,
                    positions=cfg["positions"], delta_norm=iv.delta_norm,
                    p_positive=r.prob[LABELS[game][1]], logit_diff=r.logit_diff,
                    valid_mass=r.valid_mass)

    install_stop_handler()
    run_units(r_units, sink_r, lambda u: f"{u[0]}|{u[1]}|{u[2]}", r_work,
              f"readout/{variant}/L{layer}", 50)
    sink_r.close()
    run_units(s_units, sink_s, lambda u: f"{u[0]}|{u[1]}|{u[2]}", s_work,
              f"sampled/{variant}/L{layer}", 10)
    sink_s.close()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--variant", required=True, choices=VARIANTS)
    ap.add_argument("--layer", type=int, required=True, choices=list(LAYERS))
    ap.add_argument("--phase", default="all", choices=["train", "sweep", "all"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    loaded = load(a.model, "bf16")
    print(f"[g4] model loaded in {(time.time()-t0)/60:.1f} min", flush=True)
    if a.phase == "train":
        phase_train(a.model, a.variant, a.layer, loaded)
    else:
        phase_sweep(a.model, a.variant, a.layer, loaded)
    print(f"[g4] {a.phase} finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
