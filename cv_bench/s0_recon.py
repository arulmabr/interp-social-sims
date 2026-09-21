"""S0 reconnaissance: recompute every number quoted in the S0 reports.

Read-only. CPU only. No model, no network.

Run from the repository root:

    python -m cv_bench.s0_recon

Writes:
  results/S/s0_numbers.json     every value, keyed by its MANIFEST id
  results/S/goodfire_labels.json  label + UUID + index of every SAE feature the paper names
  MANIFEST.csv                  one row per value (id, value, script, inputs, git SHA)

Nothing here reads the frozen test split; there is no test split yet.
"""
from __future__ import annotations

import ast
import collections
import csv
import glob
import json
import os
import statistics as st
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = "cv_bench/s0_recon.py"

# Some legacy CSV cells (prompts, responses, raw judge JSON) are very long.
csv.field_size_limit(10_000_000)

# id -> (value, [input paths], note)
VALUES: "collections.OrderedDict[str, tuple]" = collections.OrderedDict()


def record(vid: str, value, inputs, note: str = "") -> None:
    if vid in VALUES:
        raise KeyError(f"duplicate manifest id: {vid}")
    VALUES[vid] = (value, list(inputs), note)


def git_sha() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
    except Exception:
        return "unknown"


def rows(path: Path):
    with open(path, newline="") as f:
        yield from csv.DictReader(f)


def crossing(xs, ys, thr=0.5):
    """First linear interpolation of the level `thr`, or None if never crossed."""
    for i in range(len(xs) - 1):
        if (ys[i] - thr) * (ys[i + 1] - thr) <= 0 and ys[i] != ys[i + 1]:
            return xs[i] + (thr - ys[i]) * (xs[i + 1] - xs[i]) / (ys[i + 1] - ys[i])
    return None


def ols(x, y):
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    A = np.vstack([x, np.ones_like(x)]).T
    beta, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ beta
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")
    return float(beta[0]), float(beta[1]), r2


# ---------------------------------------------------------------------------
# A. Hosted Goodfire / EDSL stack: the curves behind Fig. 3
# ---------------------------------------------------------------------------
SAFE_RISKY_DIR = ROOT / "SAE/data/raw/games/safe_risky/results_20251008_225522"
ULTIMATUM_DIR = ROOT / "SAE/data/raw/games/ultimatum/results_20251008_201139"


def a_hosted_curves() -> None:
    src = SAFE_RISKY_DIR / "reward_experiment_summary.csv"
    cols = {}
    for r in rows(src):
        for k, v in r.items():
            if k == "reward":
                continue
            cols.setdefault(k, []).append((float(r["reward"]), float(v) / 100.0))
    rel = os.path.relpath(src, ROOT)
    for col, series in cols.items():
        cond = col.replace("risky_percent_", "")
        series.sort()
        xs = [a for a, _ in series]
        ys = [b for _, b in series]
        record(
            f"S0.A.lottery.switch.hosted.{cond}",
            crossing(xs, ys),
            [rel],
            "P(risky)=0.5 crossing, linear interpolation, hosted Goodfire/EDSL stack",
        )
        record(
            f"S0.A.lottery.pRisky_at_180.hosted.{cond}",
            ys[-1],
            [rel],
            "P(risky) at the top of the grid (n=180)",
        )
        # Dominated: the gamble's best outcome (n) is below the sure 50.
        dom = [y for x, y in series if x < 50]
        record(
            f"S0.A.lottery.pRisky_dominated.hosted.{cond}",
            float(np.mean(dom)),
            [rel],
            "mean P(risky) over n<50, where the gamble is strictly dominated",
        )
        neg = [y for x, y in series if 50 <= x < 100]
        record(
            f"S0.A.lottery.pRisky_negEV.hosted.{cond}",
            float(np.mean(neg)),
            [rel],
            "mean P(risky) over 50<=n<100, where the gamble loses in expectation",
        )

    src = ULTIMATUM_DIR / "ultimatum_experiment_summary.csv"
    rel = os.path.relpath(src, ROOT)
    ucols = {}
    for r in rows(src):
        for k, v in r.items():
            if k == "offer":
                continue
            ucols.setdefault(k, []).append((float(r["offer"]), float(v) / 100.0))
    for col, series in ucols.items():
        cond = col.replace("accept_percent_", "")
        series.sort()
        xs = [a for a, _ in series]
        ys = [b for _, b in series]
        record(
            f"S0.A.ultimatum.threshold.hosted.{cond}",
            crossing(xs, ys),
            [rel],
            "P(accept)=0.5 crossing, hosted Goodfire/EDSL stack",
        )
        hyper = [y for x, y in series if x >= 50]
        record(
            f"S0.A.ultimatum.pReject_hyperfair.hosted.{cond}",
            float(np.mean([1.0 - y for y in hyper])),
            [rel],
            "mean P(reject) on offers >= 50 of 100 (catch trials)",
        )
        record(
            f"S0.A.ultimatum.offer_grid_max.hosted.{cond}",
            max(xs),
            [rel],
            "largest offer on the grid; the grid stops short of 100",
        )


def a_controllers() -> None:
    """Every Goodfire controller actually used, read out of the logged runs."""
    out = {}
    specs = [
        ("lottery", "steering", SAFE_RISKY_DIR / "safe_risky_steering_50.csv"),
        ("lottery", "lite_steering", SAFE_RISKY_DIR / "safe_risky_lite_steering_50.csv"),
        ("ultimatum", "steering", ULTIMATUM_DIR / "ultimatum_steering_50.csv"),
        (
            "creativity",
            "high_steering",
            ROOT / "SAE/data/raw/creativity/product_innovation_20251102_202650/high_steering.csv",
        ),
    ]
    for task, cond, path in specs:
        if not path.exists():
            out[f"{task}.{cond}"] = {"status": "file_absent", "path": os.path.relpath(path, ROOT)}
            continue
        row = next(rows(path))
        raw = row.get("model.controller", "")
        feats = []
        if raw and raw != "{}":
            ctl = ast.literal_eval(raw)
            for iv in ctl["interventions"]:
                for ft in iv["features"]["features"]:
                    feats.append(
                        {
                            "uuid": ft["uuid"],
                            "label": ft["label"],
                            "index_in_sae": ft["index_in_sae"],
                            "max_activation_strength": ft["max_activation_strength"],
                            "mode": iv["mode"],
                            "value": iv["value"],
                        }
                    )
        out[f"{task}.{cond}"] = {
            "source_file": os.path.relpath(path, ROOT),
            "model": row.get("model.model"),
            "inference_service": row.get("model.inference_service"),
            "temperature": row.get("model.temperature"),
            "top_p": row.get("model.top_p"),
            "max_tokens": row.get("model.max_tokens"),
            "system_prompt": next(
                (v for k, v in row.items() if k.endswith("_system_prompt")), None
            ),
            "features": feats,
        }
    tgt = ROOT / "results/S/goodfire_labels.json"
    tgt.parent.mkdir(parents=True, exist_ok=True)
    tgt.write_text(json.dumps(out, indent=2) + "\n")
    record(
        "S0.A.goodfire.n_named_features",
        sum(len(v.get("features", [])) for v in out.values()),
        [v.get("source_file", "") for v in out.values() if v.get("source_file")],
        "SAE features named by the paper, recovered from logged EDSL controllers",
    )


# ---------------------------------------------------------------------------
# B. Local vLLM stack: the prompting ladder (Revised Prompting)
# ---------------------------------------------------------------------------
def b_prompt_ladder() -> None:
    for run, game in (("safe_risky_full", "lottery"), ("ultimatum_full", "ultimatum")):
        src = ROOT / f"Revised Prompting/runs_fp16/runs/{run}/behavior_summary.csv"
        rel = os.path.relpath(src, ROOT)
        by = collections.defaultdict(list)
        for r in rows(src):
            by[r["condition"]].append((float(r["reward"]), float(r["mean"])))
        for cond, series in by.items():
            series.sort()
            xs = [a for a, _ in series]
            ys = [b for _, b in series]
            record(
                f"S0.B.{game}.switch.vllm.{cond}",
                crossing(xs, ys),
                [rel],
                "0.5 crossing on the local vLLM bf16 stack; None = never crosses",
            )
        record(
            f"S0.B.{game}.n_conditions.vllm",
            len(by),
            [rel],
            "conditions present in the prompting-ladder run",
        )


# ---------------------------------------------------------------------------
# C. Local open-SAE replication of the hosted steering runs
# ---------------------------------------------------------------------------
def c_open_sae_runs() -> None:
    specs = [
        ("lottery", "safe_risky_open_sae_steering_full", "reward", "Risky"),
        ("lottery_lite", "safe_risky_open_sae_steering_lite_full", "reward", "Risky"),
        ("ultimatum", "ultimatum_open_sae_steering_full", "reward", "Accept"),
    ]
    for tag, run, xfield, positive in specs:
        src = ROOT / f"SAE/runs/{run}/response_units.csv"
        meta = ROOT / f"SAE/runs/{run}/open_sae_steering_metadata.json"
        rel = [os.path.relpath(src, ROOT), os.path.relpath(meta, ROOT)]
        data = list(rows(src))
        by = collections.defaultdict(list)
        for r in data:
            ans = (r["answer_text"] or "").strip()
            if not ans:
                continue
            by[float(r[xfield])].append(1 if positive.lower() in ans.lower() else 0)
        xs = sorted(by)
        ys = [st.mean(by[x]) for x in xs]
        record(f"S0.C.{tag}.switch.open_sae_local", crossing(xs, ys), rel,
               "0.5 crossing, local open-SAE clamp_min patch, greedy decoding, 4-bit")
        record(f"S0.C.{tag}.n_units", len(data), rel, "generated response units")
        record(
            f"S0.C.{tag}.n_positive",
            sum(sum(v) for v in by.values()),
            rel,
            f"count of '{positive}' answers over the whole grid",
        )
        m = json.loads(meta.read_text())
        record(f"S0.C.{tag}.strengths", m["input_strengths"], rel, "SAE feature clamp strengths")

    # Do the two lottery doses differ in behaviour at all?
    a = VALUES["S0.C.lottery.n_positive"][0]
    b = VALUES["S0.C.lottery_lite.n_positive"][0]
    record(
        "S0.C.lottery.dose_gap_risky_count",
        a - b,
        [
            "SAE/runs/safe_risky_open_sae_steering_full/response_units.csv",
            "SAE/runs/safe_risky_open_sae_steering_lite_full/response_units.csv",
        ],
        "risky-count difference between the 0.7/0.5 and 0.6/0.4 clamp doses",
    )


# ---------------------------------------------------------------------------
# D. Probe stack: lambda sign, lambda=0 extrapolation, tracking consistency
# ---------------------------------------------------------------------------
PROBE_JSON = ROOT / "Probes/raw_data/probe_results_final.json"


def d_probe_stack() -> None:
    rel = os.path.relpath(PROBE_JSON, ROOT)
    d = json.loads(PROBE_JSON.read_text())

    # -- lambda sign and range, by construct
    lam_pref, lam_cap = [], []
    for key, blob in d.items():
        for r in blob.get("data", []):
            for f in ("lambda_calibrated", "lambda_required"):
                v = r.get(f)
                if v is None:
                    continue
                (lam_cap if r.get("game") in (None, "") else lam_pref).append(float(v))
    record("S0.D.lambda.preference.min", min(lam_pref), [rel], "most negative calibrated lambda, lottery+ultimatum")
    record("S0.D.lambda.preference.max", max(lam_pref), [rel], "least negative calibrated lambda, lottery+ultimatum")
    record("S0.D.lambda.capability.min", min(lam_cap), [rel], "smallest calibrated lambda, creativity")
    record("S0.D.lambda.capability.max", max(lam_cap), [rel], "largest calibrated lambda, creativity")
    record(
        "S0.D.lambda.n_zero_rows",
        sum(1 for v in lam_pref + lam_cap if abs(v) < 1e-9),
        [rel],
        "rows logged at lambda exactly 0 -- an unsteered baseline on the probe stack",
    )

    # -- lambda = 0 extrapolation (an extrapolation, not a measurement)
    for key, tag in (
        ("figure_11_dose_response_lottery_ultimatum_llama", "llama_l48"),
        ("figure_15_dose_response_lottery_ultimatum_qwen", "qwen_l17"),
    ):
        for game in ("lottery", "ultimatum"):
            rs = [r for r in d[key]["data"] if r.get("game") == game]
            if not rs:
                continue
            x = [r["lambda_required"] for r in rs]
            y = [float(r["target_switching_point_tokens"]) for r in rs]
            slope, icpt, r2 = ols(x, y)
            record(f"S0.D.{game}.switch_at_lambda0.extrapolated.{tag}", icpt, [rel],
                   f"OLS intercept of switching point on lambda (R2={r2:.4f}); EXTRAPOLATION beyond the observed lambda range {min(x):.2f}..{max(x):.2f}")
            record(f"S0.D.{game}.switch_vs_lambda.slope.{tag}", slope, [rel], "tokens per unit lambda")
            record(f"S0.D.{game}.switch_vs_lambda.r2.{tag}", r2, [rel], "OLS R^2")

    # -- creativity: achieved score vs lambda, extrapolated to lambda = 0
    for key, tag in (
        ("figure_9_capability_brick_target_vs_achieved", "brick_llama_l48"),
        ("figure_9_capability_stapler_product_innovation_target_vs_achieved", "stapler_llama_l48"),
    ):
        m = d[key]["metadata"]
        ts = sorted(m["lambda_per_target"], key=float)
        x = [m["lambda_per_target"][t] for t in ts]
        y = [m["achieved_per_target"][t] for t in ts]
        slope, icpt, r2 = ols(x, y)
        record(f"S0.D.creativity.score_at_lambda0.extrapolated.{tag}", icpt, [rel],
               f"OLS intercept of achieved creativity on lambda (R2={r2:.4f}); EXTRAPOLATION")
        for t in ts:
            record(f"S0.D.creativity.achieved.{tag}.target{t}", m["achieved_per_target"][t], [rel],
                   "mean achieved creativity score at this target, single stored judge")
            record(f"S0.D.creativity.lambda.{tag}.target{t}", m["lambda_per_target"][t], [rel],
                   "calibrated lambda for this target")

    # -- Fig. 12 / 16 tracking: can the shipped script have produced these numbers?
    for key, tag in (
        ("figure_12_probe_scores_track_target_lottery_ultimatum_llama", "llama_l48"),
        ("figure_16_probe_scores_track_target_qwen", "qwen_l17"),
    ):
        vals = [
            (r["target_switching_point_tokens"], r["mean_probe_activation"])
            for r in d[key]["data"]
            if r.get("game") == "lottery" and r.get("choice_subset") == "all"
        ]
        vals.sort()
        spread = max(v for _, v in vals) - min(v for _, v in vals)
        record(f"S0.D.tracking.all_subset.spread.{tag}", spread, [rel],
               "range of the 'all' mean probe score across targets; the shipped script scores "
               "un-steered prompts on a target-independent grid, so this must be 0")

    # -- per-agent coverage
    for key, blob in d.items():
        n = len(blob.get("per_agent_rows", []))
        if n:
            record(f"S0.D.per_agent_rows.{key}", n, [rel], "per-agent rows stored for this figure key")
    record(
        "S0.D.figure_keys_with_per_agent_rows",
        sum(1 for b in d.values() if b.get("per_agent_rows")),
        [rel],
        f"of {len(d)} figure keys",
    )


def d_probe_key_collision() -> None:
    """The two files called probe_results_combined.csv do not agree on what the Qwen keys mean."""
    out = {}
    for tag, path in (
        ("cleaned", ROOT / "cleaned/probe_results_combined.csv"),
        ("probes_raw", ROOT / "Probes/raw_data/probe_results_combined.csv"),
    ):
        c = collections.Counter(r["source_figure"] for r in rows(path))
        out[tag] = dict(sorted(c.items()))
    shared = set(out["cleaned"]) & set(out["probes_raw"])
    conflict = sorted(
        k for k in (set(out["cleaned"]) | set(out["probes_raw"])) if k not in shared
    )
    record(
        "S0.D.probe_csv.key_conflicts",
        conflict,
        ["cleaned/probe_results_combined.csv", "Probes/raw_data/probe_results_combined.csv"],
        "figure keys present in one probe CSV and absent from the other",
    )
    record(
        "S0.D.probe_csv.rowcount_cleaned",
        sum(out["cleaned"].values()),
        ["cleaned/probe_results_combined.csv"],
        "CSV records (not lines)",
    )
    record(
        "S0.D.probe_csv.rowcount_probes_raw",
        sum(out["probes_raw"].values()),
        ["Probes/raw_data/probe_results_combined.csv"],
        "CSV records (not lines); includes the layer-50 merge",
    )


# ---------------------------------------------------------------------------
# E. Judges
# ---------------------------------------------------------------------------
def e_judges() -> None:
    src = ROOT / "cleaned/creativity_evals_combined.csv"
    rel = os.path.relpath(src, ROOT)
    single = collections.defaultdict(list)
    multi = collections.defaultdict(list)
    per_judge_n = collections.Counter()
    for r in rows(src):
        try:
            v = float(r["final_score"])
        except (TypeError, ValueError):
            continue
        if r["eval_prompt_version"] == "torrance_four_dimension_v1":
            single[(r["task"], r["condition"])].append(v)
        elif r["eval_prompt_version"] == "torrance_four_dimension_length_controlled_v1":
            per_judge_n[r["evaluator_model"]] += 1
            if r["source_file"] == "open_sae_creativity":
                multi[(r["task"], r["condition"], r["evaluator_model"])].append(v)
    for (task, cond), v in sorted(single.items()):
        record(f"S0.E.single_judge.mean.{task[:18]}.{cond}", float(st.mean(v)), [rel],
               f"GPT-5 single-judge mean, n={len(v)}")
    judges = sorted({k[2] for k in multi})
    tasks = sorted({k[0] for k in multi})
    conds = sorted({k[1] for k in multi})
    for task in tasks:
        for cond in conds:
            per = [st.mean(multi[(task, cond, j)]) for j in judges if multi[(task, cond, j)]]
            if not per:
                continue
            record(f"S0.E.multi_judge.mean5.{task[:18]}.{cond}", float(st.mean(per)), [rel],
                   "unweighted mean of the five judges' condition means")
            for j in judges:
                if multi[(task, cond, j)]:
                    record(f"S0.E.multi_judge.mean.{task[:18]}.{cond}.{j}",
                           float(st.mean(multi[(task, cond, j)])), [rel],
                           f"n={len(multi[(task, cond, j)])}")
            # does this judge order steering above baseline?
    record("S0.E.multi_judge.rows_per_judge", dict(per_judge_n), [rel],
           "multi-judge rows per judge; equal counts mean no response was silently dropped")

    agree = ROOT / "Probes/runs/mj_creativity_extra/inter_rater_agreement.json"
    a = json.loads(agree.read_text())
    ra = os.path.relpath(agree, ROOT)
    record("S0.E.spearman.mean_pairwise", a["mean_pairwise_spearman"], [ra],
           f"pooled over all {a['n_trials']} responses, all conditions and both tasks")
    record("S0.E.spearman.min_pair", min(a["pairwise_spearman"].values()), [ra], "")
    record("S0.E.spearman.max_pair", max(a["pairwise_spearman"].values()), [ra], "")
    record("S0.E.spearman.n_trials", a["n_trials"], [ra], "")

    lenreg = ROOT / "Probes/runs/mj_creativity_extra/length_regression.json"
    lr = json.loads(lenreg.read_text())
    rl = os.path.relpath(lenreg, ROOT)
    for judge, blob in lr.items():
        record(f"S0.E.length_r2.{judge}", blob["r_squared"], [rl],
               "R^2 of score on response length for this judge")

    errs = ROOT / "Probes/runs/mj_creativity_extra/errors.jsonl"
    n_err = sum(1 for _ in open(errs))
    record("S0.E.judge_errors", n_err, [os.path.relpath(errs, ROOT)],
           "logged judge failures; all were retried, every judge ends with a full set")


# ---------------------------------------------------------------------------
# F. SAE feature activations: what the top-feature readings rest on
# ---------------------------------------------------------------------------
def f_feature_activations() -> None:
    src = ROOT / "cleaned/feature_activations_combined.csv"
    rel = os.path.relpath(src, ROOT)
    top1 = collections.defaultdict(collections.Counter)
    named = collections.Counter()
    total = 0
    for r in rows(src):
        total += 1
        lab = r["feature_label"] or ""
        rank = r["rank"]
        if rank and rank.isdigit() and int(rank) == 1:
            top1[(r["source"], r["condition"])][lab[:70]] += 1
        low = lab.lower()
        if "unethical request" in low:
            named[("unethical_request", r["source"], r["condition"])] += 1
        if "writing instruments" in low:
            named[("writing_instruments", r["source"], r["condition"])] += 1
    record("S0.F.feature_rows", total, [rel], "rows in the combined feature-activation table")
    for (src_, cond), c in sorted(top1.items()):
        lab, n = c.most_common(1)[0]
        record(f"S0.F.top1.{src_}.{cond}", {"label": lab, "n": n}, [rel],
               "most frequent rank-1 feature for this cell")
    for k, v in sorted(named.items()):
        record(f"S0.F.named_feature.{k[0]}.{k[1]}.{k[2]}", v, [rel],
               "appearances of a feature the paper reads causally, by condition")


# ---------------------------------------------------------------------------
# G. Probe training design (read off the code, counted here)
# ---------------------------------------------------------------------------
def g_probe_design() -> None:
    sys.path.insert(0, str(ROOT))
    from Probes import config  # noqa: E402

    rel = ["Probes/config.py", "Probes/experiments/_common.py", "Probes/models.py"]
    n_lot = len(config.LOTTERY["reward_grid_tokens"])
    n_ult = len(config.ULTIMATUM["offer_grid_tokens"])
    record("S0.G.lottery.n_distinct_prompts", n_lot, rel,
           "distinct lottery prompts; build_preference_probe varies nothing else")
    record("S0.G.ultimatum.n_distinct_prompts", n_ult, rel, "distinct ultimatum prompts")
    record("S0.G.probe.samples_per_prompt", 8, rel,
           "build_preference_probe default n_samples_per_param")
    record("S0.G.lottery.n_training_rows", n_lot * 8, rel,
           "training rows; each distinct activation vector is repeated 8 times")
    record("S0.G.ultimatum.n_training_rows", n_ult * 8, rel, "")
    record("S0.G.capability.n_distinct_prompts", 2, rel,
           "build_capability_probe captures activations at two prompts only: "
           "the task prompt and the persona-prefixed task prompt")
    record("S0.G.capability.n_training_rows", 160, rel, "80 baseline + 80 persona samples")
    record("S0.G.steering.positions_during_prefill",
           f"last {config.STEERING['last_fraction']:.0%} of prompt tokens, ramp "
           f"{config.STEERING['position_scale_lo']}->{config.STEERING['position_scale_hi']}",
           rel, "Wrapped.install_steering hook")
    # seq_len == 1 during cached decoding: reproduce the hook's own index arithmetic.
    import math
    seq_len = 1
    frac = config.STEERING["last_fraction"]
    start_idx = max(1, seq_len - max(1, int(math.ceil(seq_len * frac))))
    n_steered = seq_len - start_idx
    record("S0.G.steering.tokens_steered_per_decode_step", n_steered, rel,
           "hook index arithmetic at seq_len=1, i.e. every cached decoding step: "
           "start_idx=max(1, 1-1)=1, n=1-1=0, so the hook returns the output untouched")
    record("S0.G.steering.v_scaled_is_unit_vector", True, ["Probes/models.py"],
           "install_steering sets v_scaled = v_unit; the norm-matching comment is a no-op")
    record("S0.G.chat_template_applied", False,
           ["Probes/models.py", "Probes/tasks/prompts.py"],
           "the probe stack tokenises raw prompt strings; no chat template, no system prompt")


# ---------------------------------------------------------------------------
# H. Environment (recorded, not asserted)
# ---------------------------------------------------------------------------
def h_environment() -> None:
    caches = {
        "home": Path.home() / ".cache/huggingface/hub",
        "pool": Path.home() / "orcd/pool/hf_cache",
    }
    present = {}
    for tag, d in caches.items():
        present[tag] = sorted(p.name for p in d.iterdir()) if d.is_dir() else None
    record("S0.H.hf_cache_contents", present, ["(filesystem)"],
           "top level of each Hugging Face cache; no directory traversal below it")
    for want in (
        "models--meta-llama--Llama-3.3-70B-Instruct",
        "models--Qwen--Qwen2-7B-Instruct",
        "models--Goodfire--Llama-3.3-70B-Instruct-SAE-l50",
        "models--meta-llama--Llama-3.1-8B-Instruct",
    ):
        found = [t for t, names in present.items() if names and want in names]
        record(f"S0.H.on_disk.{want.split('--', 1)[1]}", found or False, ["(filesystem)"],
               "which cache holds it, or False")
    record("S0.H.goodfire_api_key_in_env", bool(os.environ.get("GOODFIRE_API_KEY")),
           ["(environment)"], "no call was made; the repo records the hosted service as retired")


# ---------------------------------------------------------------------------
# I. Dominated choices under probe steering (orientation only; S1.1 does this
#    properly, per condition, with Wilson intervals)
# ---------------------------------------------------------------------------
def i_probe_dominated() -> None:
    rel = os.path.relpath(PROBE_JSON, ROOT)
    d = json.loads(PROBE_JSON.read_text())
    for key, tag in (
        ("figure_7_psychometric_curves_llama", "llama_l48"),
        ("figure_14_psychometric_curves_qwen", "qwen_l17"),
    ):
        by_target = collections.defaultdict(lambda: {"dom_n": 0, "dom_risky": 0})
        for r in d[key]["per_agent_rows"]:
            if r.get("game") != "lottery":
                continue
            n = r.get("risky_reward_tokens")
            c = r.get("parsed_choice")
            if n is None or c not in (0, 1) or n >= 50:
                continue  # sure amount is 50; n<50 means the gamble is dominated
            b = by_target[r["target_switching_point_tokens"]]
            b["dom_n"] += 1
            b["dom_risky"] += c
        for t in sorted(by_target):
            b = by_target[t]
            record(
                f"S0.I.lottery.pRisky_dominated.probe.{tag}.target{t}",
                b["dom_risky"] / b["dom_n"],
                [rel],
                f"P(risky | n<50) at this calibrated target, n={b['dom_n']} trials",
            )


# ---------------------------------------------------------------------------
# J. Layer 48 vs layer 50 (the July work, absent from the paper's figures)
# ---------------------------------------------------------------------------
def j_layer_comparison() -> None:
    rel = os.path.relpath(PROBE_JSON, ROOT)
    d = json.loads(PROBE_JSON.read_text())
    for game in ("lottery", "ultimatum"):
        a = {r["target_switching_point_tokens"]: r["lambda_calibrated"]
             for r in d["figure_7_psychometric_curves_llama"]["data"] if r["game"] == game}
        b = {r["target_switching_point_tokens"]: r["lambda_calibrated"]
             for r in d["figure_7_psychometric_curves_llama_layer50"]["data"] if r["game"] == game}
        worst = max(abs(b[t] - a[t]) / abs(a[t]) for t in set(a) & set(b))
        record(f"S0.J.{game}.lambda_l48_vs_l50.max_rel_diff", worst, [rel],
               "largest relative difference in calibrated lambda between layer 48 and layer 50")
        # monotonicity of |lambda| in the target
        ts = sorted(a)
        inversions = sum(1 for x, y in zip(ts, ts[1:]) if abs(a[y]) < abs(a[x]))
        record(f"S0.J.{game}.lambda_monotonicity_inversions.l48", inversions, [rel],
               f"targets (of {len(ts) - 1} steps) where |lambda| falls as the target rises")


# ---------------------------------------------------------------------------
def main() -> int:
    a_hosted_curves()
    a_controllers()
    b_prompt_ladder()
    c_open_sae_runs()
    d_probe_stack()
    d_probe_key_collision()
    e_judges()
    f_feature_activations()
    g_probe_design()
    i_probe_dominated()
    j_layer_comparison()
    h_environment()

    sha = git_sha()
    out = {
        vid: {"value": v, "inputs": inp, "note": note}
        for vid, (v, inp, note) in VALUES.items()
    }
    (ROOT / "results/S").mkdir(parents=True, exist_ok=True)
    (ROOT / "results/S/s0_numbers.json").write_text(
        json.dumps({"git_sha": sha, "script": SCRIPT, "values": out}, indent=2) + "\n"
    )

    man = ROOT / "MANIFEST.csv"
    write_header = not man.exists()
    with open(man, "a", newline="") as f:
        w = csv.writer(f)
        if write_header:
            w.writerow(["id", "value", "script", "inputs", "git_sha", "note"])
        for vid, (v, inp, note) in VALUES.items():
            w.writerow([vid, json.dumps(v), SCRIPT, ";".join(inp), sha, note])

    print(f"{len(VALUES)} values -> results/S/s0_numbers.json and MANIFEST.csv (sha {sha[:8]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
