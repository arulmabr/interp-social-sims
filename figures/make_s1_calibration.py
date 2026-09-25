"""Generates figures/s1_calibration.{pdf,png}.

Run from the repository root:  python figures/make_s1_calibration.py
Data: Probes/raw_data/probe_results_final.json, the psychometric curves.
Style and the validated palette: cv_bench/s1_figures.py.
"""
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from cv_bench.s1_calib import build

if __name__ == "__main__":
    build()
