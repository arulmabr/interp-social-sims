"""S1.4 — what the choice probe encodes, without new steering.

    python -m cv_bench.s1_probe

GATE_S0_RESPONSE.md §3 P4 is in force, so this reports: the label rule; whether
the train/test split was by row or by prompt; and the best accuracy any function
of n can reach, beside the paper's 82%.

Parts (a) and (c) of the plan's S1.4 are not available; see logs/DEVIATIONS.md
D-2026-09-21-02 and -03. What replaces (a) is computed here and labelled.
"""
from __future__ import annotations

import collections
import json
from typing import Dict, List

import numpy as np

from .s1_data import (
    BEHAVIOURAL, PROBE_JSON, Curve, aggregate, all_curves, append_manifest,
    rel, write_csv,
)

SCRIPT = "cv_bench/s1_probe.py"


def _fmt(v):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 4)


# ---------------------------------------------------------------------------
# The ceiling of "know n perfectly"
# ---------------------------------------------------------------------------
def ceilings(trials) -> Dict[str, float]:
    """Best accuracy attainable by (i) any function of x, (ii) a threshold rule on x.

    (i) is the Bayes rate for a predictor whose only input is the stimulus: predict
    each level's majority label. Since the legacy probe sees one activation vector
    per level, repeated, (i) is also its ceiling.
    (ii) is the one-parameter rule "choose risky iff x >= t", maximised over t and
    over both directions.
    """
    xs, k, n = aggregate(trials)
    N = float(n.sum())
    if N == 0:
        return {}
    majority = float(np.maximum(k, n - k).sum() / N)

    best_thr, best_acc, best_dir = float("nan"), -1.0, ""
    cand = list(xs) + [xs[-1] + 1.0]
    for t in cand:
        ge = xs >= t
        # "1 iff x >= t"
        acc_up = float((k[ge].sum() + (n[~ge] - k[~ge]).sum()) / N)
        # "1 iff x < t"
        acc_dn = float((k[~ge].sum() + (n[ge] - k[ge]).sum()) / N)
        for acc, d in ((acc_up, ">=t"), (acc_dn, "<t")):
            if acc > best_acc:
                best_acc, best_thr, best_dir = acc, float(t), d

    base_rate = float(max(k.sum(), N - k.sum()) / N)
    return dict(
        n_trials=int(N), n_levels=int(len(xs)),
        ceiling_any_function_of_n=majority,
        best_threshold_rule=best_acc,
        threshold=best_thr, threshold_direction=best_dir,
        majority_class_rate=base_rate,
        gap_function_minus_threshold=majority - best_acc,
        irreducible_sampling_noise=1.0 - majority,
    )


def s1_4b(curves: List[Curve]):
    rows, manifest = [], []
    for c in sorted(curves, key=lambda c: (c.stack, c.game, c.condition)):
        d = ceilings(c.trials)
        if not d:
            continue
        rows.append(dict(
            stack=c.stack, game=c.game, condition=c.condition,
            **{k: (v if isinstance(v, int) or isinstance(v, str) else _fmt(v))
               for k, v in d.items()},
        ))
        manifest.append((
            f"S1.4.{c.stack}.{c.game}.{c.condition}.ceiling_any_function_of_n",
            _fmt(d["ceiling_any_function_of_n"]), SCRIPT,
            [rel(BEHAVIOURAL) if c.stack in ("hosted", "vllm") else rel(PROBE_JSON)],
            "best accuracy attainable by any predictor whose only input is the reward level; "
            f"best one-parameter threshold rule reaches {_fmt(d['best_threshold_rule'])}",
        ))
    write_csv("s1_4_probe_ceiling.csv", rows)
    append_manifest(manifest)
    return rows


# ---------------------------------------------------------------------------
# Substitute for S1.4(a): the only logged probe scores, and what they depend on
# ---------------------------------------------------------------------------
TRACK_KEYS = {
    "figure_12_probe_scores_track_target_lottery_ultimatum_llama": ("probe-llama-l48", "fig 11"),
    "figure_16_probe_scores_track_target_qwen": ("probe-qwen-l17", "fig 18"),
}
DOSE_KEYS = {
    "probe-llama-l48": "figure_11_dose_response_lottery_ultimatum_llama",
    "probe-qwen-l17": "figure_15_dose_response_lottery_ultimatum_qwen",
}


def s1_4a_substitute():
    d = json.loads(PROBE_JSON.read_text())
    rows, manifest = [], []
    for key, (stack, paper_fig) in TRACK_KEYS.items():
        lam_by_target = {}
        for r in d[DOSE_KEYS[stack]]["data"]:
            lam_by_target[(r["game"], r["target_switching_point_tokens"])] = r["lambda_required"]
        by = collections.defaultdict(dict)
        for r in d[key]["data"]:
            by[(r["game"], r["choice_subset"])][r["target_switching_point_tokens"]] = \
                r["mean_probe_activation"]
        for (game, subset), series in sorted(by.items()):
            ts = sorted(series)
            y = np.array([series[t] for t in ts], float)
            x_t = np.array(ts, float)
            x_l = np.array([lam_by_target.get((game, t), np.nan) for t in ts], float)
            ok = np.isfinite(x_l)

            def lin(x, y):
                A = np.column_stack([x, np.ones_like(x)])
                b, *_ = np.linalg.lstsq(A, y, rcond=None)
                pred = A @ b
                ss = ((y - y.mean()) ** 2).sum()
                return float(b[0]), float(b[1]), (1 - ((y - pred) ** 2).sum() / ss if ss > 0 else np.nan)

            st, it_, r2t = lin(x_t, y)
            if ok.sum() >= 3:
                sl, il, r2l = lin(x_l[ok], y[ok])
            else:
                sl = il = r2l = float("nan")
            rows.append(dict(
                stack=stack, paper_figure=paper_fig, game=game, choice_subset=subset,
                n_targets=len(ts), score_min=_fmt(y.min()), score_max=_fmt(y.max()),
                score_spread=_fmt(y.max() - y.min()),
                slope_vs_target=_fmt(st), r2_vs_target=_fmt(r2t),
                slope_vs_lambda=_fmt(sl), r2_vs_lambda=_fmt(r2l),
                expected_spread_if_hook_inactive=0.0,
            ))
            if subset == "all":
                manifest.append((
                    f"S1.4a.{stack}.{game}.tracking_all_spread", _fmt(y.max() - y.min()), SCRIPT,
                    [rel(PROBE_JSON)],
                    "range of the 'all'-subset tracked probe score across targets; the shipped "
                    "script scores un-steered prompts on a target-independent grid, so a faithful "
                    "rerun of it must give 0",
                ))
    write_csv("s1_4_tracking_scores.csv", rows)
    append_manifest(manifest)
    return rows


# ---------------------------------------------------------------------------
# The legacy training design, restated as countable facts
# ---------------------------------------------------------------------------
def s1_4_design():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from Probes import config

    n_lot = len(config.LOTTERY["reward_grid_tokens"])
    n_ult = len(config.ULTIMATUM["offer_grid_tokens"])
    rows = [
        dict(probe="preference/lottery", n_distinct_prompts=n_lot, samples_per_prompt=8,
             n_training_rows=n_lot * 8, distinct_activation_vectors=n_lot,
             label_rule="the agent's own parsed choice on that sample: Risky=1, Safe=0",
             activation_position="final token of the prompt (capture_activations), "
                                 "second forward pass, no chat template, no steering",
             sources_of_variation="reward level n only",
             split="by row (StratifiedKFold over rows); each activation vector appears "
                   "in the training fold and the validation fold of the same split",
             artefact_saved="no"),
        dict(probe="preference/ultimatum", n_distinct_prompts=n_ult, samples_per_prompt=8,
             n_training_rows=n_ult * 8, distinct_activation_vectors=n_ult,
             label_rule="Accept=1, Reject=0", activation_position="final token of the prompt",
             sources_of_variation="offer amount only", split="by row", artefact_saved="no"),
        dict(probe="capability/creativity", n_distinct_prompts=2, samples_per_prompt=80,
             n_training_rows=160, distinct_activation_vectors=2,
             label_rule="median split of the GPT-5 judge's score of the generated text",
             activation_position="final token of the prompt (task prompt, or persona prefix + "
                                 "task prompt)",
             sources_of_variation="presence or absence of the creative-persona prefix only",
             split="by row", artefact_saved="no"),
    ]
    write_csv("s1_4_legacy_probe_design.csv", rows)
    append_manifest([
        ("S1.4.design.lottery.distinct_activation_vectors", n_lot, SCRIPT,
         ["Probes/experiments/_common.py", "Probes/config.py"],
         f"{n_lot} prompts x 8 samples = {n_lot * 8} rows, {n_lot} distinct vectors"),
        ("S1.4.design.capability.distinct_activation_vectors", 2, SCRIPT,
         ["Probes/experiments/_common.py"],
         "two prompts: the task prompt and the persona-prefixed task prompt"),
    ])
    return rows


def main() -> int:
    curves = all_curves()
    d = s1_4_design()
    print(f"S1.4 design rows {len(d)}")
    r = s1_4b(curves)
    print(f"S1.4(b) ceiling rows {len(r)}")
    t = s1_4a_substitute()
    print(f"S1.4(a)-substitute tracking rows {len(t)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
