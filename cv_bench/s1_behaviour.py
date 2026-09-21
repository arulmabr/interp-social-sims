"""S1.1, S1.2, S1.3 and S1.8 — the behavioural analyses of existing logs.

    python -m cv_bench.s1_behaviour

Constraints in force (GATE_S0_RESPONSE.md §3, applied by the authors):

P2  -- every rate is reported beside its own curve's switching point and beside
       the same stack's unsteered rate; no comparison across stacks or across
       unequal doses; where a stack has no unsteered condition the baseline
       columns say "not available" rather than borrowing another stack's.

P12 -- the reward levels are a fixed design and the randomness is in the sampled
       responses, so the primary statistics for every contrast are a permutation
       test of the condition label stratified by level and a bootstrap that holds
       the levels fixed and resamples responses within them. The level-resampling
       interval is kept beside them as a sensitivity column. Shifts are given in
       grid steps as well as tokens.

P13 -- every catch-trial rate is reported beside the rate a clean translation
       would imply (a step at the fitted switching point), with the difference
       and its interval.
"""
from __future__ import annotations

import collections
import csv
import json
from typing import Dict, List

import numpy as np

from .s1_data import (
    BASELINE_OF, BEHAVIOURAL, PIE, PROBE_JSON, SURE_AMOUNT, Curve,
    all_curves, append_manifest, bootstrap_shift_within_level, bootstrap_switch,
    bootstrap_switch_diff, bootstrap_switch_within_level, fit_logistic, grid_step,
    interp_crossing, permutation_shift_test, probe_lambda_table, rel,
    staircase_excess, write_csv,
)

SCRIPT = "cv_bench/s1_behaviour.py"
NA = "not available"
N_BOOT = 2000
N_PERM = 2000


def _rate(trials, pred) -> tuple:
    sel = [y for x, y in trials if pred(x)]
    if not sel:
        return 0, 0
    return sum(sel), len(sel)


def _fmt(v):
    return "" if v is None or (isinstance(v, float) and not np.isfinite(v)) else round(float(v), 4)


# ---------------------------------------------------------------------------
# S1.1 / S1.2 — dominated choices, negative-premium choices, catch trials
# ---------------------------------------------------------------------------
def s1_1_and_1_2(curves: List[Curve]):
    from .s1_data import wilson

    lam = probe_lambda_table()
    by_stack_game: Dict[tuple, Dict[str, Curve]] = collections.defaultdict(dict)
    for c in curves:
        by_stack_game[(c.stack, c.game)][c.condition] = c

    lot_rows, ult_rows = [], []
    manifest = []

    for (stack, game), conds in sorted(by_stack_game.items()):
        base_name = BASELINE_OF.get(stack)
        base = conds.get(base_name) if base_name else None

        for cond, c in sorted(conds.items()):
            bx = c.by_x()
            xs = list(bx)
            ys = [float(np.mean(bx[x])) for x in xs]
            sw_interp = interp_crossing(xs, ys)
            _, _, sw_logit = fit_logistic(c.trials)
            exc = staircase_excess(c.trials, game, n_boot=N_BOOT) or {}

            if game == "lottery":
                k_dom, n_dom = _rate(c.trials, lambda x: x < SURE_AMOUNT)
                k_neg, n_neg = _rate(c.trials, lambda x: SURE_AMOUNT <= x < 2 * SURE_AMOUNT)
                p_dom, lo_dom, hi_dom = wilson(k_dom, n_dom)
                p_neg, lo_neg, hi_neg = wilson(k_neg, n_neg)
                if base is not None and base is not c:
                    bk, bn = _rate(base.trials, lambda x: x < SURE_AMOUNT)
                    bp, blo, bhi = wilson(bk, bn)
                    bxx = base.by_x()
                    b_sw = interp_crossing(list(bxx), [float(np.mean(bxx[x])) for x in bxx])
                    base_rate, base_sw = _fmt(bp), _fmt(b_sw)
                    base_ci = f"[{_fmt(blo)}, {_fmt(bhi)}]"
                elif base is c:
                    base_rate, base_sw, base_ci = "self", "self", "self"
                else:
                    base_rate = base_sw = base_ci = NA
                lot_rows.append(dict(
                    stack=stack, game=game, condition=cond,
                    lambda_calibrated=_fmt(lam.get((stack, game, cond))),
                    switching_point_interp=_fmt(sw_interp),
                    switching_point_logistic=_fmt(sw_logit),
                    n_levels_below_50=sum(1 for x in xs if x < SURE_AMOUNT),
                    n_trials_dominated=n_dom, k_risky_dominated=k_dom,
                    p_risky_dominated=_fmt(p_dom),
                    ci_risky_dominated=f"[{_fmt(lo_dom)}, {_fmt(hi_dom)}]",
                    n_trials_negative_premium=n_neg, k_risky_negative_premium=k_neg,
                    p_risky_negative_premium=_fmt(p_neg),
                    ci_risky_negative_premium=f"[{_fmt(lo_neg)}, {_fmt(hi_neg)}]",
                    implied_by_translation=_fmt(exc.get("implied_rate")),
                    excess_over_staircase=_fmt(exc.get("excess")),
                    excess_ci=f"[{_fmt(exc.get('excess_ci_lo'))}, {_fmt(exc.get('excess_ci_hi'))}]",
                    excess_excludes_zero=("" if not np.isfinite(exc.get("excess_ci_lo", np.nan))
                                          else str(exc["excess_ci_lo"] > 0 or exc["excess_ci_hi"] < 0)),
                    same_stack_baseline_condition=base_name or NA,
                    same_stack_baseline_p_risky_dominated=base_rate,
                    same_stack_baseline_ci=base_ci,
                    same_stack_baseline_switching_point=base_sw,
                ))
                manifest.append((
                    f"S1.1.{stack}.{cond}.pRisky_dominated", _fmt(p_dom), SCRIPT,
                    [rel(BEHAVIOURAL) if stack in ("hosted", "vllm") else rel(PROBE_JSON)],
                    f"P(risky | n<50), n={n_dom}, Wilson [{_fmt(lo_dom)},{_fmt(hi_dom)}]; "
                    f"switching point {_fmt(sw_interp)}",
                ))
                if exc:
                    manifest.append((
                        f"S1.1.{stack}.{cond}.excess_over_staircase", _fmt(exc.get("excess")),
                        SCRIPT,
                        [rel(BEHAVIOURAL) if stack in ("hosted", "vllm") else rel(PROBE_JSON)],
                        f"observed {_fmt(exc.get('observed_rate'))} minus the rate a step at the "
                        f"fitted switching point implies ({_fmt(exc.get('implied_rate'))}); "
                        f"95% CI [{_fmt(exc.get('excess_ci_lo'))},{_fmt(exc.get('excess_ci_hi'))}]",
                    ))
            else:
                k_hf, n_hf = _rate(c.trials, lambda x: x >= PIE / 2)
                k_low, n_low = _rate(c.trials, lambda x: x <= 10)
                p_rej, lo_rej, hi_rej = wilson(n_hf - k_hf, n_hf)   # reject = 1 - accept
                p_acc, lo_acc, hi_acc = wilson(k_low, n_low)
                if base is not None and base is not c:
                    bk, bn = _rate(base.trials, lambda x: x >= PIE / 2)
                    bp, blo, bhi = wilson(bn - bk, bn)
                    bxx = base.by_x()
                    b_sw = interp_crossing(list(bxx), [float(np.mean(bxx[x])) for x in bxx])
                    base_rate, base_sw = _fmt(bp), _fmt(b_sw)
                    base_ci = f"[{_fmt(blo)}, {_fmt(bhi)}]"
                elif base is c:
                    base_rate, base_sw, base_ci = "self", "self", "self"
                else:
                    base_rate = base_sw = base_ci = NA
                ult_rows.append(dict(
                    stack=stack, game=game, condition=cond,
                    lambda_calibrated=_fmt(lam.get((stack, game, cond))),
                    threshold_interp=_fmt(sw_interp),
                    threshold_logistic=_fmt(sw_logit),
                    offer_grid_max=int(max(xs)),
                    n_levels_at_or_above_half=sum(1 for x in xs if x >= PIE / 2),
                    n_trials_hyperfair=n_hf, k_reject_hyperfair=n_hf - k_hf,
                    p_reject_hyperfair=_fmt(p_rej),
                    ci_reject_hyperfair=f"[{_fmt(lo_rej)}, {_fmt(hi_rej)}]",
                    n_trials_offer_le_10=n_low, k_accept_offer_le_10=k_low,
                    p_accept_offer_le_10=_fmt(p_acc),
                    ci_accept_offer_le_10=f"[{_fmt(lo_acc)}, {_fmt(hi_acc)}]",
                    implied_by_translation=_fmt(exc.get("implied_rate")),
                    excess_over_staircase=_fmt(exc.get("excess")),
                    excess_ci=f"[{_fmt(exc.get('excess_ci_lo'))}, {_fmt(exc.get('excess_ci_hi'))}]",
                    excess_excludes_zero=("" if not np.isfinite(exc.get("excess_ci_lo", np.nan))
                                          else str(exc["excess_ci_lo"] > 0 or exc["excess_ci_hi"] < 0)),
                    same_stack_baseline_condition=base_name or NA,
                    same_stack_baseline_p_reject_hyperfair=base_rate,
                    same_stack_baseline_ci=base_ci,
                    same_stack_baseline_threshold=base_sw,
                ))
                manifest.append((
                    f"S1.2.{stack}.{cond}.pReject_hyperfair", _fmt(p_rej), SCRIPT,
                    [rel(BEHAVIOURAL) if stack in ("hosted", "vllm") else rel(PROBE_JSON)],
                    f"P(reject | offer>=50), n={n_hf}, Wilson [{_fmt(lo_rej)},{_fmt(hi_rej)}]; "
                    f"threshold {_fmt(sw_interp)}; grid max {int(max(xs))}",
                ))
                if exc:
                    manifest.append((
                        f"S1.2.{stack}.{cond}.excess_over_staircase", _fmt(exc.get("excess")),
                        SCRIPT,
                        [rel(BEHAVIOURAL) if stack in ("hosted", "vllm") else rel(PROBE_JSON)],
                        f"observed {_fmt(exc.get('observed_rate'))} minus the rate a step at the "
                        f"fitted threshold implies ({_fmt(exc.get('implied_rate'))}); "
                        f"95% CI [{_fmt(exc.get('excess_ci_lo'))},{_fmt(exc.get('excess_ci_hi'))}]",
                    ))

    write_csv("s1_1_dominated_lottery.csv", lot_rows)
    write_csv("s1_2_catch_ultimatum.csv", ult_rows)
    append_manifest(manifest)
    return lot_rows, ult_rows


# ---------------------------------------------------------------------------
# S1.3 — switching points with uncertainty, and within-stack pairwise differences
# ---------------------------------------------------------------------------
def s1_3(curves: List[Curve], n_boot: int = 2000):
    lam = probe_lambda_table()
    rows, manifest = [], []
    for c in sorted(curves, key=lambda c: (c.stack, c.game, c.condition)):
        b0, b1, sw = fit_logistic(c.trials)
        pt_c, lo_c, hi_c, nv_c = bootstrap_switch(c.trials, n_boot=n_boot, cluster=True, seed=0)
        pt_t, lo_t, hi_t, _ = bootstrap_switch(c.trials, n_boot=n_boot, cluster=False, seed=1)
        bx = c.by_x()
        crossed = interp_crossing(list(bx), [float(np.mean(bx[x])) for x in bx]) is not None
        if not crossed:
            # The measured curve never reaches 0.5 inside the grid, so the logistic
            # is extrapolating past the data. Report the fit as unidentified rather
            # than printing a number the data does not contain.
            sw = lo_c = hi_c = lo_t = hi_t = float("nan")
        rows.append(dict(
            stack=c.stack, game=c.game, condition=c.condition,
            crosses_half_on_grid=str(crossed),
            lambda_calibrated=_fmt(lam.get((c.stack, c.game, c.condition))),
            n_trials=c.n, n_reward_levels=len(bx), n_per_level=c.n // max(1, len(bx)),
            logistic_b0=_fmt(b0), logistic_b1_per_100=_fmt(b1),
            switching_point_logistic=_fmt(sw),
            ci_lo_cluster=_fmt(lo_c), ci_hi_cluster=_fmt(hi_c),
            ci_width_cluster=_fmt(hi_c - lo_c) if np.isfinite(hi_c) and np.isfinite(lo_c) else "",
            ci_lo_trial=_fmt(lo_t), ci_hi_trial=_fmt(hi_t),
            ci_width_trial=_fmt(hi_t - lo_t) if np.isfinite(hi_t) and np.isfinite(lo_t) else "",
            switching_point_interp=_fmt(interp_crossing(list(bx), [float(np.mean(bx[x])) for x in bx])),
            n_bootstrap_valid=nv_c,
        ))
        manifest.append((
            f"S1.3.{c.stack}.{c.game}.{c.condition}.switch", _fmt(sw), SCRIPT,
            [rel(BEHAVIOURAL) if c.stack in ("hosted", "vllm") else rel(PROBE_JSON)],
            f"logistic switching point; reward-level cluster bootstrap 95% CI "
            f"[{_fmt(lo_c)},{_fmt(hi_c)}] from {nv_c} draws; n={c.n}",
        ))
    write_csv("s1_3_switching_points.csv", rows)

    # Pairwise differences, within one stack and one game only.
    by_sg = collections.defaultdict(list)
    for c in curves:
        by_sg[(c.stack, c.game)].append(c)
    diff_rows = []
    for (stack, game), cs in sorted(by_sg.items()):
        if stack.startswith("probe-"):
            # Conditions here are calibrated targets, so the informative
            # comparison is each dose against the next, not all 45 pairs.
            cs = sorted(cs, key=lambda c: int(c.condition.replace("target", "")))
            pairs = [(i, i + 1) for i in range(len(cs) - 1)]
        else:
            cs = sorted(cs, key=lambda c: c.condition)
            pairs = [(i, j) for i in range(len(cs)) for j in range(i + 1, len(cs))]
        def _crosses(c):
            bxx = c.by_x()
            return interp_crossing(list(bxx), [float(np.mean(bxx[x])) for x in bxx]) is not None

        for i, j in pairs:
            both = _crosses(cs[i]) and _crosses(cs[j])
            if both:
                d, lo, hi = bootstrap_switch_diff(cs[i].trials, cs[j].trials,
                                                  n_boot=n_boot, seed=2)
            else:
                d = lo = hi = float("nan")
            diff_rows.append(dict(
                both_identified_on_grid=str(both),
                stack=stack, game=game,
                condition_a=cs[i].condition, condition_b=cs[j].condition,
                diff_switch_a_minus_b=_fmt(d), ci_lo=_fmt(lo), ci_hi=_fmt(hi),
                excludes_zero=("" if not (np.isfinite(lo) and np.isfinite(hi))
                               else str(lo > 0 or hi < 0)),
            ))
    write_csv("s1_3_pairwise_differences.csv", diff_rows)
    append_manifest(manifest)
    return rows, diff_rows


# ---------------------------------------------------------------------------
# S1.8 — cross-stack persona table (GATE_S0_RESPONSE P3)
# ---------------------------------------------------------------------------
PERSONA_PAIRS = [
    ("hosted", "lottery", "baseline", "slightly_prompting"),
    ("hosted", "lottery", "baseline", "barely_prompting"),
    ("vllm", "lottery", "baseline_rp", "persona"),
    ("hosted", "ultimatum", "baseline", "prompting"),
    ("vllm", "ultimatum", "baseline_rp", "persona"),
]


_FIRST_ROW_CACHE: Dict[tuple, dict] = {}


def _first_row(game: str, cond: str) -> dict:
    """One verbatim record per (game, condition), from a single pass over the CSV.

    The behavioural CSV is 71 MB with 60 wide columns; scanning it once per
    lookup costs minutes, so every (game, condition) is cached on first use.
    """
    if not _FIRST_ROW_CACHE:
        for r in csv.DictReader(open(BEHAVIOURAL, newline="")):
            _FIRST_ROW_CACHE.setdefault((r["game"], r["treatment_condition"]), r)
    return _FIRST_ROW_CACHE.get((game, cond), {})


def s1_8(curves: List[Curve]):
    idx = {(c.stack, c.game, c.condition): c for c in curves}
    rows, manifest = [], []
    for stack, game, base_cond, persona_cond in PERSONA_PAIRS:
        base = idx[(stack, game, base_cond)]
        pers = idx[(stack, game, persona_cond)]
        rb, rp = _first_row(game, base_cond), _first_row(game, persona_cond)
        sysk = f"prompt.{'safe_risky_choice' if game == 'lottery' else 'ultimatum_response'}_system_prompt"
        optk = f"question_options.{'safe_risky_choice' if game == 'lottery' else 'ultimatum_response'}_question_options"
        usrk = f"prompt.{'safe_risky_choice' if game == 'lottery' else 'ultimatum_response'}_user_prompt"

        def sw(c):
            bx = c.by_x()
            return interp_crossing(list(bx), [float(np.mean(bx[x])) for x in bx])

        persona_text = rp.get(sysk, "") or rp.get("agent.personality", "")
        options = rp.get(optk, "") or "(none: free text, parsed from 'Final answer: <label>')"
        # Which answer tokens the model is asked to emit.
        if options.startswith("["):
            labels = options
        else:
            u = rp.get(usrk, "")
            labels = ('"Final answer: safe" / "Final answer: risky"' if game == "lottery"
                      else '"Final answer: accept" / "Final answer: reject"') if "Final answer" in u else "?"
        d, lo, hi = bootstrap_switch_diff(pers.trials, base.trials, n_boot=2000, seed=3)
        # A switching point exists only where the measured curve actually crosses
        # 0.5 inside the grid. Where it does not, the logistic is extrapolating
        # past the data and neither the point nor its interval means anything.
        ident = sw(base) is not None and sw(pers) is not None
        if not ident:
            d = lo = hi = float("nan")
        rows.append(dict(
            stack=stack, stack_service=rp.get("model.inference_service", ""), game=game,
            baseline_condition=base_cond, persona_condition=persona_cond,
            persona_text_verbatim=persona_text,
            option_labels=labels,
            baseline_system_prompt_verbatim=rb.get(sysk, ""),
            chat_template_applied="yes (EDSL)" if rp.get("model.inference_service") else "unknown",
            temperature=rp.get("model.temperature", ""),
            precision=("not exposed by the service" if rp.get("model.inference_service") == "goodfire"
                       else "bfloat16 (run_manifest.json)"),
            n_trials_baseline=base.n, n_trials_persona=pers.n,
            unsteered_switching_point=_fmt(sw(base)),
            persona_switching_point=_fmt(sw(pers)),
            shift=_fmt((sw(pers) - sw(base)) if sw(pers) is not None and sw(base) is not None else None),
            switch_identified_on_grid=str(ident),
            shift_logistic=_fmt(d),
            shift_ci=(f"[{_fmt(lo)}, {_fmt(hi)}]" if ident else NA),
            crosses_utility_floor_50=("n/a (ultimatum)" if game == "ultimatum"
                                      else str(sw(pers) is not None and sw(pers) < 50)),
        ))
        manifest.append((
            f"S1.8.{stack}.{game}.{persona_cond}.shift", _fmt(d), SCRIPT, [rel(BEHAVIOURAL)],
            f"persona minus baseline switching point, same stack; cluster bootstrap "
            f"95% CI [{_fmt(lo)},{_fmt(hi)}]",
        ))
    write_csv("s1_8_persona_cross_stack.csv", rows)
    append_manifest(manifest)
    return rows


def main() -> int:
    curves = all_curves()
    print(f"curves loaded: {len(curves)}")
    lot, ult = s1_1_and_1_2(curves)
    print(f"S1.1 lottery rows {len(lot)}; S1.2 ultimatum rows {len(ult)}")
    sp, diffs = s1_3(curves)
    print(f"S1.3 curves {len(sp)}; pairwise {len(diffs)}")
    pers = s1_8(curves)
    print(f"S1.8 persona pairs {len(pers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
