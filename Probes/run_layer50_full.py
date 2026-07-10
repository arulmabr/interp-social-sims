"""Regenerate all six Llama linear-probe figures at layer 50 (appendix control).

Companion to run_layer_comparison.py. Purely additive: it reuses the existing
layer-48 production runners with the model pinned to layer 50; no existing file
is modified and the layer-48 pipeline (`run_all`) is unaffected. See
experiments/layer50_full_llama.py for the six figures it regenerates and their
May/June PDF numbers.

Full run (regenerates all six; capability figures need the GPT-5 judge):
    export OPENAI_API_KEY=...          # GPT-5 judge, as in the layer-48 run
    export HF_TOKEN=...                # gated Llama weights
    python -m Probes.run_layer50_full --outdir runs/llama_layer50

Preference-only (Fig 4/8, 10/18, 11/19; no judge / API key needed):
    python -m Probes.run_layer50_full --outdir runs/llama_layer50_pref --skip-capability

The per-experiment JSONLs match the layer-48 schema (with probe_layer = 50), so
the layer-50 counterpart figures are produced by the same aggregation / figure
code used for the layer-48 run, pointed at this outdir.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .experiments import layer50_full_llama
from .models import load


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--outdir", required=True, type=Path)
    ap.add_argument("--layer", type=int, default=50,
                    help="Layer to pin every Llama probe to (default: 50, the SAE layer).")
    ap.add_argument("--skip-capability", action="store_true",
                    help="Regenerate only the 3 preference figures (no GPT-5 judge / API key).")
    args = ap.parse_args()

    model = load("llama")
    summary = layer50_full_llama.run(
        model, args.outdir, layer=args.layer, skip_capability=args.skip_capability)
    # Print the scalar fields; the nested per-runner dicts are in the summary json.
    print(json.dumps({k: v for k, v in summary.items() if not isinstance(v, dict)},
                     indent=2, default=str))


if __name__ == "__main__":
    main()
