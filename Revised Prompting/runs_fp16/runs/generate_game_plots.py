"""
generate_game_plots.py
======================

Generate the 6 missing Revised-Prompting figures for the lottery (safe_risky)
and ultimatum games. The full runs (``safe_risky_full/``, ``ultimatum_full/``)
ship with ``behavior_summary.csv`` (9 conds x N rewards x 40 agents/cell) but
no PNGs were ever produced for them. This script creates three plots per game:

1. ``<game>_psychometric_by_condition.png``    5 condition lines, % positive
                                                choice vs reward / offer.
2. ``<game>_dose_response_fewshot_cot.png``    5-level Few-shot+CoT dose sweep
                                                (0% / 25% / 50% / 75% / 100%),
                                                colour gradient + dashed baseline.
3. ``<game>_delta_vs_baseline.png``            One bar per non-baseline cond,
                                                mean Delta vs baseline averaged
                                                across all reward levels (SEM
                                                across reward levels).

Outputs:
    <game_dir>/plots/<game>_*.png

Style mirrors regenerate_all_figures.py / generate_multi_judge_plots.py
(sans-serif, no grid, 600 dpi, canonical condition palette).
"""
from __future__ import annotations

import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Style — match regenerate_all_figures.py (COLM 2025 paper look)
# ---------------------------------------------------------------------------
plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "axes.grid": False,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    "axes.spines.top": True,
    "axes.spines.right": True,
    "axes.edgecolor": "#222222",
    "axes.linewidth": 0.9,
    "legend.frameon": False,
    "figure.dpi": 150,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
})

# Condition palette — same hues as the repo's canonical CONDITION_COLORS.
COND_COLORS = {
    "baseline":            "#27286B",  # navy
    "persona":             "#E8804B",  # orange
    "cot":                 "#7B3FA0",  # purple
    "fewshot":             "#1FA8A8",  # teal
    "fewshot_cot_dose100": "#D6453D",  # red (strongest single condition)
}
COND_LABELS = {
    "baseline":            "Baseline",
    "persona":             "Persona",
    "cot":                 "CoT",
    "fewshot":             "Few-shot",
    "fewshot_cot_dose100": "Few-shot + CoT",
}
COND_ORDER = [
    "baseline", "persona", "cot", "fewshot",
    "fewshot_cot_dose000", "fewshot_cot_dose025",
    "fewshot_cot_dose050", "fewshot_cot_dose075",
    "fewshot_cot_dose100",
]

DOSES = [0.0, 0.25, 0.50, 0.75, 1.00]
DOSE_CONDS = [f"fewshot_cot_dose{int(d*100):03d}" for d in DOSES]

GAMES = [
    dict(name="lottery",
         dir="safe_risky_full",
         x_label="Risky reward (tokens)",
         y_label="% of agents choosing Risky",
         metric_filter="choice_risky",
         title_main="Lottery"),
    dict(name="ultimatum",
         dir="ultimatum_full",
         x_label="Offer amount (tokens)",
         y_label="% of agents accepting offer",
         metric_filter="accept_offer",
         title_main="Ultimatum Game"),
]


def sem_binom(p: float, n: float) -> float:
    """Binomial SEM at proportion p, sample size n."""
    n = max(int(n), 1)
    p = float(np.clip(p, 0.0, 1.0))
    return float(np.sqrt(p * (1.0 - p) / n))


def _smart_ylim(ax, data_lo: float, data_hi: float):
    """Asymmetric y-limits: tight on the empty side, always include 0."""
    plot_lo = min(0.0, data_lo)
    plot_hi = max(0.0, data_hi)
    span = max(plot_hi - plot_lo, 1e-6)
    bot_pad = 0.05 * span if data_lo >= 0 else 0.10 * span
    top_pad = 0.05 * span if data_hi <= 0 else 0.10 * span
    ax.set_ylim(plot_lo - bot_pad, plot_hi + top_pad)


for game in GAMES:
    csv_path = os.path.join(HERE, game["dir"], "behavior_summary.csv")
    df = pd.read_csv(csv_path)
    df = df[df["metric"] == game["metric_filter"]].copy()
    df["reward"] = pd.to_numeric(df["reward"], errors="coerce")
    df["mean"] = pd.to_numeric(df["mean"], errors="coerce")
    df["count"] = pd.to_numeric(df["count"], errors="coerce")

    out_dir = os.path.join(HERE, game["dir"], "plots")
    os.makedirs(out_dir, exist_ok=True)
    n_per_cell = int(df["count"].iloc[0])
    n_rewards = df["reward"].nunique()

    # ---------------------------------------------------------------------
    # 1. Psychometric curves — 5 discrete conditions
    # ---------------------------------------------------------------------
    psy_conds = ["baseline", "persona", "cot", "fewshot", "fewshot_cot_dose100"]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for cond in psy_conds:
        sub = df[df["condition"] == cond].sort_values("reward")
        if sub.empty:
            continue
        n = sub["count"].iloc[0]
        ys = sub["mean"].values * 100.0
        yerr = np.array([sem_binom(p, n) for p in sub["mean"].values]) * 100.0
        ax.errorbar(sub["reward"], ys, yerr=yerr,
                    color=COND_COLORS[cond], label=COND_LABELS[cond],
                    marker="o", markersize=4, lw=1.5, capsize=2)
    ax.axhline(50, color="grey", ls=":", lw=0.7, alpha=0.6)
    ax.set_xlabel(game["x_label"])
    ax.set_ylabel(game["y_label"])
    ax.set_ylim(-2, 102)
    ax.set_title(
        f"Revised Prompting — {game['title_main']}\n"
        f"Psychometric curves by prompting condition")
    ax.legend(loc="best", fontsize=8)
    plt.tight_layout()
    out = os.path.join(out_dir, f"{game['name']}_psychometric_by_condition.png")
    plt.savefig(out, dpi=600, bbox_inches="tight"); plt.close()
    print(f"  wrote {os.path.relpath(out, HERE)}")

    # ---------------------------------------------------------------------
    # 2. Dose-response sweep on Few-shot + CoT
    # ---------------------------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5.2))
    cmap = plt.get_cmap("plasma")
    for d, cond in zip(DOSES, DOSE_CONDS):
        sub = df[df["condition"] == cond].sort_values("reward")
        if sub.empty:
            continue
        n = sub["count"].iloc[0]
        ys = sub["mean"].values * 100.0
        yerr = np.array([sem_binom(p, n) for p in sub["mean"].values]) * 100.0
        color = cmap(0.05 + 0.80 * d)   # avoid pure yellow at the top
        ax.errorbar(sub["reward"], ys, yerr=yerr,
                    color=color, label=f"Few-shot+CoT dose={int(d*100)}%",
                    marker="o", markersize=4, lw=1.5, capsize=2)
    ax.axhline(50, color="grey", ls=":", lw=0.7, alpha=0.6)
    ax.set_xlabel(game["x_label"])
    ax.set_ylabel(game["y_label"])
    ax.set_ylim(-2, 102)
    ax.set_title(
        f"Revised Prompting — {game['title_main']}\n"
        f"Dose-response sweep on Few-shot + CoT")
    ax.legend(loc="best", fontsize=8, ncol=2)
    plt.tight_layout()
    out = os.path.join(out_dir, f"{game['name']}_dose_response_fewshot_cot.png")
    plt.savefig(out, dpi=600, bbox_inches="tight"); plt.close()
    print(f"  wrote {os.path.relpath(out, HERE)}")

    # ---------------------------------------------------------------------
    # 3. Per-condition mean Delta vs baseline, averaged across rewards
    # ---------------------------------------------------------------------
    base_series = (df[df["condition"] == "baseline"]
                   .set_index("reward")["mean"].sort_index())

    bars = []
    for cond in COND_ORDER:
        if cond == "baseline":
            continue
        sub = (df[df["condition"] == cond]
               .set_index("reward")["mean"].sort_index())
        common = base_series.index.intersection(sub.index)
        if len(common) == 0:
            continue
        diffs = (sub.loc[common] - base_series.loc[common]).values
        mean_d = float(np.mean(diffs))
        sem_d = float(np.std(diffs, ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 1 else 0.0
        bars.append((cond, mean_d, sem_d, len(diffs)))

    fig, ax = plt.subplots(figsize=(11, 5.4))
    xs = np.arange(len(bars))
    means_pct = np.array([b[1] for b in bars]) * 100.0
    sems_pct = np.array([b[2] for b in bars]) * 100.0
    colors = []
    for cond, *_ in bars:
        if cond in COND_COLORS:
            colors.append(COND_COLORS[cond])
        elif cond.startswith("fewshot_cot_dose"):
            d = int(cond.replace("fewshot_cot_dose", "")) / 100.0
            colors.append(cmap(0.05 + 0.80 * d))
        else:
            colors.append("#666666")

    ax.bar(xs, means_pct, yerr=sems_pct, color=colors,
           edgecolor="black", linewidth=0.5, capsize=3)
    ax.axhline(0.0, color="#444", ls="--", lw=0.9, alpha=0.7)

    pretty_map = {
        "persona": "Persona", "cot": "CoT", "fewshot": "Few-shot",
        "fewshot_cot_dose000": "FS+CoT @0%",
        "fewshot_cot_dose025": "FS+CoT @25%",
        "fewshot_cot_dose050": "FS+CoT @50%",
        "fewshot_cot_dose075": "FS+CoT @75%",
        "fewshot_cot_dose100": "FS+CoT @100%",
    }
    ax.set_xticks(xs)
    ax.set_xticklabels([pretty_map.get(b[0], b[0]) for b in bars],
                       rotation=20, ha="right")
    ax.set_xlabel("Condition")
    if game["name"] == "lottery":
        ax.set_ylabel(r"$\Delta$ % choosing Risky vs baseline")
    else:
        ax.set_ylabel(r"$\Delta$ % accepting vs baseline")

    # Data-driven y-lims (tight on empty side, always include 0)
    data_lo = float(np.min(means_pct - sems_pct))
    data_hi = float(np.max(means_pct + sems_pct))
    _smart_ylim(ax, data_lo, data_hi)

    ax.set_title(
        f"Revised Prompting — {game['title_main']}\n"
        f"Mean Δ vs baseline by condition")
    plt.tight_layout()
    out = os.path.join(out_dir, f"{game['name']}_delta_vs_baseline.png")
    plt.savefig(out, dpi=600, bbox_inches="tight"); plt.close()
    print(f"  wrote {os.path.relpath(out, HERE)}")

print("\nAll game plots generated.")
