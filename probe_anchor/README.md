# probe_anchor

Code and analysis outputs for the probe and anchor work: the two planted-change
anchors, the direction geometry for both games, and the permutation null that
tests it.

## Layout

    code/anchors/   the anchors themselves
                    gradient.py        the answer-readout gradient anchor
                    lora.py            the LoRA anchor, trained to clone a
                                       synthetic decision maker
                    gate_b3.py         the gate the anchors have to pass
                    probe_vs_anchors.py, analysis_b33.py
                                       where the probe sits relative to them
                    numerics_fp32.py   the precision control
    code/           g4u.py             ultimatum direction geometry
                    g4u_figure.py      its figure
                    g4null.py          the permutation null
                    test_g4u.py        direction maths, no GPU
    code/lib/       the modules the above import: the probe rebuild, the
                    steering hook, the instrument check, the resumable writer
                    and the model loader
    data/           analysis outputs, 362 files

## Running it

Paths are environment variables rather than hard-coded. Set before use:

    export ICLR_RUNROOT=/path/to/your/run/outputs
    export HF_HOME=/path/to/your/huggingface/cache

The Slurm scripts also expect `SLURM_ACCOUNT` and `SLURM_PARTITION`.

## What the null does

`multiples_of_null` in the geometry tables is the cosine between two directions
divided by 1/sqrt(d), which is the standard deviation of the cosine between two
independent directions in d dimensions. That reference is not valid here,
because the probe and the difference of means and the first component and the
ridge are all fitted from the same activation matrix and therefore lie in its
span before any label signal is involved.

`permutation_null` in `g4u.py` and `g4null.py` measures the right reference. It
permutes the labels, refits every direction, and reports the 95th percentile of
the resulting cosines. A direction whose observed value sits inside that
distribution has not shown anything.

## What is not here

The LoRA checkpoints, which are 28 GB across 36 files and exceed what a git
repository should carry. `data/` holds every analysis output the figures and
tables are built from.
