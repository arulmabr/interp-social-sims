"""Score the SAE pilot's conditions with Track B's estimator (integration 1).

The pilot at `anchor_pilot/` judges each steering direction by the RMSE of its
risky-choice probabilities against a planted target. That answers "did it hit
the target" and cannot answer "what kind of change was it", which is the
question the anchors exist for. This module reads the pilot's own frozen
prompts and per-prompt logit margins, converts them into Track B trials, and
runs the five-family attribution with its cluster bootstrap over them.

Nothing here re-runs a model. It reads the pilot's saved evidence only, and the
pilot's files are never written to.

    python -m cv_bench.anchors.pilot_bridge --evidence <dir> [--write-manifest]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Sequence, Tuple

import numpy as np

from cv_bench.tasks.core import Format, Lottery, Trial

#: The pilot writes outcomes as [amount, probability]; Lottery takes
#: (probability, amount). Getting this backwards silently inverts every gamble,
#: so it is done in one place and tested.
def _lottery(pairs: Sequence[Sequence[float]]) -> Lottery:
    return Lottery(tuple((float(p), float(a)) for a, p in pairs))


def to_trial(row: Dict) -> Trial:
    """One pilot frozen row as a Track B trial.

    `risky_label == "A"` means the gamble is printed first, which is Track B's
    option_order 1. Labels are A and B in both of the pilot's wordings, so the
    label set is neutral and the format family reduces to position alone.
    """
    dom = {"safe": 0, "risky": 1}.get(row.get("dominant_option") or "", None)
    return Trial(
        domain="risk",
        family=str(row["frame"]),
        params=tuple(sorted({"p": float(row["probability"]),
                             "s": float(row["stake"]),
                             "x": float(row["reward"])}.items())),
        canonical=(_lottery(row["safe"]), _lottery(row["risky"])),
        split="sel",
        frame_role="core",
        fmt=Format(option_order=1 if row["risky_label"] == "A" else 0,
                   label_set="neutral", response_format="mc",
                   template_id=str(row["template"])),
        is_catch=dom is not None,
        dominant=dom,
        currency="tokens",
    )


def load(evidence: Path) -> Tuple[List[Trial], Dict[str, np.ndarray]]:
    rows = json.loads((evidence / "frozen_rows.json").read_text())
    trials = [to_trial(r) for r in rows]
    z: Dict[str, np.ndarray] = {}
    for p in sorted(evidence.glob("frozen_scores_*.json")):
        name = p.stem[len("frozen_scores_"):]
        s = json.loads(p.read_text())
        if len(s) != len(trials):
            continue
        z[name] = np.array([float(e["margin"]) for e in s], dtype=float)
    return trials, z


def score(trials: Sequence[Trial], z: Dict[str, np.ndarray],
          baseline: str = "baseline", n_boot: int = 400) -> Dict[str, Dict]:
    """Attribute every condition's change from baseline to a mechanism."""
    from cv_bench.estimator import fit as FIT
    from cv_bench.estimator.agents import AgentParams, ALPHA0, GAMMA0, LAMBDA0

    init = AgentParams(alpha=ALPHA0, gamma=GAMMA0, lam=LAMBDA0, tau=0.1186)
    # The lottery lesson: seed from the fitted baseline, never from theta0.
    base_par, _, _ = FIT.fit(list(trials), z[baseline], ("alpha", "gamma", "tau"),
                             init, observe="logit", free_templates=True)
    tpl = dict(FIT.fit.last_template_offsets)

    out: Dict[str, Dict] = {}
    for name, zc in z.items():
        if name == baseline:
            continue
        fits = FIT.fit_all_models(list(trials), zc, base_par, observe="logit",
                                  template_offsets=tpl)
        shares = FIT.model_shares(fits)
        boot = FIT.cluster_bootstrap(list(trials), fits, "preference", "action",
                                     n_boot=n_boot, seed=0)
        top = max(shares, key=shares.get)
        out[name] = {
            "shares": {k: float(v) for k, v in shares.items()},
            "top_family": top,
            "preference_share": float(shares.get("preference", np.nan)),
            "action_share": float(shares.get("action", np.nan)),
            "p_preference_beats_action": float(boot.get("p_a_better", np.nan)),
            "mean_dz": float(np.nanmean(zc - z[baseline])),
            "sd_dz": float(np.nanstd(zc - z[baseline])),
            "fitted_action": float(fits["action"]["params"].action),
            "fitted_alpha": float(fits["preference"]["params"].alpha),
        }
    out["_baseline_fit"] = {"alpha": float(base_par.alpha),
                            "gamma": float(base_par.gamma),
                            "tau": float(base_par.tau)}
    return out


def compression(trials: Sequence[Trial], z: Dict[str, np.ndarray],
                baseline: str = "baseline") -> Dict[str, Dict]:
    """How much of the payoff signal each condition leaves behind.

    Regress the change in the logit on the baseline logit. A slope of 0 means
    the intervention added something without touching how the model responds to
    the payoff. A slope of -1 means it removed that response entirely. What is
    left, 1 + slope, is the share of the payoff signal the measurement still has
    to work with, and any attribution made where that share is near zero is
    attributing whatever survives the collapse.
    """
    zb = z[baseline]
    out: Dict[str, Dict] = {}
    for name, zc in z.items():
        if name == baseline:
            continue
        d = zc - zb
        slope, icpt = np.polyfit(zb, d, 1)
        out[name] = {
            "slope_of_dz_on_baseline": float(slope),
            "signal_retained": float(1.0 + slope),
            "corr_dz_baseline": float(np.corrcoef(zb, d)[0, 1]),
            "mean_dz": float(d.mean()),
            "sd_after": float(zc.std()),
            "sd_baseline": float(zb.std()),
            "intercept": float(icpt),
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--evidence", required=True, type=Path)
    ap.add_argument("--json-out", type=Path, default=Path("reports/b8_pilot_attribution.json"))
    ap.add_argument("--n-boot", type=int, default=400)
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)

    trials, z = load(a.evidence)
    print(f"{len(trials)} frozen prompts, {len(z)} conditions", flush=True)
    r = score(trials, z, n_boot=a.n_boot)
    comp = compression(trials, z)
    for k, v in comp.items():
        if k in r:
            r[k].update(v)
    r["_compression"] = comp
    a.json_out.parent.mkdir(parents=True, exist_ok=True)
    a.json_out.write_text(json.dumps(r, indent=2, sort_keys=True))

    print(f"{'condition':<44}{'pref':>8}{'action':>8}{'top':>12}{'p(pref>act)':>13}")
    for k, v in sorted(r.items(), key=lambda kv: -kv[1].get("preference_share", -1)
                       if isinstance(kv[1], dict) and "shares" in kv[1] else 1):
        if not isinstance(v, dict) or "shares" not in v:
            continue
        print(f"{k:<44}{v['preference_share']:>8.3f}{v['action_share']:>8.3f}"
              f"{v['top_family']:>12}{v['p_preference_beats_action']:>13.3f}")

    if a.write_manifest:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        with open("MANIFEST_B.csv", "a", newline="") as fh:
            for k, v in r.items():
                if not isinstance(v, dict) or "shares" not in v:
                    continue
                for f in ("preference_share", "action_share",
                          "p_preference_beats_action"):
                    fh.write(f'B8.pilot.{k}.{f},{v[f]},'
                             f'cv_bench/anchors/pilot_bridge.py,'
                             f'anchor_pilot/evidence/decision/frozen_scores_*.json,'
                             f'{sha},"estimator attribution of the SAE pilot conditions"\n')
        print("manifest rows written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
