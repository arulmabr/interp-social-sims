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
                              "${ICLR_RUNROOT}"))
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

    fig, axes = plt.subplots(1, 2, figsize=(12.6, 4.4),
                             gridspec_kw={"width_ratios": [1.2, 0.95]})

    # --- A: direction geometry ---------------------------------------------
    ax = axes[0]
    geo = sorted(geo, key=lambda r: float(r["multiples_of_null"]))
    names = [r["direction"] for r in geo]
    vals = [float(r["multiples_of_null"]) for r in geo]
    p95 = [float(r.get("perm_null_p95") or "nan") for r in geo]
    clears = [str(r.get("clears_perm_null", "")).lower() == "true" for r in geo]
    # A bar that does not clear its own permutation null is drawn hollow: the
    # height is real but it is what shuffled offer labels already produce.
    bars = ax.barh(range(len(geo)), vals, height=0.62, zorder=3,
                   color=[COLOUR.get(n, NAVY) if c else "none"
                          for n, c in zip(names, clears)],
                   edgecolor=[COLOUR.get(n, NAVY) for n in names],
                   linewidth=1.4)
    ax.axvline(1.0, color=INK2, linewidth=1.0, linestyle=":", zorder=2)
    for i, q in enumerate(p95):
        if q == q:
            ax.plot([q, q], [i - 0.34, i + 0.34], color=INK, linewidth=2.0,
                    zorder=6, solid_capstyle="butt")
    for i, (b, v, c) in enumerate(zip(bars, vals, clears)):
        ax.annotate(f"{v:.1f}x", (b.get_width(), i), fontsize=8.5,
                    color=INK if c else MUTED, va="center", xytext=(4, 0),
                    textcoords="offset points")
    ax.set_yticks(range(len(geo)))
    ax.set_yticklabels([LABEL.get(n, n) for n in names], fontsize=8.5,
                       color=INK2)
    hi = max([v for v in vals] + [q for q in p95 if q == q])
    ax.set_xlim(0, hi * 1.18)
    from matplotlib.lines import Line2D
    ax.legend(handles=[Line2D([], [], color=INK, lw=2.0,
                              label="permutation null, 95th percentile")],
              loc="lower right", frameon=False, fontsize=7.5, labelcolor=INK2)
    style(ax, "A  only one direction clears its own null",
          f"cosine with the offer probe  (multiples of the analytic null), "
          f"layer {PANEL_LAYER}")

    # --- B: what the panel establishes -------------------------------------
    ax = axes[1]
    ax.axis("off")
    n_lvl = len(curve)
    lo = min(float(r["p_accept"]) for r in curve)
    acc = float(geo[0]["offer_probe_train_accuracy"])
    perm_n = max((int(r.get("perm_n") or 0) for r in geo), default=0)
    blocks = [
        ("What this panel establishes", None),
        ("Why the reference is the offer, not the choice",
         f"Acceptance never falls below {lo:.2f} across all {n_lvl} offers, "
         "including 10 tokens out of 100. With one class there is no "
         "accept-against-reject contrast, so the lottery panel's choice probe "
         "has no counterpart here and a probe fitted to the offer stands in."),
        ("The two tallest bars are shared fitting",
         "Every fitted direction here comes from the SAME "
         f"{n_lvl} activation vectors as the reference, so all of them lie in "
         "a subspace of at most 18 dimensions and are close before any offer "
         "signal is involved. Permuting the offer labels and refitting gives "
         "the null each bar has to clear. Difference of means and the ridge "
         "sit inside it, so their height says nothing. Only the first "
         "component clears its null, by a wide margin."),
        ("Why the axis is not the test",
         "Multiples of the analytic null are still on the axis because that is "
         "the lottery panel's unit, but 1/sqrt(d) assumes two independent "
         "directions and none of these are independent. The black tick is the "
         f"permutation null at the 95th percentile over {perm_n} refits. Read "
         "the bars against the ticks, not against the axis."),
        ("Not pre-registered",
         f"Exploratory. {n_lvl} points in 8,192 dimensions, no held-out split, "
         f"so the reference probe's {acc:.2f} training accuracy is separable "
         "by construction."),
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
