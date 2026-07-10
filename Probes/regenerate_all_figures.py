"""
regenerate_all_figures.py
=========================

Regenerate every *data-driven* PNG that appears in the ``mech_interp/`` folder of
the paper, using **only** the consolidated CSVs in this ``cleaned/`` directory.

All plots are styled to **mimic the example.pdf** figures (COLM 2025 paper
"To Backtrack or Not to Backtrack"): sans-serif plot fonts, bold titles, a
full thin box (all four spines) with **no grid**, bold "(A)/(B)" panel letters,
filled markers on data points, a plasma-family gradient for ordered series, and
**600-dpi** (very high resolution) export.

--------------------------------------------------------------------------------
INPUT DATA — only these FOUR consolidated CSVs are required (all in this folder)
--------------------------------------------------------------------------------
behavioral_games_combined.csv   Lottery + Ultimatum game choices.
                                Split column: `game` in {lottery, ultimatum}.
probe_results_combined.csv      All probe-steering results (psychometric, dose-
                                response, activation-tracking, capability target-
                                vs-achieved, cross-object generalization).
                                Split column: `probe_group` in {lottery, ultimatum,
                                creativity}; figures keyed by `source_figure`.
creativity_evals_combined.csv   GPT-5 creativity evals for brick + stapler.
                                Split column: `task` in {detailed_ways_to_use_a_brick,
                                improve_the_stapler_with_many_specific_enhancements}.
feature_activations_combined.csv  SAE feature activations (lottery/ultimatum per-
                                agent ranks + creativity top-k activation strengths).

(These four replace the previous nine per-experiment CSVs; the script derives the
nine logical tables from them with simple column filters — see the load block.)

--------------------------------------------------------------------------------
OUTPUT
--------------------------------------------------------------------------------
Written to ``figures/figures_regen/`` mirroring the mech_interp layout:
    figures/figures_regen/<name>.png
    figures/figures_regen/figures/<name>.png
    figures/figures_regen/figures_llama/<name>.png

Only ``probe_results_combined.csv`` is required; the other three CSVs are optional
(their behavioural-game / capability-bar / SAE-activation figures are skipped if
the file is absent, and the probe figures still render).

--------------------------------------------------------------------------------
DATA-AVAILABILITY NOTES (see MISSING_DATA at bottom for the machine-readable list)
--------------------------------------------------------------------------------
* sae_schematic.png / probe_schematic.png are hand-drawn method diagrams, NOT
  data plots -> cannot be regenerated from any CSV. Skipped.
* The capability figures come in two judge variants in the paper:
    - "*_GPT5" / "*_Gpt5" = scored by GPT-5  -> THIS is what cleaned/ contains.
    - plain "figure9.png" / "figure10.png"  = scored by the ORIGINAL judge, with
      its own lambda calibration. Those raw scores are NOT in cleaned/. We render
      those filenames from the GPT-5 data as the closest available proxy and flag
      them in MISSING_DATA.
* Cross-object generalization (figure13a/b) is a probe-accuracy metric that does
  NOT depend on the creativity judge, so the "_GPT5" and plain variants are the
  same data and both are reproduced exactly.
"""

import os
import textwrap
from collections import defaultdict

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")              # headless/batch rendering (no display needed)
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# matplotlib.cm.get_cmap is deprecated (>=3.7) and removed (3.11); route it
# through pyplot.get_cmap, which stays supported. Unconditional = no warnings.
cm.get_cmap = plt.get_cmap

# ----------------------------------------------------------------------------
# Paths & global style
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "figures", "figures_regen")
for sub in ("", "figures", "figures_llama"):
    os.makedirs(os.path.join(OUT, sub), exist_ok=True)

# ----------------------------------------------------------------------------
# Style — mimic the COLM 2025 paper example.pdf
# ("To Backtrack or Not to Backtrack"). Characteristics observed in its figures:
#   * sans-serif plot fonts (small), bold titles (often colour-coded by group)
#   * full thin BOX (all four spines), NO grid, white background
#   * bold panel letters "(A)/(B)/(a)/(b)" at the top-left of each panel
#   * filled markers on every data point; solid + dashed line mixes
#   * ordered series use a plasma-family gradient (amber -> red -> purple -> navy)
#   * frameless inline legends
#   * exported at very high resolution (600 dpi)
# ----------------------------------------------------------------------------
plt.rcParams.update({
    # fonts (sans-serif, as in the paper's plots)
    "font.family": "sans-serif",
    "font.sans-serif": ["Helvetica", "Arial", "DejaVu Sans"],
    "mathtext.fontset": "dejavusans",
    # sizes (compact)
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.titleweight": "bold",
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 7.5,
    "figure.titlesize": 12,
    "figure.titleweight": "bold",
    # no grid, clean white background
    "axes.grid": False,
    "axes.facecolor": "white",
    "figure.facecolor": "white",
    "savefig.facecolor": "white",
    # full thin box (all four spines)
    "axes.spines.top": True,
    "axes.spines.right": True,
    "axes.edgecolor": "#222222",
    "axes.linewidth": 0.9,
    # lines / ticks
    "lines.linewidth": 1.6,
    "lines.markersize": 4.5,
    "xtick.direction": "out",
    "ytick.direction": "out",
    "xtick.major.size": 3.0,
    "ytick.major.size": 3.0,
    # legend
    "legend.frameon": False,
    # very high resolution export
    "figure.dpi": 150,
    "savefig.dpi": 600,
    "savefig.bbox": "tight",
})

LLAMA = "Llama-3.3-70B-Instruct"
QWEN = "Qwen-2-7B-Instruct"

# Paper palette (sampled from example.pdf figures): teal signature + warm/cool set.
C_TEAL = "#1FA8A8"     # signature teal/cyan
C_ORANGE = "#E8804B"   # amber/orange
C_PURPLE = "#7B3FA0"   # purple/magenta
C_NAVY = "#27286B"     # dark indigo/navy
C_RED = "#D6453D"      # coral red
# Back-compat aliases used throughout the plotting functions.
C_BLUE = C_NAVY
C_GREEN = C_TEAL
C_GREY = C_PURPLE

# ----------------------------------------------------------------------------
# CANONICAL CONDITION COLOURS — one fixed colour per experimental condition,
# reused for that condition's line/bar in EVERY figure so the legend is stable
# across plots.
# ----------------------------------------------------------------------------
CONDITION_COLORS = {
    "baseline":          C_NAVY,    # #27286B  navy/indigo
    "prompting":         C_ORANGE,  # #E8804B  orange
    "sae_steering":      C_TEAL,    # #1FA8A8  teal
    "probe_steering":    C_PURPLE,  # #7B3FA0  purple
    "high_temperature":  C_RED,     # #D6453D  coral red  (extra condition, creativity tasks)
}
# Aliases: how each dataset names a condition -> canonical key above.
CONDITION_ALIAS = {
    "baseline": "baseline",
    "prompting": "prompting",
    "slightly_prompting": "prompting",   # behavioural "Prompting" series
    "barely_prompting": "prompting",
    "steering": "sae_steering",           # behavioural "Steering" = SAE steering
    "lite_steering": "sae_steering",
    "high_steering": "sae_steering",      # creativity "Steering" = SAE steering
    "high_temperature": "high_temperature",
    "probe": "probe_steering",
    "probe_steering": "probe_steering",
}
# Lighter tints for the 2 extra variants shown only in 5_conditions.png, so they
# read as "a kind of prompting / a kind of steering" while staying distinct.
COND_VARIANT_COLORS = {
    "barely_prompting": "#F4B183",   # light orange  (a milder prompting)
    "lite_steering":    "#8FD4D4",   # light teal     (a milder SAE steering)
}

def cond_color(name):
    """Canonical colour for a dataset condition name."""
    return CONDITION_COLORS[CONDITION_ALIAS.get(name, name)]

# ----------------------------------------------------------------------------
# TASK COLOURS — used only by the feature-activation bar grids, where bars are
# coloured by TASK (row), not by condition. Kept distinct from the condition
# palette above to avoid confusion.
# ----------------------------------------------------------------------------
TASK_COLORS = {
    "detailed_ways_to_use_a_brick":                       "#2E7D32",  # forest green  (divergent creativity)
    "improve_the_stapler_with_many_specific_enhancements": "#C99700",  # goldenrod     (product innovation)
}


def ordered_colors(n, cmap="plasma", lo=0.05, hi=0.88):
    """Return n colours along a plasma-family gradient (amber->red->purple->navy),
    matching the model-size / ordered-series colouring in example.pdf."""
    cm_ = plt.get_cmap(cmap)
    return [cm_(x) for x in np.linspace(hi, lo, max(1, n))]


def panel_label(ax, text, x=-0.13, y=1.02):
    """Bold panel letter, e.g. '(A)', at the top-left of an axis (paper style)."""
    ax.text(x, y, text, transform=ax.transAxes, fontsize=11, fontweight="bold",
            va="bottom", ha="left")


# ----------------------------------------------------------------------------
# Load data once
# ----------------------------------------------------------------------------
def _read(name):
    # The consolidated probe-results file lives under Probes/raw_data/.
    return pd.read_csv(os.path.join(HERE, "raw_data", name), low_memory=False)


def _read_optional(name, columns):
    """Load a CSV if present, else return an empty frame carrying `columns` so
    the module-level filters degrade gracefully and `main()` skips the figures
    that need it (see the per-group guards in main)."""
    path = os.path.join(HERE, name)
    if os.path.exists(path):
        return pd.read_csv(path, low_memory=False)
    print(f"[regen] '{name}' not found - figures requiring it will be skipped.")
    return pd.DataFrame(columns=columns)

# ---------------------------------------------------------------------------
# probe_results_combined.csv is REQUIRED (every probe figure reads it). The
# other three consolidated CSVs are OPTIONAL: if absent, their behavioural-game
# / capability-bar / SAE-activation figures are skipped and the probe figures
# still render. The nine logical tables are derived by simple filters below.
# ---------------------------------------------------------------------------
_probe = _read("probe_results_combined.csv")           # all probe rows (col: probe_group)
_behavioral = _read_optional("behavioral_games_combined.csv",
                             ["game", "treatment_condition", "offer_amount",
                              "answer.safe_risky_choice", "answer.ultimatum_response"])
_creativity = _read_optional("creativity_evals_combined.csv",
                             ["task", "condition", "final_score"])
feat = _read_optional("feature_activations_combined.csv",
                      ["source", "condition", "task", "feature_label", "rank", "activation"])

# Behavioural games (split by game)
safe = _behavioral[_behavioral["game"] == "lottery"].copy()
ult = _behavioral[_behavioral["game"] == "ultimatum"].copy()

# GPT-5 creativity evals (split by task)
div_comb = _creativity[_creativity["task"] == "detailed_ways_to_use_a_brick"].copy()
prod_comb = _creativity[
    _creativity["task"] == "improve_the_stapler_with_many_specific_enhancements"].copy()

# Probe results (split by probe_group). div_probe / prod_probe share the same
# creativity subset; downstream code filters them by exact source_figure, so the
# brick/four-object/cross-object figures land in div_probe usage and the stapler
# figure in prod_probe usage without collision.
lot_probe = _probe[_probe["probe_group"] == "lottery"].copy()
ult_probe = _probe[_probe["probe_group"] == "ultimatum"].copy()
_creativity_probe = _probe[_probe["probe_group"] == "creativity"].copy()
div_probe = _creativity_probe
prod_probe = _creativity_probe


def _save(relpath):
    out = os.path.join(OUT, relpath)
    # 600 dpi -> very high resolution raster output
    plt.savefig(out, dpi=600, bbox_inches="tight")
    plt.close()
    print(f"wrote {os.path.relpath(out, HERE)}")


def _wrap(s, width=38):
    return "\n".join(textwrap.wrap(str(s), width=width))


# ============================================================================
# GROUP 1 — Behavioural psychometric curves & capability bars
# ============================================================================
def _psychometric_panel(ax, df, answer_col, positive_label, condition_map,
                        xlabel, ylabel, title):
    """Generic % positive-choice vs offer/reward curve, one line per condition."""
    df = df.copy()
    df["pos"] = (df[answer_col] == positive_label).astype(int)
    for cond, (label, color, ls, marker) in condition_map.items():
        sub = df[df.treatment_condition == cond]
        if sub.empty:
            continue
        pct = sub.groupby("offer_amount")["pos"].mean() * 100.0
        ax.plot(pct.index, pct.values, label=label, color=color,
                linestyle=ls, marker=marker)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(-2, 102)
    ax.legend(loc="best", fontsize=8)


# 3-condition styling used by preference.png / safe-vs-risky / ultimatum_game.
# Colours come from the canonical CONDITION_COLORS map so they match every other
# figure (baseline=navy, prompting=orange, SAE steering=teal).
LOTTERY_3 = {
    "baseline":           ("Baseline",  cond_color("baseline"),           "-",  "o"),
    "slightly_prompting": ("Prompting", cond_color("slightly_prompting"), "--", "s"),
    "steering":           ("Steering",  cond_color("steering"),           ":",  "^"),
}
ULT_3 = {
    "baseline":  ("Baseline",  cond_color("baseline"),  "-",  "o"),
    "prompting": ("Prompting", cond_color("prompting"), "--", "s"),
    "steering":  ("Steering",  cond_color("steering"),  ":",  "^"),
}


def plot_preference():
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.6))
    _psychometric_panel(
        axes[0], safe, "answer.safe_risky_choice", "Risky Option", LOTTERY_3,
        "Risky Reward Value (tokens)", "Percentage of Agents Choosing Risky Option",
        "Lottery Game Results: Safe vs. Risky\n(N=40 agents per condition)")
    _psychometric_panel(
        axes[1], ult, "answer.ultimatum_response", "Accept", ULT_3,
        "Offer Amount (tokens)", "Percentage of Agents Accepting Offer",
        "Ultimatum Game Results: Selfless vs. Selfish\n(N=40 agents per condition)")
    panel_label(axes[0], "(A)")
    panel_label(axes[1], "(B)")
    plt.tight_layout()
    _save("preference.png")


def plot_safe_vs_risky():
    fig, ax = plt.subplots(figsize=(8, 5))
    _psychometric_panel(
        ax, safe, "answer.safe_risky_choice", "Risky Option", LOTTERY_3,
        "Risky Reward Value (tokens)", "Percentage of Agents Choosing Risky Option",
        "Lottery Game Results: Safe vs. Risky\n(N=40 agents per condition)")
    plt.tight_layout()
    _save("figures/safe-vs-risky.png")


def plot_ultimatum_game():
    fig, ax = plt.subplots(figsize=(8, 5))
    _psychometric_panel(
        ax, ult, "answer.ultimatum_response", "Accept", ULT_3,
        "Offer Amount (tokens)", "Percentage of Agents Accepting Offer",
        "Ultimatum Game Results: Selfless vs. Selfish\n(N=40 agents per condition)")
    plt.tight_layout()
    _save("figures/ultimatum_game.png")


def plot_5_conditions():
    """Lottery with all five conditions present in safe_risky_combined.csv."""
    # baseline / prompting / SAE-steering keep their canonical colours; the two
    # extra variants use lighter tints of prompting (orange) and steering (teal).
    five = {
        "baseline":           ("Baseline",                  cond_color("baseline")),
        "barely_prompting":   ("Prompting: Barely Risky",   COND_VARIANT_COLORS["barely_prompting"]),
        "slightly_prompting": ("Prompting: Slightly Risky", cond_color("slightly_prompting")),
        "lite_steering":      ("Steering: 0.6, 0.4",        COND_VARIANT_COLORS["lite_steering"]),
        "steering":           ("Steering: 0.7, 0.5",        cond_color("steering")),
    }
    fig, ax = plt.subplots(figsize=(9, 5.5))
    s = safe.copy()
    s["risky"] = (s["answer.safe_risky_choice"] == "Risky Option").astype(int)
    for cond, (label, color) in five.items():
        sub = s[s.treatment_condition == cond]
        if sub.empty:
            continue
        pct = sub.groupby("offer_amount")["risky"].mean() * 100.0
        ax.plot(pct.index, pct.values, label=label, color=color, marker="o", markersize=4)
    ax.set_xlabel("Risky Reward Value (tokens)")
    ax.set_ylabel("Percentage of Agents Choosing Risky Option")
    ax.set_title("Lottery Game Results: Safe vs. Risky\n(N=40 agents per condition)")
    ax.set_ylim(-2, 102)
    ax.legend(fontsize=8, loc="center right")
    plt.tight_layout()
    _save("5_conditions.png")


def plot_capability_bar():
    """Creativity score by condition for brick (divergent) & stapler (product)."""
    order = ["baseline", "prompting", "high_temperature", "high_steering"]
    labels = {"baseline": "Baseline", "prompting": "Prompting",
              "high_temperature": "High Temp", "high_steering": "Steering"}
    # canonical condition colours (consistent with preference.png / 5_conditions.png):
    # baseline=navy, prompting=orange, high_temperature=coral red, high_steering=teal
    colors = {c: cond_color(c) for c in order}
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
    for pl, ax, df, title in [
        ("(A)", axes[0], div_comb, "Divergent Creativity Tasks"),
        ("(B)", axes[1], prod_comb, "Product Innovation Tasks"),
    ]:
        means = df.groupby("condition")["final_score"].mean().reindex(order)
        stds = df.groupby("condition")["final_score"].std().reindex(order)
        x = np.arange(len(order))
        ax.bar(x, means.values, yerr=stds.values, capsize=5,
               color=[colors[c] for c in order], edgecolor="black", linewidth=0.5)
        for xi, m, s in zip(x, means.values, stds.values):
            ax.text(xi, m + s + 0.2, f"{m:.2f}±{s:.2f}", ha="center", va="bottom", fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels([labels[c] for c in order])
        ax.set_ylim(0, 10)
        ax.set_ylabel("Creativity Score (1-10)")
        ax.set_title(title)
        panel_label(ax, pl)
    plt.tight_layout()
    _save("capability.png")


# ============================================================================
# GROUP 2 — Probe-steering plots
# ============================================================================
def plot_probe_psychometric(lot_fig, ult_fig, model_name, out_relpath,
                            ult_cmap="plasma", lot_xmax=245, ult_xmax=102):
    """Figure 7 (Llama) / Figure 5 (Qwen).

    IMPORTANT (per regen_figure7.py): use the aggregate `data` section's
    plotted_fraction_* (smoothed/monotonised) rather than re-deriving from
    per-agent rows, which is quantised to 1/40 steps and looks jagged.
    """
    fig, (ax_l, ax_u) = plt.subplots(1, 2, figsize=(14, 5))

    # ---- Lottery (viridis) ----
    d = lot_probe[(lot_probe.source_figure == lot_fig) &
                  (lot_probe.data_section == "data")].copy()
    by_t = defaultdict(list)
    for _, r in d.iterrows():
        by_t[r["target_switching_point_tokens"]].append(
            (r["risky_reward_tokens"], r["plotted_fraction_risky"]))
    targets = sorted(by_t)
    norm = mcolors.Normalize(vmin=min(targets), vmax=max(targets))
    cmap = cm.get_cmap("viridis")
    for t in targets:
        xs, ys = zip(*sorted(by_t[t]))
        ax_l.plot(xs, [y * 100 for y in ys], color=cmap(norm(t)), lw=1.6)
    ax_l.axhline(50, color="gray", ls=":", lw=0.8, alpha=0.5)
    ax_l.set_xlabel("Risky reward (tokens)")
    ax_l.set_ylabel("Percentage of Agents Choosing Risky Option")
    ax_l.set_title(f"Lottery game: Safe vs. Risky under probe steering ({model_name})")
    ax_l.set_ylim(0, 102); ax_l.set_xlim(0, lot_xmax)
    sm = cm.ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
    fig.colorbar(sm, ax=ax_l).set_label("Target switching point (tokens)")

    # ---- Ultimatum (warm cmap) ----
    d = ult_probe[(ult_probe.source_figure == ult_fig) &
                  (ult_probe.data_section == "data")].copy()
    by_t = defaultdict(list)
    for _, r in d.iterrows():
        by_t[r["target_switching_point_tokens"]].append(
            (r["offer_amount_tokens"], r["plotted_fraction_accept"]))
    targets = sorted(by_t)
    norm = mcolors.Normalize(vmin=min(targets), vmax=max(targets))
    cmap = cm.get_cmap(ult_cmap)
    for t in targets:
        xs, ys = zip(*sorted(by_t[t]))
        ax_u.plot(xs, [y * 100 for y in ys], color=cmap(norm(t)), lw=1.6)
    ax_u.axhline(50, color="gray", ls=":", lw=0.8, alpha=0.5)
    ax_u.set_xlabel("Offer amount (tokens)")
    ax_u.set_ylabel("Percentage of Agents Accepting Offer")
    ax_u.set_title(f"Ultimatum game: Selfless vs. Selfish under probe steering ({model_name})")
    ax_u.set_ylim(0, 102); ax_u.set_xlim(0, ult_xmax)
    sm = cm.ScalarMappable(norm=norm, cmap=cmap); sm.set_array([])
    fig.colorbar(sm, ax=ax_u).set_label("Target switching point (tokens)")

    panel_label(ax_l, "(a)")
    panel_label(ax_u, "(b)")
    plt.tight_layout()
    _save(out_relpath)


def _capability_curve(ax, sub, color, label, annotate_lambda=True, stack=None):
    """Shared helper: target vs achieved creativity with optional lambda labels."""
    sub = sub.copy()
    sub["target"] = pd.to_numeric(sub["target_creativity_score"], errors="coerce")
    sub["score"] = pd.to_numeric(sub["creativity_score"], errors="coerce")
    sub["lam"] = pd.to_numeric(sub["lambda_calibrated"], errors="coerce")
    g = sub.groupby("target").agg(mean=("score", "mean"), sem=("score", "sem"),
                                  lam=("lam", "first")).sort_index()
    ax.errorbar(g.index, g["mean"], yerr=g["sem"], fmt="-o", color=color,
                label=label, capsize=4)
    if annotate_lambda and stack is None:
        for t, m, lam in zip(g.index, g["mean"], g["lam"]):
            if pd.notna(lam):
                ax.text(t, m + 0.35, rf"$\lambda$={lam:.2f}", color=color, fontsize=9, ha="center")
    if stack is not None:
        for t, lam in zip(g.index, g["lam"]):
            if pd.notna(lam):
                stack.setdefault(t, []).append((color, lam))
    return g


def plot_probe_capability_combined():
    """probe_capability_target_vs_achieved_combined.png (Llama brick + stapler)."""
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    brick = div_probe[div_probe.source_figure == "figure_9_capability_brick_target_vs_achieved"]
    stap = prod_probe[prod_probe.source_figure ==
                      "figure_9_capability_stapler_product_innovation_target_vs_achieved"]
    for pl, ax, sub, title, label, color in [
        ("(A)", axes[0], brick, "Divergent Creativity (brick)", "Brick", C_NAVY),
        ("(B)", axes[1], stap, "Product Innovation (stapler)", "Stapler", C_TEAL),
    ]:
        ax.plot([2, 10], [2, 10], "--", color="grey", lw=1.3, label="Perfect control")
        _capability_curve(ax, sub, color, label)
        ax.set_xlim(2, 10); ax.set_ylim(2, 10)
        ax.set_xlabel("Target creativity score"); ax.set_ylabel("Achieved creativity score")
        ax.set_title(title); ax.legend(loc="lower right", fontsize=8)
        panel_label(ax, pl)
    fig.suptitle("Capability Control: Target vs Achieved Creativity", fontsize=13)
    plt.tight_layout()
    _save("probe_capability_target_vs_achieved_combined.png")


def plot_capability_brick(fig_key, out_relpath):
    """Single-object brick capability (figure9_Gpt5 = fig9 Llama, figd_brick = fig15 Qwen)."""
    fig, ax = plt.subplots(figsize=(7, 5))
    sub = div_probe[div_probe.source_figure == fig_key]
    ax.plot([2, 10], [2, 10], "--", color="grey", lw=1.3, label="Perfect control")
    _capability_curve(ax, sub, C_BLUE, "Brick")
    ax.set_xlim(2, 10); ax.set_ylim(2, 10)
    ax.set_xlabel("Target creativity score"); ax.set_ylabel("Achieved creativity score")
    ax.set_title("Capability Control: Target vs Achieved Creativity")
    ax.legend(loc="lower right", fontsize=9)
    plt.tight_layout()
    _save(out_relpath)


def plot_capability_four_objects(fig_key, out_relpath, with_errorbars=True):
    """Four-object capability (figd / figd_appendix = Qwen fig16, figure10_GPT5 = Llama fig10)."""
    obj_style = {"brick": C_BLUE, "stapler": C_GREEN, "paperclip": C_ORANGE, "bowl": "#FFC400"}
    fig, ax = plt.subplots(figsize=(8, 5.5))
    ax.plot([2, 10], [2, 10], "--", color="grey", lw=1.3, label="Perfect control")
    stack = {}
    sub_all = div_probe[div_probe.source_figure == fig_key]
    for obj, color in obj_style.items():
        sub = sub_all[sub_all.object == obj]
        if sub.empty:
            continue
        _capability_curve(ax, sub, color, obj.title(), stack=stack)
    # vertically stacked lambda labels per target column
    for t, items in stack.items():
        for i, (color, lam) in enumerate(items):
            ax.text(t - 0.05, 9.4 - 0.42 * i, rf"$\lambda$={lam:.2f}",
                    color=color, fontsize=8, ha="right", va="top")
    ax.set_xlim(2, 10); ax.set_ylim(2, 10)
    ax.set_xlabel("Target creativity score"); ax.set_ylabel("Achieved creativity score")
    ax.set_title("Capability Control: Target vs Achieved Creativity")
    ax.legend(loc="lower right", fontsize=8)
    plt.tight_layout()
    _save(out_relpath)


def plot_dose_response(lot_fig, ult_fig, out_relpath, panel_labels=False):
    """Required lambda vs target switching point (figure11 = Llama, dose_response_lambda = Qwen)."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.6))
    for pl, ax, df_probe, fig_key, title in [
        ("(a)", axes[0], lot_probe, lot_fig, r"Dose-Response: $\lambda$ Required for Target Behavior"),
        ("(b)", axes[1], ult_probe, ult_fig, r"Ultimatum: Dose-Response: $\lambda$ Required for Target Behavior"),
    ]:
        sub = df_probe[df_probe.source_figure == fig_key].copy()
        sub["target"] = pd.to_numeric(sub["target_switching_point_tokens"], errors="coerce")
        sub["lam"] = pd.to_numeric(sub["lambda_required"], errors="coerce")
        sub = sub.sort_values("target")
        ax.plot(sub["target"], sub["lam"], "-o", color=C_NAVY)
        ax.set_xlabel("Target Switching Point (tokens)")
        ax.set_ylabel(r"Required $\lambda$ (steering strength)")
        ax.set_title(title)
        panel_label(ax, pl)
    plt.tight_layout()
    _save(out_relpath)


def plot_activation_tracking(lot_fig, ult_fig, out_relpath):
    """Probe scores track target (figure12 = Llama, figc = Qwen)."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 4.8))
    lottery_style = {"all": (C_NAVY, "o", "-", "Mean probe scores"),
                     "risky": (C_ORANGE, "s", "--", "Risky choices"),
                     "safe": (C_TEAL, "^", "--", "Safe choices")}
    ultimatum_style = {"all": (C_NAVY, "o", "-", "Mean probe scores"),
                       "accept": (C_ORANGE, "s", "--", "Accept choices"),
                       "reject": (C_TEAL, "^", "--", "Reject choices")}
    for pl, ax, df_probe, fig_key, title, style in [
        ("(a)", axes[0], lot_probe, lot_fig, "Lottery: Probe Scores Track Target Behavior", lottery_style),
        ("(b)", axes[1], ult_probe, ult_fig, "Ultimatum: Probe Scores Track Target Behavior", ultimatum_style),
    ]:
        sub = df_probe[df_probe.source_figure == fig_key].copy()
        sub["target"] = pd.to_numeric(sub["target_switching_point_tokens"], errors="coerce")
        sub["mean"] = pd.to_numeric(sub["mean_probe_activation"], errors="coerce")
        for subset in [k for k in style if k in sub.choice_subset.unique()]:
            srows = sub[sub.choice_subset == subset].sort_values("target")
            color, marker, ls, label = style[subset]
            ax.plot(srows["target"], srows["mean"], color=color, marker=marker,
                    linestyle=ls, label=label)
        ax.set_xlabel("Target switching point (tokens)")
        ax.set_ylabel("Probe activation score")
        ax.set_title(title)
        ax.legend(loc="upper left", ncol=2 if ax is axes[0] else 1, fontsize=8)
        panel_label(ax, pl)
    plt.tight_layout()
    _save(out_relpath)


def plot_crossgen_bar(fig_key, model_name, out_relpath):
    """In-distribution vs cross-object accuracy bars (figure13a = Llama, crossgen_bar = Qwen)."""
    sub = div_probe[div_probe.source_figure == fig_key].copy()
    sub["mean"] = pd.to_numeric(sub["mean_score"], errors="coerce")
    sub["std"] = pd.to_numeric(sub["std_score"], errors="coerce")
    objs = sorted(sub.test_object.dropna().unique())
    x = np.arange(len(objs)); width = 0.36
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for i, (split, color) in enumerate([("in_distribution", C_BLUE), ("cross_object", C_ORANGE)]):
        means = [sub[(sub.test_object == o) & (sub.split_type == split)]["mean"].mean() for o in objs]
        stds = [sub[(sub.test_object == o) & (sub.split_type == split)]["std"].mean() for o in objs]
        ax.bar(x + (i - 0.5) * width, means, width, yerr=stds, capsize=4,
               label=split, color=color, edgecolor="black", linewidth=0.5)
    ax.set_xticks(x); ax.set_xticklabels(objs)
    ax.set_ylim(0.70, 1.0)
    ax.set_xlabel("Test object"); ax.set_ylabel("Accuracy")
    ax.set_title("Probe Performance: In-distribution vs Cross-object")
    ax.legend(title="Evaluation split", loc="upper right", fontsize=8)
    plt.tight_layout()
    _save(out_relpath)


def plot_crossgen_profile(fig_key, out_relpath):
    """Cross-object generalization profile lines (figure13b = Llama, crossgen_profile = Qwen)."""
    sub = div_probe[div_probe.source_figure == fig_key].copy()
    sub["mean"] = pd.to_numeric(sub["mean_score"], errors="coerce")
    objs = sorted(sub.test_object.dropna().unique())
    obj_color = {"bowl": C_BLUE, "brick": C_ORANGE, "paperclip": C_GREEN, "stapler": C_RED}
    splits = ["in_distribution", "cross_object"]
    fig, ax = plt.subplots(figsize=(7.5, 5))
    for o in objs:
        ys = [sub[(sub.test_object == o) & (sub.split_type == s)]["mean"].mean() for s in splits]
        ax.plot(splits, ys, "-o", color=obj_color.get(o, "grey"), label=o)
    ax.set_ylim(0.70, 1.0)
    ax.set_xlabel("Evaluation split"); ax.set_ylabel("Accuracy")
    ax.set_title("Cross-object Generalization Profile by Object")
    ax.legend(title="Test object", loc="upper right", fontsize=8)
    plt.tight_layout()
    _save(out_relpath)


# ============================================================================
# GROUP 2b — Multi-judge panel (reads the mj_<judge>_* columns synced into
# probe_results_combined.csv). The panel's gpt-5 is the length-controlled
# rescore (same protocol as the other four judges), NOT the original GPT-5
# used in the single-judge capability figures above.
# ============================================================================
MJ_JUDGES = ["gpt-5", "claude-sonnet-4-6", "gemini-2.5-pro", "kimi-k2.6", "deepseek-v4-pro"]
MJ_LABELS = {"gpt-5": "GPT-5", "claude-sonnet-4-6": "Claude Sonnet 4.6",
             "gemini-2.5-pro": "Gemini 2.5 Pro", "kimi-k2.6": "Kimi K2.6",
             "deepseek-v4-pro": "DeepSeek V4 Pro"}
MJ_COLORS = {"gpt-5": C_NAVY, "claude-sonnet-4-6": C_ORANGE, "gemini-2.5-pro": C_TEAL,
             "kimi-k2.6": C_PURPLE, "deepseek-v4-pro": C_RED}
_CAP_LLAMA = ["figure_9_capability_brick_target_vs_achieved",
              "figure_9_capability_stapler_product_innovation_target_vs_achieved",
              "figure_10_capability_four_objects_target_vs_achieved"]
_CAP_QWEN = ["figure_17_capability_brick_target_vs_achieved_qwen",
             "figure_18_capability_four_objects_target_vs_achieved_qwen"]


def _mj_capability_frame():
    """Tidy capability frame with per-judge creativity scores.
    Returns None if the mj_* columns are absent (panel not synced into the CSV)."""
    need = [f"mj_{j}_creativity_score" for j in MJ_JUDGES]
    if not all(c in _probe.columns for c in need):
        return None
    df = _probe[(_probe.source_figure.isin(_CAP_LLAMA + _CAP_QWEN)) &
                (_probe.data_section == "data")].copy()
    if df.empty:
        return None
    df["target"] = pd.to_numeric(df["target_creativity_score"], errors="coerce")
    for j in MJ_JUDGES:
        df[f"cs_{j}"] = pd.to_numeric(df[f"mj_{j}_creativity_score"], errors="coerce")
    df["is_qwen"] = df.source_figure.isin(_CAP_QWEN)
    return df


def _pearson(x, y):
    x = np.asarray(x, float); y = np.asarray(y, float)
    m = ~(np.isnan(x) | np.isnan(y))
    if m.sum() < 3 or x[m].std() == 0 or y[m].std() == 0:
        return np.nan
    return float(np.corrcoef(x[m], y[m])[0, 1])


def _spearman(x, y):
    x = pd.Series(np.asarray(x, float)); y = pd.Series(np.asarray(y, float))
    m = x.notna() & y.notna()
    if m.sum() < 3:
        return np.nan
    return _pearson(x[m].rank().values, y[m].rank().values)


def plot_mj_target_vs_achieved(out_relpath):
    """All-judge achieved-vs-target creativity (Llama | Qwen), one line per judge."""
    df = _mj_capability_frame()
    if df is None:
        print("[regen] skipping multi-judge target-vs-achieved (mj_* columns not in CSV)"); return
    fig, axes = plt.subplots(1, 2, figsize=(13, 5.2))
    for pl, ax, mask, title in [("(a)", axes[0], ~df.is_qwen, "Llama-3.3-70B"),
                                ("(b)", axes[1], df.is_qwen, "Qwen-2-7B")]:
        sub = df[mask]
        ax.plot([2, 10], [2, 10], "--", color="grey", lw=1.2, label="Perfect control")
        for j in MJ_JUDGES:
            g = sub.groupby("target")[f"cs_{j}"].agg(["mean", "sem"]).sort_index()
            ax.errorbar(g.index, g["mean"], yerr=g["sem"], fmt="-o",
                        color=MJ_COLORS[j], label=MJ_LABELS[j], capsize=3, markersize=4)
        ax.set_xlim(2, 10); ax.set_ylim(2, 10)
        ax.set_xlabel("Target creativity score"); ax.set_ylabel("Achieved creativity score")
        ax.set_title(title); panel_label(ax, pl)
        if ax is axes[0]:
            ax.legend(loc="lower right", fontsize=7)
    fig.suptitle("Multi-judge controllability: achieved vs target creativity", fontsize=13)
    plt.tight_layout()
    _save(out_relpath)


def plot_mj_agreement_heatmap(out_relpath):
    """Pairwise Spearman agreement between the 5 judges (all capability responses)."""
    df = _mj_capability_frame()
    if df is None:
        print("[regen] skipping multi-judge agreement heatmap (mj_* columns not in CSV)"); return
    n = len(MJ_JUDGES)
    M = np.ones((n, n))
    for i in range(n):
        for k in range(n):
            if i != k:
                M[i, k] = _spearman(df[f"cs_{MJ_JUDGES[i]}"], df[f"cs_{MJ_JUDGES[k]}"])
    fig, ax = plt.subplots(figsize=(6.8, 5.8))
    im = ax.imshow(M, cmap="viridis", vmin=0.6, vmax=1.0)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels([MJ_LABELS[j] for j in MJ_JUDGES], rotation=35, ha="right", fontsize=8)
    ax.set_yticklabels([MJ_LABELS[j] for j in MJ_JUDGES], fontsize=8)
    for i in range(n):
        for k in range(n):
            ax.text(k, i, f"{M[i, k]:.2f}", ha="center", va="center",
                    color="white" if M[i, k] < 0.85 else "black", fontsize=8)
    off = M[~np.eye(n, dtype=bool)]
    ax.set_title(f"Inter-judge agreement (Spearman)\nmean pairwise = {off.mean():.3f}", fontsize=11)
    fig.colorbar(im, ax=ax, shrink=0.85).set_label("Spearman correlation")
    plt.tight_layout()
    _save(out_relpath)


# ============================================================================
# GROUP 3 — SAE feature-activation plots
# ============================================================================
def plot_feature_rank_grid(out_relpath):
    """Top-10 features by mean rank for lottery & ultimatum (3 conditions x 2 games).

    Source: feature_activations_combined.csv per-agent rows (rank per agent).
    """
    rows = [("baseline", "Baseline"), ("prompting", "Prompting"), ("steering", "Steering")]
    games = [("lottery", "Lottery Game"), ("ultimatum", "Ultimatum Game")]
    # lottery has 'slightly_prompting' rather than 'prompting'
    cond_alias = {("lottery", "prompting"): "slightly_prompting"}

    fig, axes = plt.subplots(3, 2, figsize=(14, 13))
    for r, (cond, cond_label) in enumerate(rows):
        for c, (game, game_label) in enumerate(games):
            ax = axes[r, c]
            real_cond = cond_alias.get((game, cond), cond)
            sub = feat[(feat["source"] == game) & (feat["condition"] == real_cond)]
            # mean / min / max rank per feature across agents (+offers)
            stats = sub.groupby("feature_label")["rank"].agg(["mean", "min", "max", "count"])
            stats = stats.sort_values("mean").head(10)[::-1]
            ys = np.arange(len(stats))
            ax.hlines(ys, stats["min"], stats["max"], color="#888", lw=1.5)
            ax.scatter(stats["mean"], ys, color=C_RED, s=40, zorder=3, label="Mean Rank")
            ax.scatter(stats["min"], ys, color="#888", s=16, marker="|", zorder=3)
            ax.scatter(stats["max"], ys, color="#888", s=16, marker="|", zorder=3,
                       label="Min/Max Range")
            ax.set_yticks(ys)
            ax.set_yticklabels([_wrap(n, 40) for n in stats.index], fontsize=7)
            ax.set_xlim(0.5, 10.5); ax.set_xticks(range(1, 11))
            ax.set_xlabel("Rank")
            ax.set_title(f"{game_label} — {cond_label}", fontsize=10)
            if r == 0 and c == 1:
                ax.legend(loc="lower right", fontsize=8)
    fig.suptitle("Top 10 Features by Mean Rank — Lottery and Ultimatum Games",
                 fontsize=14, y=1.005)
    plt.tight_layout()
    _save(out_relpath)


def plot_feature_top5_bars(out_relpath, two_tone=True):
    """Top-5 activated features by activation strength for creativity tasks.

    Source: feature_activations_combined.csv source=='product_innovation_folder'.
    Rows: 2 tasks (brick=divergent, stapler=product) x 4 conditions.
    Bars are coloured by TASK (row): divergent creativity vs product innovation
    use the two distinct TASK_COLORS so the two rows are visually different.
    """
    tasks = [("detailed_ways_to_use_a_brick", "Divergent Creativity Tasks"),
             ("improve_the_stapler_with_many_specific_enhancements",
              "Product Innovation Tasks")]
    conds = [("baseline", "Baseline"), ("high_temperature", "High Temperature"),
             ("prompting", "Prompting"), ("high_steering", "Steering")]
    sub_all = feat[feat["source"] == "product_innovation_folder"]

    fig, axes = plt.subplots(2, 4, figsize=(20, 9))
    for ti, (task, task_label) in enumerate(tasks):
        for ci, (cond, cond_label) in enumerate(conds):
            ax = axes[ti, ci]
            sub = sub_all[(sub_all.task == task) & (sub_all.condition == cond)]
            sub = sub.sort_values("activation", ascending=False).head(5)[::-1]
            # row 1 (divergent creativity) and row 2 (product innovation) differ
            color = TASK_COLORS[task] if two_tone else C_BLUE
            y = np.arange(len(sub))
            ax.barh(y, sub["activation"], color=color, edgecolor="none")
            for yi, v in zip(y, sub["activation"]):
                ax.text(v, yi, f" {v:.0f}", va="center", fontsize=8)
            ax.set_yticks(y)
            ax.set_yticklabels([_wrap(n, 30) for n in sub["feature_label"]], fontsize=7)
            ax.set_xlabel("Activation Strength")
            ax.set_title(f"{task_label}\nCondition: {cond_label}", fontsize=9)
    fig.suptitle("Top 5 Activated Features by Task and Condition", fontsize=14, y=1.01)
    plt.tight_layout()
    _save(out_relpath)


# ============================================================================
# Machine-readable record of what could NOT be exactly reproduced.
# ============================================================================
MISSING_DATA = {
    "schematics_not_data_driven": [
        "figures/sae_schematic.png",
        "figures/probe_schematic.png",
    ],
    "original_judge_capability_not_in_cleaned": [
        # cleaned/ holds only GPT-5-judged capability scores; these plain (original
        # judge) variants used a different judge + lambda calibration. Rendered from
        # GPT-5 data as a proxy.
        "figures_llama/figure9.png",
        "figures_llama/figure10.png",
    ],
}


def main():
    # ---- Group 1 (behavioural games + capability bars; need OPTIONAL CSVs) ----
    if not _behavioral.empty:
        plot_preference()
        plot_safe_vs_risky()
        plot_ultimatum_game()
        plot_5_conditions()
    else:
        print("[regen] skipping behavioural-game figures (behavioral_games_combined.csv missing)")
    if not _creativity.empty:
        plot_capability_bar()
    else:
        print("[regen] skipping capability-bar figure (creativity_evals_combined.csv missing)")

    # ---- Group 2: probe psychometric ----
    plot_probe_psychometric("figure_7_psychometric_curves_llama",
                            "figure_7_psychometric_curves_llama",
                            "Llama-3.3-70B", "figures_llama/figure7.png",
                            ult_cmap="plasma", lot_xmax=245, ult_xmax=102)
    plot_probe_psychometric("figure_14_psychometric_curves_qwen",
                            "figure_14_psychometric_curves_qwen",
                            "Qwen-2-7B", "figures/figure5.png",
                            ult_cmap="plasma", lot_xmax=125, ult_xmax=95)

    # ---- Group 2: capability target vs achieved ----
    plot_probe_capability_combined()
    # Brick single-object
    plot_capability_brick("figure_9_capability_brick_target_vs_achieved",
                          "figures_llama/figure9_Gpt5.png")           # Llama, GPT-5
    plot_capability_brick("figure_9_capability_brick_target_vs_achieved",
                          "figures_llama/figure9.png")                # proxy (orig-judge missing)
    plot_capability_brick("figure_17_capability_brick_target_vs_achieved_qwen",
                          "figures/figd_brick.png")                   # Qwen
    # Four-object
    plot_capability_four_objects("figure_10_capability_four_objects_target_vs_achieved",
                                 "figures_llama/figure10_GPT5.png")   # Llama, GPT-5
    plot_capability_four_objects("figure_10_capability_four_objects_target_vs_achieved",
                                 "figures_llama/figure10.png")        # proxy (orig-judge missing)
    plot_capability_four_objects("figure_18_capability_four_objects_target_vs_achieved_qwen",
                                 "figures/figd.png")                  # Qwen
    plot_capability_four_objects("figure_18_capability_four_objects_target_vs_achieved_qwen",
                                 "figures/figd_appendix.png")         # Qwen (appendix copy)

    # ---- Group 2: dose response ----
    plot_dose_response("figure_11_dose_response_lottery_ultimatum_llama",
                       "figure_11_dose_response_lottery_ultimatum_llama",
                       "figures_llama/figure11.png")
    plot_dose_response("figure_15_dose_response_lottery_ultimatum_qwen",
                       "figure_15_dose_response_lottery_ultimatum_qwen",
                       "figures/dose_response_lambda.png", panel_labels=True)

    # ---- Group 2: probe activation tracking ----
    plot_activation_tracking("figure_12_probe_scores_track_target_lottery_ultimatum_llama",
                             "figure_12_probe_scores_track_target_lottery_ultimatum_llama",
                             "figures_llama/figure12.png")
    plot_activation_tracking("figure_16_probe_scores_track_target_qwen",
                             "figure_16_probe_scores_track_target_qwen",
                             "figures/figc.png")

    # ---- Group 2: cross-object generalization ----
    plot_crossgen_bar("figure_13_cross_object_generalization_llama", "Llama",
                      "figures_llama/figure13a.png")
    plot_crossgen_bar("figure_13_cross_object_generalization_llama", "Llama",
                      "figures_llama/figure13a_GPT5.png")
    plot_crossgen_profile("figure_13_cross_object_generalization_llama",
                          "figures_llama/figure13b.png")
    plot_crossgen_profile("figure_13_cross_object_generalization_llama",
                          "figures_llama/figure13b_GPT5.png")
    plot_crossgen_bar("figure_19_cross_object_generalization_qwen", "Qwen",
                      "figures/crossgen_bar.png")
    plot_crossgen_profile("figure_19_cross_object_generalization_qwen",
                          "figures/crossgen_profile.png")

    # ---- Group 2b: multi-judge panel (needs mj_* columns in probe_results_combined.csv) ----
    plot_mj_target_vs_achieved("figures/multi_judge_target_vs_achieved.png")
    plot_mj_agreement_heatmap("figures/multi_judge_agreement_heatmap.png")

    # ---- Group 3: feature activations (need feature_activations_combined.csv) ----
    if not feat.empty:
        plot_feature_rank_grid("preference_activations.png")
        plot_feature_rank_grid("combined_lottery_ultimatum_grid.png")
        plot_feature_top5_bars("activation_grid_top5.png", two_tone=True)
        plot_feature_top5_bars("top5_task_condition.png", two_tone=True)
        plot_feature_top5_bars("capability_activations.png", two_tone=True)
    else:
        print("[regen] skipping SAE feature-activation figures (feature_activations_combined.csv missing)")

    print("\n--- DATA MISSING / NOT EXACTLY REPRODUCIBLE ---")
    for reason, files in MISSING_DATA.items():
        print(f"{reason}:")
        for f in files:
            print(f"    {f}")
    print(f"\nAll regenerated PNGs written under {os.path.relpath(OUT, HERE)}/")


if __name__ == "__main__":
    main()
