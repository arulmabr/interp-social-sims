#!/bin/bash
#SBATCH --job-name=cvb_g4u
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:2
#SBATCH --time=02:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/cvb_g4u_%j.out
#SBATCH --error=logs/cvb_g4u_%j.err

# G4u collection: ultimatum activations at layers 48 and 50, one model load,
# both layers hooked in the same forward pass. 19 offers, 8 samples each.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
echo "host=$(hostname) job=${SLURM_JOB_ID} start=$(date -Is)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
python -m cv_bench.g4u --stage collect
python -m cv_bench.g4u --stage build
echo "done=$(date -Is)"
