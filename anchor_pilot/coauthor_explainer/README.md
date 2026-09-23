# Coauthor explanation package

Prepared with Codex from the saved experiment, with numerical claims checked
against the local code and analysis. No new model training or inference was run.

Read [ERRATA.md](ERRATA.md) and [COAUTHOR_CLARIFICATIONS.md](COAUTHOR_CLARIFICATIONS.md) first. The PDFs are historical snapshots; the probe-layer clarification came afterward.

Recommended sharing order:

1. Attach [the illustrated PDF](output/pdf/sae_preference_experiment_illustrated.pdf)
   for two introductory illustrations followed by the six-page visual walkthrough. It expands the terminology and explains the design,
   results, limitations, and the original-probe comparison gap.
2. Use `experiment_overview.png` for the overall result, or `why_bias_like.png`
   for the direct answer to why the measured pattern was described as bias-like.
3. Paste or adapt `MESSAGE_TO_COAUTHORS.md` as the accompanying Slack message.
4. Keep `METHODS_AND_CLAIM_BOUNDARIES.md` for technical questions. It includes
   equations, acceptance thresholds and differences from the original probes.

`figure_data.csv` contains the exact eight pairs plotted in the comparison.
`provenance.json` records source hashes; `QA.json` records verification.

The figure ranges span seeds/conditions, not confidence intervals. The bias
model's predictive advantage is not proof of a mechanism: it has seven fitted
parameters and uses the base-model responses; the restricted CPT fit has five.
The correct decision remains to defer the full SAE sweep with this setup.

Rebuild the PDF from the repository root with the bundled Python runtime:

```
python anchor_pilot/build_coauthor_explainer.py
```

The builder requires ReportLab and the macOS Arial fonts. PNGs are rendered from
the verified PDF using Poppler. Rebuilding does not run any GPU experiment.

## Image-generated illustrations

The two new illustrations were made with the built-in image-generation tool and visually inspected:

- `imagegen_experiment_overview.png`: independent action and intended preference anchors, matched dense/SAE steering comparison, robustness checks and bounded verdict.
- `imagegen_cpt_explained.png`: Cumulative Prospect Theory in plain language, with an illustrative gamble and the three main preference parameters.

Attach both images alongside the existing evidence PDF and Slack message. These are conceptual illustrations; arrows are schematic, not to scale, and the gamble is an example rather than measured data. The exact numerical evidence remains in the PDF and `figure_data.csv`. No new experiment was run.

`IMAGEGEN_PROMPTS.md` preserves the generation and correction prompts. `imagegen_manifest.json` records final assets and visual review. The local ZIP is not versioned; its report, message and final illustrations are included individually in this directory.

The historical `provenance.json` records the original PDF-generation inputs and hashes. Later publication edits and errata are reflected in Git history; the saved PDF bytes are unchanged.
