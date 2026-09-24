"""Can the estimator recover a planted inequity shift? (B7, the Gate B2 analogue.)

Run before any adapter is trained. If the estimator cannot retrieve a planted
`beta_adv` shift from simulated choices of an agent whose parameters are known
exactly, there is no point spending GPU time teaching a 70B model to imitate it.

    python -m cv_bench.estimator.social_recovery [--write-manifest]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import replace
from typing import Dict, List

import numpy as np

from cv_bench.estimator import agents as A
from cv_bench.estimator.fit import (
    SOCIAL_FREE_SETS, cluster_bootstrap, fit, fit_all_models, model_shares)
from cv_bench.tasks import core, social

TAU = 0.1186
REPLICATES = 40
SEED = 20260924


def responder_trials() -> List[core.Trial]:
    content = list(social.generate_responder(splits=("disc", "sel", "cal")))
    return list(core.expand_formats(content, response_formats=("mc",),
                                    label_sets=("accept_reject", "neutral")))


def agents(mdc: float) -> Dict[str, A.AgentParams]:
    base = A.AgentParams(tau=TAU)
    return {
        "reference": base,
        "preference_1x": replace(base, beta_adv=A.BETA0 - mdc),
        "preference_3x": replace(base, beta_adv=A.BETA0 - 3.0 * mdc),
        "bias": replace(base, action=0.6),
    }


def draw(trials, par, rng) -> np.ndarray:
    z = A.latent_z_packed(A.pack(trials), par)
    p = A.choice_prob(z)
    return (rng.random(len(trials)) < p).astype(int)


def run(mdc: float) -> Dict[str, object]:
    base_trials = responder_trials()
    trials = base_trials * REPLICATES
    rng = np.random.default_rng(SEED)
    zoo = agents(mdc)
    choices = {k: draw(trials, v, rng) for k, v in zoo.items()}

    # The lottery lesson: seed the fits from the fitted baseline, not theta0.
    init0 = A.AgentParams(tau=TAU)
    ref_par, ref_lapse, _ = fit(trials, choices["reference"],
                                ("beta_adv", "tau"), init0,
                                dominated_policy="exclude", seed=0)
    out: Dict[str, object] = {
        "n_trials": len(trials), "n_content": len(base_trials),
        "mdc_beta_adv": mdc,
        "beta_adv_truth_reference": A.BETA0,
        "beta_adv_fitted_reference": float(ref_par.beta_adv),
        "tau_fitted_reference": float(ref_par.tau),
        "arms": {},
    }
    for name in ("preference_1x", "preference_3x", "bias"):
        fits = fit_all_models(trials, choices[name], ref_par,
                              dominated_policy="exclude", seed=0,
                              free_sets=SOCIAL_FREE_SETS)
        shares = model_shares(fits)
        got = float(fits["preference"]["params"].beta_adv)
        planted = A.BETA0 - zoo[name].beta_adv
        recovered = ref_par.beta_adv - got
        out["arms"][name] = {
            "planted_beta_shift": float(planted),
            "recovered_beta_shift": float(recovered),
            "error_in_mdc": float(abs(recovered - planted) / mdc),
            "preference_share": float(shares.get("preference", float("nan"))),
            "top_family": max(shares, key=shares.get),
            "shares": {k: float(v) for k, v in shares.items()},
        }
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write-manifest", action="store_true")
    a = ap.parse_args(argv)
    from cv_bench.estimator.social_mdc import social_mdc
    mdc = social_mdc()["mdc_beta_adv"]
    r = run(mdc)
    print(json.dumps(r, indent=2, default=str))
    if a.write_manifest:
        sha = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                             text=True).stdout.strip()
        with open("MANIFEST_B.csv", "a", newline="") as fh:
            for arm, v in r["arms"].items():
                for key in ("recovered_beta_shift", "error_in_mdc", "preference_share"):
                    fh.write(f'B7.recovery.{arm}.{key},{v[key]},'
                             f'cv_bench/estimator/social_recovery.py,'
                             f'cv_bench/tasks/social.py|cv_bench/estimator/agents.py,'
                             f'{sha},"synthetic recovery, no model involved"\n')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
