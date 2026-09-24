"""Figure builders for S1. One function per figure id.

Each `figures/make_<id>.py` is a two-line wrapper around a function here, so the
generating script sits beside its output as CLAUDE.md requires while the shared
style lives in one place.

**Palette.** The repository already fixes a condition-to-colour map in
`cleaned/regenerate_all_figures.py`, and the paper's figures depend on it. That
map's hue *assignments* are kept exactly — baseline navy, prompting/persona
orange, SAE steering teal, probe steering purple, few-shot gold, CoT and high
temperature sienna — so a reader can still tell the family from the colour across
every figure in the paper. Three of its six hexes fail the computable palette
checks (navy sits at OKLCH L 0.32, below the 0.43-0.77 band; orange, teal and
goldenrod fall under 3:1 against the surface), so each was snapped to the nearest
step of the *same hue* that passes. The snapped set passes all five checks:

    validate_palette.py "#42478D,#DD7641,#14A3A3,#7B3FA0,#BD8A00,#C0442D" --mode light
    -> lightness band PASS, chroma floor PASS, CVD separation PASS (worst adjacent
       dE 11.2 deutan), normal-vision floor PASS (16.9), contrast PASS

Hues are assigned in fixed order and never cycled. Where two conditions share a
family colour (the two lottery personas, the two SAE doses) they are separated by
marker shape and a direct label, never by inventing a hue. Every figure has a
table view: the CSV it is drawn from, under `results/S/s1/`.
"""
from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# The condition names say 0.25 and 0.75; six exemplars can only realise sixths.
REALISED_RHO = {0.0: 0.0, 0.25: 2 / 6, 0.5: 0.5, 0.75: 4 / 6, 1.0: 1.0}
DATA = ROOT / "results/S/s1"
FIGS = ROOT / "figures"

# --- validated categorical palette, fixed order -----------------------------
NAVY, ORANGE, TEAL, PURPLE, GOLD, SIENNA = (
    "#42478D", "#DD7641", "#14A3A3", "#7B3FA0", "#BD8A00", "#C0442D")
SURFACE = "#FCFCFB"
INK, INK2, MUTED, GRID = "#1E1E1C", "#5A5A55", "#8A8A83", "#E4E4E0"

FAMILY = {
    "baseline": NAVY, "baseline_rp": NAVY,
    "slightly_prompting": ORANGE, "barely_prompting": ORANGE,
    "prompting": ORANGE, "persona": ORANGE,
    "steering": TEAL, "lite_steering": TEAL,
    "cot": SIENNA, "high_temperature": SIENNA,
    "fewshot": GOLD,
}
# The few-shot family shares a hue so it reads as one family across figures, but
# five members at one colour are indistinguishable when several are on an axis.
# Graded by dose, dark to light, with plain `fewshot` left on the base gold.
GOLD_RAMP = {"000": "#7A5A00", "025": "#9C7300", "050": "#BD8A00",
             "075": "#D3A63A", "100": "#E0BE6B"}
for _d, _c in GOLD_RAMP.items():
    FAMILY[f"fewshot_cot_dose{_d}"] = _c

STACK_TITLE = {
    "hosted": "Goodfire hosted API",
    "vllm": "local vLLM",
    "probe-llama-l48": "local probe, Llama layer 48",
    "probe-llama-l50": "local probe, Llama layer 50",
    "probe-qwen-l17": "local probe, Qwen layer 17",
}

# Short forms for axis ticks, where the full STACK_TITLE will not fit.
SHORT_STACK = {
    "hosted": "Goodfire",
    "vllm": "local vLLM",
    "probe-llama-l48": "local probe L48",
    "probe-llama-l50": "local probe L50",
    "probe-qwen-l17": "local probe Qwen17",
}

MARKERS = ["o", "s", "^", "D", "v", "P", "X", "*", "<"]

# Conditions that share a family colour are separated by marker shape, assigned
# once and globally so the same condition wears the same mark in every figure.
MARKER_OF = {
    "baseline": "o", "baseline_rp": "o",
    "slightly_prompting": "^", "barely_prompting": "v",
    "prompting": "^", "persona": "^",
    "steering": "s", "lite_steering": "D",
    "cot": "P", "high_temperature": "P",
    "fewshot": "X",
}
for _d, _m in zip(("000", "025", "050", "075", "100"), ("<", ">", "*", "h", "p")):
    MARKER_OF[f"fewshot_cot_dose{_d}"] = _m


DASH_OF = {"fewshot": "-",
           "fewshot_cot_dose000": (0, (5, 2)),
           "fewshot_cot_dose025": (0, (3, 1.5)),
           "fewshot_cot_dose050": (0, (1.5, 1.5)),
           "fewshot_cot_dose075": (0, (6, 1.5, 1.5, 1.5)),
           "fewshot_cot_dose100": (0, (1, 1, 4, 1))}


def dash(cond: str):
    """Line style within a colour family; solid for everything else."""
    return DASH_OF.get(cond, "-")


def marker(cond: str) -> str:
    if cond.startswith("target"):
        return "o"
    return MARKER_OF.get(cond, "o")


def colour(cond: str) -> str:
    if cond.startswith("target"):
        return PURPLE
    return FAMILY.get(cond, MUTED)


def style(ax, title: str = "", xlabel: str = "", ylabel: str = ""):
    ax.set_facecolor(SURFACE)
    ax.grid(False)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8.5, length=3)
    if title:
        ax.set_title(title, color=INK, fontsize=10.5, pad=7, loc="left")
    if xlabel:
        ax.set_xlabel(xlabel, color=INK2, fontsize=9)
    if ylabel:
        ax.set_ylabel(ylabel, color=INK2, fontsize=9)


def save(fig, fig_id: str):
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.patch.set_facecolor(SURFACE)
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"{fig_id}.{ext}", dpi=300, bbox_inches="tight",
                    facecolor=SURFACE)
    plt.close(fig)
    print(f"wrote figures/{fig_id}.pdf and .png")


def read(name: str) -> List[dict]:
    return list(csv.DictReader(open(DATA / name, newline="")))


def f(v, default=np.nan) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def ci_of(s: str):
    try:
        lo, hi = s.strip("[]").split(",")
        return float(lo), float(hi)
    except Exception:
        return np.nan, np.nan


# ===========================================================================
# s1_1_dominated
# ===========================================================================
def s1_1_dominated():
    rows = read("s1_1_dominated_lottery.csv")
    stacks = ["hosted", "vllm", "probe-llama-l48"]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.3), sharey=True)
    for ax, stack in zip(axes, stacks):
        sub = [r for r in rows if r["stack"] == stack]
        levels = sorted({f(x) for r in sub for x in [r["n_levels_below_50"]]})
        n_below = int(levels[0]) if levels else 8
        # The staircase a perfectly sharp curve would trace: if the model switches
        # at s, it takes every dominated gamble above s and none below it.
        grid = np.array(sorted({f(r["switching_point_interp"]) for r in sub
                                if np.isfinite(f(r["switching_point_interp"]))}))
        gx = np.linspace(0, 210, 800)
        step = 5.0
        lo_level = 50 - step * n_below
        pred = np.clip((50 - np.maximum(gx, lo_level)) / (50 - lo_level), 0, 1)
        ax.plot(gx, pred, color=MUTED, linewidth=1.4, linestyle=(0, (4, 3)), zorder=2,
                label="implied by the switching point alone (P13)")
        missing = []
        for r in sorted(sub, key=lambda r: f(r["switching_point_interp"], 1e9)):
            x = f(r["switching_point_interp"])
            y = f(r["p_risky_dominated"])
            lo, hi = ci_of(r["ci_risky_dominated"])
            if not np.isfinite(x):
                missing.append(r["condition"])
                continue
            c = colour(r["condition"])
            # P13: the gap to the staircase is the excess over a clean translation.
            imp = f(r.get("implied_by_translation", ""))
            if np.isfinite(imp) and abs(y - imp) > 0.015:
                ax.plot([x, x], [imp, y], color=c, linewidth=1.1, alpha=0.8, zorder=3)
                ax.plot([x], [imp], "_", color=c, markersize=9, zorder=3)
            ax.errorbar(x, y, yerr=[[max(0, y - lo)], [max(0, hi - y)]],
                        fmt=marker(r["condition"]),
                        color=c, markersize=8, capsize=3, elinewidth=1.6,
                        markeredgecolor=SURFACE, markeredgewidth=1.4, zorder=4)
            if y > 0.02 or r["condition"] in ("baseline", "baseline_rp"):
                ax.annotate(r["condition"].replace("fewshot_cot_dose", "fs+cot "),
                            (x, y), textcoords="offset points", xytext=(7, 5),
                            fontsize=7.5, color=INK2)
        ax.axvline(50, color=INK2, linewidth=1.1, linestyle=":", zorder=3)
        ax.text(52, 0.965, "utility floor  n* = 50", fontsize=7.5, color=INK2, va="top")
        if missing:
            ax.text(0.98, 0.52, "no switching point\n(curve never crosses 0.5):\n"
                    + "\n".join(missing), transform=ax.transAxes, ha="right", va="top",
                    fontsize=7, color=MUTED)
        style(ax, STACK_TITLE[stack], "switching point of the same curve (tokens)",
              "P(risky | n < 50)" if stack == "hosted" else "")
        ax.set_xlim(0, 210)
        ax.set_ylim(-0.04, 1.04)
    axes[0].legend(loc="upper right", bbox_to_anchor=(0.99, 0.88), fontsize=7.5,
                   frameon=False, labelcolor=INK2)
    fig.suptitle("S1.1  Dominated choices against the rate a clean translation implies "
                 "(P13); the stacks are not compared",
                 fontsize=11.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "s1_1_dominated")


# ===========================================================================
# s1_2_catch
# ===========================================================================
def s1_2_catch():
    rows = read("s1_2_catch_ultimatum.csv")
    stacks = ["hosted", "vllm", "probe-llama-l50"]
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.3), sharey=True)
    # Opaque background for every small annotation: several dashed reference
    # lines run the full width of these panels and struck through the text.
    LBOX = dict(facecolor=SURFACE, edgecolor="none", pad=1.2)
    for ax, stack in zip(axes, stacks):
        sub = [r for r in rows if r["stack"] == stack]
        seen = {}
        unidentified = []            # collected, then laid out as one block
        placed = []                  # (x, y) of labels already written
        pts = [(f(r["threshold_interp"]), f(r["p_reject_hyperfair"])) for r in sub
               if np.isfinite(f(r["threshold_interp"]))]
        for r in sorted(sub, key=lambda r: f(r["threshold_interp"], 1e9)):
            x = f(r["threshold_interp"])
            y = f(r["p_reject_hyperfair"])
            lo, hi = ci_of(r["ci_reject_hyperfair"])
            c = colour(r["condition"])
            m = MARKERS[seen.setdefault(c, len(seen)) % len(MARKERS)]
            if not np.isfinite(x):
                ax.axhline(y, color=c, linewidth=1.0, linestyle=(0, (2, 3)), zorder=3)
                unidentified.append((r["condition"], c))
                continue
            imp = f(r.get("implied_by_translation", ""))
            if np.isfinite(imp):
                ax.plot([x], [imp], "_", color=c, markersize=10, zorder=3)
                if abs(y - imp) > 0.008:
                    ax.plot([x, x], [imp, y], color=c, linewidth=1.1, alpha=0.8, zorder=3)
            ax.errorbar(x, y, yerr=[[max(0, y - lo)], [max(0, hi - y)]], fmt=m, color=c,
                        markersize=8, capsize=3, elinewidth=1.6,
                        markeredgecolor=SURFACE, markeredgewidth=1.4, zorder=4)
            if y > 0.005:
                # Drop the label below the marker when a previous label sits within
                # 0.02 of it in y (a fixed offset stacked fs+cot 025 on 075), and
                # flip it to the left when another point's marker is where the text
                # would go (target30's label ran through target40's marker).
                dy = 5
                if any(abs(y - py) < 0.02 and abs(x - px) < 12 for px, py in placed):
                    dy = -11
                dx, ha = 8, "left"
                if any(0 < px - x < 9 and abs(py - y) < 0.03 for px, py in pts):
                    dx, ha = -8, "right"
                # 3.5: above the dashed reference lines (3) so the box still masks
                # them, below the markers (4) so a box never covers its own point
                ax.annotate(r["condition"].replace("fewshot_cot_dose", "fs+cot "), (x, y),
                            textcoords="offset points", xytext=(dx, dy), fontsize=7.5,
                            color=INK2, ha=ha, bbox=LBOX, zorder=3.5)
                placed.append((x, y))
        if unidentified:
            names = ", ".join(n for n, _ in unidentified)
            ax.text(0.03, 0.97, f"no threshold on this grid:\n{names}",
                    transform=ax.transAxes, fontsize=7, color=INK2, va="top",
                    bbox=LBOX, zorder=5)
        gmax = max((f(r["offer_grid_max"]) for r in sub), default=90)
        ax.axvline(50, color=INK2, linewidth=1.1, linestyle=":", zorder=3)
        # left of the rule, not right: on the probe panel the right side is where
        # the target60 point and its interval sit
        # mid height, so the top row belongs to the two corner notes alone
        ax.text(49, 0.235, "offers at or above\nhalf the pie", fontsize=7.5, color=INK2,
                va="top", ha="right", bbox=LBOX, zorder=5)
        # top right, not bottom: the bottom right is where the fs+cot labels land
        ax.text(0.98, 0.97, f"offer grid ends at {int(gmax)}", transform=ax.transAxes,
                ha="right", va="top", fontsize=7.5, color=MUTED, bbox=LBOX, zorder=5)
        style(ax, STACK_TITLE[stack], "acceptance threshold of the same curve (tokens)",
              "P(reject | offer $\\geq$ 50)" if stack == "hosted" else "")
        ax.set_xlim(0, 70)
        # headroom for the layer-50 target60 interval, whose top is 0.3115
        ax.set_ylim(-0.014, 0.37)
    fig.suptitle("S1.2  Hyper-fair rejections, against the rate a clean translation implies "
                 "(P13); dash = implied, marker = observed",
                 fontsize=11.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "s1_2_catch")


# ===========================================================================
# s1_3_switching
# ===========================================================================
def s1_3_switching():
    rows = [r for r in read("s1_3_switching_points.csv")
            if np.isfinite(f(r["switching_point_logistic"]))
            and np.isfinite(f(r["ci_lo_cluster"]))]
    for game, xmax, fid in (("lottery", 260, "s1_3_switching_lottery"),
                            ("ultimatum", 110, "s1_3_switching_ultimatum")):
        sub = [r for r in rows if r["game"] == game]
        order = ["hosted", "vllm", "probe-llama-l48", "probe-llama-l50", "probe-qwen-l17"]
        sub.sort(key=lambda r: (order.index(r["stack"]) if r["stack"] in order else 9,
                                f(r["switching_point_logistic"])))
        fig, ax = plt.subplots(figsize=(9.2, max(4.0, 0.26 * len(sub) + 1.6)))
        ypos, labels, last = [], [], None
        y = 0
        for r in sub:
            if r["stack"] != last:
                y += 1.0
                last = r["stack"]
            ypos.append(y)
            labels.append(f"{r['condition']}")
            y += 1
        for r, yy in zip(sub, ypos):
            c = colour(r["condition"])
            lo, hi = f(r["ci_lo_cluster"]), f(r["ci_hi_cluster"])
            tlo, thi = f(r["ci_lo_trial"]), f(r["ci_hi_trial"])
            ax.plot([tlo, thi], [yy, yy], color=c, linewidth=4.5, alpha=0.28,
                    solid_capstyle="butt", zorder=2)
            ax.plot([lo, hi], [yy, yy], color=c, linewidth=2.0,
                    solid_capstyle="butt", zorder=3)
            ax.plot([f(r["switching_point_logistic"])], [yy], "o", color=c, markersize=7,
                    markeredgecolor=SURFACE, markeredgewidth=1.3, zorder=4)
        ax.set_yticks(ypos)
        ax.set_yticklabels(labels, fontsize=7.6)
        ax.invert_yaxis()
        if game == "lottery":
            ax.axvline(50, color=INK2, linewidth=1.1, linestyle=":", zorder=1)
            ax.text(51.5, ypos[0] - 0.9, "utility floor n* = 50", fontsize=8, color=INK2)
        last = None
        for r, yy in zip(sub, ypos):
            if r["stack"] != last:
                ax.text(xmax * 0.995, yy - 1.0, STACK_TITLE[r["stack"]], fontsize=8.5,
                        color=INK, ha="right", va="center", style="italic")
                last = r["stack"]
        style(ax, f"S1.3  {game.title()}: switching points with bootstrap intervals",
              "switching point (tokens)", "")
        ax.set_xlim(0, xmax)
        from matplotlib.lines import Line2D
        ax.legend(handles=[
            Line2D([], [], color=MUTED, linewidth=2.0, label="95% CI, reward levels resampled"),
            Line2D([], [], color=MUTED, linewidth=4.5, alpha=0.28, label="95% CI, trials resampled"),
        ], loc="lower right", fontsize=7.8, frameon=False, labelcolor=INK2)
        fig.tight_layout()
        save(fig, fid)


# ===========================================================================
# s1_4_ceiling
# ===========================================================================
def s1_4_ceiling():
    rows = read("s1_4_probe_ceiling.csv")
    keep = [r for r in rows if r["stack"] in ("hosted", "vllm", "probe-llama-l48")
            and r["game"] == "lottery"]
    keep.sort(key=lambda r: (r["stack"], -f(r["ceiling_any_function_of_n"])))
    fig, ax = plt.subplots(figsize=(10.2, max(4.2, 0.28 * len(keep) + 1.6)))
    ypos, labels, last, y = [], [], None, 0
    for r in keep:
        if r["stack"] != last:
            y += 1.0
            last = r["stack"]
        ypos.append(y)
        labels.append(r["condition"])
        y += 1
    for r, yy in zip(keep, ypos):
        c = colour(r["condition"])
        a, b = f(r["ceiling_any_function_of_n"]), f(r["best_threshold_rule"])
        ax.plot([b, a], [yy, yy], color=GRID, linewidth=2.2, zorder=2)
        ax.plot([b], [yy], "s", color=SURFACE, markeredgecolor=c, markeredgewidth=1.8,
                markersize=7, zorder=3)
        ax.plot([a], [yy], "o", color=c, markersize=8, markeredgecolor=SURFACE,
                markeredgewidth=1.3, zorder=4)
    ax.axvline(0.82, color=SIENNA, linewidth=1.5, linestyle="--", zorder=1)
    ax.text(0.822, ypos[0] - 0.9, "the paper's 82%", fontsize=8.5, color=SIENNA)
    ax.set_yticks(ypos)
    ax.set_yticklabels(labels, fontsize=7.6)
    ax.invert_yaxis()
    last = None
    for r, yy in zip(keep, ypos):
        if r["stack"] != last:
            ax.text(0.505, yy - 1.0, STACK_TITLE[r["stack"]], fontsize=8.5, color=INK,
                    va="center", style="italic")
            last = r["stack"]
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker="o", linestyle="", color=MUTED, markersize=8,
               label="ceiling of any function of n"),
        Line2D([], [], marker="s", linestyle="", color=SURFACE, markeredgecolor=MUTED,
               markeredgewidth=1.8, markersize=7, label="best one-parameter threshold on n"),
    ], loc="lower right", fontsize=7.8, frameon=False, labelcolor=INK2)
    style(ax, "S1.4  What a predictor that knows only the reward level can reach",
          "accuracy on the logged choices", "")
    ax.set_xlim(0.5, 1.02)
    fig.tight_layout()
    save(fig, "s1_4_ceiling")


# ===========================================================================
# s1_5_judges
# ===========================================================================
def s1_5_judges():
    """Dot plot, not bars: the differences at issue are 0.2-0.6 on a 1-10 scale, and a
    bar chart of them either wastes two thirds of the panel on an empty zero baseline
    or truncates one. Dots carry no area, so a non-zero y range is honest."""
    rows = read("s1_5_condition_ordering.csv")
    conds = ["baseline", "prompting", "high_temperature", "high_steering"]
    judges = sorted({r["judge"] for r in rows
                     if r["judge"] not in ("MEAN_of_5_judges",
                                           "single_judge_gpt5_original_rubric")})
    # Fixed hue order over the five judges; navy is reserved for the mean.
    jcol = dict(zip(judges, [ORANGE, TEAL, PURPLE, GOLD, SIENNA]))
    jmark = dict(zip(judges, ["^", "s", "D", "v", "P"]))
    titles = {"detailed_ways_to_use_a_brick": "Brick: divergent creativity",
              "improve_the_stapler_with_many_specific_enhancements":
                  "Stapler: product innovation"}
    tasks = sorted({r["task"] for r in rows})
    fig, axes = plt.subplots(1, len(tasks), figsize=(12.8, 4.9), sharey=True)
    axes = np.atleast_1d(axes)
    x = np.arange(len(conds))
    for ax, task in zip(axes, tasks):
        for j in judges:
            rec = next((r for r in rows if r["task"] == task and r["judge"] == j), None)
            if not rec:
                continue
            vals = [f(rec[f"mean_{c}"]) for c in conds]
            ax.plot(x, vals, "-", color=jcol[j], linewidth=1.3, alpha=0.75, zorder=3)
            ax.plot(x, vals, jmark[j], color=jcol[j], markersize=7.5,
                    markeredgecolor=SURFACE, markeredgewidth=1.2, zorder=4,
                    label=j if ax is axes[0] else None)
            ax.annotate(j.split("-")[0], (x[-1], vals[-1]), textcoords="offset points",
                        xytext=(8, -2), fontsize=7, color=jcol[j], va="center")
        rec = next((r for r in rows if r["task"] == task
                    and r["judge"] == "MEAN_of_5_judges"), None)
        if rec:
            vals = [f(rec[f"mean_{c}"]) for c in conds]
            ax.plot(x, vals, "-o", color=NAVY, linewidth=2.6, markersize=9.5,
                    markeredgecolor=SURFACE, markeredgewidth=1.5, zorder=6,
                    label="mean of five judges" if ax is axes[0] else None)
            for xi, v in zip(x, vals):
                ax.annotate(f"{v:.2f}", (xi, v), textcoords="offset points",
                            xytext=(0, 11), ha="center", fontsize=8.5, color=INK,
                            zorder=7)
            ax.axhline(vals[0], color=NAVY, linewidth=1.0, linestyle=":", zorder=2)
            ax.annotate("baseline level", (3.42, vals[0]), fontsize=7, color=NAVY,
                        va="bottom", ha="right")
        ax.set_xticks(x)
        ax.set_xticklabels([c.replace("_", "\n") for c in conds], fontsize=8.5)
        ax.set_xlim(-0.35, 3.75)
        style(ax, titles.get(task, task),
              "", "creativity score, 1-10" if ax is axes[0] else "")
    axes[0].set_ylim(4.0, 7.1)
    axes[0].legend(loc="lower left", fontsize=7.4, ncol=2, frameon=False,
                   labelcolor=INK2)
    fig.suptitle("S1.5  Five judges, one condition ordering each, repository data only "
                 "(the PDF's values differ; see reports/S1_5.md section 5)",
                 fontsize=11, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    save(fig, "s1_5_judges")


# ===========================================================================
# s1_6_measures
# ===========================================================================
def s1_6_measures():
    rows = [r for r in read("s1_6_measure_judge_correlations.csv")
            if r["scope"] == "open_sae_creativity"]
    measures = ["n_ideas", "n_words", "category_spread", "object_distance", "dsi_approx"]
    judges = sorted({r["judge"] for r in rows if r["judge"] != "MEAN_of_5_judges"})
    cols = judges + ["MEAN_of_5_judges"]
    M = np.full((len(measures), len(cols)), np.nan)
    for r in rows:
        if r["measure"] in measures and r["judge"] in cols:
            M[measures.index(r["measure"]), cols.index(r["judge"])] = f(r["spearman"])
    fig, ax = plt.subplots(figsize=(8.6, 3.9))
    lim = float(np.nanmax(np.abs(M))) if np.isfinite(M).any() else 1.0
    lim = max(lim, 0.2)
    # diverging: two hues, neutral grey midpoint, no hue at zero
    from matplotlib.colors import LinearSegmentedColormap
    cmap = LinearSegmentedColormap.from_list("div", [TEAL, "#EFEFEC", SIENNA])
    im = ax.imshow(M, cmap=cmap, vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(len(cols)))
    ax.set_xticklabels([c.replace("MEAN_of_5_judges", "mean of 5") for c in cols],
                       fontsize=8, rotation=20, ha="right")
    ax.set_yticks(range(len(measures)))
    ax.set_yticklabels(measures, fontsize=8.5)
    for i in range(len(measures)):
        for j in range(len(cols)):
            if np.isfinite(M[i, j]):
                ax.text(j, i, f"{M[i, j]:.2f}", ha="center", va="center", fontsize=8,
                        color=INK)
    ax.grid(False)
    cb = fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02)
    cb.set_label("Spearman", color=INK2, fontsize=8.5)
    cb.ax.tick_params(colors=INK2, labelsize=8)
    ax.set_title("S1.6  Judge-independent text measures against each judge "
                 "(open-SAE creativity slice)", color=INK, fontsize=10.5, loc="left", pad=8)
    fig.tight_layout()
    save(fig, "s1_6_measures")


# ===========================================================================
# s1_7_ladder
# ===========================================================================
def s1_7_ladder():
    import json
    from .s1_data import load_behavioural
    curves = {(c.stack, c.game, c.condition): c for c in load_behavioural()}
    rows = read("s1_7_ladder_behaviour.csv")
    fig, axes = plt.subplots(1, 3, figsize=(16.6, 4.5))

    order = ["baseline_rp", "persona", "cot", "fewshot", "fewshot_cot_dose000",
             "fewshot_cot_dose100"]
    # Both games on their own axes. The dotted rule is 50 in each, but it means
    # different things: the lottery's utility floor, and the even split of the pie.
    # `baseline_rp` is the condition name in the logs; the legend shows the
    # plain word, since the suffix means nothing to a reader.
    SHOWN = {"baseline_rp": "baseline"}
    ladders = (("lottery", "risky reward n (tokens)", "P(risky)",
                "Lottery Game"),
               ("ultimatum", "offer (tokens)", "P(accept)",
                "Ultimatum Game"))
    for ax, (game, xlab, ylab, title) in zip(axes[:2], ladders):
        for cond in order:
            c = curves.get(("vllm", game, cond))
            if c is None:
                continue
            bx = c.by_x()
            xs = np.array(list(bx), float)
            ys = np.array([np.mean(bx[x]) for x in bx], float)
            col = colour(cond)
            ax.plot(xs, ys, linestyle=dash(cond), color=col, linewidth=1.9,
                    marker=marker(cond), markersize=4.8,
                    markeredgecolor=SURFACE, markeredgewidth=0.7,
                    label=SHOWN.get(cond, cond), zorder=3)
        ax.axvline(50, color=INK2, linewidth=1.0, linestyle=":", zorder=1)
        ax.axhline(0.5, color=MUTED, linewidth=0.9, linestyle=(0, (2, 3)), zorder=1)
        style(ax, title, xlab, ylab)
        ax.set_ylim(-0.03, 1.03)
    # one legend for both ladders: the conditions are the same set
    axes[0].legend(fontsize=7.0, frameon=False, loc="upper left",
                   bbox_to_anchor=(0.0, 0.99), labelcolor=INK2, ncol=2,
                   columnspacing=0.8, handlelength=1.6)

    ax = axes[2]
    for game, col, mk in (("lottery", GOLD, "o"), ("ultimatum", PURPLE, "s")):
        sub = [r for r in rows if r["game"] == game and r["rho"] != ""]
        sub.sort(key=lambda r: f(r["rho"]))
        # Plot at the fraction the six demonstrations actually realise, not at the
        # condition's name: with six exemplars only multiples of 1/6 are reachable,
        # so "dose025" is 2/6 and "dose075" is 4/6 (reports/S1_7.md section 3).
        xs = [REALISED_RHO.get(f(r["rho"]), f(r["rho"])) for r in sub]
        ys = [f(r["switching_point_logistic"]) for r in sub]
        lo = [f(r["ci_lo"]) for r in sub]
        hi = [f(r["ci_hi"]) for r in sub]
        ok = [i for i, v in enumerate(ys) if np.isfinite(v)]
        ax.errorbar([xs[i] for i in ok], [ys[i] for i in ok],
                    yerr=[[max(0, ys[i] - lo[i]) for i in ok], [max(0, hi[i] - ys[i]) for i in ok]],
                    fmt="-" + mk, color=col, linewidth=2.0, markersize=8, capsize=3,
                    markeredgecolor=SURFACE, markeredgewidth=1.3,
                    label=f"{game} switching point")
        base = next((f(r["same_stack_baseline_switching_point"]) for r in sub), np.nan)
        if np.isfinite(base):
            ax.axhline(base, color=col, linewidth=1.0, linestyle=":", zorder=1)
            ax.annotate(f"{game} baseline {base:.0f}", (0.97, base), fontsize=7.5,
                        color=col, ha="right", va="bottom")
    style(ax, "Few-shot + CoT: the $\\rho$ dose-response",
          "realised fraction of risky / accept demonstrations",
          "switching point (tokens)")
    ax.set_xlim(-0.06, 1.06)
    ax.legend(fontsize=7.8, frameon=False, loc="center right", labelcolor=INK2)
    fig.suptitle("S1.7  The prompting ladder on both games, local vLLM stack",
                 fontsize=11.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    save(fig, "s1_7_ladder")


# ===========================================================================
# s1_8_persona
# ===========================================================================
def s1_8_persona():
    rows = read("s1_8_persona_cross_stack.csv")
    fig, ax = plt.subplots(figsize=(10.4, 3.9))
    labels, y = [], 0
    for r in rows:
        b, p = f(r["unsteered_switching_point"]), f(r["persona_switching_point"])
        col = colour(r["persona_condition"])
        lab = f"{SHORT_STACK.get(r['stack'], r['stack'])} / {r['game']}\n{r['persona_condition']}"
        if not (np.isfinite(b) and np.isfinite(p)):
            ax.text(2, y, "switching point not identified on this grid "
                          "(the curve never crosses 0.5)", fontsize=8, color=MUTED,
                    va="center")
        else:
            ax.annotate("", xy=(p, y), xytext=(b, y),
                        arrowprops=dict(arrowstyle="-|>", color=col, linewidth=2.2,
                                        shrinkA=0, shrinkB=0))
            ax.plot([b], [y], "o", color=NAVY, markersize=8, markeredgecolor=SURFACE,
                    markeredgewidth=1.3, zorder=4)
            ax.plot([p], [y], "o", color=col, markersize=8, markeredgecolor=SURFACE,
                    markeredgewidth=1.3, zorder=4)
            ax.annotate(f"{b:.0f}", (b, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8, color=INK2)
            ax.annotate(f"{p:.0f}", (p, y), textcoords="offset points", xytext=(0, 9),
                        ha="center", fontsize=8, color=INK)
        labels.append(lab)
        y += 1
    ax.axvline(50, color=INK2, linewidth=1.2, linestyle=":", zorder=1)
    ax.text(51, len(rows) - 0.45, "utility floor n* = 50 (lottery only)", fontsize=8,
            color=INK2, va="bottom")
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(labels, fontsize=8)
    ax.invert_yaxis()
    from matplotlib.lines import Line2D
    ax.legend(handles=[
        Line2D([], [], marker="o", linestyle="", color=NAVY, markersize=8,
               label="unsteered, same stack"),
        Line2D([], [], marker="o", linestyle="", color=ORANGE, markersize=8,
               label="with the persona"),
    ], loc="lower right", fontsize=8, frameon=False, labelcolor=INK2)
    style(ax, "S1.8  The persona shift, within each stack",
          "switching point / acceptance threshold (tokens)", "")
    ax.set_xlim(0, 145)
    ax.set_ylim(len(rows) - 0.4, -0.7)
    fig.text(0.012, 0.955, "The two stacks use different persona text and different "
             "option labels; nothing here is differenced across them.",
             fontsize=8.5, color=INK2)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "s1_8_persona")


ALL = {
    "s1_1_dominated": s1_1_dominated,
    "s1_2_catch": s1_2_catch,
    "s1_3_switching": s1_3_switching,
    "s1_4_ceiling": s1_4_ceiling,
    "s1_5_judges": s1_5_judges,
    "s1_6_measures": s1_6_measures,
    "s1_7_ladder": s1_7_ladder,
    "s1_8_persona": s1_8_persona,
}
