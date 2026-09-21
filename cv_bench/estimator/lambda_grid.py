"""Find the smallest mixed-frame grid that identifies lambda (author item 2).

Lambda moved to its own gate on 22 Sept, keeping its 0.15 RMSE bar, and is to be
tested "once a denser mixed-frame grid passes on synthetic agents", with the
smallest such grid found by simulation. This is that simulation.

Lambda cancels exactly wherever a trial's outcomes share a sign (BD10), so only
mixed frames carry any information about it. The sweep therefore varies exactly
two things -- how many loss-aversion ratios and how many loss levels the mixed
family uses -- and leaves everything else at the B1 grid, so that what it costs
is legible: the answer is "this many more mixed trials", not "a different
experiment".

CPU only. Run as a Slurm job.
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

from cv_bench.estimator import decision as DEC, fit as FIT
from cv_bench.estimator.agents import (
    AgentParams, LAMBDA0, MDC, choice_prob, draw_template_offsets, simulate)
from cv_bench.tasks import core, risk

DEFAULT_OUT = Path("/orcd/data/gabrieli/001/guna23/iclr_risk_2027/trackB/b2_lambda_grid")

#: Loss levels the sweep may add, beyond the four in the B1 grid.
LOSS_LADDER: Tuple[Tuple[float, ...], ...] = (
    (20.0, 50.0, 100.0, 500.0),
    (20.0, 50.0, 100.0, 200.0, 500.0, 1000.0),
    (10.0, 20.0, 50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0),
)


def build_grid(n_ratios: int, losses: Sequence[float]) -> List[core.Trial]:
    """The B1 grid with the mixed family at the requested density."""
    content = list(risk.generate_risk(
        mixed_ratios=risk.mixed_ratio_grid(n_ratios), mixed_losses=losses))
    return list(core.expand_formats(content))


def lambda_rmse(trials: Sequence[core.Trial], reps: int, template_noise: float,
                numerical_noise: float, seed: int = 0,
                free: Sequence[str] = ("alpha", "gamma", "lam")) -> Dict[str, float]:
    """RMSE of lambda from a full-MDC lambda shift, at the fitted scale.

    By default alpha and gamma are freed alongside lambda, because that is what
    the decision rule does. Passing ``free=("lam",)`` instead holds them at the
    baseline fit, which separates two very different diagnoses: lambda being
    invisible on this grid, or lambda being visible but confounded with the
    curvature it has to be estimated beside.
    """
    base = AgentParams()
    truth = replace(base, lam=LAMBDA0 + MDC["lambda"])
    sigma = max(numerical_noise, 1e-3)
    errs: List[float] = []
    for rep in range(reps):
        rng = np.random.default_rng(seed * 1000 + rep)
        offsets = draw_template_offsets(trials, template_noise, rng) \
            if template_noise > 0 else None
        sim_b = simulate(trials, base, rng, template_noise, numerical_noise,
                         template_offsets=offsets)
        fitted_base, _, _ = FIT.fit(trials, sim_b["z"], ("alpha", "gamma", "tau"),
                                    base, free_templates=template_noise > 0,
                                    observe="logit", sigma=sigma, seed=rep)
        tpl = dict(FIT.fit.last_template_offsets)
        sim_i = simulate(trials, truth, rng, template_noise, numerical_noise,
                         template_offsets=offsets)
        par, _, _ = FIT.fit(trials, sim_i["z"], tuple(free),
                            fitted_base, template_offsets=tpl,
                            observe="logit", sigma=sigma, seed=rep)
        errs.append(float(par.lam - truth.lam))
    e = np.array(errs)
    return {"rmse": float(np.sqrt(np.mean(e ** 2))),
            "bias": float(np.mean(e)), "sd": float(np.std(e, ddof=1)) if len(e) > 1 else 0.0,
            "reps": reps}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ratios", type=int, nargs="+", default=[12, 18, 24, 32, 48, 64])
    ap.add_argument("--loss-ladder", type=int, nargs="+", default=[0, 1, 2])
    ap.add_argument("--reps", type=int, default=12)
    ap.add_argument("--template-noise", type=float, default=0.5)
    ap.add_argument("--numerical-noise", type=float, default=0.0)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)

    args.out.mkdir(parents=True, exist_ok=True)
    limit = DEC.GATE_RMSE_FRACTION * MDC["lambda"]
    baseline_rows = len(build_grid(12, LOSS_LADDER[0]))

    rows: List[Dict[str, object]] = []
    smallest: Optional[Dict[str, object]] = None
    for li in args.loss_ladder:
        losses = LOSS_LADDER[li]
        for n in args.ratios:
            trials = build_grid(n, losses)
            n_mixed = sum(1 for t in trials if t.family == "mixed")
            res = lambda_rmse(trials, args.reps, args.template_noise,
                              args.numerical_noise, args.seed)
            # Same grid, but with the curvature held at the baseline fit. If
            # this passes where the joint fit fails, lambda is not invisible --
            # it is confounded with alpha, and the remedy is to pin alpha on the
            # gain frame rather than to add mixed trials.
            held = lambda_rmse(trials, args.reps, args.template_noise,
                               args.numerical_noise, args.seed, free=("lam",))
            row = {"n_ratios": n, "n_losses": len(losses), "losses": list(losses),
                   "total_rows": len(trials), "mixed_rows": n_mixed,
                   "rows_vs_b1": round(len(trials) / baseline_rows, 3),
                   "limit": limit, **res,
                   "rmse_alpha_gamma_held": held["rmse"],
                   "PASS": bool(res["rmse"] <= limit),
                   "PASS_with_alpha_held": bool(held["rmse"] <= limit)}
            rows.append(row)
            print(f"ratios={n:3d} losses={len(losses)} mixed_rows={n_mixed:5d} "
                  f"total={len(trials):6d} ({row['rows_vs_b1']:.2f}x B1)  "
                  f"lambda RMSE joint={res['rmse']:.4f} "
                  f"{'PASS' if row['PASS'] else 'fail'} | "
                  f"alpha,gamma held={held['rmse']:.4f} "
                  f"{'PASS' if row['PASS_with_alpha_held'] else 'fail'}", flush=True)
            if row["PASS"] and (smallest is None
                                or row["total_rows"] < smallest["total_rows"]):
                smallest = row

    out = {"utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "limit": limit, "b1_rows": baseline_rows,
           "template_noise_sd": args.template_noise,
           "numerical_noise_sd": args.numerical_noise,
           "reps": args.reps, "rows": rows,
           "smallest_passing_grid": smallest}
    (args.out / "lambda_grid.json").write_text(
        json.dumps(out, indent=2, sort_keys=True, default=float) + "\n")

    if smallest:
        print(f"\nSMALLEST PASSING GRID: {smallest['n_ratios']} ratios x "
              f"{smallest['n_losses']} loss levels = {smallest['mixed_rows']} mixed rows, "
              f"{smallest['total_rows']} rows total ({smallest['rows_vs_b1']:.2f}x B1), "
              f"lambda RMSE {smallest['rmse']:.4f} <= {limit}")
    else:
        print(f"\nNO GRID IN THE SWEEP IDENTIFIES LAMBDA to RMSE <= {limit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
