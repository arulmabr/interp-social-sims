"""figures/g4u_summary.{pdf,png} -- the ultimatum counterpart of G4's panel B.

Every number is read from the G4u run directory. Nothing here is typed by hand.

Panel A is the acceptance curve on the pre-registered offer grid. It is the
reason panel B measures what it measures: with the curve flat at the top there
is no accept-against-reject contrast, so no choice probe.

Panel B places each candidate direction against the **offer probe**, in
multiples of the 1/sqrt(d) null, mirroring the lottery panel's layout.
"""
from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from cv_bench.s1_figures import (GRID, INK, INK2, MUTED, NAVY, SURFACE, TEAL,
                                 GOLD, PURPLE, SIENNA, style)

ROOT = Path(__file__).resolve().parents[1]
FIGS = ROOT / "figures"
RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "g4u"

PANEL_LAYER = 50          # the lottery panel is layer 50; match it
LABEL = {
    "diffmean": "diff-of-means",
    "pca1": "first PCA",
    "ridge_logn": "ridge, log offer",
    "readout_gradient": "readout gradient",
    "rand0": "random direction",
    "rand1": "random direction 2",
}
COLOUR = {
    "diffmean": TEAL, "pca1": NAVY, "ridge_logn": NAVY,
    "readout_gradient": MUTED, "rand0": MUTED, "rand1": MUTED,
}


def _rows(name: str) -> List[dict]:
    with open(OUT / name, newline="") as fh:
        return list(csv.DictReader(fh))


def make() -> Path:
    geo = [r for r in _rows("g4u_geometry.csv")
           if int(r["layer"]) == PANEL_LAYER]
    curve = _rows("g4u_acceptance.csv")
    if not geo or not curve:
        raise SystemExit("g4u: no rows; run --stage build first")

    fig, axes = plt.subplots(1, 3, figsize=(16.4, 4.4),
                             gridspec_kw={"width_ratios": [1.05, 1.15, 0.9]})

    # --- A: the acceptance curve -------------------------------------------
    ax = axes[0]
    x = [float(r["offer"]) for r in curve]
    y = [float(r["p_accept"]) for r in curve]
    ax.plot(x, y, marker="o", markersize=4.5, linewidth=1.8, color=NAVY,
            markeredgecolor=SURFACE, markeredgewidth=1.1, zorder=3)
    ax.axhline(0.5, color=MUTED, linewidth=0.9, linestyle=(0, (2, 3)), zorder=1)
    ax.axvline(50, color=INK2, linewidth=1.0, linestyle=":", zorder=1)
    ax.annotate("half the pie", (50, 0.06), fontsize=7.5, color=INK2,
                ha="left", va="bottom", xytext=(3, 0), textcoords="offset points")
    ax.set_ylim(-0.03, 1.03)
    style(ax, "A  the model accepts every offer on the grid",
          "offer (tokens out of 100)", "P(accept)")

    # --- B: direction geometry ---------------------------------------------
    ax = axes[1]
    geo = sorted(geo, key=lambda r: float(r["multiples_of_null"]))
    names = [r["direction"] for r in geo]
    vals = [float(r["multiples_of_null"]) for r in geo]
    bars = ax.barh(range(len(geo)), vals, height=0.62,
                   color=[COLOUR.get(n, NAVY) for n in names], zorder=3)
    ax.axvline(1.0, color=INK2, linewidth=1.0, linestyle=":", zorder=2)
    for i, (b, v) in enumerate(zip(bars, vals)):
        ax.annotate(f"{v:.1f}x", (b.get_width(), i), fontsize=8.5, color=INK,
                    va="center", xytext=(4, 0), textcoords="offset points")
    ax.set_yticks(range(len(geo)))
    ax.set_yticklabels([LABEL.get(n, n) for n in names], fontsize=8.5,
                       color=INK2)
    ax.set_xlim(0, max(vals) * 1.22)
    style(ax, "B  what the offer probe is close to",
          f"cosine with the offer probe  (multiples of the null), layer {PANEL_LAYER}")

    # --- C: what the panels establish --------------------------------------
    ax = axes[2]
    ax.axis("off")
    n_lvl = len(curve)
    lo = min(float(r["p_accept"]) for r in curve)
    acc = float(geo[0]["offer_probe_train_accuracy"])
    blocks = [
        ("What each panel establishes", None),
        ("A  There is no choice to probe",
         f"Acceptance never falls below {lo:.2f} across all {n_lvl} offers, "
         "including 10 tokens out of 100. With one class there is no "
         "accept-against-reject contrast, so the lottery panel's choice probe "
         "has no counterpart here."),
        ("B  Read only the gradient bar as evidence",
         "The top three directions are fitted to the SAME "
         f"{n_lvl} activation vectors as the reference, so their agreement is "
         "largely shared fitting rather than a shared offer signal. The "
         "readout gradient is the one direction built by another procedure, "
         "and it lands with the random controls, which is what shows the high "
         "bars are inflated."),
        ("Not pre-registered",
         f"Exploratory. {n_lvl} points in 8,192 dimensions, no held-out split, "
         f"so the reference probe's {acc:.2f} training accuracy is separable "
         "by construction. A permutation null over the offer labels is the "
         "test that would make the high bars interpretable; it has not run."),
    ]
    yy = 0.97
    for head, body in blocks:
        ax.text(0.0, yy, head, fontsize=(11.5 if body is None else 10),
                color=INK, va="top", fontweight="bold", transform=ax.transAxes)
        yy -= 0.09 if body is None else 0.065
        if body:
            ax.text(0.02, yy, body, fontsize=8.6, color=INK2, va="top",
                    wrap=True, transform=ax.transAxes)
            yy -= 0.075 * (1 + len(body) // 95)

    fig.suptitle("G4u: the ultimatum game, instrument and direction geometry",
                 fontsize=12.5, color=INK, x=0.02, ha="left")
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    FIGS.mkdir(parents=True, exist_ok=True)
    fig.patch.set_facecolor(SURFACE)
    for ext in ("pdf", "png"):
        fig.savefig(FIGS / f"g4u_summary.{ext}", dpi=300, bbox_inches="tight",
                    facecolor=SURFACE)
    plt.close(fig)
    print(f"[g4u] wrote {FIGS / 'g4u_summary.png'}", flush=True)
    return FIGS / "g4u_summary.png"


if __name__ == "__main__":
    make()
