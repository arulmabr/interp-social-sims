#!/bin/bash
#SBATCH --job-name=cvb_b0_numerics
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=256G
#SBATCH --time=06:00:00
#SBATCH --requeue
#SBATCH --output=logs/cvb_b0_numerics_%j.out
#SBATCH --error=logs/cvb_b0_numerics_%j.err

# Amendment item 5(c): the 70B in fp32 against bf16 unbatched, at baseline and
# one dose, on ~200 calibration-split prompts. 4 GPUs as instructed.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
echo "host=$(hostname) job=${SLURM_JOB_ID} gpus=${SLURM_GPUS_ON_NODE:-?} start=$(date -Is)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
python -m cv_bench.anchors.numerics_fp32 --n-prompts 200 --scale 0.5
echo "done=$(date -Is)"
