"""B3.3 pass 1 - put the choice probe beside the anchors and the controls.

EXPLORATORY, SELECTION SPLIT, NOT PRE-REGISTERED. Gate B2 stands failed, so no
direction is certified preference-like here; the question this answers is the
weaker, descriptive one the authors asked for:

    does the probe's behaviour resemble the bias adapter, the readout
    direction, or neither?

Every direction is dosed to the SAME BEHAVIOURAL EFFECT - the shift of the
legacy switching point produced by the bias adapter - solved on the calibration
split, so the comparison is at matched behaviour rather than matched norm. The
readout anchor and the bias adapter are the two poles; the probe is placed
between them; the reward probe, the difference-of-means direction and two
random directions say how much of any resemblance is free.

Directions are LOADED BY HASH from the Friday session's G4 artefacts and from
B3.1. Nothing is refitted here.

Stages, each resumable:

    --stage directions   CPU. Assemble and hash every direction.
    --stage dose         GPU. Solve each direction's scale on `cal`.
    --stage read         GPU. Read the selection split under every condition.
    --stage analyse      CPU. D1-D7, parametric shares, out-of-frame, report.

A note on D4 and D6. Both are implemented for synthetic agents: `d4_ce_vs_choice`
takes true and fitted AgentParams, and `d6_recall` takes the true parameters of
the intervened agent. A real direction has no true parameters - that is the whole
point of measuring it - and the model-side versions would need certainty
equivalents and fact recall ELICITED from the model, which is a prompt family
this repo does not have. They are reported as "not available" with that reason
rather than filled with a synthetic stand-in.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

SHARE = Path("${ICLR_RUNROOT}")
G4 = SHARE / "g4"
B31 = SHARE / "trackB" / "b3_gradient"
B32 = SHARE / "trackB" / "b3_lora_70b"
DEFAULT_OUT = SHARE / "trackB" / "b33_probe_vs_anchors"

LAYERS = (48, 50)
STEM = "My choice: "
MODEL_ID = "meta-llama/Llama-3.3-70B-Instruct"

# The legacy cell the switching point is read in: safe 50 tokens at p = 0.5.
LEGACY_CELL = (0.5, 50.0)


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for blk in iter(lambda: fh.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


@dataclass
class Direction:
    name: str
    layer: int
    vector: np.ndarray
    source: str
    source_sha256: str
    role: str           # anchor | probe | control


# --------------------------------------------------------------------------
def load_directions(seed: int = 0) -> List[Direction]:
    """Every direction, by hash, from artefacts this session did not produce."""
    out: List[Direction] = []
    for L in LAYERS:
        # --- the rebuilt choice probe, and two of the controls, from G4 ---
        src = G4 / f"probe_reconstruction_L{L}.json"
        d = json.loads(src.read_text())
        sha = sha256(src)
        game = d["games"]["lottery"]
        for key, name, role in (("direction_raw", "choice_probe", "probe"),
                                ("reward_raw", "reward_probe", "control"),
                                ("diffmean_raw", "diffmean", "control")):
            out.append(Direction(name, L, np.asarray(game[key], dtype=np.float32),
                                 src.name, sha, role))
        # --- the readout-direction anchor, order-invariant, from B3.1 ---
        gsrc = B31 / f"grad_L{L}_legacy_sum.npy"
        out.append(Direction("readout_anchor", L, np.load(gsrc).astype(np.float32),
                             gsrc.name, sha256(gsrc), "anchor"))
        # --- two isotropic random controls, seeded, same dimension ---
        dim = out[-1].vector.shape[-1]
        rng = np.random.default_rng(seed + L)
        for k in ("random_a", "random_b"):
            out.append(Direction(k, L, rng.standard_normal(dim).astype(np.float32),
                                 f"isotropic seed={seed + L}", "n/a", "control"))
    return out


# --------------------------------------------------------------------------
def legacy_switch(trials, p_risky: np.ndarray) -> Optional[float]:
    """The legacy cell's switching point, or the mean cell if it is absent."""
    from cv_bench.estimator import fingerprint as FP
    sw = FP.switching_points(trials, p_risky)
    if not sw:
        return None
    if LEGACY_CELL in sw:
        return float(sw[LEGACY_CELL])
    return float(np.mean(list(sw.values())))


def _p_from_z(z: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.asarray(z, dtype=float)))


def measure(trials, z: np.ndarray, s0: float) -> Tuple[float, Optional[str]]:
    """Switching-point shift, and if there is no crossing, which way it ran out.

    `switching_points` returns nothing when P(risky) never crosses 0.5 across
    the ramp, and that happens for OPPOSITE reasons: a dose strong enough that
    the model always takes the gamble, or one that pushes it to always take the
    sure thing. Collapsing both to NaN and treating NaN as "too weak" is what
    made the first solver march the scale upwards and match 2 of 12.
    """
    p = _p_from_z(z)
    s = legacy_switch(trials, p)
    if s is not None:
        return s - s0, None
    return float("nan"), ("risky" if float(np.nanmean(p)) > 0.5 else "safe")


# --------------------------------------------------------------------------
def dose_trials():
    """The legacy cell's sure-gain ramp on `cal`: 11 reward levels, 30..230.

    Restricted to the one cell the switching point is defined in. The whole
    sure-gain family would be 348 rows and the dose search reads it ~74 times;
    the cell alone is 44 and carries the same switching point.
    """
    from cv_bench.tasks import risk, core
    content = [t for t in risk.generate_risk(splits=("cal",))
               if t.family == "sure_gain"
               and (t.param_dict["p"], t.param_dict["s"]) == LEGACY_CELL]
    return list(core.expand_formats(content, response_formats=("mc",),
                                    label_sets=("legacy",)))


def eval_trials():
    """The selection split with format variation, which D5 requires."""
    from cv_bench.tasks import risk, core
    content = list(risk.generate_risk(splits=("sel",)))
    return list(core.expand_formats(content, response_formats=("mc",),
                                    label_sets=("legacy", "neutral")))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True,
                    choices=("directions", "dose", "read", "analyse"))
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--tol", type=float, default=0.03,
                    help="relative tolerance on the matched switching-point shift")
    ap.add_argument("--max-iter", type=int, default=5)
    ap.add_argument("--scale-hi", type=float, default=4.0,
                    help="upper bracket, in median-residual-norm units")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)

    if a.stage == "directions":
        return stage_directions(a)
    if a.stage == "dose":
        return stage_dose(a)
    if a.stage == "read":
        return stage_read(a)
    return stage_analyse(a)


def stage_directions(a) -> int:
    ds = load_directions(a.seed)
    np.savez(a.out / "directions.npz", **{f"{d.name}_L{d.layer}": d.vector for d in ds})
    meta = [{"name": d.name, "layer": d.layer, "role": d.role,
             "source": d.source, "source_sha256": d.source_sha256,
             "dim": int(d.vector.shape[-1]),
             "norm": float(np.linalg.norm(d.vector))} for d in ds]
    (a.out / "directions.json").write_text(json.dumps(meta, indent=2))
    for m in meta:
        print(f"{m['name']:<16} L{m['layer']}  {m['role']:<8} "
              f"dim={m['dim']} |v|={m['norm']:.3f}  {m['source']}  {m['source_sha256'][:12]}")
    print(f"\n{len(ds)} directions -> {a.out/'directions.json'}")
    return 0


# -- the GPU stages are thin: they exist so the run is resumable -------------
def _load_stack(out: Path):
    """Base model + the B3.2 bias adapter, with the adapter switchable off."""
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import LoraConfig, get_peft_model, set_peft_model_state_dict
    tok = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.bfloat16, device_map="auto",
        low_cpu_mem_usage=True)
    model.eval()
    cfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.0, bias="none",
                     task_type="CAUSAL_LM",
                     target_modules=["q_proj", "k_proj", "v_proj", "o_proj",
                                     "gate_proj", "up_proj", "down_proj"])
    peft_model = get_peft_model(model, cfg, adapter_name="bias")
    sd = torch.load(B32 / "adapter_bias.pt", map_location="cpu")
    set_peft_model_state_dict(peft_model, sd, adapter_name="bias")
    peft_model.eval()
    from cv_bench.readout import Readout
    return peft_model, tok, Readout(peft_model, tok)


def _read(ro, peft_model, trials, out: Path, tag: str,
          intervention=None, use_adapter: bool = False) -> np.ndarray:
    """Unbatched z for one condition, resumable, adapter on or bypassed."""
    import contextlib
    from cv_bench.estimator import checkpoint as CK
    from cv_bench.tasks import core
    # keyed on the rendered prompt, not the trial id (BD33): ids hash content
    # and format, not the words the model is shown.
    key = CK.items_key([t.trial_id for t in trials],
                       [ro.render(core.to_trial_spec(t, stem=STEM)) for t in trials])
    part = CK.Partial(out / f"ckpt_{tag}.npz", len(trials), chunk=50, key=key)
    ctx = contextlib.nullcontext() if use_adapter else peft_model.disable_adapter()
    with ctx:
        for i in range(part.n_done, len(trials)):
            spec = core.to_trial_spec(trials[i], stem=STEM)
            part.append(ro.score(spec, intervention=intervention).logit_diff)
            if i % 100 == 0:
                CK.heartbeat(out / "heartbeat.json", stage=tag,
                             done=i + 1, total=len(trials))
    part.flush()
    return np.asarray(part.data[:, 0], dtype=float)


def stage_dose(a) -> int:
    """Solve each direction's scale so its switching-point shift matches bias."""
    from cv_bench import steer
    from cv_bench.tasks import core
    meta = json.loads((a.out / "directions.json").read_text())
    vecs = np.load(a.out / "directions.npz")
    trials = dose_trials()
    print(f"dose split: {len(trials)} sure-gain rows on cal", flush=True)

    peft_model, tok, ro = _load_stack(a.out)

    z0 = _read(ro, peft_model, trials, a.out, "dose_unmodified")
    s0 = legacy_switch(trials, _p_from_z(z0))
    zb = _read(ro, peft_model, trials, a.out, "dose_bias", use_adapter=True)
    sb = legacy_switch(trials, _p_from_z(zb))
    target = sb - s0
    print(f"unmodified switch {s0:.2f}; bias adapter {sb:.2f}; "
          f"target shift {target:+.2f}", flush=True)

    # residual-stream unit so doses are comparable across directions
    prompts = [ro.render(core.to_trial_spec(t, stem=STEM)) for t in trials[:32]]
    units = {L: float(steer.median_residual_norm(peft_model, tok, prompts, L))
             for L in LAYERS}
    print("median residual norm:", units, flush=True)

    solved = {}
    LADDER = (0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0)

    def read_at(name, L, v, scale, sign, tag):
        iv = steer.Intervention(layer=L, vectors=v, scale=scale, sign=sign,
                                positions="last", mode="add", norm_unit=units[L])
        z = _read(ro, peft_model, trials, a.out, tag, intervention=iv)
        return measure(trials, z, s0)

    for m in meta:
        name, L = m["name"], m["layer"]
        v = vecs[f"{name}_L{L}"]

        # 1. which sign moves the switching point toward the target at all
        sign, probe = +1, None
        for cand in (+1, -1):
            sh, sat = read_at(name, L, v, 1.0, cand, f"dose_{name}_L{L}_sgn{cand}")
            toward = (np.isfinite(sh) and np.sign(sh) == np.sign(target)) or \
                     (sat == ("risky" if target < 0 else "safe"))
            print(f"  {name} L{L} sign{cand:+d} scale=1.0 shift={sh:+.3f} "
                  f"sat={sat} toward={toward}", flush=True)
            if toward:
                sign, probe = cand, (sh, sat)
                break
        if probe is None:
            solved[f"{name}_L{L}"] = {**m, "scale": float("nan"), "sign": 0,
                                      "shift": float("nan"), "switch": None,
                                      "target_shift": target, "norm_unit": units[L],
                                      "matched": False,
                                      "note": "no sign moves the switching point "
                                              "toward the bias adapter's shift"}
            continue

        # 2. ladder until the shift overshoots the target or the ramp saturates
        lo, hi, best = 0.0, None, {"scale": 0.0, "shift": 0.0, "switch": s0}
        for sc in LADDER:
            sh, sat = read_at(name, L, v, sc, sign, f"dose_{name}_L{L}_lad{sc}")
            print(f"  {name} L{L} sign{sign:+d} scale={sc:.3f} shift={sh:+.3f} "
                  f"sat={sat} (target {target:+.3f})", flush=True)
            if np.isfinite(sh) and abs(sh - target) < abs(best["shift"] - target):
                best = {"scale": sc, "shift": sh, "switch": s0 + sh}
            if sat is not None or (np.isfinite(sh) and abs(sh) >= abs(target)):
                hi = sc
                break
            lo = sc
        if hi is None:
            hi = LADDER[-1]

        # 3. bisect the bracket
        for it in range(a.max_iter):
            if abs(best["shift"] - target) <= abs(target) * a.tol:
                break
            mid = 0.5 * (lo + hi)
            sh, sat = read_at(name, L, v, mid, sign, f"dose_{name}_L{L}_bis{it}")
            print(f"  {name} L{L} sign{sign:+d} scale={mid:.4f} shift={sh:+.3f} "
                  f"sat={sat} (target {target:+.3f})", flush=True)
            if np.isfinite(sh) and abs(sh - target) < abs(best["shift"] - target):
                best = {"scale": mid, "shift": sh, "switch": s0 + sh}
            if sat is not None or (np.isfinite(sh) and abs(sh) > abs(target)):
                hi = mid          # saturated or overshot: come down
            else:
                lo = mid          # still short: go up
        solved[f"{name}_L{L}"] = {
            **m, **best, "sign": sign, "target_shift": target,
            "norm_unit": units[L],
            "matched": bool(np.isfinite(best["shift"]) and
                            abs(best["shift"] - target) <= abs(target) * a.tol)}

    (a.out / "doses.json").write_text(json.dumps(
        {"target_shift": target, "switch_unmodified": s0, "switch_bias": sb,
         "units": units, "solved": solved}, indent=2))
    n_ok = sum(1 for v in solved.values() if v["matched"])
    print(f"\nmatched {n_ok} of {len(solved)} directions to within {a.tol:.0%}")
    return 0


def stage_read(a) -> int:
    """Read the selection split under every condition at its matched dose."""
    from cv_bench import steer
    doses = json.loads((a.out / "doses.json").read_text())
    vecs = np.load(a.out / "directions.npz")
    trials = eval_trials()
    print(f"eval split: {len(trials)} selection rows, "
          f"{len({t.fmt.label_set for t in trials})} label sets", flush=True)

    peft_model, tok, ro = _load_stack(a.out)
    z = {"unmodified": _read(ro, peft_model, trials, a.out, "sel_unmodified"),
         "bias_adapter": _read(ro, peft_model, trials, a.out, "sel_bias",
                               use_adapter=True)}
    for key, d in doses["solved"].items():
        iv = steer.Intervention(layer=d["layer"], vectors=vecs[key],
                                scale=d["scale"], positions="last", mode="add",
                                norm_unit=d["norm_unit"])
        z[key] = _read(ro, peft_model, trials, a.out, f"sel_{key}", intervention=iv)
        print(f"read {key} at scale {d['scale']:.4f}", flush=True)
    np.savez(a.out / "z_selection.npz", **z)
    (a.out / "read_done.json").write_text(json.dumps(
        {"n_trials": len(trials), "conditions": sorted(z),
         "utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}, indent=2))
    print(f"wrote {a.out/'z_selection.npz'} with {len(z)} conditions")
    return 0


def stage_analyse(a) -> int:
    from cv_bench.anchors.analysis_b33 import analyse
    return analyse(a.out, eval_trials())


if __name__ == "__main__":
    raise SystemExit(main())
