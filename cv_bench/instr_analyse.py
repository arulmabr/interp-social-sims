"""Does the readout measure what free generation does? (FRIDAY item 2, analysis)

CPU only. Reads what `cv_bench/instr.py` produced on the GPU and sets the readout
beside free generation at the same grid points:

  crossing   where each curve passes 0.5, on the observed grid, by interpolation
  slope      free-generation frequency regressed on readout probability
  r          their correlation

The amendment's bar: crossings within one grid step (5 tokens) and a slope in
0.8-1.2. If both hold, the readout may be reported as primary in G4; if not,
sampled generation is primary and the readout is a secondary measurement.

Free generation is read three ways, because which one is used changes the answer:
`legacy` (last label mention), `strict` (first mention), and `decision` (a choice
only when the response states one). The comparison of record is against the
decision coding, since the other two assign choices to responses that never made
one -- see reports/G2_RESULTS.md.

    python -m cv_bench.instr_analyse
"""
from __future__ import annotations

import collections
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from cv_bench.s1_data import (interp_crossing, wilson, write_csv,
                              append_manifest, rel)
from cv_bench.instr import decision_code, LABELS, CAPS

RUNROOT = Path(os.environ.get("ICLR_RUNROOT",
                              "/orcd/data/gabrieli/001/guna23/iclr_risk_2027"))
OUT = RUNROOT / "instr"
G2DIR = RUNROOT / "g2_lambda0"
GRID_STEP = 5.0
SLOPE_BAND = (0.8, 1.2)


def jread(p: Path) -> List[dict]:
    if not p.exists():
        return []
    out = []
    for line in open(p):
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def g2_freqs(model: str, game: str) -> Dict[str, Dict[float, Tuple[int, int]]]:
    """Per level, (successes, n) under each of the three codings."""
    rows = jread(G2DIR / f"{model}_chat64_{game}.jsonl")
    out = {c: collections.defaultdict(lambda: [0, 0]) for c in
           ("legacy", "strict", "decision")}
    for r in rows:
        x = float(r["param_value"])
        if r["legacy_code"] in (0, 1):
            out["legacy"][x][0] += int(r["legacy_code"])
            out["legacy"][x][1] += 1
        sc = r.get("strict_choice")
        if sc in (0, 1):
            out["strict"][x][0] += int(sc)
            out["strict"][x][1] += 1
        d = decision_code(r.get("raw_generation", ""), game)
        if d["choice"] is not None:
            out["decision"][x][0] += int(d["choice"])
            out["decision"][x][1] += 1
    return {c: {x: tuple(v) for x, v in d.items()} for c, d in out.items()}


def readout_by_level(model: str, game: str, template: bool) -> Dict[float, float]:
    rows = jread(OUT / f"readout_grid_{model}.jsonl")
    return {float(r["value"]): float(r["p_positive"]) for r in rows
            if r["game"] == game and bool(r["template"]) == template}


def compare(x_read: Dict[float, float], counts: Dict[float, Tuple[int, int]],
            label: str) -> dict:
    """Crossing, slope and r for one (readout, free-generation) pair."""
    xs = sorted(set(x_read) & set(counts))
    if len(xs) < 4:
        return dict(comparison=label, n_levels=len(xs), enough=False)
    p = np.array([x_read[x] for x in xs])
    k = np.array([counts[x][0] for x in xs], dtype=float)
    n = np.array([counts[x][1] for x in xs], dtype=float)
    fq = np.divide(k, n, out=np.full_like(k, np.nan), where=n > 0)
    ok = np.isfinite(fq)
    xs_a = np.array(xs, dtype=float)
    cr_read = interp_crossing(list(xs_a), list(p))
    cr_free = interp_crossing(list(xs_a[ok]), list(fq[ok]))
    rec = dict(comparison=label, n_levels=len(xs), enough=True,
               crossing_readout=cr_read, crossing_free=cr_free,
               readout_sd=float(np.std(p)), free_sd=float(np.nanstd(fq)),
               n_trials=int(n.sum()))
    if cr_read is not None and cr_free is not None:
        d = abs(cr_read - cr_free)
        rec.update(crossing_gap=d, crossing_gap_steps=d / GRID_STEP,
                   crossings_within_one_step=bool(d <= GRID_STEP))
    else:
        rec.update(crossing_gap=None, crossing_gap_steps=None,
                   crossings_within_one_step=False)
    if np.std(p) > 1e-6 and np.nanstd(fq) > 1e-6:
        A = np.vstack([p[ok], np.ones(ok.sum())]).T
        sl, ic = np.linalg.lstsq(A, fq[ok], rcond=None)[0]
        rec.update(slope=float(sl), intercept=float(ic),
                   r=float(np.corrcoef(p[ok], fq[ok])[0, 1]),
                   slope_in_band=bool(SLOPE_BAND[0] <= sl <= SLOPE_BAND[1]))
    else:
        which = ("readout" if np.std(p) <= 1e-6 else "free generation")
        rec.update(slope=None, r=None, slope_in_band=False,
                   constant_column=which)
    rec["agrees"] = bool(rec.get("crossings_within_one_step") and
                         rec.get("slope_in_band"))
    return rec


def cap_table(model: str) -> List[dict]:
    """The decision rate by token cap, from the freegen phase."""
    rows = jread(OUT / f"freegen_{model}.jsonl")
    agg = collections.defaultdict(lambda: collections.Counter())
    for r in rows:
        key = (r["game"], r["cap"])
        agg[key]["n"] += 1
        agg[key][r["decision_kind"]] += 1
        agg[key]["truncated"] += int(bool(r.get("truncated")))
        agg[key]["legacy_coded"] += int(r.get("legacy_code", -1) in (0, 1))
    out = []
    for (game, cap), c in sorted(agg.items()):
        n = c["n"]
        out.append(dict(game=game, cap=cap, n=n,
                        decision_rate=(n - c["no_decision"]) / n,
                        bare_label=c["bare_label"] / n,
                        stated=c["stated"] / n,
                        no_decision=c["no_decision"] / n,
                        truncated=c["truncated"] / n,
                        legacy_assigns_a_choice=c["legacy_coded"] / n))
    return out


def figure(model: str, rows: List[dict]) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from cv_bench.s1_figures import (save, NAVY, ORANGE, TEAL, SURFACE, INK,
                                     INK2, MUTED, GRID)

    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.9))
    for ax, game in zip(axes, ("lottery", "ultimatum")):
        rd = readout_by_level(model, game, True)
        fr = g2_freqs(model, game)
        xs = sorted(rd)
        ax.plot(xs, [rd[x] for x in xs], color=NAVY, lw=2,
                label="readout, stem “Answer:”")
        for coding, colour in (("decision", ORANGE), ("legacy", TEAL)):
            c = fr[coding]
            gx = sorted(c)
            gy = [c[x][0] / c[x][1] if c[x][1] else np.nan for x in gx]
            ax.plot(gx, gy, color=colour, lw=1.8, ls="--" if coding == "legacy" else "-",
                    marker="o" if coding == "decision" else "s", ms=3.4,
                    label=f"free generation, {coding} coding")
        ax.axhline(0.5, color=MUTED, lw=0.8, ls=":")
        ax.set_title(game, color=INK, fontsize=11)
        ax.set_xlabel("reward" if game == "lottery" else "offer", color=INK2)
        ax.set_ylim(-0.03, 1.03)
        ax.grid(True, color=GRID, lw=0.6)
        ax.set_facecolor(SURFACE)
        for s in ax.spines.values():
            s.set_color(GRID)
    axes[0].set_ylabel("P(risky) / P(accept)", color=INK2)
    axes[0].legend(frameon=False, fontsize=7.5, loc="upper left")
    fig.suptitle("The readout against free generation, unsteered, same grid",
                 color=INK, fontsize=11.5)
    fig.tight_layout()
    save(fig, "instr_readout_vs_free")


def main() -> int:
    model = "llama"
    rows: List[dict] = []
    for game in ("lottery", "ultimatum"):
        for template in (True, False):
            rd = readout_by_level(model, game, template)
            if not rd:
                continue
            for coding, counts in g2_freqs(model, game).items():
                rec = compare(rd, counts, f"{game}|template={template}|{coding}")
                rec.update(model=model, game=game, template=template, coding=coding,
                           free_source="G2 chat64")
                rows.append(rec)
    caps = cap_table(model)
    if rows:
        write_csv("instr_agreement.csv", rows,
                  ["model", "game", "template", "coding", "free_source", "n_levels",
                   "n_trials", "enough", "crossing_readout", "crossing_free",
                   "crossing_gap", "crossing_gap_steps", "crossings_within_one_step",
                   "slope", "intercept", "r", "slope_in_band", "agrees",
                   "readout_sd", "free_sd", "constant_column", "comparison"])
    if caps:
        write_csv("instr_cap.csv", caps,
                  ["game", "cap", "n", "decision_rate", "bare_label", "stated",
                   "no_decision", "truncated", "legacy_assigns_a_choice"])
    for r in rows:
        print(f"{r['comparison']:42s} crossing {str(r.get('crossing_readout')):>8.8s} vs "
              f"{str(r.get('crossing_free')):>8.8s}  slope {str(r.get('slope')):>8.8s}  "
              f"r {str(r.get('r')):>7.7s}  agrees={r.get('agrees')}")
    for c in caps:
        print(f"cap {c['game']:9s} {c['cap']:4d}  decision {c['decision_rate']:.3f}  "
              f"legacy-codes {c['legacy_assigns_a_choice']:.3f}  "
              f"truncated {c['truncated']:.3f}")
    try:
        figure(model, rows)
    except Exception as e:
        print(f"figure skipped: {type(e).__name__}: {e}")
    ent = []
    for r in rows:
        if not r.get("enough"):
            continue
        tag = f"INSTR.{r['game']}.tpl{int(r['template'])}.{r['coding']}"
        src = [rel(OUT / "readout_grid_llama.jsonl"),
               rel(G2DIR / f"llama_chat64_{r['game']}.jsonl")]
        if r.get("slope") is not None:
            ent.append((f"{tag}.slope", round(r["slope"], 4),
                        "free-generation frequency on readout probability",
                        src, "cv_bench/instr_analyse.py"))
        if r.get("crossing_gap") is not None:
            ent.append((f"{tag}.crossing_gap_steps", round(r["crossing_gap_steps"], 3),
                        "gap between the two crossings, in grid steps", src,
                        "cv_bench/instr_analyse.py"))
    for c in caps:
        ent.append((f"INSTR.cap.{c['game']}.{c['cap']}.decision_rate",
                    round(c["decision_rate"], 4),
                    "share of generations that state a choice",
                    [rel(OUT / "freegen_llama.jsonl")], "cv_bench/instr_analyse.py"))
    if ent:
        append_manifest(ent)
        print(f"manifest += {len(ent)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
