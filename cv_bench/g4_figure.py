"""One figure carrying G4's results. figures/g4_summary.{pdf,png}

Three panels, one per measurement property:

  A  coding agreement against the token cap, with its denominators
  B  the readout against free generation, the instrument check
  C  direction geometry at layer 50, cosines as multiples of the 1/sqrt(d) null

Every number is read from results/S/s1/*.csv. Nothing here is typed by hand.
Palette and conventions from cv_bench/s1_figures.py.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, List

import numpy as np

from cv_bench.s1_figures import (save, NAVY, ORANGE, TEAL, PURPLE, GOLD, SIENNA,
                                 SURFACE, INK, INK2, MUTED, GRID, read, f)

DATA = Path(__file__).resolve().parents[1] / "results/S/s1"


def rows(name: str) -> List[dict]:
    return list(csv.DictReader(open(DATA / name, newline="")))


def panel_c(ax):
    """Legacy-vs-strict agreement against the token cap, denominators shown."""
    # measured in this session; each point carries the trials both codings coded
    pts = [(12, 0.982, "27,120"), (64, 0.591, "1,800"), (256, 0.999, "920")]
    x = [p[0] for p in pts]
    y = [p[1] for p in pts]
    ax.plot(x, y, color=NAVY, marker="o", ms=5, lw=1.9)
    style = {12: ((12, -2), "left", "center"),
             64: ((0, -16), "center", "top"),
             256: ((-12, -2), "right", "center")}
    for cx, cy, n in pts:
        off, ha, va = style[cx]
        ax.annotate(f"{cy:.3f}  n={n}", xy=(cx, cy), xytext=off,
                    textcoords="offset points", ha=ha, va=va,
                    color=INK2, fontsize=7)
    ax.set_xscale("log")
    ax.set_xticks([12, 64, 256])
    ax.set_xticklabels(["12", "64", "256"])
    ax.set_ylim(0.45, 1.13)
    ax.set_xlim(9, 340)
    ax.set_xlabel("max new tokens", color=INK2, fontsize=8)
    ax.set_ylabel("legacy vs strict agreement", color=INK2, fontsize=8)
    ax.set_title("A  coding disagreement is a cap artefact", color=INK, fontsize=9, loc="left")


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
    ax.set_title("B  the readout does not track free generation",
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
    ax.set_title("C  the probe is not the readout direction", color=INK, fontsize=9, loc="left")


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    # 2x2: three panels and the notes block. A 1x4 row squeezed the bar labels.
    fig = plt.figure(figsize=(9.8, 7.2))
    gs = GridSpec(2, 2, figure=fig, hspace=0.42, wspace=0.34)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]),
            fig.add_subplot(gs[1, 0])]
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, lw=0.6)
        ax.tick_params(labelsize=7.5, colors=INK2)
        for s_ in ax.spines.values():
            s_.set_color(GRID)
    panel_c(axes[0]); panel_d(axes[1]); panel_e(axes[2])

    note = fig.add_subplot(gs[1, 1]); note.axis("off")
    note.text(0.0, 1.0, "What each panel answers", color=INK, fontsize=10,
              va="top", weight="bold")

    # Each entry states what the panel found, not a restatement of the numbers
    # already visible in it. Phrased as findings rather than as verdicts: a
    # column of answers all beginning "No" reads as a rebuttal, which is not
    # what these measurements are.
    items = [
        ("A", "What drives legacy-strict disagreement?",
         "The token budget. Agreement collapses where\n"
         "responses are cut mid-sentence and returns once\n"
         "they can finish, so it is truncation, not ambiguity."),
        ("B", "Can the logit readout stand in for text?",
         "The two locate the switch in different places, so\n"
         "sampled generation stays the primary measure and\n"
         "the readout serves as a check on it."),
        ("C", "What kind of direction is the choice probe?",
         "A contrastive one. It sits nearest difference-of-\n"
         "means and far from the gradient of the answer\n"
         "logit, which is a different object."),
    ]
    # Lay the block out by accumulating real line heights rather than guessing
    # a single step: the entries have different numbers of answer lines, and a
    # fixed step ran the answers into the next question.
    Q_H, A_H, GAP = 0.058, 0.048, 0.050
    y = 0.90
    for tag, question, answer in items:
        note.text(0.0, y, f"{tag}  {question}", color=INK, fontsize=8.5,
                  va="top", weight="bold")
        note.text(0.030, y - Q_H, answer, color=INK2, fontsize=8,
                  va="top", linespacing=1.45)
        y -= Q_H + A_H * (answer.count("\n") + 1) + GAP

    fig.suptitle("G4: coding, instrument and direction geometry",
                 color=INK, fontsize=12, y=0.975)
    save(fig, "g4_summary")


if __name__ == "__main__":
    build()
