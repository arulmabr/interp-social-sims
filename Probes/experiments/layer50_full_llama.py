"""Full layer-50 regeneration of the six Llama linear-probe figures.

Reviewer control (companion to layer_comparison_llama.py). The six Llama-probe
figures were plotted at the CV-selected layer 48, while the SAE steers at layer
50. This runner regenerates all six at layer 50 so each layer-48 figure has a
matched-layer counterpart for the appendix.

PURELY ADDITIVE: no existing experiment module or the layer-48 pipeline is
modified. Layer 50 is pinned by locally swapping the model config
(`probe_layer=50`, `layer_sweep_range=(50, 50)`) so that

  * every probe (preference AND capability) is trained/calibrated/steered/
    captured at layer 50 -- the degenerate sweep range makes build_*_probe's
    cross-validated layer sweep able to pick only layer 50, and
  * every per-row `probe_layer` field is written as 50,

and the existing production runners are then reused read-only. The swap is
undone in a `finally` block, so a later layer-48 run via `run_all` is
unaffected; the shared `config.LLAMA` dataclass is never mutated (only a
`replace()` copy is installed on the model instance for the duration).

Regenerated figures (May PDF / June PDF numbering) and their runner:
- preference psychometric      (Fig 4  / Fig 8)   psychometric_llama
- probe lambda dose-response   (Fig 10 / Fig 18)  dose_response_llama
- probe-score tracking         (Fig 11 / Fig 19)  probe_tracking_llama
- in-distribution capability   (Fig 6  / Fig 11)  capability_llama (brick + stapler)
- cross-object creativity      (Fig 9  / Fig 20)  four_objects_llama
- cross-object generalization  (Fig 12 / Fig 21)  cross_object_llama

Outputs: the same per-experiment subdirectories the layer-48 runners produce
(`psychometric_llama/`, `dose_response_llama/`, `capability_llama/`, ...),
written under `outdir`, every row's `probe_layer` = 50. The JSONL schema is
identical to the layer-48 run, so the existing aggregation / figure-regen code
plots the layer-50 counterparts directly.

The capability figures call the GPT-5 judge (needs OPENAI_API_KEY), exactly as
the layer-48 capability runs do. Pass `skip_capability=True` to regenerate only
the three preference figures (no judge / API key required).
"""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import Dict

from .. import config
from ..models import Wrapped
from ._common import build_preference_probe
from . import (
    capability_llama,
    cross_object_llama,
    dose_response_llama,
    four_objects_llama,
    probe_tracking_llama,
    psychometric_llama,
)

DEFAULT_LAYER = 50


def run(
    model: Wrapped,
    outdir: Path,
    layer: int = DEFAULT_LAYER,
    skip_capability: bool = False,
) -> Dict:
    outdir.mkdir(parents=True, exist_ok=True)
    layer = int(layer)
    orig_cfg = model.cfg
    summary: Dict = {"probe_layer": layer, "outdir": str(outdir)}
    try:
        # Pin every layer-dependent path to `layer`. `probe_layer` drives
        # activation capture, steering-hook placement, and row metadata; the
        # degenerate `layer_sweep_range` forces build_*_probe's CV layer sweep
        # (used by the capability runners) to select only `layer`.
        model.cfg = replace(orig_cfg, probe_layer=layer, layer_sweep_range=(layer, layer))

        # ---- Preference probes (shared by the 3 preference figures) ----
        lottery_probe = build_preference_probe(model, game="lottery")
        ultimatum_probe = build_preference_probe(model, game="ultimatum")
        lottery_probe.save(outdir / f"lottery_probe_layer{layer}.pkl")
        ultimatum_probe.save(outdir / f"ultimatum_probe_layer{layer}.pkl")
        assert lottery_probe.layer == layer and ultimatum_probe.layer == layer, \
            f"preference probe not pinned to layer {layer}"
        summary["lottery_probe_cv_accuracy"] = float(lottery_probe.cv_accuracy)
        summary["ultimatum_probe_cv_accuracy"] = float(ultimatum_probe.cv_accuracy)

        # ---- Fig 4/8, 10/18, 11/19 (preference; no judge needed) ----
        summary["psychometric"] = psychometric_llama.run(
            model, outdir, lottery_probe, ultimatum_probe)          # Fig 4 / Fig 8
        summary["dose_response"] = dose_response_llama.run(
            model, outdir, lottery_probe, ultimatum_probe)          # Fig 10 / Fig 18
        summary["probe_tracking"] = probe_tracking_llama.run(
            model, outdir, lottery_probe, ultimatum_probe)          # Fig 11 / Fig 19

        # ---- Fig 6/11, 9/20, 12/21 (capability; needs the GPT-5 judge) ----
        if skip_capability:
            summary["capability_skipped"] = True
        else:
            summary["capability_brick"] = capability_llama.run_brick(
                model, outdir)                                      # Fig 6 / Fig 11
            summary["capability_stapler"] = capability_llama.run_stapler_product_innovation(
                model, outdir)                                      # Fig 6 / Fig 11
            summary["four_objects"] = four_objects_llama.run(
                model, outdir)                                      # Fig 9 / Fig 20
            summary["cross_object"] = cross_object_llama.run(
                model, outdir)                                      # Fig 12 / Fig 21
    finally:
        model.cfg = orig_cfg

    # The shared config object must be pristine: a subsequent layer-48 run must
    # see probe_layer 48 and the full sweep range.
    assert model.cfg is orig_cfg
    assert config.LLAMA.probe_layer == 48, "config.LLAMA was mutated!"

    with open(outdir / f"layer{layer}_run_summary.json", "w") as f:
        json.dump(summary, f, indent=2, default=str)
    return summary
