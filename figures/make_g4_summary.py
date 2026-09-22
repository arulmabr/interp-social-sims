"""Generates figures/g4_summary.{pdf,png}.

Run from the repository root:  python figures/make_g4_summary.py
Data: results/S/s1/ (the table view of this figure).
Style and the validated palette: cv_bench/s1_figures.py.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cv_bench.g4_figure import build

if __name__ == "__main__":
    build()
