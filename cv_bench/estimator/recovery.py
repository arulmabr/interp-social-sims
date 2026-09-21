"""B2 recovery study (ICLR_PLAN.md B2). CPU only; run as a Slurm array job.

Every agent type is run through the actual B1 grid at several assumed noise
levels, fitted, and put through the decision rule. One process handles one
(template noise, numerical noise, dominated policy) configuration; `aggregate.py`
combines them and evaluates Gate B2.

Noise has two independent components (amendment item 5):
  * template-level noise, SD of z across templates, at 0.5, 1 and 2 logits;
  * numerical noise, SD 0.1 and 0.25 logits, standing for the non-determinism
    measured on the 70B in bf16 (SD about 0.094 in z across batch compositions).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.estimator import decision as DEC, fingerprint as FP, fit as FIT
from cv_bench.estimator.agents import (
    AgentParams, MDC, MISSPECIFIED_AGENTS, NON_PREFERENCE_AGENTS,
    PREFERENCE_AGENTS, agent_zoo, behavioural_effect, choice_prob,
    draw_template_offsets, latent_z_packed, match_effect_sizes, pack, simulate)
from cv_bench.tasks import core, risk

DEFAULT_SHARE = Path("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB")

#: Which AgentParams field each preference agent moves, and its MDC key.
SHIFTED: Dict[str, Tuple[str, str]] = {
    "pref_alpha": ("alpha", "alpha"),
    "pref_gamma": ("gamma", "gamma"),
    "pref_lambda": ("lam", "lambda"),
}


def build_trials(expand: bool = True) -> List[core.Trial]:
    """The risk grid B2 runs on, with formats expanded."""
    content = list(risk.generate_risk())
    return list(core.expand_formats(content)) if expand else content


def run_config(trials: Sequence[core.Trial],
               template_noise: float,
               numerical_noise: float,
               dominated_policy: str,
               reps: int = 20,
               seed: int = 0) -> Dict[str, object]:
    """One configuration: every agent, `reps` independent simulations each."""
    base = AgentParams()
    zoo = dict(agent_zoo())

    # Match the non-preference agents to the preference agents on behavioural
    # effect size, so Gate B2's rejection requirement is a fair comparison.
    pref_effect = float(np.mean([behavioural_effect(trials, zoo[a]) for a in PREFERENCE_AGENTS]))
    zoo.update(match_effect_sizes(trials, pref_effect))
    matched_effects = {a: behavioural_effect(trials, zoo[a])
                       for a in list(PREFERENCE_AGENTS) + list(NON_PREFERENCE_AGENTS)
                       + list(MISSPECIFIED_AGENTS)}

    records: List[Dict[str, object]] = []
    classifications: Dict[str, List[bool]] = {}
    misspec_modelfree: Dict[str, List[bool]] = {}

    for rep in range(reps):
        rng = np.random.default_rng(seed * 10_000 + rep)
        # One draw of the template effects, shared by both conditions: it is a
        # property of the template and cancels in the comparison, as it does in
        # a real experiment that reuses the same prompts.
        offsets = draw_template_offsets(trials, template_noise, rng) \
            if template_noise > 0 else None
        sim_b = simulate(trials, base, rng, template_noise, numerical_noise,
                         template_offsets=offsets)
        fitted_base, lapse_b, _ = FIT.fit(trials, sim_b["choice"], ("alpha", "gamma", "tau"),
                                          base, dominated_policy=dominated_policy, seed=rep)
        d1_base = FP.d1_dominance_violations(trials, sim_b["choice"])
        p_base = choice_prob(sim_b["z"])

        for name, par in zoo.items():
            if name == "baseline":
                continue
            sim_i = simulate(trials, par, rng, template_noise, numerical_noise,
                             template_offsets=offsets)
            p_int = choice_prob(sim_i["z"])
            dz = sim_i["z"] - sim_b["z"]

            fits = FIT.fit_all_models(trials, sim_i["choice"], fitted_base,
                                      dominated_policy=dominated_policy, seed=rep)
            shares = FIT.model_shares(fits)
            boot = FIT.cluster_bootstrap(trials, fits, "preference", "action",
                                         n_boot=200, seed=rep)
            oof = DEC.out_of_frame_check(trials, sim_i["choice"], fitted_base,
                                         dominated_policy=dominated_policy, seed=rep)
            fitted_int = fits["preference"]["params"]
            fp = FP.fingerprint(trials, base, par, fitted_base, fitted_int,
                                sim_i["choice"], p_base, p_int, dz)
            verdict = DEC.decide(shares, fp, d1_base, oof, boot)

            classifications.setdefault(name, []).append(verdict["preference_like"])

            rec: Dict[str, object] = {
                "rep": rep, "agent": name,
                "preference_like": verdict["preference_like"],
                "criteria": verdict["criteria"],
                "shares": shares,
                "vuong": FIT.vuong(fits, "preference", "action"),
                "bootstrap": boot,
                "D1": fp["D1_dominance"], "D1_baseline": d1_base,
                "D2_shares": {k: v for k, v in fp["D2_variance"].items()
                              if k.endswith("_share")},
                "D3": fp["D3_paired_shift"],
                "D4_ratio": fp["D4_ce"]["ratio"],
                "D5_ratio_worst": fp["D5_format"]["ratio_worst"],
                "D6_intact": fp["D6_recall"]["intact"],
                "D7_cv": fp["D7_stakes"]["cv"],
                "effect_size": matched_effects.get(name),
            }
            if name in SHIFTED:
                field, mdc_key = SHIFTED[name]
                rec["shifted_param"] = mdc_key
                rec["true_value"] = float(getattr(par, field))
                rec["fitted_value"] = float(getattr(fitted_int, field))
            if name in MISSPECIFIED_AGENTS:
                c = verdict["criteria"]
                misspec_modelfree.setdefault(name, []).append(
                    bool(c["dominance_intact"] and c["transfer_in_band"]
                         and c["recall_intact"]))
            records.append(rec)

    rmse = DEC.parameter_rmse(records)
    misspecified_ok = {k: bool(np.mean(v) >= DEC.GATE_CLASSIFICATION_MIN)
                       for k, v in misspec_modelfree.items()}
    gate = DEC.gate_b2(rmse, classifications, misspecified_ok)

    return {
        "config": {"template_noise_sd": template_noise,
                   "numerical_noise_sd": numerical_noise,
                   "dominated_policy": dominated_policy,
                   "reps": reps, "n_trials": len(trials), "seed": seed},
        "matched_effect_target": pref_effect,
        "effect_sizes": matched_effects,
        "rmse": rmse,
        "classification_rates": {k: float(np.mean(v)) for k, v in classifications.items()},
        "misspecified_modelfree_rates": {k: float(np.mean(v))
                                         for k, v in misspec_modelfree.items()},
        "gate_b2": gate,
        "records": records,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template-noise", type=float, required=True)
    ap.add_argument("--numerical-noise", type=float, required=True)
    ap.add_argument("--policy", choices=("exclude", "lapse"), required=True)
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=DEFAULT_SHARE / "b2_recovery")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="cap the expanded grid, for a fast smoke run")
    args = ap.parse_args(argv)

    trials = build_trials(expand=True)
    if args.max_rows:
        # Stride rather than truncate, so every format and cell stays present.
        step = max(1, len(trials) // args.max_rows)
        trials = trials[::step]
    res = run_config(trials, args.template_noise, args.numerical_noise,
                     args.policy, reps=args.reps, seed=args.seed)
    res["utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"t{args.template_noise}_n{args.numerical_noise}_{args.policy}"
    path = args.out / f"recovery_{tag}.json"
    path.write_text(json.dumps(res, indent=2, sort_keys=True, default=float) + "\n")

    g = res["gate_b2"]
    print(f"config {tag}: GATE B2 {'PASS' if g['PASS'] else 'FAIL'}")
    print("  rmse:", {k: (None if v['rmse'] is None else round(v['rmse'], 4))
                      for k, v in g["rmse"].items()})
    print("  limits:", {k: v["limit"] for k, v in g["rmse"].items()})
    print("  preference-like rates:", {k: round(v, 3)
                                       for k, v in res["classification_rates"].items()})
    print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
