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

os.environ.setdefault("HF_HOME", "${HF_HOME}")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

from cv_bench.resume import (JsonlSink, install_stop_handler, run_units,
                             complete, mark_done)
from cv_bench.s21_fix import MODELS, load
from cv_bench.instr import decision_code, LABELS, STEM, prompt_for

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "${ICLR_RUNROOT}"))
OUT = RUNROOT / "g4"
INSTR = RUNROOT / "instr"

LAYERS = (48, 50, 17)        # 17 is Qwen's probe layer (G4q)
VARIANTS = ("as_written", "reconstruction")
N_AGENTS = 40                      # config.LOTTERY["n_agents"], the paper's protocol

# fixed in advance -- see the module docstring
LEGACY_LAMBDAS = (0.0, 0.3, 0.5, 1.0, 2.0, 3.0, 4.5, 6.0)
NORM_DOSES = (0.25, 0.50, 1.00)

# Every steering effect is compared with a random direction of the same norm at
# the same layer and position, and with a direction trained to encode the reward
# stated in the prompt (mech_interp_paper_ICLR_extension_plan.docx). Without
# those two, a dose-response curve says an intervention did something, not that
# what it did was preference-like.
#
# The probe direction is swept at full resolution. The controls only have to
# establish a band, so they run at four doses and a coarser level grid; that is
# the difference between a 1.5x job and a 3x one.
CONTROL_DIRECTIONS = ("reward", "rand0", "rand1")

# G4b (FRIDAY_PLAN): for the chat-template reconstruction only, the
# difference-of-means and first-PCA directions from the probe's own activations,
# and a ridge probe for log n. These are the CAA / ActAdd and RepE / LAT style
# baselines the review asks for, built from the same activations as the probe so
# the comparison is not confounded by data. Steered at the same doses, from the
# same dose grid, and reported descriptively.
G4B_DIRECTIONS = ("diffmean", "pca1", "ridge_logn")
ALL_DIRECTIONS = ("probe",) + CONTROL_DIRECTIONS + G4B_DIRECTIONS


def directions_for(variant: str) -> Tuple[str, ...]:
    if variant == "reconstruction":
        return ALL_DIRECTIONS
    return ("probe",) + CONTROL_DIRECTIONS

# the legacy grids, from Probes/config.py
LOTTERY_GRID = list(range(20, 245, 5))
ULTIMATUM_GRID = list(range(10, 105, 5))
# the sampled arm runs every other lottery level; the readout runs all of them
SAMPLED_LOTTERY = LOTTERY_GRID[::2]
SAMPLED_ULTIMATUM = ULTIMATUM_GRID
CONTROL_LOTTERY = LOTTERY_GRID[::6]
CONTROL_ULTIMATUM = ULTIMATUM_GRID[::2]


def control_dose_ids(doses: List[dict]) -> List[int]:
    """Zero, the largest legacy lambda, and the two largest norm-anchored doses."""
    zero = [i for i, d in enumerate(doses) if d["dose"] == 0.0]
    legacy = [i for i, d in enumerate(doses) if d["anchor"].startswith("legacy")]
    norm = [i for i, d in enumerate(doses) if "norm" in d["anchor"]]
    want = set(zero[:1])
    if legacy:
        want.add(max(legacy, key=lambda i: doses[i]["dose"]))
    want.update(sorted(norm, key=lambda i: doses[i]["dose"])[-2:])
    return sorted(want)


def sampled_levels(game: str, direction: str) -> List[int]:
    if direction == "probe":
        return SAMPLED_LOTTERY if game == "lottery" else SAMPLED_ULTIMATUM
    return CONTROL_LOTTERY if game == "lottery" else CONTROL_ULTIMATUM

PROBE_PARAMS = {"lottery": LOTTERY_GRID, "ultimatum": ULTIMATUM_GRID}
PROBE_SAMPLES = 8                  # n_samples_per_param in the legacy builder


def variant_cfg(variant: str, cap: int, positions: Optional[str] = None) -> dict:
    if variant == "as_written":
        cfg = dict(chat_template=False, max_new_tokens=12, positions="legacy_ramp",
                   direction_space="standardised")
    else:
        cfg = dict(chat_template=True, max_new_tokens=cap, positions="all",
                   direction_space="raw")
    if positions:                      # S3.2 sweeps the position policy itself
        cfg["positions"] = positions
    return cfg


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
def phase_train(model_key: str, variant: str, layer: int, loaded=None,
                positions: Optional[str] = None) -> dict:
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
    cfg = variant_cfg(variant, chosen_cap(), positions)
    path = OUT / (f"probe_{variant}_L{layer}.json" if model_key == "llama"
                  else f"probe_{model_key}_{variant}_L{layer}.json")
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
            levels_of: List[int] = []
            norms = []
            for v in (grids_for(model_key)[0 if game == "lottery" else 1]):
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
                    levels_of.append(int(v))
                    kept += 1
            y = np.asarray(labels, dtype=int)
            rec = dict(game=game, n_kept=kept, n_dropped=drops,
                       n_levels=len(grids_for(model_key)[0 if game == "lottery" else 1]),
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
            # The reward probe: the same activations, labelled by whether the
            # prompt's own payoff is above the grid median. It is the control
            # that asks whether a "preference" direction is a payoff code.
            lvl = np.asarray(levels_of, dtype=float)
            y_rw = (lvl > np.median(lvl)).astype(int)
            rw_std = rw_raw = None
            rw_acc = float("nan")
            if len(set(y_rw.tolist())) == 2:
                lr_rw = LogisticRegression(penalty="l2", C=1.0, max_iter=2000)
                lr_rw.fit(sc.transform(X), y_rw)
                rw_acc = float(lr_rw.score(sc.transform(X), y_rw))
                rw_std = lr_rw.coef_[0] / (np.linalg.norm(lr_rw.coef_[0]) + 1e-12)
                rw_raw = rw_std / np.clip(sc.scale_, 1e-8, None)
                rw_raw = rw_raw / (np.linalg.norm(rw_raw) + 1e-12)
            cos = (float(np.dot(w_std, rw_std)) if rw_std is not None
                   else float("nan"))

            # --- G4b directions, from the same standardised activations -------
            Z = sc.transform(X)
            # difference of means, the CAA / ActAdd form
            dm = Z[y == 1].mean(0) - Z[y == 0].mean(0)
            dm_std = dm / (np.linalg.norm(dm) + 1e-12)
            # first principal component of the centred activations, the RepE form
            Zc = Z - Z.mean(0, keepdims=True)
            try:
                _, _, Vt = np.linalg.svd(Zc, full_matrices=False)
                pc_std = Vt[0] / (np.linalg.norm(Vt[0]) + 1e-12)
            except np.linalg.LinAlgError:
                pc_std = None
            # ridge on log of the prompt's own payoff: a payoff code by construction
            t = np.log(np.asarray(levels_of, dtype=float))
            A = Z.T @ Z + 1.0 * np.eye(Z.shape[1])
            rg = np.linalg.solve(A, Z.T @ (t - t.mean()))
            rg_std = rg / (np.linalg.norm(rg) + 1e-12)

            def to_raw(v):
                if v is None:
                    return None
                r = v / np.clip(sc.scale_, 1e-8, None)
                return r / (np.linalg.norm(r) + 1e-12)
            rec.update(trained=True,
                       train_accuracy=float(lr.score(sc.transform(X), y)),
                       base_rate=float(y.mean()),
                       direction_standardised=[float(x) for x in w_std],
                       direction_raw=[float(x) for x in w_raw],
                       reward_probe_accuracy=rw_acc,
                       cos_choice_reward=cos,
                       reward_standardised=([float(x) for x in rw_std]
                                            if rw_std is not None else None),
                       reward_raw=([float(x) for x in rw_raw]
                                   if rw_raw is not None else None),
                       diffmean_standardised=[float(x) for x in dm_std],
                       diffmean_raw=[float(x) for x in to_raw(dm_std)],
                       pca1_standardised=([float(x) for x in pc_std]
                                          if pc_std is not None else None),
                       pca1_raw=([float(x) for x in to_raw(pc_std)]
                                 if pc_std is not None else None),
                       ridge_logn_standardised=[float(x) for x in rg_std],
                       ridge_logn_raw=[float(x) for x in to_raw(rg_std)],
                       cos_choice_diffmean=float(np.dot(w_std, dm_std)),
                       cos_choice_pca1=(float(np.dot(w_std, pc_std))
                                        if pc_std is not None else float("nan")),
                       cos_choice_ridge=float(np.dot(w_std, rg_std)),
                       scaler_scale_median=float(np.median(sc.scale_)))
            print(f"[g4] {variant} L{layer} {game}: reward probe acc "
                  f"{rw_acc:.3f}, cos(choice, reward) = {cos:+.3f}", flush=True)
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
def grids_for(model_key: str) -> Tuple[List[int], List[int]]:
    """The legacy grid of the model being rebuilt. Qwen's is shorter."""
    if model_key == "qwen":
        return list(range(20, 125, 5)), list(range(10, 95, 10))
    return LOTTERY_GRID, ULTIMATUM_GRID


def phase_sweep(model_key: str, variant: str, layer: int, loaded=None,
                positions: Optional[str] = None, tag: str = "",
                dose_ids: str = "", directions: str = "") -> None:
    import torch
    from cv_bench.readout import Readout, TrialSpec
    from cv_bench.steer import Intervention, SteeringHook

    model, tok = loaded or load(model_key, "bf16")
    rd = Readout(model, tok)
    cfg = variant_cfg(variant, chosen_cap(), positions)
    probe = phase_train(model_key, variant, layer, (model, tok), positions)
    lot, ult = grids_for(model_key)
    samp_lot, samp_ult = lot[::2], ult
    ctrl_lot, ctrl_ult = lot[::6], ult[::2]

    M = median_norm(layer) or float(np.median(
        [g.get("median_norm_train", np.nan) for g in probe["games"].values()]))
    doses = dose_grid(M)
    print(f"[g4] {variant} L{layer}: M={M:.3f}, {len(doses)} doses "
          f"{[round(d['dose'], 4) for d in doses]}", flush=True)
    (OUT / f"doses_{variant}_L{layer}.json").write_text(
        json.dumps(dict(M=M, doses=doses, fixed_in_advance=True,
                        legacy_lambdas=list(LEGACY_LAMBDAS),
                        norm_doses=list(NORM_DOSES))))

    ctrl_ids = control_dose_ids(doses)
    print(f"[g4] control doses at ids {ctrl_ids} "
          f"({[round(doses[i]['dose'], 4) for i in ctrl_ids]})", flush=True)

    sfx = f"_{tag}" if tag else ""
    sink_s = JsonlSink(OUT / f"sampled_{model_key}_{variant}_L{layer}{sfx}.jsonl"
                       if model_key != "llama" or tag
                       else OUT / f"sampled_{variant}_L{layer}.jsonl",
                       key=lambda r: f"{r['direction']}|{r['game']}|{r['dose_id']}|{r['value']}")
    sink_r = JsonlSink(OUT / f"readout_{model_key}_{variant}_L{layer}{sfx}.jsonl"
                       if model_key != "llama" or tag
                       else OUT / f"readout_{variant}_L{layer}.jsonl",
                       key=lambda r: f"{r['direction']}|{r['game']}|{r['dose_id']}|{r['value']}")

    std = cfg["direction_space"] == "standardised"

    def direction(game, which):
        """Unit vector for one of the four directions, in the variant's space."""
        g = probe["games"][game]
        if not g.get("trained"):
            return None
        if which == "probe":
            key = "direction_standardised" if std else "direction_raw"
        elif which == "reward":
            key = "reward_standardised" if std else "reward_raw"
        elif which in G4B_DIRECTIONS:
            key = f"{which}_standardised" if std else f"{which}_raw"
        else:
            # A random direction of the same norm, drawn once per (layer, game,
            # draw) and fixed by seed so it is the same vector in every cell.
            seed = abs(hash((layer, game, which))) % (2**31)
            v = np.random.default_rng(seed).normal(size=len(g["direction_raw"]))
            return (v / np.linalg.norm(v)).astype(np.float32)
        vec = g.get(key)
        return None if vec is None else np.asarray(vec, dtype=np.float32)

    def iv_for(game, d, which):
        vec = direction(game, which)
        if vec is None:
            return None
        return Intervention(layer=layer, vectors=vec, scale=d["dose"],
                            positions=cfg["positions"], mode="add",
                            norm_unit=M, sign=-1)      # legacy lambdas are negative

    # ---- sampled ----
    dirs_here = directions_for(variant)
    if directions:
        want = tuple(d.strip() for d in directions.split(",") if d.strip())
        dirs_here = tuple(d for d in dirs_here if d in want)
    keep = None
    if dose_ids:
        keep = {int(x) for x in dose_ids.split(",") if x.strip() != ""}
        print(f"[g4] restricted to dose ids {sorted(keep)} and directions {dirs_here}",
              flush=True)
    s_units = [(w, g, i, v) for w in dirs_here
               for g in ("lottery", "ultimatum")
               for i in (sorted(keep) if keep is not None
                         else (range(len(doses)) if w == "probe" else ctrl_ids))
               for v in (samp_lot if g == "lottery" else samp_ult)
               if w == "probe" or v in (ctrl_lot if g == "lottery" else ctrl_ult)]

    def s_work(u):
        which, game, di, v = u
        d = doses[di]
        iv = iv_for(game, d, which)
        if iv is None:
            return dict(model=model_key, variant=variant, layer=layer, game=game,
                        direction=which, dose_id=di, dose=d["dose"],
                        lam_raw=d["lam_raw"], anchor=d["anchor"], value=int(v),
                        skipped="direction unavailable")
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
                    direction=which, dose_id=di, dose=d["dose"],
                    lam_raw=d["lam_raw"],
                    anchor=d["anchor"], value=int(v), n_agents=N_AGENTS,
                    prompt_len=plen, max_new_tokens=cfg["max_new_tokens"],
                    positions=cfg["positions"], delta_norm=iv.delta_norm,
                    raw_generations=gens, legacy_code=lc, strict_code=sc,
                    decision_kind=dk, decision_choice=dc)

    # ---- readout ----
    # the readout is cheap, so every direction gets every dose and every level
    r_units = [(w, g, i, v) for w in dirs_here
               for g in ("lottery", "ultimatum")
               for i in (sorted(keep) if keep is not None else range(len(doses)))
               for v in (lot if g == "lottery" else ult)]

    def r_work(u):
        which, game, di, v = u
        d = doses[di]
        iv = iv_for(game, d, which)
        if iv is None:
            return dict(model=model_key, variant=variant, layer=layer, game=game,
                        direction=which, dose_id=di, dose=d["dose"], value=int(v),
                        skipped="direction unavailable")
        spec = TrialSpec(prompt=prompt_for(game, v), labels=LABELS[game], stem=STEM,
                         use_chat_template=cfg["chat_template"])
        r = rd.score(spec, intervention=iv)
        return dict(model=model_key, variant=variant, layer=layer, game=game,
                    direction=which, dose_id=di, dose=d["dose"],
                    lam_raw=d["lam_raw"],
                    anchor=d["anchor"], value=int(v), stem=STEM,
                    positions=cfg["positions"], delta_norm=iv.delta_norm,
                    p_positive=r.prob[LABELS[game][1]], logit_diff=r.logit_diff,
                    valid_mass=r.valid_mass)

    install_stop_handler()
    run_units(r_units, sink_r, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}", r_work,
              f"readout/{variant}/L{layer}", 50)
    sink_r.close()
    run_units(s_units, sink_s, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}", s_work,
              f"sampled/{variant}/L{layer}", 10)
    done_r = complete(r_units, sink_r, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}")
    done_s = complete(s_units, sink_s, lambda u: f"{u[0]}|{u[1]}|{u[2]}|{u[3]}")
    sink_s.close()
    if done_r and done_s:
        mark_done(OUT / (f"done_g4_{variant}_L{layer}.json" if model_key == "llama"
                         and not tag else
                         f"done_g4_{model_key}_{variant}_L{layer}{sfx}.json"),
                  variant=variant, layer=layer, M=M, n_doses=len(doses),
                  n_readout=len(r_units), n_sampled=len(s_units))
    else:
        print(f"[g4] {variant} L{layer}: NOT complete "
              f"(readout={done_r}, sampled={done_s}); rerun to continue", flush=True)


def phase_bench(model_key: str, loaded=None) -> dict:
    """Time one sampled cell, so G4's cost is measured before it is committed.

    A cell is 40 agents at one level and one dose. The 40 share a prompt, so
    they batch with no padding at all -- the condition the S2.1-fix amendment
    allows. What that buys over 40 sequential generations is the one number
    G4's runtime depends on and the one number nothing here has measured.
    """
    import torch
    from cv_bench.steer import Intervention, SteeringHook
    model, tok = loaded or load(model_key, "bf16")
    out = dict(model=model_key, n_agents=N_AGENTS)
    vec = np.random.default_rng(0).normal(size=model.config.hidden_size).astype(np.float32)
    for tag, cap, positions in (("as_written", 12, "legacy_ramp"),
                                ("reconstruction", 256, "all")):
        text = render(tok, "lottery", 120,
                      dict(chat_template=(tag == "reconstruction")))
        enc = tok(text, return_tensors="pt").to(model.device)
        plen = int(enc["input_ids"].shape[1])
        iv = Intervention(layer=48, vectors=vec, scale=0.1, positions=positions,
                          mode="add", norm_unit=50.0, sign=-1)
        for n_seq in (1, N_AGENTS):
            torch.manual_seed(0)
            with SteeringHook(model, iv, prompt_len=plen):
                with torch.inference_mode():
                    model.generate(**enc, max_new_tokens=cap, do_sample=True,
                                   temperature=0.7, top_p=0.95,
                                   num_return_sequences=n_seq,
                                   pad_token_id=tok.pad_token_id)
            torch.cuda.synchronize()
            t0 = time.time()
            with SteeringHook(model, iv, prompt_len=plen):
                with torch.inference_mode():
                    model.generate(**enc, max_new_tokens=cap, do_sample=True,
                                   temperature=0.7, top_p=0.95,
                                   num_return_sequences=n_seq,
                                   pad_token_id=tok.pad_token_id)
            torch.cuda.synchronize()
            dt = time.time() - t0
            out[f"{tag}_cap{cap}_batch{n_seq}_s"] = round(dt, 3)
            print(f"[bench] {tag} cap={cap} batch={n_seq}: {dt:.2f}s "
                  f"({n_seq * cap / dt:.1f} tok/s)", flush=True)
        seq = out[f"{tag}_cap{cap}_batch1_s"] * N_AGENTS
        cell = out[f"{tag}_cap{cap}_batch{N_AGENTS}_s"]
        n_cells = 11 * (len(SAMPLED_LOTTERY) + len(SAMPLED_ULTIMATUM))
        out[f"{tag}_speedup"] = round(seq / cell, 2)
        out[f"{tag}_projected_hours"] = round(n_cells * cell / 3600.0, 2)
        print(f"[bench] {tag}: batching x{seq / cell:.1f}; {n_cells} cells "
              f"=> {n_cells * cell / 3600.0:.2f} h per replica", flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bench_cell.json").write_text(json.dumps(out))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="llama", choices=list(MODELS))
    ap.add_argument("--variant", required=True, choices=VARIANTS)
    ap.add_argument("--layer", type=int, required=True, choices=list(LAYERS))
    ap.add_argument("--positions", default=None,
                    choices=["legacy_ramp", "all_prompt", "all", "last"],
                    help="S3.2: override the variant's position policy")
    ap.add_argument("--tag", default="", help="suffix for this run's output files")
    ap.add_argument("--dose-ids", default="", dest="dose_ids",
                    help="S3.2: restrict to these dose indices, e.g. 0,7")
    ap.add_argument("--directions", default="",
                    help="restrict to these directions, e.g. probe")
    ap.add_argument("--phase", default="all",
                    choices=["train", "sweep", "bench", "all"])
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    loaded = load(a.model, "bf16")
    print(f"[g4] model loaded in {(time.time()-t0)/60:.1f} min", flush=True)
    if a.phase == "bench":
        phase_bench(a.model, loaded)
    elif a.phase == "train":
        phase_train(a.model, a.variant, a.layer, loaded, a.positions)
    else:
        phase_sweep(a.model, a.variant, a.layer, loaded, a.positions, a.tag,
                    a.dose_ids, a.directions)
    print(f"[g4] {a.phase} finished in {(time.time()-t0)/60:.1f} min", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
