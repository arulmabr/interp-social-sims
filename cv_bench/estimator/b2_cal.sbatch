#!/bin/bash
#SBATCH --job-name=cvb_b2_cal
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=03:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/cvb_b2_cal_%j.out
#SBATCH --error=logs/cvb_b2_cal_%j.err

# Author item 1: calibrate the B2 synthetic agents against the real model.
# Legacy labels only (item 7). Unbatched reads only (amendment item 5a).
# The numerical-noise floor is measured in THIS run, per D50.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
echo "host=$(hostname) job=${SLURM_JOB_ID} start=$(date -Is)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
python -m cv_bench.estimator.b2_cal --model llama70b \
  --noise-prompts 40 --noise-repeats 5 --gen-prompts 100
echo "done=$(date -Is)"
