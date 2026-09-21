"""Generates figures/s1_2_catch.{pdf,png}.

Run from the repository root:  python figures/make_s1_2_catch.py
Data: results/S/s1/ (the table view of this figure).
Style and the validated palette: cv_bench/s1_figures.py.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cv_bench.s1_figures import s1_2_catch

if __name__ == "__main__":
    s1_2_catch()
