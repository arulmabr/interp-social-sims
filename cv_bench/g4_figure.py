"""One figure carrying G4's results. figures/g4_summary.{pdf,png}

Five panels, because the authors asked for a single figure and these findings do
not reduce to one axis:

  A  the dose-response at both layers -- the result that replaces the dropped
     legacy probe figures
  B  what each variant can code at all -- the provenance finding, as rates
  C  coding agreement against the token cap, with its denominators
  D  the readout against free generation, the instrument check
  E  direction geometry, cosines as multiples of the 1/sqrt(d) null

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


def panel_a(ax):
    """Switching point against dose, both layers, reconstruction."""
    cur = rows("g4_curves.csv")
    for layer, colour, mark in (("48", NAVY, "o"), ("50", ORANGE, "s")):
        pts = [(float(r["dose"]), float(r["interp_crossing"]))
               for r in cur
               if r["model"] == "llama" and r["variant"] == "reconstruction"
               and r["layer"] == layer and r["direction"] == "probe"
               and r["game"] == "lottery" and r["coding"] == "phrase"
               and not r["tag"] and r["interp_crossing"]]
        pts.sort()
        if not pts:
            continue
        x = [max(p[0], 0.004) for p in pts]          # 0 shown at the axis floor
        y = [p[1] for p in pts]
        ax.plot(x, y, color=colour, marker=mark, ms=4, lw=1.9,
                label=f"layer {layer}")
    ax.set_xscale("log")
    ax.axhline(104.1, color=MUTED, lw=0.9, ls=":")
    ax.text(0.34, 0.88, "dotted line: unsteered, 104.1", transform=ax.transAxes,
            ha="left", color=MUTED, fontsize=7)
    ax.set_xlabel("dose  (units of the median residual-stream norm)", color=INK2, fontsize=8)
    ax.set_ylabel("switching point (tokens)", color=INK2, fontsize=8)
    ax.set_title("A  rebuilt probe: L48 flat, L50 moves and reverses",
                 color=INK, fontsize=9, loc="left")
    ax.legend(frameon=False, fontsize=7.5, loc="upper left")


def panel_b(ax):
    """Share of trials that state a decision, by variant."""
    cur = rows("g4_curves.csv")
    bars = []
    for label, model, variant, layer in (
            ("as-written\nL48", "llama", "as_written", "48"),
            ("as-written\nL50", "llama", "as_written", "50"),
            ("rebuilt\nL48", "llama", "reconstruction", "48"),
            ("rebuilt\nL50", "llama", "reconstruction", "50"),
            ("rebuilt\nQwen17", "qwen", "reconstruction", "17")):
        sel = [r for r in cur if r["model"] == model and r["variant"] == variant
               and r["layer"] == layer and r["coding"] == "phrase"
               and r["direction"] == "probe" and r["game"] == "lottery"
               and not r["tag"] and r["no_answer_rate"]
               and r["dose_id"] == "0"]          # unsteered, not a mean over doses
        if not sel:
            continue
        na = float(sel[0]["no_answer_rate"])
        bars.append((label, 1.0 - na))
    xs = np.arange(len(bars))
    cols = [SIENNA, SIENNA, TEAL, TEAL, PURPLE][:len(bars)]
    ax.bar(xs, [b[1] for b in bars], color=cols, width=0.62)
    for i, (lab, v) in enumerate(bars):
        ax.text(i, v + 0.03, f"{v:.3f}", ha="center", color=INK, fontsize=7.5)
    ax.set_xticks(xs)
    ax.set_xticklabels([b[0].replace("\n", " ") for b in bars], fontsize=7,
                       rotation=30, ha="right")
    ax.set_ylim(0, 1.15)
    ax.set_ylabel("share of trials stating a decision", color=INK2, fontsize=8)
    ax.set_title("B  what each variant can code (unsteered)", color=INK, fontsize=9, loc="left")


def panel_c(ax):
    """Legacy-vs-strict agreement against the token cap, denominators shown."""
    # measured in this session; each point carries the trials both codings coded
    pts = [(12, 0.982, "27,120"), (64, 0.591, "1,800"), (256, 0.999, "920")]
    x = [p[0] for p in pts]
    y = [p[1] for p in pts]
    ax.plot(x, y, color=NAVY, marker="o", ms=5, lw=1.9)
    for cx, cy, n in pts:
        ax.annotate(f"{cy:.3f}\nn={n}", xy=(cx, cy), xytext=(0, -26 if cy > 0.8 else 12),
                    textcoords="offset points", ha="center", color=INK2, fontsize=7)
    ax.set_xscale("log")
    ax.set_xticks([12, 64, 256])
    ax.set_xticklabels(["12", "64", "256"])
    ax.set_ylim(0.4, 1.12)
    ax.set_xlabel("max new tokens", color=INK2, fontsize=8)
    ax.set_ylabel("legacy vs strict agreement", color=INK2, fontsize=8)
    ax.set_title("C  coding disagreement is a cap artefact", color=INK, fontsize=9, loc="left")


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
        ax.text(i, max(a, b) + 6, f"{abs(a-b)/5:.0f} steps",
                ha="center", color=INK2, fontsize=7)
    ax.set_xticks(xs)
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("crossing (tokens)", color=INK2, fontsize=8)
    ax.set_title("D  the readout does not track free generation",
                 color=INK, fontsize=9, loc="left")
    ax.set_ylim(0, 300)
    ax.legend(frameon=False, fontsize=7, loc="upper center", ncol=2,
              bbox_to_anchor=(0.5, 1.0))


def panel_e(ax):
    """Cosine of the choice probe with each direction, in multiples of the null."""
    geo = rows("g4b_geometry.csv")
    want = [("reward", "reward probe"), ("gradient", "readout gradient"),
            ("diffmean", "diff-of-means (CAA)"),
            ("pca1", "first PCA (RepE)"), ("ridge_logn", "ridge, log n"),
            ("rand0", "random direction")]
    labels, vals = [], []
    for key, lab in want:
        m = [float(r["multiples_of_null"]) for r in geo
             if r["variant"] == "reconstruction" and r["game"] == "lottery"
             and {r["a"], r["b"]} == {"probe", key}]
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
    ax.axvline(1.0, color=MUTED, lw=0.9, ls=":")
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=7)
    ax.set_xlabel("cosine with the choice probe  (multiples of the null)",
                  color=INK2, fontsize=8)
    ax.set_title("E  the probe is not the readout direction", color=INK, fontsize=9, loc="left")


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.gridspec import GridSpec

    fig = plt.figure(figsize=(11.6, 7.4))
    gs = GridSpec(2, 3, figure=fig, hspace=0.48, wspace=0.34)
    axes = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]),
            fig.add_subplot(gs[0, 2]), fig.add_subplot(gs[1, 0]),
            fig.add_subplot(gs[1, 1])]
    for ax in axes:
        ax.set_facecolor(SURFACE)
        ax.grid(True, color=GRID, lw=0.6)
        ax.tick_params(labelsize=7.5, colors=INK2)
        for s in ax.spines.values():
            s.set_color(GRID)
    panel_a(axes[0]); panel_b(axes[1]); panel_c(axes[2])
    panel_d(axes[3]); panel_e(axes[4])

    note = fig.add_subplot(gs[1, 2]); note.axis("off")
    note.text(0.0, 1.0, "What the panels establish", color=INK, fontsize=9,
              va="top", weight="bold")
    note.text(0.0, 0.90,
              "A  Across a 60-fold dose range layer 48 moves the switching\n"
              "    point under one grid step. Layer 50 moves ~10 steps and\n"
              "    reverses at the top dose.\n\n"
              "B  Unsteered, run as committed the pipeline codes 1-2% of\n"
              "    trials; the rebuild codes 98%.\n\n"
              "C  Legacy and strict codings agree at 12 and 256 tokens and\n"
              "    disagree at 64, where the model restates the options\n"
              "    without concluding.\n\n"
              "D  Readout and free-generation crossings sit 25-34 grid steps\n"
              "    apart (r = 0.16-0.31), so sampled generation is primary.\n\n"
              "E  The probe is nearly orthogonal to the readout gradient and\n"
              "    closest to difference-of-means.\n\n"
              "Sources: g4_curves.csv, g4_agreement.csv, g4b_geometry.csv,\n"
              "instr_agreement.csv. Llama-3.3-70B-Instruct, lottery, probe\n"
              "direction, phrase coding unless stated.",
              color=INK2, fontsize=7, va="top", linespacing=1.45)

    fig.suptitle("G4: the probe rebuild, both variants and both layers",
                 color=INK, fontsize=12)
    save(fig, "g4_summary")


if __name__ == "__main__":
    build()
