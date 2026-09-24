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
    for i, (a, b) in enumerate(zip(rd, fr)):
        ax.text(i, 262, f"{abs(a-b)/5:.0f} steps", ha="center",
                color=INK2, fontsize=7, clip_on=True)
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
    order = np.argsort(vals)
    labels = [labels[i] for i in order]
    vals = [vals[i] for i in order]
    ys = np.arange(len(vals))
    cols = [TEAL if v >= 10 else (NAVY if v >= 3 else MUTED) for v in vals]
    ax.barh(ys, vals, color=cols, height=0.62)
    for i, v in enumerate(vals):
        ax.text(v + 0.4, i, f"{v:.1f}x", va="center", color=INK, fontsize=7.5)
    ax.set_xlim(0, max(vals) * 1.22)
    ax.axvline(1.0, color=MUTED, lw=0.9, ls=":")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("cosine with the choice probe  (multiples of the null)",
                  color=INK2, fontsize=8)
    ax.set_title("B  the probe is not the readout direction", color=INK, fontsize=9, loc="left")



def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    # one row: two panels and the notes block
    fig = plt.figure(figsize=(12.6, 4.4))
    gs = GridSpec(1, 3, figure=fig, wspace=0.34)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(False)
        ax.tick_params(labelsize=7.5, colors=INK2)
        for s_ in ax.spines.values():
            s_.set_color(GRID)
    panel_d(axes[0]); panel_e(axes[1])

    note = fig.add_subplot(gs[0, 2]); note.axis("off")
    note.text(0.0, 1.0, "What each panel establishes", color=INK, fontsize=10,
              va="top", weight="bold")

    # Claim first, evidence under it. Findings, not verdicts.
    items = [
        ("A", "Sampled generation stays the primary measure",
         "The readout and free generation locate the switch\n"
         "in different places, so the readout is a check on\n"
         "text rather than a substitute for it."),
        ("B", "The choice probe is a contrastive direction",
         "It sits nearest difference-of-means and far from\n"
         "the gradient of the answer logit, which is a\n"
         "different object."),
    ]
    Q_H, A_H, GAP = 0.075, 0.062, 0.070
    y = 0.88
    for tag, question, answer in items:
        note.text(0.0, y, f"{tag}  {question}", color=INK, fontsize=8.0,
                  va="top", weight="bold")
        note.text(0.030, y - Q_H, answer, color=INK2, fontsize=8,
                  va="top", linespacing=1.45)
        y -= Q_H + A_H * (answer.count("\n") + 1) + GAP

    fig.suptitle("G4: instrument and direction geometry (lottery)",
                 color=INK, fontsize=12, y=0.985)
    save(fig, "g4_summary")


if __name__ == "__main__":
    build()
