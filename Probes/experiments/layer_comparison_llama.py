"""Layer-matched probe steering comparison (Llama-3.3-70B-Instruct).

Reviewer control. The SAE interventions are applied at layer 50, but the linear
probes were CV-selected to layer 48, so the probe-vs-SAE steering comparison
mixes a *method* difference with a two-layer *depth* difference. This runner
removes that confound: it rebuilds the preference probes at a fixed layer (48
and 50 by default) with an otherwise identical training / calibration / sweep
procedure, and reports steering efficacy for each. If the layer-48 and layer-50
probes steer equivalently, the head-to-head against the layer-50 SAE reflects
the method, not the depth.

The labeling, sample budget, lambda calibration, and reward/offer grids are held
identical across the two probes; the residual-stream layer is the only variable
that changes. Steering efficacy is quantified as how well the achieved switching
point (interpolated at P(risky)=0.5 / P(accept)=0.5) tracks the calibration
target across the target sweep.

Outputs (under {outdir}/layer_comparison/):
- llama_layer{L}_{game}_per_agent.jsonl   per-trial records (probe_layer = L)
- llama_layer{L}_{game}_cells.jsonl       per-(target, param) raw fractions
- llama_layer{L}_calibration.json         lambda per target, achieved, cv accuracy
- comparison.csv                          per-(game, target) achieved SP, both layers
- comparison_summary.json                 headline efficacy metrics + equivalence verdict
"""
from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import replace
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .. import config
from ..calibration import (
    calibrate_lottery_switching_point,
    calibrate_ultimatum_acceptance_threshold,
    switching_point_from_rows,
)
from ..models import Wrapped
from ..probes import Probe
from ..tasks import preference
from ._common import (
    build_preference_probe,
    make_lottery_switching_point_evaluator,
    make_ultimatum_threshold_evaluator,
    write_jsonl,
)


# =========================================================================
# Per-(game, layer) steering run
# =========================================================================
def _cells(rows: List[Dict], param_field: str, success_field: str) -> List[Dict]:
    """Per-(target, param) aggregate with raw success fraction and counts."""
    by_cell = defaultdict(list)
    for r in rows:
        by_cell[(r["target_switching_point_tokens"], r[param_field])].append(r)
    out = []
    for (t, p), trs in sorted(by_cell.items()):
        choices = [r[success_field] for r in trs if r[success_field] in (0, 1)]
        n = len(choices)
        n_succ = int(sum(choices))
        out.append({
            "model": trs[0]["model"],
            "probe_layer": trs[0]["probe_layer"],
            "game": trs[0]["game"],
            "target_switching_point_tokens": int(t),
            "lambda_calibrated": trs[0]["lambda_calibrated"],
            param_field: int(p),
            "n_agents": n,
            "n_success": n_succ,
            "raw_fraction": (n_succ / n) if n else 0.0,
        })
    return out


def _run_game_at_layer(
    model: Wrapped,
    game: str,
    probe: Probe,
    targets: Sequence[int],
    n_agents: int,
    n_agents_calib: int,
    seed_base: int,
) -> Tuple[List[Dict], List[Dict], List[Dict]]:
    """Calibrate lambda per target, sweep the full grid, measure achieved SP.

    Returns (per_target_records, per_agent_rows, per_cell_rows).
    """
    if game == "lottery":
        grid = config.LOTTERY["reward_grid_tokens"]
        param_field = "risky_reward_tokens"
        evaluator = make_lottery_switching_point_evaluator(
            model, probe, n_agents_eval=n_agents_calib
        )
        calibrate = calibrate_lottery_switching_point
        sweep_kwargs = lambda t, lam: dict(
            model=model, rewards=grid, n_agents=n_agents, seed_base=seed_base,
            probe=probe, lambda_value=lam, target_switching_point_tokens=t,
        )
        sweep = preference.sweep_lottery
    else:
        grid = config.ULTIMATUM["offer_grid_tokens"]
        param_field = "offer_amount_tokens"
        evaluator = make_ultimatum_threshold_evaluator(
            model, probe, n_agents_eval=n_agents_calib
        )
        calibrate = calibrate_ultimatum_acceptance_threshold
        sweep_kwargs = lambda t, lam: dict(
            model=model, offers=grid, n_agents=n_agents, seed_base=seed_base,
            probe=probe, lambda_value=lam, target_switching_point_tokens=t,
        )
        sweep = preference.sweep_ultimatum

    per_target: List[Dict] = []
    per_agent: List[Dict] = []
    cache: Dict[float, float] = {}
    for t in targets:
        lam, _ = calibrate(float(t), evaluator, cache=cache)
        lam = round(lam, 4)
        rows = sweep(**sweep_kwargs(int(t), lam))
        achieved = switching_point_from_rows(rows, param_field, "parsed_choice", 0.5)
        per_target.append({
            "game": game,
            "probe_layer": int(probe.layer),
            "target_switching_point_tokens": int(t),
            "lambda_calibrated": float(lam),
            "achieved_switching_point_tokens": float(achieved),
            "abs_error_tokens": float(abs(achieved - t)) if np.isfinite(achieved) else float("nan"),
        })
        per_agent.extend(rows)

    cells = _cells(per_agent, param_field, "parsed_choice")
    return per_target, per_agent, cells


# =========================================================================
# Efficacy metrics
# =========================================================================
def _efficacy(per_target: List[Dict]) -> Dict:
    """RMSE / MAE / correlation of achieved-vs-target across the target sweep."""
    tgt = np.array([r["target_switching_point_tokens"] for r in per_target], dtype=float)
    ach = np.array([r["achieved_switching_point_tokens"] for r in per_target], dtype=float)
    ok = np.isfinite(ach)
    tgt, ach = tgt[ok], ach[ok]
    if len(tgt) == 0:
        return {"rmse_tokens": float("nan"), "mae_tokens": float("nan"),
                "pearson_r": float("nan"), "n_targets": 0}
    err = ach - tgt
    rmse = float(np.sqrt(np.mean(err ** 2)))
    mae = float(np.mean(np.abs(err)))
    if len(tgt) >= 2 and np.std(tgt) > 0 and np.std(ach) > 0:
        r = float(np.corrcoef(tgt, ach)[0, 1])
    else:
        r = float("nan")
    return {"rmse_tokens": rmse, "mae_tokens": mae, "pearson_r": r, "n_targets": int(len(tgt))}


def _cross_layer_diff(pt_a: List[Dict], pt_b: List[Dict]) -> Dict:
    """Mean / max absolute difference between the two layers' achieved SP curves,
    matched by calibration target."""
    a = {r["target_switching_point_tokens"]: r["achieved_switching_point_tokens"] for r in pt_a}
    b = {r["target_switching_point_tokens"]: r["achieved_switching_point_tokens"] for r in pt_b}
    diffs = [
        abs(a[t] - b[t])
        for t in sorted(set(a) & set(b))
        if np.isfinite(a[t]) and np.isfinite(b[t])
    ]
    if not diffs:
        return {"mean_abs_diff_tokens": float("nan"), "max_abs_diff_tokens": float("nan"),
                "n_matched_targets": 0}
    return {
        "mean_abs_diff_tokens": float(np.mean(diffs)),
        "max_abs_diff_tokens": float(np.max(diffs)),
        "n_matched_targets": int(len(diffs)),
    }


# =========================================================================
# Entry point
# =========================================================================
def run(
    model: Wrapped,
    outdir: Path,
    layers: Sequence[int] = (48, 50),
    n_agents: Optional[int] = None,
    n_agents_calib: int = 12,
    lottery_targets: Optional[Sequence[int]] = None,
    ultimatum_targets: Optional[Sequence[int]] = None,
) -> Dict:
    out = outdir / "layer_comparison"
    out.mkdir(parents=True, exist_ok=True)

    n_agents = int(n_agents if n_agents is not None else config.LOTTERY["n_agents"])
    lottery_targets = list(lottery_targets or config.LOTTERY["targets_llama"])
    ultimatum_targets = list(ultimatum_targets or config.ULTIMATUM["targets_llama"])
    seed_base = config.SEED["psychometric_llama"]

    orig_cfg = model.cfg
    per_layer: Dict[int, Dict] = {}
    try:
        for layer in layers:
            # Pin every layer-dependent code path (training, capture, steering,
            # and row metadata) to this layer by swapping the model config.
            model.cfg = replace(orig_cfg, probe_layer=int(layer))

            lottery_probe = build_preference_probe(model, game="lottery", layer_sweep=False)
            ultimatum_probe = build_preference_probe(model, game="ultimatum", layer_sweep=False)
            lottery_probe.save(out / f"lottery_probe_layer{layer}.pkl")
            ultimatum_probe.save(out / f"ultimatum_probe_layer{layer}.pkl")

            l_targets, l_rows, l_cells = _run_game_at_layer(
                model, "lottery", lottery_probe, lottery_targets,
                n_agents, n_agents_calib, seed_base,
            )
            u_targets, u_rows, u_cells = _run_game_at_layer(
                model, "ultimatum", ultimatum_probe, ultimatum_targets,
                n_agents, n_agents_calib, seed_base,
            )

            write_jsonl(l_rows, out / f"llama_layer{layer}_lottery_per_agent.jsonl")
            write_jsonl(u_rows, out / f"llama_layer{layer}_ultimatum_per_agent.jsonl")
            write_jsonl(l_cells, out / f"llama_layer{layer}_lottery_cells.jsonl")
            write_jsonl(u_cells, out / f"llama_layer{layer}_ultimatum_cells.jsonl")

            calibration = {
                "layer": int(layer),
                "lottery_probe_cv_accuracy": float(lottery_probe.cv_accuracy),
                "ultimatum_probe_cv_accuracy": float(ultimatum_probe.cv_accuracy),
                "lottery": l_targets,
                "ultimatum": u_targets,
            }
            with open(out / f"llama_layer{layer}_calibration.json", "w") as f:
                json.dump(calibration, f, indent=2)

            per_layer[int(layer)] = {
                "lottery_probe_cv_accuracy": float(lottery_probe.cv_accuracy),
                "ultimatum_probe_cv_accuracy": float(ultimatum_probe.cv_accuracy),
                "lottery_per_target": l_targets,
                "ultimatum_per_target": u_targets,
                "lottery_efficacy": _efficacy(l_targets),
                "ultimatum_efficacy": _efficacy(u_targets),
            }
    finally:
        model.cfg = orig_cfg

    # ---- Flat CSV: one row per (game, target, layer) ----
    csv_lines = ["game,target_switching_point_tokens,probe_layer,lambda_calibrated,"
                 "achieved_switching_point_tokens,abs_error_tokens"]
    for layer in layers:
        for game in ("lottery", "ultimatum"):
            for r in per_layer[int(layer)][f"{game}_per_target"]:
                csv_lines.append(
                    f'{game},{r["target_switching_point_tokens"]},{r["probe_layer"]},'
                    f'{r["lambda_calibrated"]:.4f},{r["achieved_switching_point_tokens"]:.4f},'
                    f'{r["abs_error_tokens"]:.4f}'
                )
    (out / "comparison.csv").write_text("\n".join(csv_lines) + "\n")

    # ---- Headline summary + equivalence verdict ----
    summary: Dict = {
        "model": model.cfg.name,
        "layers": [int(x) for x in layers],
        "n_agents": n_agents,
        "n_agents_calib": n_agents_calib,
        "lottery_targets": lottery_targets,
        "ultimatum_targets": ultimatum_targets,
        "per_layer_efficacy": {
            str(layer): {
                "lottery": per_layer[int(layer)]["lottery_efficacy"],
                "ultimatum": per_layer[int(layer)]["ultimatum_efficacy"],
                "lottery_probe_cv_accuracy": per_layer[int(layer)]["lottery_probe_cv_accuracy"],
                "ultimatum_probe_cv_accuracy": per_layer[int(layer)]["ultimatum_probe_cv_accuracy"],
            }
            for layer in layers
        },
    }

    if len(layers) == 2:
        a, b = int(layers[0]), int(layers[1])
        lottery_diff = _cross_layer_diff(
            per_layer[a]["lottery_per_target"], per_layer[b]["lottery_per_target"]
        )
        ultimatum_diff = _cross_layer_diff(
            per_layer[a]["ultimatum_per_target"], per_layer[b]["ultimatum_per_target"]
        )
        # Equivalence: the two layers' achieved curves agree within the same
        # tolerance used to accept a calibration target as "hit".
        tol = config.CALIBRATION["tolerance_switching_point_tokens"]
        lottery_equiv = np.isfinite(lottery_diff["mean_abs_diff_tokens"]) and \
            lottery_diff["mean_abs_diff_tokens"] <= tol
        ultimatum_equiv = np.isfinite(ultimatum_diff["mean_abs_diff_tokens"]) and \
            ultimatum_diff["mean_abs_diff_tokens"] <= config.CALIBRATION[
                "tolerance_acceptance_threshold_tokens"]
        summary["cross_layer"] = {
            "compared_layers": [a, b],
            "lottery": lottery_diff,
            "ultimatum": ultimatum_diff,
            "equivalence_tolerance_lottery_tokens": float(tol),
            "equivalence_tolerance_ultimatum_tokens": float(
                config.CALIBRATION["tolerance_acceptance_threshold_tokens"]),
            "lottery_equivalent": bool(lottery_equiv),
            "ultimatum_equivalent": bool(ultimatum_equiv),
            "verdict": (
                "probe steering is equivalent across the compared layers; the "
                "probe-vs-SAE comparison at layer 50 reflects method, not depth"
                if (lottery_equiv and ultimatum_equiv)
                else "layers differ beyond calibration tolerance; inspect comparison.csv"
            ),
        }

    with open(out / "comparison_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    return summary
