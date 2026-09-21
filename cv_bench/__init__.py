"""cv_bench — analysis code for the ICLR extension.

Shared machine. The S1 analyses solve millions of 2x2 systems, and on a
multi-socket login node OpenBLAS will happily spread each one across every core
it can see: measured at 394% CPU for a single-threaded workload. These variables
must be set before numpy is imported, which is what this file is for, so they
take effect however a submodule is reached. Override deliberately with
CV_BENCH_THREADS if a future task really is parallel.
"""
import os as _os

_n = _os.environ.get("CV_BENCH_THREADS", "1")
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
           "NUMEXPR_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):
    _os.environ.setdefault(_v, _n)
