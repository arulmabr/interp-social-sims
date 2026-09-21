# cv_bench

Analysis code for the ICLR extension. Nothing here reads or writes the four legacy directories
(`cleaned/`, `Probes/`, `Revised Prompting/`, `SAE/`); they are inputs only.

## Regenerating every number

`MANIFEST.csv` is append-only, so a full regeneration starts by removing it. Order matters only in that
`s0_recon.py` writes the header.

```bash
cd <repo root>
rm -f MANIFEST.csv
python -m cv_bench.s0_recon        # S0: 234 values, results/S/s0_numbers.json, goodfire_labels.json
python -m cv_bench.s1_behaviour    # S1.1, S1.2, S1.3, S1.8   (~15 min, the bootstraps)
python -m cv_bench.s1_probe        # S1.4
python -m cv_bench.s1_capability   # S1.5
python -m cv_bench.s1_ladder       # S1.7 + paper_patches/appendix_prompts.md
python -m cv_bench.s1_text         # S1.6  (runs a 22M-parameter encoder on CPU, ~3 min)
for f in figures/make_s1_*.py; do python "$f"; done
```

Total 517 manifest rows. Every value carries its inputs and the git SHA it was computed at.

## Notes

- **Threads.** `__init__.py` pins BLAS to one thread before numpy is imported. The S1 bootstraps solve
  millions of 2×2 systems, and on a shared login node OpenBLAS otherwise spreads each across every core
  it can see — measured at 394% CPU for a single-threaded workload. Override with `CV_BENCH_THREADS`.
- **No pandas or scikit-learn in the S0 path.** This machine has scikit-learn 1.2.2 against
  `Probes/requirements.txt`'s floor of 1.4, and the user slice caps memory at 10 GB. `s1_capability.py`
  does use pandas and statsmodels for the mixed model.
- **Logistic fits work on per-level binomial counts**, not on individual trials. The estimate is
  identical and each bootstrap draw costs ~35 rows instead of ~1,400.
- **A switching point is reported only where the measured curve crosses 0.5 inside the grid.** Curves
  that never cross carry `crosses_half_on_grid = False` and blank estimates rather than an
  extrapolation with an interval hundreds of tokens wide.
- **Intervals resample reward levels, not trials.** The 40 "agents" at one reward level are i.i.d.
  draws from one prompt; both intervals are reported and the reward-level one is primary.
