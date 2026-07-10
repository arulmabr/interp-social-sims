"""Aggregate a layer-50 Llama probe run into the raw-results file schema.

Companion to run_layer50_full. The stock `aggregator.py` requires BOTH a Llama
and a Qwen run and emits all 13 figure keys; the layer-50 control only
regenerates the six Llama linear-probe figures. This helper builds just those
keys from the layer-50 run directory -- reusing `aggregator.py`'s tested builder
functions -- rewrites the figure-name captions from "layer 48" to "layer 50",
and flattens to a `probe_results_combined.csv`-schema CSV that the existing
figure scripts (`regenerate_all_figures.py` / `regen_from_rawdata.py`) read
directly (they filter by `probe_group`; only the six Llama figures are present,
the rest are skipped).

The flatten reproduces the shipped `probe_results_combined.csv` exactly, verified
by round-trip on the layer-48 data (22,651 rows; every per-(figure, section)
count and numeric-column sum identical).

No existing module is modified. Two modes:

`into-raw-data` (primary) -- merge layer 50 INTO the raw-results files so BOTH
layers live in the same `probe_results_final.json` / `probe_results_combined.csv`,
distinguishable by the `probe_layer` column (CSV) and `_layer50` key suffix
(JSON). Layer 48 is preserved (append-only, idempotent, with a one-time
`.layer48_backup`):
    python -m Probes.aggregate_layer50_llama into-raw-data --run-dir runs/llama_layer50

`single` -- write the layer-50 figures to their OWN files instead, leaving
raw_data untouched (guarded against clobbering the canonical files):
    python -m Probes.aggregate_layer50_llama single --run-dir runs/llama_layer50 \
        --out-json probe_results_layer50.json --out-csv probe_results_layer50_combined.csv

Then regenerate figures with the existing figure code (it filters by
`probe_group`; select a layer via the `probe_layer` column).
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List

from .aggregator import FIGURE_BUILDERS

# The seven Llama-probe builder keys (figure_9 has a brick + a stapler key that
# together make the single in-distribution capability figure).
LLAMA_KEYS = [k for k in FIGURE_BUILDERS if "_qwen" not in k]


def canonical_raw_path(name: str) -> Path:
    """Resolve a raw-results file to wherever it actually lives.

    The repo ships these files directly under Probes/ (no raw_data/ folder);
    some checkouts also keep a raw_data/ copy. Prefer raw_data/ when it exists,
    otherwise fall back to the top-level Probes/ file, so the merge targets the
    real files in either layout instead of creating a phantom folder.
    """
    here = Path(__file__).resolve().parent
    rd = here / "raw_data" / name
    return rd if rd.exists() else here / name

# Canonical leading columns of probe_results_combined.csv.
PREFIX_COLS = [
    "probe_group", "source_figure", "figure_name", "experiment_type", "data_section",
]


def _probe_group(row: Dict) -> str:
    g = row.get("game")
    return g if g in ("lottery", "ultimatum") else "creativity"


def _expand_scores(row: Dict) -> Dict:
    """Expand the nested judge-score dicts into the flat columns that
    combined.csv uses, matching the original flatten:

      scores={fluency,..}            -> scores_fluency, ...
      multi_judge_scores={judge:{scores:{..}, creativity_score}}
                                     -> mj_<judge>_<dim>, mj_<judge>_creativity_score

    The nested dicts themselves are dropped (their scalars now live in the flat
    columns). Rows without these keys (e.g. preference rows) pass through
    unchanged.
    """
    r = dict(row)
    scores = r.pop("scores", None)
    if isinstance(scores, dict):
        for dim, val in scores.items():
            r[f"scores_{dim}"] = val
    mj = r.pop("multi_judge_scores", None)
    if isinstance(mj, dict):
        for judge, payload in mj.items():
            sub = (payload or {}).get("scores", {}) or {}
            for dim, val in sub.items():
                r[f"mj_{judge}_{dim}"] = val
            if "creativity_score" in (payload or {}):
                r[f"mj_{judge}_creativity_score"] = payload["creativity_score"]
    return r


def build_layer50_json(run_dir: Path, layer: int = 50) -> Dict[str, Dict]:
    """Build the six Llama-probe figure keys from a layer-50 run dir.

    Reuses aggregator.py's builders, then rewrites the layer label in each
    figure_name so the caption reflects the layer the data was actually
    produced at.
    """
    top: Dict[str, Dict] = {}
    for key in LLAMA_KEYS:
        fig = FIGURE_BUILDERS[key](run_dir)
        if "figure_name" in fig:
            fig["figure_name"] = fig["figure_name"].replace("layer 48", f"layer {layer}")
        top[key] = fig
    return top


def flatten(top: Dict[str, Dict]) -> List[Dict]:
    """Flatten the figure JSON to combined.csv rows (data + per_agent_rows)."""
    rows: List[Dict] = []
    for key, fig in top.items():
        fn = fig.get("figure_name", "")
        et = fig.get("experiment_type", "")
        for section in ("data", "per_agent_rows"):
            for r in fig.get(section, []) or []:
                rows.append({
                    "probe_group": _probe_group(r),
                    "source_figure": key,
                    "figure_name": fn,
                    "experiment_type": et,
                    "data_section": section,
                    **_expand_scores(r),
                })
    return rows


def _fieldnames(rows: List[Dict], reference_csv: Path | None) -> List[str]:
    """Column order: match the reference combined.csv header when available so
    the output is schema-identical; otherwise derive from the rows."""
    if reference_csv and reference_csv.exists():
        # Use the shipped header verbatim so the output is schema-identical; any
        # row key outside it (e.g. a leftover nested dict) is dropped by the
        # writer's extrasaction="ignore".
        with open(reference_csv, newline="") as f:
            return next(csv.reader(f))
    cols = list(PREFIX_COLS)
    seen = set(cols)
    for r in rows:
        for k in r:
            if k not in seen:
                cols.append(k)
                seen.add(k)
    return cols


def write_combined_csv(rows: List[Dict], out_csv: Path, reference_csv: Path | None) -> None:
    fields = _fieldnames(rows, reference_csv)
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})


# The canonical layer-48 raw-results artifacts. Writing layer-50 output over
# these would destroy the layer-48 numbers, so it is refused by default.
CANONICAL_LAYER48_FILES = {"probe_results_final.json", "probe_results_combined.csv"}


def _assert_not_overwriting(paths, reference_csv: Path | None, force: bool) -> None:
    """Refuse to clobber the layer-48 raw-results files (unless force=True).

    The layer-50 run must land in its own files so both layers coexist and stay
    distinguishable by the probe_layer column; it must never overwrite layer 48.
    """
    if force:
        return
    ref = reference_csv.resolve() if reference_csv else None
    for p in paths:
        rp = Path(p).resolve()
        if rp.name in CANONICAL_LAYER48_FILES or (ref is not None and rp == ref):
            raise ValueError(
                f"Refusing to write layer-50 results to {rp}: that is a canonical "
                f"layer-48 raw-results file and would overwrite the layer-48 numbers. "
                f"Use a distinct path (e.g. probe_results_layer50.json / "
                f"probe_results_layer50_combined.csv), or pass force=True to override."
            )


def run(run_dir: Path, out_json: Path, out_csv: Path,
        layer: int = 50, reference_csv: Path | None = None, force: bool = False) -> Dict:
    _assert_not_overwriting([out_json, out_csv], reference_csv, force)
    top = build_layer50_json(run_dir, layer=layer)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    with open(out_json, "w") as f:
        json.dump(top, f, indent=2)
    rows = flatten(top)
    write_combined_csv(rows, out_csv, reference_csv)
    # Distinguishability check: every row must carry the layer it was produced
    # at, and this run must contain only `layer` (never mixed with layer 48).
    layers_present = sorted({r.get("probe_layer") for r in rows if r.get("probe_layer") is not None})
    return {
        "figures": list(top),
        "n_rows": len(rows),
        "out_json": str(out_json),
        "out_csv": str(out_csv),
        "probe_layer_requested": int(layer),
        "probe_layers_present_in_output": layers_present,
    }


def _read_csv_rows(path: Path) -> tuple[List[str], List[Dict]]:
    with open(path, newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def merge_into_raw_data(
    run_dir: Path,
    final_json: Path | None = None,
    combined_csv: Path | None = None,
    layer: int = 50,
    backup: bool = True,
) -> Dict:
    """Merge the layer-`layer` figures INTO the existing raw-results files, so
    both layers live in the SAME `probe_results_final.json` /
    `probe_results_combined.csv`.

    Distinguishability:
      * CSV -- layer-48 and layer-`layer` rows share the same `source_figure`
        keys and are told apart by the `probe_layer` column (48/17 vs `layer`),
        so a figure's two layers group-and-compare directly.
      * JSON -- layer-`layer` figures use `<key>_layer{layer}` keys (JSON object
        keys must be unique); the layer-48 keys are left exactly as they are.

    Non-destructive to layer 48:
      * The layer-48 rows/keys are carried over unchanged (append-only for the
        new layer); a preservation check asserts their count/keys are intact.
      * Idempotent: any previously merged layer-`layer` rows/keys are replaced,
        not duplicated, so re-running does not stack copies.
      * On the first merge a one-time backup of each file is written next to it
        (`<name>.layer48_backup`), preserving the pristine layer-48-only version.
    """
    import shutil

    final_json = final_json or canonical_raw_path("probe_results_final.json")
    combined_csv = combined_csv or canonical_raw_path("probe_results_combined.csv")
    suffix = f"_layer{layer}"

    # One-time pristine backup (never overwrite an existing backup).
    if backup:
        for p in (final_json, combined_csv):
            bak = p.with_suffix(p.suffix + ".layer48_backup")
            if not bak.exists():
                shutil.copy2(p, bak)

    layer50_top = build_layer50_json(run_dir, layer=layer)

    # ---- JSON: keep every non-suffixed (layer-48) key; replace suffixed ones ----
    with open(final_json) as f:
        merged_json = json.load(f)
    base_keys = [k for k in merged_json if not k.endswith(suffix)]
    merged_json = {k: merged_json[k] for k in base_keys}          # drop stale layer-N keys
    n_base_keys = len(merged_json)
    for k, v in layer50_top.items():
        merged_json[f"{k}{suffix}"] = v
    with open(final_json, "w") as f:
        json.dump(merged_json, f, indent=2)

    # ---- CSV: keep every non-layer-`layer` row; re-append fresh layer-`layer` ----
    header, existing = _read_csv_rows(combined_csv)
    base_rows = [r for r in existing if str(r.get("probe_layer")) != str(layer)]
    n_base_rows = len(base_rows)
    layer50_rows = flatten(layer50_top)
    with open(combined_csv, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, extrasaction="ignore", restval="")
        w.writeheader()
        for r in base_rows:
            w.writerow(r)
        for r in layer50_rows:
            w.writerow({k: ("" if v is None else v) for k, v in r.items()})

    # ---- preservation guarantees ----
    _, after = _read_csv_rows(combined_csv)
    after_base = [r for r in after if str(r.get("probe_layer")) != str(layer)]
    assert len(after_base) == n_base_rows, (
        f"layer-48 rows changed: {n_base_rows} -> {len(after_base)}")
    assert all(k in merged_json for k in base_keys), "a layer-48 JSON key went missing"

    layers_present = sorted({str(r.get("probe_layer")) for r in after if r.get("probe_layer") not in (None, "")})
    return {
        "final_json": str(final_json),
        "combined_csv": str(combined_csv),
        "layer48_rows_preserved": n_base_rows,
        "layer50_rows_added": len(layer50_rows),
        "csv_rows_total": len(after),
        "json_keys_layer48": n_base_keys,
        "json_keys_added": len(layer50_top),
        "probe_layers_present_in_output": layers_present,
        "backup_written": bool(backup),
    }


def main() -> None:
    # Resolve to wherever the raw-results files actually live (Probes/ on the
    # repo; Probes/raw_data/ in checkouts that keep that copy).
    def_final = canonical_raw_path("probe_results_final.json")
    def_csv = canonical_raw_path("probe_results_combined.csv")
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)

    # Primary mode: merge both layers INTO the shipped raw-results files.
    m = sub.add_parser("into-raw-data",
                       help="Merge layer-50 into probe_results_final.json / _combined.csv "
                            "so both layers live in the same files (layer 48 preserved).")
    m.add_argument("--run-dir", required=True, type=Path,
                   help="Layer-50 run directory (from run_layer50_full).")
    m.add_argument("--final-json", type=Path, default=def_final)
    m.add_argument("--combined-csv", type=Path, default=def_csv)
    m.add_argument("--layer", type=int, default=50)
    m.add_argument("--no-backup", action="store_true",
                   help="Skip the one-time .layer48_backup of each raw-results file.")

    # Alternate mode: write the layer-50 figures to their OWN files (guarded).
    s = sub.add_parser("single",
                       help="Write the layer-50 figures to separate files (does not "
                            "touch the raw-results files).")
    s.add_argument("--run-dir", required=True, type=Path)
    s.add_argument("--out-json", required=True, type=Path)
    s.add_argument("--out-csv", required=True, type=Path)
    s.add_argument("--layer", type=int, default=50)
    s.add_argument("--reference-csv", type=Path, default=def_csv,
                   help="Header template so the output is schema-identical.")
    s.add_argument("--force", action="store_true",
                   help="Override the guard against overwriting the canonical layer-48 files.")

    args = ap.parse_args()
    if args.mode == "into-raw-data":
        summary = merge_into_raw_data(
            args.run_dir, final_json=args.final_json, combined_csv=args.combined_csv,
            layer=args.layer, backup=not args.no_backup)
    else:
        summary = run(args.run_dir, args.out_json, args.out_csv,
                      layer=args.layer, reference_csv=args.reference_csv, force=args.force)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
