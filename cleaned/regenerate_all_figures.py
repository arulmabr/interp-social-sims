"""
regenerate_all_figures.py
=========================

Regenerate every *data-driven* PNG that appears in the ``mech_interp/`` folder
of the paper, using **only** the consolidated CSVs in this ``cleaned/`` folder.
This single script harmonises three earlier ad-hoc renderers
(``regenerate_all_figures.py``, ``generate_multi_judge_plots.py``,
``generate_game_plots.py``) into one set of plotting functions that share a
single style block, a single condition palette, and a single output tree.

All plots use the COLM-2025 paper look ("To Backtrack or Not to Backtrack"):
sans-serif plot fonts, bold titles, a full thin box (all four spines) with
**no grid**, bold "(A)/(B)" panel letters, filled markers on data points, a
plasma-family gradient for ordered series, and **600-dpi** export.

--------------------------------------------------------------------------------
INPUT DATA — only these FOUR consolidated CSVs are required (all in this folder)
--------------------------------------------------------------------------------
behavioral_games_combined.csv     Lottery + Ultimatum game choices.
                                  Split column: `game` in {lottery, ultimatum}.
                                  Two generations of data:
                                    - Goodfire baseline + SAE steering + prompting
                                      conditions (the original psychometric runs)
                                    - Revised-Prompting vLLM run with
                                      treatment_condition in {baseline_rp, cot,
                                      fewshot, persona, fewshot_cot_dose000..100}.
                                  The `_rp` suffix on baseline keeps the two
                                  baselines from being silently averaged.
probe_results_combined.csv        All probe-steering results (psychometric, dose-
                                  response, activation-tracking, capability target-
                                  vs-achieved, cross-object generalization).
                                  Split column: `probe_group` in {lottery, ultimatum,
                                  creativity}; figures keyed by `source_figure`.
creativity_evals_combined.csv     Creativity evals for brick + stapler.
                                  Two generations of data:
                                    - Original 320 GPT-5-only rows
                                      (eval_prompt_version='torrance_four_dimension_v1')
                                    - 3,400 multi-judge re-scores from 5 judges
                                      (eval_prompt_version=
                                       'torrance_four_dimension_length_controlled_v1'),
                                      spanning open_sae_creativity (same responses,
                                      different judges) + revised_prompting_brick +
                                      revised_prompting_stapler.
feature_activations_combined.csv  SAE feature activations (lottery/ultimatum per-
                                  agent ranks + creativity top-k activation strengths).

(These four CSVs replace the previous nine per-experiment CSVs; the script
derives all logical tables from them with simple column filters — see the
"Load data once" block.)

--------------------------------------------------------------------------------
OUTPUT
--------------------------------------------------------------------------------
Written to ``cleaned/regenerated_figures/`` mirroring the mech_interp layout:
    regenerated_figures/<name>.png                    -- top-level figures
    regenerated_figures/figures/<name>.png            -- Qwen appendix figures
    regenerated_figures/figures_llama/<name>.png      -- Llama probe figures
    regenerated_figures/figures_revised_prompting/    -- Few-shot / CoT plots
    regenerated_figures/figures_multijudge/           -- 5-judge creativity plots

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
import matplotlib.pyplot as plt
import matplotlib.cm as cm
import matplotlib.colors as mcolors

# ----------------------------------------------------------------------------
# Paths & global style
# ----------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "regenerated_figures")
for sub in ("", "figures", "figures_llama",
            "figures_revised_prompting", "figures_multijudge"):
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
    return pd.read_csv(os.path.join(HERE, name), low_memory=False)

# ---------------------------------------------------------------------------
# Only FOUR consolidated CSVs are required (see header). The nine logical
# tables the plotting code expects are derived from them by simple filters.
# ---------------------------------------------------------------------------
_behavioral = _read("behavioral_games_combined.csv")   # safe + ultimatum (col: game)
_probe = _read("probe_results_combined.csv")           # all probe rows (col: probe_group)
_creativity = _read("creativity_evals_combined.csv")   # all creativity evals (col: task)
feat = _read("feature_activations_combined.csv")        # SAE feature activations

# ---------------------------------------------------------------------------
# The behavioural CSV now holds *two* generations of data: the original
# Goodfire baseline + SAE-steering psychometric runs AND the Revised-Prompting
# vLLM runs (baseline_rp / cot / fewshot / persona / fewshot_cot_dose*).
# We split them on `treatment_condition` so GROUP 1 functions (the original
# psychometric plots) only see Goodfire rows, while GROUP 4 (Revised-Prompting
# plots, added below) loads the rest. This is the same split that the user
# requested: the cleaned/ CSVs hold all generations of data, but each plotting
# function reads only the slice it was designed for.
# ---------------------------------------------------------------------------
ORIGINAL_LOTTERY_CONDS = {"baseline", "barely_prompting", "slightly_prompting",
                          "lite_steering", "steering"}
ORIGINAL_ULT_CONDS = {"baseline", "prompting", "steering"}
REVISED_CONDS = {"baseline_rp", "cot", "fewshot", "persona",
                 "fewshot_cot_dose000", "fewshot_cot_dose025",
                 "fewshot_cot_dose050", "fewshot_cot_dose075",
                 "fewshot_cot_dose100"}

# Behavioural games (split by game), keeping only the ORIGINAL generation of
# rows for the GROUP 1 plots — this preserves the exact figures the paper
# shipped, regardless of what new data has since been appended to the CSV.
safe = _behavioral[(_behavioral["game"] == "lottery")
                   & _behavioral["treatment_condition"].isin(ORIGINAL_LOTTERY_CONDS)].copy()
ult = _behavioral[(_behavioral["game"] == "ultimatum")
                  & _behavioral["treatment_condition"].isin(ORIGINAL_ULT_CONDS)].copy()

# ---------------------------------------------------------------------------
# Creativity evals: the CSV now also holds the 5-judge multi-judge rows. The
# GROUP 1 capability bars (capability.png) were designed for the single-judge
# GPT-5 eval — feeding them the 5-judge mix would change every bar height.
# We therefore filter to the original eval-prompt version here; GROUP 5
# (multi-judge plots) loads the multi-judge rows directly.
# ---------------------------------------------------------------------------
ORIGINAL_EVAL_PROMPT = "torrance_four_dimension_v1"
_creativity_single = _creativity[
    _creativity["eval_prompt_version"] == ORIGINAL_EVAL_PROMPT].copy()
div_comb = _creativity_single[
    _creativity_single["task"] == "detailed_ways_to_use_a_brick"].copy()
prod_comb = _creativity_single[
    _creativity_single["task"] == "improve_the_stapler_with_many_specific_enhancements"].copy()

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
# GROUP 4 — Revised-Prompting behavioural plots  (Few-shot / CoT / Persona)
# ----------------------------------------------------------------------------
# Source slice: behavioral_games_combined.csv rows where
#   treatment_condition in REVISED_CONDS  (baseline_rp + cot/fewshot/persona +
#   fewshot_cot_dose000..100).
# These rows are the result of a *separate* vLLM-local generation run (see
# Revised Prompting/runs_fp16/runs/{safe_risky_full,ultimatum_full}/behavior_units.csv)
# and are appended to the consolidated CSV by ``integrate_new_data.py``.
# All plots use the same style + palette as Group 1, so the per-condition
# bar/line colours are consistent with the figures in the rest of the paper.
# ============================================================================
RP_GAMES = {
    "lottery":   {"answer_col": "answer.safe_risky_choice",
                  "pos_label":  "Risky Option",
                  "x_label":    "Risky reward (tokens)",
                  "y_label":    "% of agents choosing Risky Option",
                  "title_main": "Lottery"},
    "ultimatum": {"answer_col": "answer.ultimatum_response",
                  "pos_label":  "Accept",
                  "x_label":    "Offer amount (tokens)",
                  "y_label":    "% of agents accepting offer",
                  "title_main": "Ultimatum Game"},
}
RP_DOSES = [0.00, 0.25, 0.50, 0.75, 1.00]
RP_DOSE_CONDS = [f"fewshot_cot_dose{int(d*100):03d}" for d in RP_DOSES]
# Canonical RP palette — keeps colours **semantically aligned** with the rest
# of the paper:
#   * baseline_rp stays NAVY so it reads as "control" everywhere baseline does
#     (preference.png, 5_conditions.png, capability.png, Group-5 multi-judge).
#   * persona reuses the canonical "prompting" ORANGE because persona is the
#     same KIND of intervention (prompt-engineering) as the original prompting
#     condition; a reader scanning two figures sees a coherent identity.
#   * cot / fewshot / fewshot_cot are ALSO prompting-family interventions, so
#     they live in the WARM (orange→red) half of the palette as well — never
#     teal (which is reserved for SAE steering) or purple (probe steering).
#     Within Group 4 the four warm hues are picked far enough apart in
#     lightness to stay distinguishable on a single 5-line plot.
#   * the dose sweep uses a sequential YlOrRd gradient (yellow→orange→red) so
#     the highest dose lands near the same red as fewshot_cot_dose100, giving
#     a coherent "intensity = darker red" story across the psychometric,
#     dose-response and delta-vs-baseline panels.
RP_COND_COLORS = {
    "baseline_rp":         C_NAVY,      # #27286B  navy        — matches 'baseline' everywhere
    "persona":             C_ORANGE,    # #E8804B  orange      — matches 'prompting' everywhere
    "cot":                 "#C0442D",   #          burnt sienna — distinct warm (red-orange)
    "fewshot":             "#D4A017",   #          goldenrod   — distinct warm (yellow-orange)
    "fewshot_cot_dose100": "#970026",   #          deep red    — strongest prompting intervention
                                        #                       (= YlOrRd(0.95), so this exact bar
                                        #                       in the 5-line psychometric matches
                                        #                       the 100%-dose colour in the dose-
                                        #                       response & Δ-vs-baseline panels)
}
# Sequential colormap for the 5-step Few-shot+CoT dose sweep. YlOrRd stays in
# the warm half of colour space (yellow→orange→red), so it lines up with the
# "all-prompting=warm" semantic above and the 100% dose lands near the same
# deep red that RP_COND_COLORS["fewshot_cot_dose100"] uses.
RP_DOSE_CMAP = "YlOrRd"
RP_DOSE_LO, RP_DOSE_HI = 0.30, 0.95   # skip the palest yellow; end at a true red
RP_COND_LABELS = {
    "baseline_rp":         "Baseline",
    "persona":             "Persona",
    "cot":                 "CoT",
    "fewshot":             "Few-shot",
    "fewshot_cot_dose100": "Few-shot + CoT",
}
RP_PSY_CONDS = ["baseline_rp", "persona", "cot", "fewshot", "fewshot_cot_dose100"]
RP_DELTA_CONDS = ["persona", "cot", "fewshot",
                  "fewshot_cot_dose000", "fewshot_cot_dose025",
                  "fewshot_cot_dose050", "fewshot_cot_dose075",
                  "fewshot_cot_dose100"]


def _rp_curve(df, game, cond):
    """Return a sorted Series indexed by reward of % positive choices."""
    spec = RP_GAMES[game]
    sub = df[(df["game"] == game)
             & (df["treatment_condition"] == cond)].copy()
    if sub.empty:
        return None, 0
    sub["pos"] = (sub[spec["answer_col"]] == spec["pos_label"]).astype(int)
    grp = sub.groupby("offer_amount")["pos"]
    return grp.mean().sort_index(), int(grp.count().iloc[0])


def _sem_binom(p, n):
    n = max(int(n), 1)
    p = float(np.clip(p, 0.0, 1.0))
    return float(np.sqrt(p * (1.0 - p) / n))


def _smart_ylim(ax, data_lo, data_hi):
    """Asymmetric y-limits: tight on the empty side, always include 0."""
    plot_lo = min(0.0, float(data_lo))
    plot_hi = max(0.0, float(data_hi))
    span = max(plot_hi - plot_lo, 1e-6)
    bot_pad = 0.05 * span if data_lo >= 0 else 0.10 * span
    top_pad = 0.05 * span if data_hi <= 0 else 0.10 * span
    ax.set_ylim(plot_lo - bot_pad, plot_hi + top_pad)


def plot_rp_psychometric(game, out_relpath):
    """5-line psychometric curve for the Revised Prompting conditions."""
    spec = RP_GAMES[game]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    for cond in RP_PSY_CONDS:
        curve, n = _rp_curve(_behavioral, game, cond)
        if curve is None:
            continue
        ys = curve.values * 100.0
        yerr = np.array([_sem_binom(p, n) for p in curve.values]) * 100.0
        ax.errorbar(curve.index, ys, yerr=yerr,
                    color=RP_COND_COLORS[cond], label=RP_COND_LABELS[cond],
                    marker="o", markersize=4, lw=1.5, capsize=2)
    ax.axhline(50, color="gray", ls=":", lw=0.7, alpha=0.6)
    ax.set_xlabel(spec["x_label"])
    ax.set_ylabel(spec["y_label"])
    ax.set_ylim(-2, 102)
    ax.set_title(f"Revised Prompting — {spec['title_main']}\n"
                 f"Psychometric curves by prompting condition")
    ax.legend(loc="best", fontsize=8)
    plt.tight_layout()
    _save(out_relpath)


def plot_rp_dose_response(game, out_relpath):
    """5-level Few-shot + CoT dose sweep, warm sequential gradient.

    The gradient stays in the warm half of colour space so the sweep visually
    reads as "all prompting-family"; the highest dose lands near the same deep
    red that ``RP_COND_COLORS['fewshot_cot_dose100']`` uses elsewhere.
    """
    spec = RP_GAMES[game]
    fig, ax = plt.subplots(figsize=(9, 5.2))
    cmap = plt.get_cmap(RP_DOSE_CMAP)
    span = RP_DOSE_HI - RP_DOSE_LO
    for d, cond in zip(RP_DOSES, RP_DOSE_CONDS):
        curve, n = _rp_curve(_behavioral, game, cond)
        if curve is None:
            continue
        ys = curve.values * 100.0
        yerr = np.array([_sem_binom(p, n) for p in curve.values]) * 100.0
        color = cmap(RP_DOSE_LO + span * d)
        ax.errorbar(curve.index, ys, yerr=yerr, color=color,
                    label=f"Few-shot+CoT dose={int(d*100)}%",
                    marker="o", markersize=4, lw=1.5, capsize=2)
    ax.axhline(50, color="gray", ls=":", lw=0.7, alpha=0.6)
    ax.set_xlabel(spec["x_label"])
    ax.set_ylabel(spec["y_label"])
    ax.set_ylim(-2, 102)
    ax.set_title(f"Revised Prompting — {spec['title_main']}\n"
                 f"Dose-response sweep on Few-shot + CoT")
    ax.legend(loc="best", fontsize=8, ncol=2)
    plt.tight_layout()
    _save(out_relpath)


def plot_rp_delta_vs_baseline(game, out_relpath):
    """Mean delta vs baseline by condition (averaged across reward levels)."""
    base_curve, _ = _rp_curve(_behavioral, game, "baseline_rp")
    if base_curve is None:
        print(f"  skip rp_delta_{game}: no baseline_rp rows")
        return

    cmap = plt.get_cmap(RP_DOSE_CMAP)
    bars = []
    for cond in RP_DELTA_CONDS:
        curve, _ = _rp_curve(_behavioral, game, cond)
        if curve is None:
            continue
        common = base_curve.index.intersection(curve.index)
        if len(common) == 0:
            continue
        diffs = (curve.loc[common] - base_curve.loc[common]).values
        mean_d = float(np.mean(diffs))
        sem_d = float(np.std(diffs, ddof=1) / np.sqrt(len(diffs))) if len(diffs) > 1 else 0.0
        bars.append((cond, mean_d, sem_d))

    fig, ax = plt.subplots(figsize=(11, 5.4))
    xs = np.arange(len(bars))
    means_pct = np.array([b[1] for b in bars]) * 100.0
    sems_pct = np.array([b[2] for b in bars]) * 100.0
    colors = []
    for cond, *_ in bars:
        if cond in RP_COND_COLORS:
            colors.append(RP_COND_COLORS[cond])
        elif cond.startswith("fewshot_cot_dose"):
            d = int(cond.replace("fewshot_cot_dose", "")) / 100.0
            colors.append(cmap(RP_DOSE_LO + (RP_DOSE_HI - RP_DOSE_LO) * d))
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
    ax.set_ylabel(r"$\Delta$ % choosing Risky vs baseline" if game == "lottery"
                  else r"$\Delta$ % accepting vs baseline")
    _smart_ylim(ax, float(np.min(means_pct - sems_pct)),
                float(np.max(means_pct + sems_pct)))
    ax.set_title(f"Revised Prompting — {RP_GAMES[game]['title_main']}\n"
                 f"Mean Δ vs baseline by condition")
    plt.tight_layout()
    _save(out_relpath)


# ============================================================================
# GROUP 5 — Multi-judge creativity plots
# ----------------------------------------------------------------------------
# Source slice: creativity_evals_combined.csv rows where
#   eval_prompt_version == 'torrance_four_dimension_length_controlled_v1'.
# This slice contains 3,400 rows: 680 creativity responses x 5 judges, drawn
# from three datasets (open_sae_creativity / revised_prompting_brick /
# revised_prompting_stapler) and stored side-by-side with the original 320
# single-judge GPT-5 rows.
# ============================================================================
MJ_JUDGES = ["gpt-5", "claude-sonnet-4-6", "gemini-2.5-pro",
             "kimi-k2.6", "deepseek-v4-pro"]
MJ_JUDGE_LABELS = {
    "gpt-5":             "GPT-5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "gemini-2.5-pro":    "Gemini 2.5 Pro",
    "kimi-k2.6":         "Kimi K2.6",
    "deepseek-v4-pro":   "DeepSeek V4 Pro",
}
# Re-use the canonical condition palette so the multi-judge bars hit the same
# hues as the rest of the paper — there are 5 judges so each gets a distinct
# palette colour with no overlap with the condition colours.
MJ_JUDGE_COLORS = {
    "gpt-5":             C_NAVY,
    "claude-sonnet-4-6": C_ORANGE,
    "gemini-2.5-pro":    C_TEAL,
    "kimi-k2.6":         C_PURPLE,
    "deepseek-v4-pro":   C_RED,
}
MJ_DIMS = ["fluency", "flexibility", "originality", "elaboration"]

MJ_TASK_NAMES = {
    "brick":   "detailed_ways_to_use_a_brick",
    "stapler": "improve_the_stapler_with_many_specific_enhancements",
}

# Canonical condition orderings per dataset (mirrors the experiment design;
# baseline first, then non-baseline conditions left to right).
MJ_SAE_CONDS = ["baseline", "high_temperature", "prompting", "high_steering"]
MJ_RP_BRICK_CONDS = ["baseline_rp", "persona", "cot", "fewshot", "fewshot_cot"]
MJ_RP_STAP_CONDS = ["baseline_rp", "persona", "cot", "persona_cot"]


_multi_judge = _creativity[
    _creativity["eval_prompt_version"] == "torrance_four_dimension_length_controlled_v1"].copy()


def _mj_slice(source_filter, task=None):
    """Return the rows for a given source_file (and optional task)."""
    sub = _multi_judge[_multi_judge["source_file"] == source_filter]
    if task is not None:
        sub = sub[sub["task"] == task]
    return sub


def _mj_grouped(rows, conditions, value_col="final_score"):
    """Return (judge -> condition -> (mean, sem)) and overall per-condition mean."""
    out = {j: {} for j in MJ_JUDGES}
    overall = {}
    for c in conditions:
        sub_c = rows[rows["condition"] == c]
        if sub_c.empty:
            for j in MJ_JUDGES:
                out[j][c] = (np.nan, 0.0)
            overall[c] = np.nan
            continue
        overall[c] = float(sub_c[value_col].mean())
        for j in MJ_JUDGES:
            vs = sub_c[sub_c["evaluator_model"] == j][value_col].dropna().values
            if len(vs):
                m = float(np.mean(vs))
                s = float(np.std(vs, ddof=1) / np.sqrt(len(vs))) if len(vs) > 1 else 0.0
                out[j][c] = (m, s)
            else:
                out[j][c] = (np.nan, 0.0)
    return out, overall


def plot_mj_final_score(rows, conditions, title, out_relpath,
                        n_per_condition=None):
    """Grouped bars: condition on x, one bar per judge, black-diamond overlay = mean."""
    by_jc, overall = _mj_grouped(rows, conditions)
    fig, ax = plt.subplots(figsize=(11, 5.6))
    x = np.arange(len(conditions))
    width = 0.155
    offsets = np.linspace(-2, 2, len(MJ_JUDGES)) * width
    for i, j in enumerate(MJ_JUDGES):
        means = [by_jc[j][c][0] for c in conditions]
        sems = [by_jc[j][c][1] for c in conditions]
        ax.bar(x + offsets[i], means, width, yerr=sems,
               label=MJ_JUDGE_LABELS[j], color=MJ_JUDGE_COLORS[j],
               edgecolor="black", linewidth=0.4, capsize=2)
    ax.plot(x, [overall[c] for c in conditions], color="black", marker="D",
            linestyle="-", linewidth=2, markersize=7,
            label="Mean across 5 judges", zorder=10)
    pretty = [c.replace("baseline_rp", "baseline").replace("_", " ") for c in conditions]
    if n_per_condition is not None:
        pretty = [f"{p}\n(N={n_per_condition})" for p in pretty]
    ax.set_xticks(x); ax.set_xticklabels(pretty)
    ax.set_xlabel("Condition")
    ax.set_ylabel("Creativity score  (mean of 4 Torrance dimensions, 1-10)")
    ax.set_ylim(0, 10)
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=7.5, ncol=2)
    plt.tight_layout()
    _save(out_relpath)


def plot_mj_dimensions(rows, conditions, title, out_relpath):
    """2x2 panels (one per Torrance dimension), bars = judges within each condition."""
    fig, axes = plt.subplots(2, 2, figsize=(14, 9))
    x = np.arange(len(conditions))
    width = 0.155
    offsets = np.linspace(-2, 2, len(MJ_JUDGES)) * width
    for ax_i, dim in enumerate(MJ_DIMS):
        ax = axes[ax_i // 2, ax_i % 2]
        by_jc, _ = _mj_grouped(rows, conditions, value_col=dim)
        for i, j in enumerate(MJ_JUDGES):
            means = [by_jc[j][c][0] for c in conditions]
            sems = [by_jc[j][c][1] for c in conditions]
            ax.bar(x + offsets[i], means, width, yerr=sems,
                   label=(MJ_JUDGE_LABELS[j] if ax_i == 0 else None),
                   color=MJ_JUDGE_COLORS[j], edgecolor="black",
                   linewidth=0.3, capsize=2)
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("baseline_rp", "baseline").replace("_", " ")
                            for c in conditions], rotation=15, ha="right")
        ax.set_ylim(0, 10)
        ax.set_ylabel("Score (1-10)")
        ax.set_title(dim.title())
        if ax_i == 0:
            ax.legend(loc="upper right", fontsize=7)
    fig.suptitle(title, fontsize=13, fontweight="bold")
    plt.tight_layout()
    _save(out_relpath)


def plot_mj_final_score_delta(rows, conditions, baseline_name, title,
                              out_relpath, n_per_condition=None):
    """Same layout as plot_mj_final_score, but bars = (cond - baseline) per judge."""
    by_jc, _ = _mj_grouped(rows, conditions)
    non_base = [c for c in conditions if c != baseline_name]
    fig, ax = plt.subplots(figsize=(11, 5.8))
    x = np.arange(len(non_base))
    width = 0.155
    offsets = np.linspace(-2, 2, len(MJ_JUDGES)) * width
    bar_lo, bar_hi = [], []
    for i, j in enumerate(MJ_JUDGES):
        bm, bs = by_jc[j][baseline_name]
        deltas, errs = [], []
        for c in non_base:
            m, s = by_jc[j][c]
            if np.isnan(m) or np.isnan(bm):
                deltas.append(np.nan); errs.append(0.0); continue
            d = m - bm
            e = float(np.sqrt(s ** 2 + bs ** 2))
            deltas.append(d); errs.append(e)
            bar_lo.append(d - e); bar_hi.append(d + e)
        ax.bar(x + offsets[i], deltas, width, yerr=errs,
               label=MJ_JUDGE_LABELS[j], color=MJ_JUDGE_COLORS[j],
               edgecolor="black", linewidth=0.4, capsize=2)
    # Black-diamond overlay: mean delta across the 5 judges.
    overlay = []
    for c in non_base:
        d_vs = []
        for j in MJ_JUDGES:
            m, _ = by_jc[j][c]; bm, _ = by_jc[j][baseline_name]
            if not (np.isnan(m) or np.isnan(bm)):
                d_vs.append(m - bm)
        overlay.append(float(np.mean(d_vs)) if d_vs else np.nan)
    ax.plot(x, overlay, color="black", marker="D", linestyle="-",
            linewidth=2, markersize=7,
            label="Mean delta across 5 judges", zorder=10)
    ax.axhline(0.0, color="#444", linestyle="--", linewidth=0.9, alpha=0.7)
    pretty = [c.replace("_", " ") for c in non_base]
    if n_per_condition is not None:
        pretty = [f"{p}\n(N={n_per_condition})" for p in pretty]
    ax.set_xticks(x); ax.set_xticklabels(pretty)
    ax.set_xlabel("Condition")
    ax.set_ylabel("Delta creativity score vs baseline (1-10 scale)")
    _smart_ylim(ax, min(bar_lo) if bar_lo else -0.5,
                max(bar_hi) if bar_hi else 0.5)
    ax.set_title(title)
    ax.legend(loc="upper left", fontsize=7.5, ncol=2)
    plt.tight_layout()
    _save(out_relpath)


def _spearman(xs, ys):
    xs = np.asarray(xs, float); ys = np.asarray(ys, float)
    m = ~np.isnan(xs) & ~np.isnan(ys)
    if m.sum() < 3:
        return np.nan
    if pd.Series(xs[m]).std() == 0 or pd.Series(ys[m]).std() == 0:
        return np.nan
    return float(np.corrcoef(pd.Series(xs[m]).rank().values,
                             pd.Series(ys[m]).rank().values)[0, 1])


def plot_mj_agreement(rows, title, out_relpath):
    """Pairwise Spearman heatmap (5x5) across judges for ``final_score``."""
    # Group rows by unique response key, collect each judge's score.
    # source_file + condition + subject_id + task uniquely identifies a response.
    by_row = defaultdict(dict)
    for _, r in rows.iterrows():
        key = (r.get("source_file"), r.get("condition"),
               r.get("subject_id"), r.get("task"))
        j = r.get("evaluator_model")
        if j in MJ_JUDGES and pd.notna(r.get("final_score")):
            by_row[key][j] = r["final_score"]
    n = len(MJ_JUDGES)
    M = np.ones((n, n))
    for i in range(n):
        for k in range(n):
            if i == k:
                continue
            xs, ys = [], []
            for d in by_row.values():
                if MJ_JUDGES[i] in d and MJ_JUDGES[k] in d:
                    xs.append(d[MJ_JUDGES[i]]); ys.append(d[MJ_JUDGES[k]])
            M[i, k] = _spearman(xs, ys) if len(xs) >= 3 else np.nan
    fig, ax = plt.subplots(figsize=(6.8, 5.8))
    im = ax.imshow(M, cmap="viridis", vmin=0.5, vmax=1.0)
    ax.set_xticks(range(n)); ax.set_yticks(range(n))
    ax.set_xticklabels([MJ_JUDGE_LABELS[j] for j in MJ_JUDGES],
                       rotation=35, ha="right", fontsize=8)
    ax.set_yticklabels([MJ_JUDGE_LABELS[j] for j in MJ_JUDGES], fontsize=8)
    for i in range(n):
        for k in range(n):
            v = M[i, k]
            txt = "1.00" if i == k else (f"{v:.2f}" if not np.isnan(v) else "—")
            ax.text(k, i, txt, ha="center", va="center",
                    color=("white" if (np.isnan(v) or v < 0.85) else "black"),
                    fontsize=9)
    off = M[~np.eye(n, dtype=bool)]
    off_f = off[np.isfinite(off)]
    mean_off = float(off_f.mean()) if off_f.size else float("nan")
    n_unique = len(by_row)
    ax.set_title(f"{title}\nMean pairwise Spearman = {mean_off:.3f}   "
                 f"(N={n_unique} responses)", fontsize=11)
    fig.colorbar(im, ax=ax, shrink=0.85).set_label("Spearman correlation")
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
    # ---- Group 1 ----
    plot_preference()
    plot_safe_vs_risky()
    plot_ultimatum_game()
    plot_5_conditions()
    plot_capability_bar()

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
    plot_capability_brick("figure_15_capability_brick_target_vs_achieved_qwen",
                          "figures/figd_brick.png")                   # Qwen
    # Four-object
    plot_capability_four_objects("figure_10_capability_four_objects_target_vs_achieved",
                                 "figures_llama/figure10_GPT5.png")   # Llama, GPT-5
    plot_capability_four_objects("figure_10_capability_four_objects_target_vs_achieved",
                                 "figures_llama/figure10.png")        # proxy (orig-judge missing)
    plot_capability_four_objects("figure_16_capability_four_objects_target_vs_achieved_qwen",
                                 "figures/figd.png")                  # Qwen
    plot_capability_four_objects("figure_16_capability_four_objects_target_vs_achieved_qwen",
                                 "figures/figd_appendix.png")         # Qwen (appendix copy)

    # ---- Group 2: dose response ----
    plot_dose_response("figure_11_dose_response_lottery_ultimatum_llama",
                       "figure_11_dose_response_lottery_ultimatum_llama",
                       "figures_llama/figure11.png")
    plot_dose_response("figure_17_dose_response_lottery_ultimatum_qwen",
                       "figure_17_dose_response_lottery_ultimatum_qwen",
                       "figures/dose_response_lambda.png", panel_labels=True)

    # ---- Group 2: probe activation tracking ----
    plot_activation_tracking("figure_12_probe_scores_track_target_lottery_ultimatum_llama",
                             "figure_12_probe_scores_track_target_lottery_ultimatum_llama",
                             "figures_llama/figure12.png")
    plot_activation_tracking("figure_18_probe_scores_track_target_qwen",
                             "figure_18_probe_scores_track_target_qwen",
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

    # ---- Group 3: feature activations ----
    plot_feature_rank_grid("preference_activations.png")
    plot_feature_rank_grid("combined_lottery_ultimatum_grid.png")
    plot_feature_top5_bars("activation_grid_top5.png", two_tone=True)
    plot_feature_top5_bars("top5_task_condition.png", two_tone=True)
    plot_feature_top5_bars("capability_activations.png", two_tone=True)

    # ---- Group 4: revised-prompting behavioural plots ----
    plot_rp_psychometric("lottery",
        "figures_revised_prompting/lottery_psychometric_by_condition.png")
    plot_rp_psychometric("ultimatum",
        "figures_revised_prompting/ultimatum_psychometric_by_condition.png")
    plot_rp_dose_response("lottery",
        "figures_revised_prompting/lottery_dose_response_fewshot_cot.png")
    plot_rp_dose_response("ultimatum",
        "figures_revised_prompting/ultimatum_dose_response_fewshot_cot.png")
    plot_rp_delta_vs_baseline("lottery",
        "figures_revised_prompting/lottery_delta_vs_baseline.png")
    plot_rp_delta_vs_baseline("ultimatum",
        "figures_revised_prompting/ultimatum_delta_vs_baseline.png")

    # ---- Group 5: multi-judge creativity plots ----
    # 5a. SAE creativity (open_sae_creativity, 4 conditions, 40 agents each).
    sae_brick = _mj_slice("open_sae_creativity", MJ_TASK_NAMES["brick"])
    sae_stap  = _mj_slice("open_sae_creativity", MJ_TASK_NAMES["stapler"])
    plot_mj_final_score(
        sae_brick, MJ_SAE_CONDS,
        "SAE creativity steering — brick (Torrance, 5-judge re-score)",
        "figures_multijudge/brick_final_score_multijudge.png",
        n_per_condition=40)
    plot_mj_final_score(
        sae_stap, MJ_SAE_CONDS,
        "SAE creativity steering — stapler (Torrance, 5-judge re-score)",
        "figures_multijudge/stapler_final_score_multijudge.png",
        n_per_condition=40)
    plot_mj_dimensions(
        sae_brick, MJ_SAE_CONDS,
        "SAE creativity — brick: per-dimension scores by condition x judge",
        "figures_multijudge/brick_dimensions_multijudge.png")
    plot_mj_dimensions(
        sae_stap, MJ_SAE_CONDS,
        "SAE creativity — stapler: per-dimension scores by condition x judge",
        "figures_multijudge/stapler_dimensions_multijudge.png")
    plot_mj_agreement(
        _mj_slice("open_sae_creativity"),
        "SAE creativity (brick + stapler) — judge agreement",
        "figures_multijudge/sae_creativity_agreement_heatmap.png")

    # 5b. Revised-Prompting brick & stapler multi-judge plots.
    rp_brick = _mj_slice("revised_prompting_brick")
    rp_stap  = _mj_slice("revised_prompting_stapler")
    plot_mj_final_score_delta(
        rp_brick, MJ_RP_BRICK_CONDS, "baseline_rp",
        "Revised Prompting — brick: final-score DELTA vs baseline",
        "figures_revised_prompting/creativity_brick_multijudge_final_score_delta_vs_baseline.png",
        n_per_condition=40)
    plot_mj_final_score_delta(
        rp_stap, MJ_RP_STAP_CONDS, "baseline_rp",
        "Revised Prompting — stapler: final-score DELTA vs baseline",
        "figures_revised_prompting/creativity_stapler_multijudge_final_score_delta_vs_baseline.png",
        n_per_condition=40)

    print("\n--- DATA MISSING / NOT EXACTLY REPRODUCIBLE ---")
    for reason, files in MISSING_DATA.items():
        print(f"{reason}:")
        for f in files:
            print(f"    {f}")
    print(f"\nAll regenerated PNGs written under {os.path.relpath(OUT, HERE)}/")


if __name__ == "__main__":
    main()
