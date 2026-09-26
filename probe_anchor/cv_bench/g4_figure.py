"""One figure carrying G4's results. figures/g4_summary.{pdf,png}

Two panels, one per measurement property:

  A  direction geometry at layer 50, cosines as multiples of the 1/sqrt(d) null

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
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    ys = np.arange(len(vals))
    cols = [TEAL if v >= 10 else (NAVY if v >= 3 else MUTED) for v in vals]
    ax.barh(ys, vals, color=cols, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + 0.4, i, f"{v:.1f}x", va="center", color=INK, fontsize=7.5)
    ax.set_xlim(0, max(vals) * 1.22)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("cosine with the choice probe  (multiples of the null)",
                  color=INK2, fontsize=8)
    ax.set_title("A  Lottery Game", color=INK, fontsize=9, loc="left")



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
    # The ultimatum geometry is computed by code/g4u.py and released beside it.
    # $ICLR_RUNROOT points at the run tree when one is mounted; otherwise the
    # released copy under data/ is used, so this builds from a clean checkout.
    cands = []
    if os.environ.get("ICLR_RUNROOT"):
        cands.append(Path(os.environ["ICLR_RUNROOT"]) / "g4u/g4u_geometry.csv")
    cands.append(DATA.parents[2] / "data/g4u/g4u_geometry.csv")
    geo_u = next((c for c in cands if c.exists()), None)
    if geo_u is None:
        raise FileNotFoundError("g4u_geometry.csv: " + ", ".join(map(str, cands)))
    rs = [r for r in _csv.DictReader(open(geo_u))
          if r["layer"] == "50"]
    want = [("readout_gradient", "readout gradient"), ("diffmean", "diff-of-means"),
            ("pca1", "first PCA"), ("ridge_logn", "ridge, log offer"),
            ("rand0", "random direction")]
    labels, vals = [], []
    for key, lab in want:
        m = [r for r in rs if r["direction"] == key]
        if not m:
            continue
        labels.append(lab)
        vals.append(float(m[0]["multiples_of_null"]))
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    ys = np.arange(len(vals))
    cols = [TEAL if v >= 10 else (NAVY if v >= 3 else MUTED) for v in vals]
    ax.barh(ys, vals, color=cols, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + 0.4, i, f"{v:.1f}x", va="center", color=INK, fontsize=7.5)
    ax.set_xlim(0, max(vals) * 1.22)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("cosine with the offer probe  (multiples of the null)",
                  color=INK2, fontsize=8)
    ax.set_title("B  Ultimatum Game", color=INK, fontsize=9, loc="left")


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    # one row, two panels
    fig = plt.figure(figsize=(10.0, 4.4))
    gs = GridSpec(1, 2, figure=fig, wspace=0.32)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(False)
        ax.tick_params(labelsize=7.5, colors=INK2)
        for s_ in ax.spines.values():
            s_.set_color(GRID)
    panel_e(axes[0]); panel_u(axes[1])

    fig.suptitle("The steering probe: which directions it is closest to",
                 color=INK, fontsize=12, y=0.985)
    save(fig, "g4_summary")


if __name__ == "__main__":
    build()
