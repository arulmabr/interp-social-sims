"""G4b -- direction geometry.

Which of the directions G4 steers along are the same direction?

The measurement is a cosine table over every direction in play at one layer and
game, together with the null that two unrelated directions in d dimensions have
a cosine of about 1/sqrt(d), so a "small" cosine can be read against something.

  probe      the rebuilt choice probe                      (cv_bench/g4.py)
  reward     a probe on the same activations, labelled by
             whether the prompt's payoff is above the grid
             median -- the extension plan's hypothesis 1    (cv_bench/g4.py)
  rand0/1    seeded unit vectors                            (cv_bench/g4.py)
  gradient   B3.1's answer-readout anchor, `legacy_one_format`
             version: grad of z with respect to the residual
             stream at the intervention layer, final prompt
             token, averaged over calibration-split core
             prompts, at layers 48 and 50                    (Track B, B3.1)
  gradient_both_orders
             the same anchor averaged over option orders and
             label sets. The cosine between the two versions
             is reported: it says how much of the anchor is a
             property of the surface format rather than of
             the readout                                     (Track B, B3.1)

**The gradient anchor belongs to Track B (ICLR_PLAN.md B3.1, amendment A5) and
is not built here.** This module loads Track B's saved direction from `trackB/`
on the lab share once its hash is committed on `iclr-trackB`. If it is not there
when G4 is committed, `--fallback` computes one to the same definition and every
row carrying it is labelled `duplicate_to_reconcile`, because two independently
computed anchors are two numbers until someone reconciles them. The fallback
also records which prompt set it used: Track B's calibration-split core prompts
are defined by B1/B2 and are not available on this side, so the fallback uses
this session's off-grid calibration set and says so in the same field.

    python -m cv_bench.g4b                    # geometry from what exists
    python -m cv_bench.g4b --fallback --layer 48   # GPU; only if B3.1 is absent
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

os.environ.setdefault("HF_HOME", "${HF_HOME}")
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

ROOT = Path(__file__).resolve().parents[1]
RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "${ICLR_RUNROOT}"))
G4DIR = RUNROOT / "g4"
TRACKB = RUNROOT / "trackB"
OUT = RUNROOT / "g4b"

LAYERS = (48, 50)
GAMES = ("lottery", "ultimatum")
VARIANTS = ("as_written", "reconstruction")


# ---------------------------------------------------------------------------
# Track B's gradient anchor
# ---------------------------------------------------------------------------
def _sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _hash_is_committed(digest: str) -> Tuple[bool, str]:
    """Is this file's hash recorded anywhere in the repository's history?

    Track B commits the hash of the artefact rather than the artefact, so the
    direction we load can be tied to a commit. A direction on the share whose
    hash is not committed is not yet the anchor of record.
    """
    for args in (["git", "log", "--all", "-S", digest, "--oneline"],
                 ["git", "grep", "-l", digest, "--all-match"]):
        try:
            out = subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                                 timeout=60)
            if out.returncode == 0 and out.stdout.strip():
                return True, out.stdout.strip().splitlines()[0]
        except Exception:
            continue
    return False, ""


# B3.1 produces two versions, and Track B names them. `legacy_one_format` is the
# one G4b steers against, per the authors' instruction of 22 Sept; `both_orders`
# is the version averaged over option orders and label sets, and the cosine
# between the two is itself a reported number -- it says how much of the anchor
# is a property of the format rather than of the readout.
TRACKB_VERSIONS = ("legacy_one_format", "both_orders")


def trackB_gradient(layer: int, game: str,
                    version: str = "legacy_one_format") -> Optional[dict]:
    """One version of Track B's B3.1 direction, if its hash is committed.

    A direction sitting on the share whose hash is not recorded in the history is
    not yet the anchor of record, and is skipped with a note rather than used.
    """
    if not TRACKB.exists():
        return None
    pats = [f"b3*/gradient_{version}_L{layer}_{game}.npy",
            f"b3*/gradient_{version}_L{layer}_{game}*.npy",
            f"b3*/*{version}*L{layer}*{game}*.npy",
            f"b3*/*{version}*L{layer}*{game}*.json"]
    hits: List[Path] = []
    for pat in pats:
        hits.extend(sorted(TRACKB.glob(pat)))
    seen = set()
    for q in hits:
        if q in seen:
            continue
        seen.add(q)
        digest = _sha256(q)
        committed, where = _hash_is_committed(digest)
        if not committed:
            print(f"[g4b] {q.name} is on the share but its hash is not committed; "
                  f"not using it", flush=True)
            continue
        vec = (np.load(q) if q.suffix == ".npy"
               else np.asarray(json.loads(q.read_text())["direction"], dtype=np.float32))
        vec = np.asarray(vec, dtype=np.float32).ravel()
        return dict(direction=vec / (np.linalg.norm(vec) + 1e-12),
                    source=f"trackB/B3.1/{version}", version=version,
                    path=str(q.relative_to(RUNROOT)), sha256=digest,
                    committed_at=where, duplicate_to_reconcile=False)
    return None


def fallback_gradient(layer: int, game: str, model_key: str = "llama",
                      loaded=None) -> dict:
    """B3.1's definition, computed here because Track B's is not yet committed.

    grad of z with respect to the residual stream at `layer`, final prompt token,
    averaged over calibration prompts. Two versions: within one format, and
    averaged over option orders and label sets. Both are unit vectors.

    z is the logit difference between the two option tokens -- the same z the
    readout reports (ICLR_PLAN.md S2.1).
    """
    import torch
    from cv_bench.s21_fix import load, CAL_LOTTERY, CAL_ULTIMATUM
    from cv_bench.readout import Readout, TrialSpec
    from cv_bench.neutral import build as build_neutral

    done = OUT / f"fallback_gradient_L{layer}_{game}.npy"
    if done.exists():
        print(f"[g4b] L{layer} {game} already computed; skipping", flush=True)
        import numpy as _np
        return dict(direction=_np.load(done), source="cv_bench/g4b.py friday-session",
                    version="friday_session", layer=layer, game=game,
                    duplicate_to_reconcile=True, note="loaded from disk")
    model, tok = loaded or load(model_key, "bf16")
    rd = Readout(model, tok)
    from cv_bench.instr import LABELS, STEM, prompt_for

    vals = (CAL_LOTTERY if game == "lottery" else CAL_ULTIMATUM)[:25]
    grabbed: Dict[str, torch.Tensor] = {}

    def hook(_m, _i, out):
        h = out[0] if isinstance(out, tuple) else out
        h.retain_grad()
        grabbed["h"] = h
        return out

    handle = model.model.layers[layer].register_forward_hook(hook)

    def one(text: str, labels) -> np.ndarray:
        enc = tok(text, return_tensors="pt").to(model.device)
        model.zero_grad(set_to_none=True)
        out = model(**enc, use_cache=False)          # no inference_mode: we need grad
        neg = rd.label_token_ids(labels[0])
        pos = rd.label_token_ids(labels[1])
        last = out.logits[0, -1, :].float()
        z = torch.logsumexp(last[pos], 0) - torch.logsumexp(last[neg], 0)
        z.backward()
        g = grabbed["h"].grad[0, -1, :].detach().float().cpu().numpy()
        return g

    try:
        # version 1: one format
        acc = np.zeros(model.config.hidden_size, dtype=np.float64)
        for v in vals:
            spec = TrialSpec(prompt=prompt_for(game, v), labels=LABELS[game],
                             stem=STEM, use_chat_template=True)
            acc += one(rd.render(spec), LABELS[game])
        v1 = acc / len(vals)

        # version 2: averaged over option orders and label sets
        acc2 = np.zeros_like(acc)
        n2 = 0
        for framing, flips in (("counterbalanced", (False, True)),):
            for flip in flips:
                for v in vals:
                    prompt, labels = build_neutral(framing, game, int(v), flip)
                    spec = TrialSpec(prompt=prompt, labels=labels, stem="Answer:",
                                     use_chat_template=True)
                    acc2 += one(rd.render(spec), labels)
                    n2 += 1
        for v in vals:
            spec = TrialSpec(prompt=prompt_for(game, v), labels=LABELS[game],
                             stem=STEM, use_chat_template=True)
            acc2 += one(rd.render(spec), LABELS[game])
            n2 += 1
        v2 = acc2 / max(n2, 1)
    finally:
        handle.remove()

    def unit(x):
        return (x / (np.linalg.norm(x) + 1e-12)).astype(np.float32)

    OUT.mkdir(parents=True, exist_ok=True)
    doc = dict(direction=unit(v1), direction_format_averaged=unit(v2),
               source="cv_bench/g4b.py friday-session",
               version="friday_session",
               definition=("grad of z (logit difference) wrt the residual stream at "
                           "the layer, final prompt token, averaged over prompts; "
                           "ICLR_PLAN.md B3.1"),
               prompt_set=("this session's off-grid calibration values "
                           "(n %% 5 in (2,3)), NOT Track B's calibration-split core "
                           "prompts, which are defined by B1/B2 and are not "
                           "available on this side"),
               n_prompts=len(vals), layer=layer, game=game,
               duplicate_to_reconcile=True,
               note=("the Friday-session version. Track B's B3.1 is being rebuilt "
                     "after a labelling bug, so this is computed here rather than "
                     "waited for. It is a second measurement of the same defined "
                     "quantity, not a replacement: reconcile the two when B3.1 "
                     "lands."))
    np.save(OUT / f"fallback_gradient_L{layer}_{game}.npy", doc["direction"])
    np.save(OUT / f"fallback_gradient_fmtavg_L{layer}_{game}.npy",
            doc["direction_format_averaged"])
    meta = {k: v for k, v in doc.items() if not isinstance(v, np.ndarray)}
    (OUT / f"fallback_gradient_L{layer}_{game}.json").write_text(json.dumps(meta))
    print(f"[g4b] friday-session gradient L{layer} {game}: computed here; "
          f"reconcile with Track B's B3.1 when it lands", flush=True)
    return doc


# ---------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------
def g4_directions(variant: str, layer: int, game: str) -> Dict[str, np.ndarray]:
    """The directions G4 built, in raw space."""
    p = G4DIR / f"probe_{variant}_L{layer}.json"
    if not p.exists():
        return {}
    g = json.loads(p.read_text())["games"].get(game, {})
    if not g.get("trained"):
        return {}
    out = {}
    if g.get("direction_raw"):
        out["probe"] = np.asarray(g["direction_raw"], dtype=np.float32)
    if g.get("reward_raw"):
        out["reward"] = np.asarray(g["reward_raw"], dtype=np.float32)
    # The G4b baselines themselves: difference-of-means (CAA / ActAdd form),
    # first PCA (RepE / LAT form) and a ridge probe for log n. FRIDAY_PLAN asks
    # for the cosine matrix among all of them and the choice probe, so leaving
    # them out of this table left the question unanswered.
    for name in ("diffmean", "pca1", "ridge_logn"):
        v = g.get(f"{name}_raw")
        if v:
            out[name] = np.asarray(v, dtype=np.float32)
    d = len(g["direction_raw"])
    for which in ("rand0", "rand1"):
        seed = abs(hash((layer, game, which))) % (2**31)
        v = np.random.default_rng(seed).normal(size=d)
        out[which] = (v / np.linalg.norm(v)).astype(np.float32)
    return out


def cosine(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.dot(a, b) / ((np.linalg.norm(a) * np.linalg.norm(b)) + 1e-12))


def geometry() -> List[dict]:
    from cv_bench.s1_data import write_csv
    rows: List[dict] = []
    for variant in VARIANTS:
        for layer in LAYERS:
            for game in GAMES:
                dirs = g4_directions(variant, layer, game)
                if not dirs:
                    continue
                gsrc, dup = "", False
                for version, name in ((("legacy_one_format"), "gradient"),
                                      (("both_orders"), "gradient_both_orders")):
                    g = trackB_gradient(layer, game, version)
                    if g is not None:
                        dirs[name] = g["direction"]
                        if name == "gradient":
                            gsrc, dup = g["source"], False
                if "gradient" not in dirs:
                    fb = OUT / f"fallback_gradient_L{layer}_{game}.npy"
                    fb2 = OUT / f"fallback_gradient_fmtavg_L{layer}_{game}.npy"
                    if fb.exists():
                        dirs["gradient"] = np.load(fb)
                        gsrc, dup = "cv_bench/g4b.py friday-session", True
                    if fb2.exists():
                        dirs["gradient_both_orders"] = np.load(fb2)
                d = len(next(iter(dirs.values())))
                null = 1.0 / np.sqrt(d)
                names = list(dirs)
                for i, a in enumerate(names):
                    for b in names[i + 1:]:
                        c = cosine(dirs[a], dirs[b])
                        rows.append(dict(
                            variant=variant, layer=layer, game=game, a=a, b=b,
                            cosine=round(c, 5), abs_cosine=round(abs(c), 5),
                            null_scale=round(float(null), 5),
                            multiples_of_null=round(abs(c) / null, 2),
                            d=d,
                            gradient_source=(gsrc if a.startswith("gradient")
                                             or b.startswith("gradient") else ""),
                            duplicate_to_reconcile=(dup if a.startswith("gradient")
                                                    or b.startswith("gradient")
                                                    else False)))
    if rows:
        write_csv("g4b_geometry.csv", rows,
                  ["variant", "layer", "game", "a", "b", "cosine", "abs_cosine",
                   "null_scale", "multiples_of_null", "d", "gradient_source",
                   "duplicate_to_reconcile"])
        for r in rows:
            flag = " [DUPLICATE]" if r["duplicate_to_reconcile"] else ""
            print(f"{r['variant']:14s} L{r['layer']} {r['game']:9s} "
                  f"{r['a']:8s} x {r['b']:8s}  cos {r['cosine']:+.4f}  "
                  f"({r['multiples_of_null']:.1f}x null){flag}")
    else:
        print("[g4b] no directions yet: G4's probe files do not exist")
    return rows


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--fallback", action="store_true",
                    help="compute the B3.1 gradient here, labelled a duplicate")
    ap.add_argument("--layer", type=int, default=0,
                    help="48 or 50; 0 (the default) means every layer in LAYERS")
    ap.add_argument("--game", default="both", choices=["lottery", "ultimatum", "both"])
    a = ap.parse_args()
    if a.fallback:
        # One load for every (layer, game). Separate sruns per layer could not
        # work: the second reloads 141 GB while the first still holds the GPUs
        # (D75). `--layer 0` means every layer in LAYERS, and is the default --
        # an explicit layer is still honoured.
        layers = [L for L in LAYERS if L in (48, 50)] if a.layer == 0 else [a.layer]
        if any(L not in (48, 50) for L in layers):
            raise SystemExit(f"refusing to compute a gradient at {layers}: "
                             f"B3.1 is defined at layers 48 and 50")
        games = GAMES if a.game == "both" else (a.game,)
        todo = [(L, g) for L in layers for g in games
                if not (OUT / f"fallback_gradient_L{L}_{g}.npy").exists()
                and trackB_gradient(L, g, "legacy_one_format") is None]
        if not todo:
            print("[g4b] every gradient is on disk or committed by Track B", flush=True)
        else:
            from cv_bench.s21_fix import load as _load
            shared = _load("llama", "bf16")
            print(f"[g4b] model loaded once for {len(todo)} pairs: {todo}", flush=True)
            for L, g in todo:
                fallback_gradient(L, g, loaded=shared)
    geometry()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
