#!/bin/bash
#SBATCH --job-name=cvb_zoo_check
#SBATCH --partition=mit_normal
#SBATCH --account=mit_amf_advanced_cpu
#SBATCH --qos=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=00:30:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/cvb_zoo_check_%j.out
#SBATCH --error=logs/cvb_zoo_check_%j.err
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
python -m cv_bench.estimator.recovery --dump-zoo
