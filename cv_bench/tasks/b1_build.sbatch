#!/bin/bash
#SBATCH --job-name=cvb_b1_build
#SBATCH --partition=mit_normal
#SBATCH --account=mit_amf_advanced_cpu
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:20:00
#SBATCH --requeue
#SBATCH --output=logs/cvb_b1_build_%j.out
#SBATCH --error=logs/cvb_b1_build_%j.err

# B1 trial materialisation. CPU only: this consumes no GPU-hours against the
# shared 400 GPU-hour cap, which is totalled from sacct over the cvb_ prefix.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
echo "host=$(hostname) job=${SLURM_JOB_ID} start=$(date -Is)"
python -m pytest cv_bench/tests/test_tasks.py -q
python -m cv_bench.tasks.build --splits disc sel cal
echo "done=$(date -Is)"
