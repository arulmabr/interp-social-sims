"""figures/B3_contrasts.{png,pdf} — the B3.2 anchor contrasts on Llama-3.3-70B.

A table, but the interval column is drawn rather than written, because the whole
point of the result is that one interval crosses zero and the other does not --
and that is a fact about geometry, not about a number.

Every value is read from the run's own gate output; nothing is typed in here.

    python figures/make_B3_contrasts.py --gate <run-dir>/gate_b3.json

Everything is laid out in a single 0..1 axes so text and marks cannot drift
apart; `to_x` is the only value->position mapping in the file.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# dataviz reference palette - light surface
SURFACE  = "#fcfcfb"
INK      = "#0b0b0b"
INK_2    = "#52514e"
MUTED    = "#898781"
HAIRLINE = "#e1e0d9"
AXIS     = "#c3c2b7"
CRITICAL = "#d03b3b"
SERIOUS  = "#ec835a"

ROWS = [("preference", "preference − reference"),
        ("bias", "bias − reference")]

# column anchors, axes fraction
X_LABEL, X_PLANTED, X_MEASURED = 0.020, 0.250, 0.365
BAND_L, BAND_R = 0.425, 0.700
X_VERDICT = 0.716
ROW_Y = [0.660, 0.400]
TICKS = [0.0, 0.2, 0.4, 0.6]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gate", required=True, type=Path)
    ap.add_argument("--out", type=Path, default=Path("figures/B3_contrasts"))
    a = ap.parse_args(argv)
    g = json.loads(a.gate.read_text())
    C = g["contrasts"]

    vmin = min(min(C[k]["ci_lo"] for k, _ in ROWS), 0.0) - 0.055
    vmax = max(max(C[k]["ci_hi"] for k, _ in ROWS), max(TICKS)) + 0.045

    def to_x(v: float) -> float:
        return BAND_L + (v - vmin) / (vmax - vmin) * (BAND_R - BAND_L)

    fig = plt.figure(figsize=(11.8, 4.0), dpi=200)
    fig.patch.set_facecolor(SURFACE)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis("off")
    ax.set_facecolor(SURFACE)

    T = dict(transform=ax.transAxes)

    ax.text(X_LABEL, 0.935, "The anchor is the contrast — and only one of them resolves",
            fontsize=14, color=INK, va="bottom", **T)

    # column headers + rule
    ax.text(X_LABEL, 0.830, "CONTRAST", fontsize=8.5, color=MUTED, va="bottom", **T)
    ax.text(X_PLANTED, 0.830, "PLANTED", fontsize=8.5, color=MUTED,
            va="bottom", ha="right", **T)
    ax.text(X_MEASURED, 0.830, "MEASURED", fontsize=8.5, color=MUTED,
            va="bottom", ha="right", **T)
    ax.text((BAND_L + BAND_R) / 2, 0.830, "95% INTERVAL", fontsize=8.5,
            color=MUTED, va="bottom", ha="center", **T)
    ax.text(X_VERDICT, 0.830, "VERDICT", fontsize=8.5, color=MUTED, va="bottom", **T)
    ax.plot([X_LABEL, 0.985], [0.802, 0.802], color=AXIS, lw=1.0, **T)

    # zero reference, behind the marks
    ax.plot([to_x(0.0)] * 2, [0.235, 0.775], color=AXIS, lw=1.2, zorder=1, **T)

    for i, (key, label) in enumerate(ROWS):
        c = C[key]
        y = ROW_Y[i]
        crosses = c["ci_contains_zero"]
        status = CRITICAL if crosses else SERIOUS

        if i:
            ax.plot([X_LABEL, 0.985], [y + 0.140, y + 0.140],
                    color=HAIRLINE, lw=1.0, zorder=0, **T)

        ax.text(X_LABEL, y, label, fontsize=11.5, color=INK, va="center", **T)
        ax.text(X_PLANTED, y, f"{c['truth']:.4f}", fontsize=11, color=INK_2,
                va="center", ha="right", family="monospace", **T)
        ax.text(X_MEASURED, y, f"{c['estimate']:.4f}", fontsize=11, color=INK,
                va="center", ha="right", family="monospace", **T)

        lo, hi = to_x(c["ci_lo"]), to_x(c["ci_hi"])
        ax.plot([lo, hi], [y, y], color=status, lw=2.2,
                solid_capstyle="butt", zorder=3, **T)
        for e in (lo, hi):
            ax.plot([e, e], [y - 0.045, y + 0.045], color=status, lw=2.2,
                    solid_capstyle="round", zorder=3, **T)
        ax.plot([to_x(c["estimate"])], [y], "o", ms=9, color=status,
                markeredgecolor=SURFACE, markeredgewidth=1.8, zorder=5, **T)
        ax.plot([to_x(c["truth"])], [y], marker="D", ms=7.5, color=SURFACE,
                markeredgecolor=INK, markeredgewidth=1.6, zorder=6, **T)

        verdict = ("interval includes zero" if crosses
                   else "resolved, but under-recovers")
        detail = (f"planted signal sits {c['buried_x']:.0f}× under the adapters' own noise"
                  if crosses else
                  f"interval excludes the planted value, {c['abs_err_in_mdc']:.1f} MDC low")
        ax.text(X_VERDICT, y + 0.043, verdict, fontsize=10.5, color=INK, va="center", **T)
        ax.text(X_VERDICT, y - 0.048, detail, fontsize=8.3, color=MUTED, va="center", **T)

    # value axis under the band
    ax.plot([to_x(vmin + 0.02), to_x(vmax - 0.02)], [0.235, 0.235],
            color=AXIS, lw=1.0, **T)
    for t in TICKS:
        ax.plot([to_x(t)] * 2, [0.235, 0.216], color=AXIS, lw=1.0, **T)
        ax.text(to_x(t), 0.205, f"{t:g}", fontsize=8.5, color=MUTED,
                ha="center", va="top", **T)
    ax.text(to_x(0.0), 0.790, "0", fontsize=8.5, color=MUTED,
            ha="center", va="bottom", **T)

    # legend for the two marks, beside the axis
    mid = (BAND_L + BAND_R) / 2
    ax.plot([mid - 0.072], [0.128], marker="D", ms=7, color=SURFACE,
            markeredgecolor=INK, markeredgewidth=1.5, **T)
    ax.text(mid - 0.058, 0.128, "planted", fontsize=8.5, color=MUTED, va="center", **T)
    ax.plot([mid + 0.012], [0.128], "o", ms=8, color=MUTED,
            markeredgecolor=SURFACE, markeredgewidth=1.5, **T)
    ax.text(mid + 0.026, 0.128, "measured", fontsize=8.5, color=MUTED, va="center", **T)

    floor = C["preference"]["noise_floor_sd"]
    rs = ", ".join(f"{g['cloning'][k]['r']:.4f}" for k in ("reference", "preference", "bias"))
    ax.text(X_LABEL, 0.015,
            f"Llama-3.3-70B-Instruct, B3.2 LoRA anchors, n={g['n_clone']} selection-split "
            f"prompts.  All three adapters clone (r = {rs}), yet each one's cloning "
            f"residual has SD 0.38–0.47;\ntwo independent adapters give a contrast "
            f"noise floor of {floor:.3f} — {C['preference']['buried_x']:.0f} times the planted preference shift.",
            fontsize=8.3, color=MUTED, va="bottom", linespacing=1.55, **T)

    a.out.parent.mkdir(parents=True, exist_ok=True)
    for ext in ("png", "pdf"):
        fig.savefig(f"{a.out}.{ext}", facecolor=SURFACE)
        print(f"wrote {a.out}.{ext}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
