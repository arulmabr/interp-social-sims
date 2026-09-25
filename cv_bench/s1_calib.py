"""Achieved against target switching point, the forward view of the calibration.

`figure_11_dose_response_*` in the released data reports the lambda a bracketed
search returned for each target. That is the inverse: it says what the search
selected, and a search returns a number whether or not it arrived. The forward
question is whether the switching point landed where it was aimed, and the
psychometric curves answer it directly.

Each point is one calibration target. Its x is the target switching point and
its y is the 0.5 crossing interpolated from the raw per-level counts, 40 agents
per level. The diagonal is perfect calibration, so distance from it is the
calibration error in tokens.

    python figures/make_s1_calib.py
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
PROBE = ROOT / "Probes/raw_data/probe_results_final.json"

KEYS = {48: "figure_7_psychometric_curves_llama",
        50: "figure_7_psychometric_curves_llama_layer50"}
XF = {"lottery": "risky_reward_tokens", "ultimatum": "offer_amount_tokens"}
YF = {"lottery": "raw_fraction_risky", "ultimatum": "raw_fraction_accept"}


def _crossing(xs: List[float], ys: List[float]) -> Optional[float]:
    """First upward crossing of 0.5, linearly interpolated between grid points."""
    for i in range(len(xs) - 1):
        a, b = ys[i], ys[i + 1]
        if (a - 0.5) * (b - 0.5) <= 0 and b != a:
            return xs[i] + (0.5 - a) * (xs[i + 1] - xs[i]) / (b - a)
    return None


def achieved() -> Dict[Tuple[str, int], List[dict]]:
    """Per game and layer, the achieved crossing at each calibration target."""
    d = json.loads(PROBE.read_text())
    out: Dict[Tuple[str, int], List[dict]] = {}
    for layer, key in KEYS.items():
        rows = d[key]["per_agent_rows"] if "per_agent_rows" in d[key] else None
        rows = d[key]["data"]
        for game in ("lottery", "ultimatum"):
            sub = [r for r in rows if r["game"] == game]
            if not sub:
                continue
            recs = []
            for t in sorted({r["target_switching_point_tokens"] for r in sub}):
                cell = sorted((r for r in sub if r["target_switching_point_tokens"] == t),
                              key=lambda r: r[XF[game]])
                c = _crossing([r[XF[game]] for r in cell], [r[YF[game]] for r in cell])
                if c is None:
                    continue
                recs.append(dict(target=float(t), achieved=float(c),
                                 error=float(c - t), n_levels=len(cell),
                                 n_agents=int(cell[0]["n_agents"]),
                                 lam=float(cell[0]["lambda_calibrated"])))
            out[(game, layer)] = recs
    return out


def build():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from cv_bench.s1_figures import (save, style, NAVY, ORANGE, SURFACE, INK,
                                     INK2, MUTED)

    a = achieved()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.6))
    for ax, game, title in ((axes[0], "lottery", "Lottery Game"),
                            (axes[1], "ultimatum", "Ultimatum Game")):
        series = [(48, NAVY, "o"), (50, ORANGE, "s")]
        pts = [r for L, _, _ in series for r in a.get((game, L), [])]
        lo = min(min(r["target"], r["achieved"]) for r in pts) - 8
        hi = max(max(r["target"], r["achieved"]) for r in pts) + 8
        # the diagonal is perfect calibration; recessive, behind the marks
        ax.plot([lo, hi], [lo, hi], color=MUTED, lw=1.0, zorder=1)
        # below the line and horizontal: rotated onto it, the line struck it through
        span = hi - lo
        ax.text(lo + span * 0.62, lo + span * 0.46, "perfect calibration",
                fontsize=7.5, color=MUTED, ha="center", va="top")
        for L, col, mk in series:
            rs = a.get((game, L), [])
            if not rs:
                continue
            err = np.abs([r["error"] for r in rs])
            # The two layers land on top of each other almost everywhere, so the
            # second is drawn open rather than filled. Offsetting it would move
            # the points off their own coordinates, which is the thing the
            # diagonal is there to measure.
            face = col if L == 48 else "none"
            ax.plot([r["target"] for r in rs], [r["achieved"] for r in rs],
                    mk, markerfacecolor=face, markeredgecolor=col,
                    markersize=9 if L == 50 else 7, markeredgewidth=1.8,
                    linestyle="none", zorder=3 if L == 48 else 4,
                    label=f"layer {L}   mean error {err.mean():.1f} tokens")
        ax.set_xlim(lo, hi); ax.set_ylim(lo, hi)
        ax.set_aspect("equal", adjustable="box")
        style(ax, title, "target switching point (tokens)",
              "achieved switching point (tokens)" if game == "lottery" else "")
        ax.legend(frameon=False, fontsize=7.6, loc="upper left",
                  labelcolor=INK2, handletextpad=0.4)
    fig.suptitle("Calibration lands where it is aimed: achieved against target",
                 color=INK, fontsize=12, y=0.98)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "s1_calibration")


if __name__ == "__main__":
    build()
