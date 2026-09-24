"""G4u -- direction geometry for the ultimatum game.

The lottery version of this panel (`figures/g4_summary.png`, panel B) places
candidate directions by their cosine with the **choice probe**. That cannot be
repeated here. G4's own reconstruction run recorded, for ultimatum:

    n_kept=152, n_levels=19, classes=[1], trained=false,
    why="the legacy builder needs both classes; it raises here"

The model accepted at every offer on the pre-registered grid, which runs from 10
to 100 tokens out of a pie of 100. With one class there is no choice to separate,
so no choice probe, and no difference of means between chosen and rejected.

So the reference direction here is the **offer probe**: the same activations,
labelled by whether the prompt's own offer is above the grid median. That label
exists whatever the model answers. Every other direction is then placed against
it, exactly as the lottery panel places directions against the choice probe:

    offer probe     logistic regression on above/below the median offer
    diffmean        mean activation at high offers minus mean at low offers
                    (the CAA / ActAdd form, on the offer contrast)
    pca1            first principal component of the centred activations
                    (the RepE / LAT form; uses no label at all)
    ridge_logn      ridge regression on log(offer); a payoff code by construction
    readout grad    the answer-logit gradient, loaded from the existing
                    fallback_gradient_L{layer}_ultimatum.npy rather than rebuilt
    rand0, rand1    isotropic random directions, the null

Cosines are reported in multiples of the 1/sqrt(d) null scale, d = 8192, which is
what the lottery panel does.

**Limits, stated because they bound every number here.** The activation is taken
at the final prompt token and does not depend on which sample was drawn, so there
are only **19 distinct activation vectors**, one per offer level. A direction in
8,192 dimensions fitted to 19 points is heavily underdetermined. The lottery panel
has the same structure with 45 levels. Neither is a held-out measurement, and
nothing here is pre-registered.

Stages:
    collect   one model load, both layers hooked, 19 offers, 8 samples each
    build     directions and the cosine table, no GPU
    figure    the two-panel PNG and PDF
"""
from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
from typing import Dict, List

import numpy as np

os.environ.setdefault("HF_HOME", "/orcd/data/gabrieli/001/guna23/hf_cache")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g4u"
G4BDIR = RUNROOT / "g4b"

# the legacy grid, unchanged: offers 10..100 in steps of 5
ULTIMATUM_GRID = list(range(10, 105, 5))
PROBE_SAMPLES = 8          # matches G4's n_samples_per_param
LAYERS = (48, 50)
MAX_NEW_TOKENS = 256       # matches G4's reconstruction cap
NULL_D = 8192

# Deterministic, unlike G4b's `abs(hash((layer, game, which)))`, which is salted
# per process for strings and so does not reproduce across runs.
RAND_SEEDS = {"rand0": 40810, "rand1": 40811}


# ---------------------------------------------------------------------------
# collect
# ---------------------------------------------------------------------------
def collect() -> Path:
    import torch
    from cv_bench.instr import prompt_for, decision_code
    from cv_bench.s21_fix import load

    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / "ultimatum_activations.npz"
    meta_path = OUT / "ultimatum_collect.json"
    if path.exists():
        print(f"[g4u] already collected: {path}", flush=True)
        return path

    model, tok = load("llama", "bf16")
    grabbed: Dict[int, "torch.Tensor"] = {}
    handles = []

    def make_hook(layer: int):
        def hook(_m, _i, out):
            h = out[0] if isinstance(out, tuple) else out
            grabbed[layer] = h.detach()
        return hook

    for layer in LAYERS:
        handles.append(model.model.layers[layer].register_forward_hook(make_hook(layer)))

    acts = {layer: [] for layer in LAYERS}
    norms = {layer: [] for layer in LAYERS}
    rows: List[dict] = []
    try:
        for offer in ULTIMATUM_GRID:
            text = prompt_for("ultimatum", offer)
            msgs = [{"role": "user", "content": text}]
            rendered = tok.apply_chat_template(msgs, tokenize=False,
                                               add_generation_prompt=True)
            enc = tok(rendered, return_tensors="pt").to(model.device)
            with torch.inference_mode():
                model(**enc, use_cache=False)
            for layer in LAYERS:
                h_all = grabbed[layer][0].float()
                norms[layer].append(float(h_all[1:].norm(dim=-1).median()))
                acts[layer].append(h_all[-1].cpu().numpy())

            torch.manual_seed(int(offer))
            with torch.inference_mode():
                gen = model.generate(**enc, max_new_tokens=MAX_NEW_TOKENS,
                                     do_sample=True, temperature=0.7, top_p=0.95,
                                     num_return_sequences=PROBE_SAMPLES,
                                     pad_token_id=tok.pad_token_id)
            n_in = enc["input_ids"].shape[1]
            for row in gen:
                out_text = tok.decode(row[n_in:], skip_special_tokens=True)
                dd = decision_code(out_text, "ultimatum")
                rows.append(dict(offer=int(offer), kind=dd["kind"],
                                 choice=(-1 if dd["choice"] is None
                                         else int(dd["choice"])),
                                 text=out_text))
            coded = [r for r in rows if r["offer"] == offer and r["choice"] >= 0]
            acc = sum(r["choice"] for r in coded)
            print(f"[g4u] offer {offer:3d}: {acc}/{len(coded)} accept "
                  f"({PROBE_SAMPLES - len(coded)} uncoded)", flush=True)
    finally:
        for h in handles:
            h.remove()

    np.savez(path, offers=np.asarray(ULTIMATUM_GRID, dtype=float),
             **{f"acts_L{layer}": np.stack(acts[layer], 0) for layer in LAYERS})
    meta_path.write_text(json.dumps(dict(
        grid=ULTIMATUM_GRID, probe_samples=PROBE_SAMPLES,
        max_new_tokens=MAX_NEW_TOKENS, layers=list(LAYERS),
        median_norm={str(k): float(np.median(v)) for k, v in norms.items()},
        rows=rows), indent=1))
    print(f"[g4u] wrote {path} and {meta_path}", flush=True)
    return path


# ---------------------------------------------------------------------------
# build
# ---------------------------------------------------------------------------
def _unit(v):
    n = np.linalg.norm(v)
    return v / n if n > 0 else v


def directions(X: np.ndarray, offers: np.ndarray) -> Dict[str, np.ndarray]:
    """Everything G4 builds, with the offer contrast in place of the choice one.

    Built in standardised space and mapped back to raw, which is what G4's
    `*_raw` fields hold and therefore what the lottery panel compares.
    """
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    sc = StandardScaler().fit(X)
    Z = sc.transform(X)
    hi = (offers > np.median(offers)).astype(int)

    def to_raw(v):
        return None if v is None else _unit(v / np.clip(sc.scale_, 1e-8, None))

    out: Dict[str, np.ndarray] = {}

    lr = LogisticRegression(penalty="l2", C=1.0, max_iter=2000).fit(Z, hi)
    out["offer_probe"] = to_raw(_unit(lr.coef_[0]))
    out["_offer_probe_acc"] = float(lr.score(Z, hi))

    dm = Z[hi == 1].mean(0) - Z[hi == 0].mean(0)
    out["diffmean"] = to_raw(_unit(dm))

    Zc = Z - Z.mean(0, keepdims=True)
    _, _, Vt = np.linalg.svd(Zc, full_matrices=False)
    out["pca1"] = to_raw(_unit(Vt[0]))

    t = np.log(offers.astype(float))
    A = Z.T @ Z + 1.0 * np.eye(Z.shape[1])
    out["ridge_logn"] = to_raw(_unit(np.linalg.solve(A, Z.T @ (t - t.mean()))))

    d = X.shape[1]
    for name, seed in RAND_SEEDS.items():
        out[name] = _unit(np.random.default_rng(seed).normal(size=d))
    return out


def build() -> Path:
    npz = np.load(OUT / "ultimatum_activations.npz", allow_pickle=False)
    offers = npz["offers"]
    meta = json.loads((OUT / "ultimatum_collect.json").read_text())

    null_scale = 1.0 / np.sqrt(NULL_D)
    recs: List[dict] = []
    for layer in LAYERS:
        X = npz[f"acts_L{layer}"]
        dirs = directions(X, offers)
        acc = dirs.pop("_offer_probe_acc")
        g = G4BDIR / f"fallback_gradient_L{layer}_ultimatum.npy"
        if g.exists():
            dirs["readout_gradient"] = _unit(np.load(g).astype(float))
        ref = dirs["offer_probe"]
        for name, v in dirs.items():
            if name == "offer_probe":
                continue
            c = float(np.dot(ref, v))
            recs.append(dict(layer=layer, game="ultimatum", reference="offer_probe",
                             direction=name, cosine=round(c, 5),
                             abs_cosine=round(abs(c), 5),
                             null_scale=round(null_scale, 5),
                             multiples_of_null=round(abs(c) / null_scale, 2),
                             d=X.shape[1], n_levels=len(offers),
                             offer_probe_train_accuracy=round(acc, 4)))
        print(f"[g4u] L{layer}: offer probe train accuracy {acc:.3f}", flush=True)

    # the acceptance curve, for panel A
    per: Dict[int, List[int]] = {}
    for r in meta["rows"]:
        if r["choice"] >= 0:
            per.setdefault(r["offer"], []).append(r["choice"])
    curve = [dict(offer=o, n_coded=len(v), n_accept=int(sum(v)),
                  p_accept=round(sum(v) / len(v), 4)) for o, v in sorted(per.items())]

    OUT.mkdir(parents=True, exist_ok=True)
    geo = OUT / "g4u_geometry.csv"
    with open(geo, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(recs[0].keys()))
        w.writeheader()
        w.writerows(recs)
    cur = OUT / "g4u_acceptance.csv"
    with open(cur, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(curve[0].keys()))
        w.writeheader()
        w.writerows(curve)
    print(f"[g4u] wrote {geo} and {cur}", flush=True)
    return geo


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--stage", required=True,
                    choices=("collect", "build", "figure"))
    a = ap.parse_args(argv)
    if a.stage == "collect":
        collect()
    elif a.stage == "build":
        build()
    else:
        from cv_bench.g4u_figure import make
        make()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
