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
    AgentParams, BASES, base_scale_report, CPT_PREFERENCE_CELLS, INTERVENTIONS, MDC,
    MISSPECIFIED_BASES, base_params, behavioural_effect, build_crossed_zoo,
    choice_prob, draw_template_offsets, latent_z_packed, pack, simulate)
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
               seed: int = 0,
               observe: str = "logit") -> Dict[str, object]:
    """One configuration: every (base, intervention) cell, `reps` times each.

    Author item 3: base in {CPT, mean-variance, monotone} crossed with
    intervention in {preference, action, belief, noise, format}. Each base is
    simulated with its own baseline and each intervention is measured against
    *that* baseline, so D1 is a change from the base agent's own dominance rate
    rather than from CPT's.
    """
    crossed, bases, effects = build_crossed_zoo(trials)
    sigma = max(numerical_noise, 1e-3)

    records: List[Dict[str, object]] = []
    classifications: Dict[str, List[bool]] = {}
    mf_correct: Dict[str, List[bool]] = {}
    contradiction: Dict[str, List[bool]] = {}

    for rep in range(reps):
        rng = np.random.default_rng(seed * 10_000 + rep)
        # One draw of the template effects, shared by every condition in this
        # replication: it is a property of the template and cancels in the
        # comparison, as it does in a real experiment reusing the same prompts.
        offsets = draw_template_offsets(trials, template_noise, rng) \
            if template_noise > 0 else None

        for base, par0 in bases.items():
            sim_b = simulate(trials, par0, rng, template_noise, numerical_noise,
                             template_offsets=offsets)
            obs_b = sim_b["z"] if observe == "logit" else sim_b["choice"]
            fitted_base, _, _ = FIT.fit(trials, obs_b, ("alpha", "gamma", "tau"),
                                        AgentParams(), dominated_policy=dominated_policy,
                                        seed=rep, free_templates=template_noise > 0,
                                        observe=observe, sigma=sigma)
            tpl_offsets = dict(FIT.fit.last_template_offsets)
            d1_base = FP.d1_dominance_violations(trials, sim_b["choice"])
            p_base = choice_prob(sim_b["z"])

            for iv in [k[1] for k in crossed if k[0] == base]:
                par = crossed[(base, iv)]
                sim_i = simulate(trials, par, rng, template_noise, numerical_noise,
                                 template_offsets=offsets)
                obs_i = sim_i["z"] if observe == "logit" else sim_i["choice"]
                p_int = choice_prob(sim_i["z"])
                dz = sim_i["z"] - sim_b["z"]

                fits = FIT.fit_all_models(trials, obs_i, fitted_base,
                                          dominated_policy=dominated_policy, seed=rep,
                                          template_offsets=tpl_offsets,
                                          observe=observe, sigma=sigma)
                shares = FIT.model_shares(fits)
                boot = FIT.cluster_bootstrap(trials, fits, "preference", "action",
                                             n_boot=200, seed=rep)
                oof = DEC.out_of_frame_check(trials, obs_i, fitted_base,
                                             dominated_policy=dominated_policy, seed=rep,
                                             template_offsets=tpl_offsets,
                                             observe=observe, sigma=sigma)
                fitted_int = fits["preference"]["params"]
                fp = FP.fingerprint(trials, par0, par, fitted_base, fitted_int,
                                    sim_i["choice"], p_base, p_int, dz,
                                    z_base=sim_b["z"])
                verdict = DEC.decide(shares, fp, d1_base, oof, boot)

                key = f"{base}/{iv}"
                expected = "preference" if iv.startswith("preference") else iv
                mf_label = FP.modelfree_classify(fp)
                top_model = max(shares, key=shares.get)

                classifications.setdefault(key, []).append(verdict["preference_like"])
                mf_correct.setdefault(key, []).append(mf_label == expected)
                # A contradiction is the parametric layer being confident (share
                # above 0.8) about a different answer from the model-free one.
                contradiction.setdefault(key, []).append(
                    bool(shares[top_model] > 0.8 and top_model != mf_label))

                rec: Dict[str, object] = {
                    "rep": rep, "base": base, "intervention": iv,
                    "expected": expected,
                    "modelfree_label": mf_label,
                    "parametric_top": top_model,
                    "parametric_top_share": float(shares[top_model]),
                    "preference_like": verdict["preference_like"],
                    "criteria": verdict["criteria"],
                    "shares": shares,
                    "vuong": FIT.vuong(fits, "preference", "action"),
                    "bootstrap": boot,
                    "D1": fp["D1_dominance"], "D1_base": d1_base,
                    "D2_shares": {k: v for k, v in fp["D2_variance"].items()
                                  if k.endswith("_share")},
                    "D3": fp["D3_paired_shift"],
                    "D4_ratio": fp["D4_ce"]["ratio"],
                    "D5_ratio_worst": fp["D5_format"]["ratio_worst"],
                    "D6_intact": fp["D6_recall"]["intact"],
                    "D7_cv": fp["D7_stakes"]["cv"],
                    "effect_size": effects.get(key),
                }
                if base == "cpt" and iv in CPT_PREFERENCE_CELLS:
                    field = CPT_PREFERENCE_CELLS[iv]
                    rec["shifted_param"] = {"alpha": "alpha", "gamma": "gamma",
                                            "lam": "lambda"}[field]
                    rec["true_value"] = float(getattr(par, field))
                    rec["fitted_value"] = float(getattr(fitted_int, field))
                records.append(rec)

    rmse = DEC.parameter_rmse(records)
    rates = {k: float(np.mean(v)) for k, v in classifications.items()}
    mf_rates = {k: float(np.mean(v)) for k, v in mf_correct.items()}
    contra_rates = {k: float(np.mean(v)) for k, v in contradiction.items()}
    miss_mf = {k: v for k, v in mf_rates.items()
               if k.split("/", 1)[0] in MISSPECIFIED_BASES}

    gate = DEC.gate_b2(rmse, classifications, miss_mf, contra_rates)
    lam = DEC.gate_lambda(rmse)

    return {
        "config": {"template_noise_sd": template_noise,
                   "numerical_noise_sd": numerical_noise,
                   "dominated_policy": dominated_policy, "observe": observe,
                   "reps": reps, "n_trials": len(trials), "seed": seed},
        "effect_sizes": effects,
        "rmse": rmse,
        "classification_rates": rates,
        "modelfree_accuracy": mf_rates,
        "parametric_contradiction_rate": contra_rates,
        "gate_b2": gate,
        "gate_lambda": lam,
        "records": records,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template-noise", type=float, default=0.5)
    ap.add_argument("--numerical-noise", type=float, default=0.0)
    ap.add_argument("--policy", choices=("exclude", "lapse"), default="exclude")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--observe", choices=("logit", "choice"), default="logit",
                    help="logit: z is read directly, which is what the readout gives; "
                         "choice: one Bernoulli draw per row, as sampled generation gives")
    ap.add_argument("--out", type=Path, default=DEFAULT_SHARE / "b2_recovery")
    ap.add_argument("--dump-zoo", action="store_true",
                    help="print the (base, intervention) grid and its matched "
                         "effect sizes, then exit")
    ap.add_argument("--max-rows", type=int, default=None,
                    help="cap the expanded grid, for a fast smoke run")
    args = ap.parse_args(argv)

    if args.dump_zoo:
        trials = build_trials(expand=True)
        crossed, bases, effects = build_crossed_zoo(trials)
        from cv_bench.estimator.agents import (
            base_scale_report, calibrate_mean_variance_b)
        print(f"calibrated mean_variance mv_b = "
              f"{calibrate_mean_variance_b(trials):.6f}  (current default "
              f"{AgentParams().mv_b})")
        print("base agent scales (a base must be neither flat nor saturated):")
        for b, v in base_scale_report(trials).items():
            print(f"  {b:15s} z_sd={v['z_sd']:8.4f} z=[{v['z_min']:8.2f},{v['z_max']:6.2f}] "
                  f"P spread={v['p_spread']:.4f} P mean={v['p_mean']:.4f}")
        print()
        print(f"target effect (CPT alpha at its MDC): {effects['_target']:.4f}")
        print(f"{len(crossed)} cells over {len(bases)} bases\n")
        for (b, iv) in sorted(crossed):
            print(f"  {b:15s} {iv:20s} effect={effects[f'{b}/{iv}']:.4f}")
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    tag_early = (f"t{args.template_noise}_n{args.numerical_noise}"
                 f"_{args.policy}_{args.observe}")
    done_path = args.out / f"recovery_{tag_early}.json"
    if done_path.exists():
        # Requeue-safe: a configuration that finished is not recomputed. Each
        # array task owns exactly one output file, so this is unambiguous.
        print(f"config {tag_early}: already complete at {done_path}, skipping")
        return 0

    trials = build_trials(expand=True)
    if args.max_rows:
        # Stride rather than truncate, so every format and cell stays present.
        step = max(1, len(trials) // args.max_rows)
        trials = trials[::step]
    res = run_config(trials, args.template_noise, args.numerical_noise,
                     args.policy, reps=args.reps, seed=args.seed,
                     observe=args.observe)
    res["utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")

    args.out.mkdir(parents=True, exist_ok=True)
    tag = f"t{args.template_noise}_n{args.numerical_noise}_{args.policy}_{args.observe}"
    path = args.out / f"recovery_{tag}.json"
    path.write_text(json.dumps(res, indent=2, sort_keys=True, default=float) + "\n")

    g = res["gate_b2"]
    print(f"config {tag}: GATE B2 {'PASS' if g['PASS'] else 'FAIL'} "
          f"| lambda gate {'PASS' if res['gate_lambda']['PASS'] else 'FAIL'}")
    print("  rmse (alpha, gamma):", {k: (None if v['rmse'] is None else round(v['rmse'], 4))
                                     for k, v in g["rmse"].items()})
    print("  lambda rmse:", res["gate_lambda"]["rmse"])
    print("  cpt preference-like:", round(g["cpt_preference_classified_preference_like"] or -1, 3))
    print("  cpt non-preference:", {k: round(v, 3)
                                    for k, v in g["cpt_non_preference_classified_preference_like"].items()})
    print("  misspecified model-free accuracy:", {k: round(v, 3)
                                                  for k, v in g["misspecified_modelfree_accuracy"].items()})
    print(f"  wrote {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
