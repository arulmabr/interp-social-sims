"""Layer-matched probe steering comparison runner.

Addresses the reviewer's "uneven experimental controls" point: the SAE steers at
layer 50 while the probes were CV-selected to layer 48, so the probe-vs-SAE
head-to-head confounds the method with a two-layer depth gap. This rebuilds the
preference probes at fixed layers (48 and 50 by default) with an otherwise
identical procedure and reports steering efficacy for each, so the comparison can
be made at the SAE's own layer. See experiments/layer_comparison_llama.py.

Usage (full, mirrors the paper's psychometric settings):
    python -m Probes.run_layer_comparison --model llama --outdir runs/layer_cmp \
        --layers 48 50 --n-agents 40

Fast smoke run (a few targets, fewer agents; validates the pipeline end-to-end):
    python -m Probes.run_layer_comparison --model llama --outdir runs/layer_cmp_fast \
        --layers 48 50 --n-agents 8 --n-agents-calib 6 \
        --lottery-targets 68 124 181 --ultimatum-targets 40 60

Then read runs/<outdir>/layer_comparison/comparison_summary.json for the verdict.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiments import layer_comparison_llama
from .models import load


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", choices=["llama"], default="llama",
                        help="Only Llama has the 48-vs-50 probe/SAE layer gap.")
    parser.add_argument("--outdir", required=True, type=Path)
    parser.add_argument("--layers", type=int, nargs="+", default=[48, 50],
                        help="Fixed layers to rebuild + steer at (default: 48 50).")
    parser.add_argument("--n-agents", type=int, default=None,
                        help="Agents per grid cell in the final sweep (default: config value, 40).")
    parser.add_argument("--n-agents-calib", type=int, default=12,
                        help="Agents per cell during lambda calibration (default: 12).")
    parser.add_argument("--lottery-targets", type=int, nargs="+", default=None,
                        help="Override lottery switching-point targets (default: config).")
    parser.add_argument("--ultimatum-targets", type=int, nargs="+", default=None,
                        help="Override ultimatum acceptance-threshold targets (default: config).")
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    model = load(args.model)
    summary = layer_comparison_llama.run(
        model=model,
        outdir=args.outdir,
        layers=args.layers,
        n_agents=args.n_agents,
        n_agents_calib=args.n_agents_calib,
        lottery_targets=args.lottery_targets,
        ultimatum_targets=args.ultimatum_targets,
    )
    print(json.dumps(summary.get("cross_layer", summary), indent=2))


if __name__ == "__main__":
    main()
