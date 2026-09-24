#!/bin/bash
#SBATCH --job-name=cvb_b3_grad
#SBATCH --partition=${SLURM_PARTITION}
#SBATCH --account=${SLURM_ACCOUNT}
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --time=04:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/cvb_b3_grad_%j.out
#SBATCH --error=logs/cvb_b3_grad_%j.err

# B3.1 gradient anchor. MODEL and LAYERS come from the environment so the same
# script serves the 8B dry run and the 70B run.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
export HF_HOME=${HF_HOME}
MODEL="${B3_MODEL:-llama70b}"
LAYERS="${B3_LAYERS:-48 50}"
OUT="${B3_OUT:-${ICLR_RUNROOT}/trackB/b3_gradient}"
echo "host=$(hostname) job=${SLURM_JOB_ID} model=${MODEL} layers=${LAYERS} start=$(date -Is)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
python -m cv_bench.anchors.gradient --model "${MODEL}" --layers ${LAYERS} --out "${OUT}"
echo "done=$(date -Is)"
