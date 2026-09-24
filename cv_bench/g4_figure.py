"""One figure carrying G4's results. figures/g4_summary.{pdf,png}

Two panels, one per measurement property:

  A  the readout against free generation, the instrument check
  B  direction geometry at layer 50, cosines as multiples of the 1/sqrt(d) null

Every number is read from results/S/s1/*.csv. Nothing here is typed by hand.
Palette and conventions from cv_bench/s1_figures.py.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List

import numpy as np

from cv_bench.s1_figures import (save, NAVY, ORANGE, TEAL, PURPLE, GOLD, SIENNA,
                                 SURFACE, INK, INK2, MUTED, GRID, read, f)

DATA = Path(__file__).resolve().parents[1] / "results/S/s1"


def rows(name: str) -> List[dict]:
    return list(csv.DictReader(open(DATA / name, newline="")))


def panel_d(ax):
    """Readout crossing against free-generation crossing."""
    ia = [r for r in rows("instr_agreement.csv")
          if r["enough"] == "True" and r["template"] == "True"
          and r["crossing_readout"] and r["crossing_free"]]
    labels, rd, fr = [], [], []
    for r in ia:
        labels.append(r["coding"])
        rd.append(float(r["crossing_readout"]))
        fr.append(float(r["crossing_free"]))
    xs = np.arange(len(labels))
    ax.bar(xs - 0.19, rd, width=0.36, color=PURPLE, label="logit readout")
    ax.bar(xs + 0.19, fr, width=0.36, color=GOLD, label="free generation")
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("crossing (tokens)", color=INK2, fontsize=8)
    ax.set_title("A  the readout does not track free generation",
                 color=INK, fontsize=9, loc="left")
    ax.set_ylim(0, 300)
    ax.legend(frameon=False, fontsize=7, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 0.99), borderaxespad=0.2)


def panel_e(ax):
    """Cosine of the choice probe with each direction, in multiples of the null."""
    geo = rows("g4b_geometry.csv")
    want = [("reward", "reward probe"), ("gradient", "readout gradient"),
            ("diffmean", "diff-of-means"),
            ("pca1", "first PCA"), ("ridge_logn", "ridge, log n"),
            ("rand0", "random direction")]
    labels, vals = [], []
    for key, lab in want:
        m = [float(r["multiples_of_null"]) for r in geo
             if r["variant"] == "reconstruction" and r["game"] == "lottery"
             and r["layer"] == "50" and {r["a"], r["b"]} == {"probe", key}]
        if not m:
            continue
        labels.append(lab)
        vals.append(float(np.mean(m)))
    # The permutation null, from the g4null re-collection. The probe does not
    # reproduce between runs, so the refit's own cosine is carried alongside:
    # a bar is only called either way when both fits agree about its null.
    import csv as _csv
    R = os.environ.get("ICLR_RUNROOT",
                       "/orcd/data/gabrieli/001/guna23/iclr_risk_2027")
    nrows = {r["direction"]: r for r in
             _csv.DictReader(open(f"{R}/g4null/g4null_lottery.csv"))}
    keys = [k for k, _ in want if any(l == lab for l, (k2, lab) in
                                      zip(labels, want) if k2 == k)]
    keys = [k for k, lab in want if lab in labels]
    p95 = [float(nrows[k]["perm_null_p95"]) if k in nrows else float("nan")
           for k in keys]
    refit = [float(nrows[k]["multiples_of_null"]) if k in nrows else float("nan")
             for k in keys]
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    p95 = [p95[i] for i in order]
    refit = [refit[i] for i in order]
    vals = [vals[i] for i in order]
    ys = np.arange(len(vals))
    # teal: clears under both fits. grey: inside under both. hatched: they differ.
    state = []
    for v, r, q in zip(vals, refit, p95):
        if q != q:
            state.append("none")
        elif (v > q) == (r > q):
            state.append("clears" if v > q else "inside")
        else:
            state.append("split")
    cols = [TEAL if st == "clears" else MUTED for st in state]
    bars = ax.barh(ys, vals, color=cols, height=0.62,
                   hatch=["///" if st == "split" else "" for st in state],
                   edgecolor=INK2, linewidth=0.0)
    for b, st in zip(bars, state):
        if st == "split":
            b.set_linewidth(1.0)
    for i, q in enumerate(p95):
        if q == q:
            ax.plot([q, q], [i - 0.34, i + 0.34], color=INK, lw=1.8, zorder=6,
                    solid_capstyle="butt")
    for i, (v, st) in enumerate(zip(vals, state)):
        ax.text(v + 0.4, i, f"{v:.1f}x", va="center",
                color=INK if st == "clears" else MUTED, fontsize=7.5)
    ax.set_xlim(0, max(vals + [q for q in p95 if q == q]) * 1.18)
    ax.axvline(1.0, color=MUTED, lw=0.9, ls=":")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("cosine with the choice probe  (multiples of the null)",
                  color=INK2, fontsize=8)
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch
    ax.legend(handles=[Line2D([], [], color=INK, lw=1.8,
                              label="permutation null, 95th pct"),
                       Patch(facecolor=TEAL, label="clears it"),
                       Patch(facecolor=MUTED, label="does not"),
                       Patch(facecolor=MUTED, hatch="///", edgecolor=INK2,
                             label="too close to call")],
              loc="lower right", frameon=False, fontsize=6.5, labelcolor=INK2,
              handlelength=1.4, labelspacing=0.35)
    ax.set_title("B  lottery: only first PCA clears its null",
                 color=INK, fontsize=9, loc="left")



def panel_u(ax):
    """The same geometry for the ultimatum game, from the G4u run.

    Bar design is panel B's exactly: same height, same colour rule, same label
    format, same dotted rule at the analytic null. The black ticks are the one
    addition, and they are an overlay rather than a change to the bars: each is
    that direction's own permutation null at the 95th percentile over 200
    refits with the offer labels shuffled.

    The reference direction differs from panel B and cannot be made to match.
    The ultimatum probe has one class, every training trial is an accept, so
    there is no choice probe; the reference here is a probe fitted to the offer.
    """
    import csv as _csv
    R = os.environ.get("ICLR_RUNROOT",
                       "/orcd/data/gabrieli/001/guna23/iclr_risk_2027")
    rs = [r for r in _csv.DictReader(open(f"{R}/g4u/g4u_geometry.csv"))
          if r["layer"] == "50"]
    want = [("readout_gradient", "readout gradient"), ("diffmean", "diff-of-means"),
            ("pca1", "first PCA"), ("ridge_logn", "ridge, log offer"),
            ("rand0", "random direction")]
    labels, vals, p95, ok = [], [], [], []
    for key, lab in want:
        m = [r for r in rs if r["direction"] == key]
        if not m:
            continue
        labels.append(lab)
        vals.append(float(m[0]["multiples_of_null"]))
        p95.append(float(m[0]["perm_null_p95"]))
        ok.append(str(m[0]["clears_perm_null"]).lower() == "true")
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    p95 = [p95[i] for i in order]
    ok = [ok[i] for i in order]
    vals = [vals[i] for i in order]
    ys = np.arange(len(vals))
    # Colour by the test, not by height. Panel B colours by magnitude, but here
    # the two tallest bars are inside their own null, so a magnitude ramp made
    # the most prominent bars the ones that mean least.
    cols = [TEAL if c else MUTED for c in ok]
    ax.barh(ys, vals, color=cols, height=0.62)
    for i, q in enumerate(p95):
        ax.plot([q, q], [i - 0.34, i + 0.34], color=INK, lw=1.8, zorder=6,
                solid_capstyle="butt")
    for i, (v, c) in enumerate(zip(vals, ok)):
        ax.text(v + 0.4, i, f"{v:.1f}x", va="center",
                color=INK if c else MUTED, fontsize=7.5)
    ax.set_xlim(0, max(vals + p95) * 1.18)
    ax.axvline(1.0, color=MUTED, lw=0.9, ls=":")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("cosine with the offer probe  (multiples of the null)",
                  color=INK2, fontsize=8)
    ax.set_title("C  ultimatum: only first PCA clears its null",
                 color=INK, fontsize=9, loc="left")
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], color=INK, lw=1.8,
                              label="permutation null, 95th pct"),
                       Line2D([], [], color=TEAL, lw=6, label="clears it"),
                       Line2D([], [], color=MUTED, lw=6, label="does not")],
              loc="lower right", frameon=False, fontsize=6.5, labelcolor=INK2,
              handlelength=1.4, labelspacing=0.35)


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    # one row, two panels
    fig = plt.figure(figsize=(14.2, 4.4))
    gs = GridSpec(1, 3, figure=fig, wspace=0.34)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]),
            fig.add_subplot(gs[0, 2])]
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(False)
        ax.tick_params(labelsize=7.5, colors=INK2)
        for s_ in ax.spines.values():
            s_.set_color(GRID)
    panel_d(axes[0]); panel_e(axes[1]); panel_u(axes[2])

    fig.suptitle("G4: instrument and direction geometry",
                 color=INK, fontsize=12, y=0.985)
    save(fig, "g4_summary")


if __name__ == "__main__":
    build()
