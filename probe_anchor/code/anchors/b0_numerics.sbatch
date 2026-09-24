#!/bin/bash
#SBATCH --job-name=cvb_b0_numerics
#SBATCH --partition=ou_bcs_normal,${SLURM_PARTITION}
#SBATCH --account=${SLURM_ACCOUNT}
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --gres=gpu:a100:4
#SBATCH --cpus-per-task=16
#SBATCH --mem=64G
#SBATCH --time=04:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=logs/cvb_b0_numerics_%j.out
#SBATCH --error=logs/cvb_b0_numerics_%j.err
#SBATCH --exclude=node2119

# Amendment item 5(c): the 70B in fp32 against bf16 unbatched, at baseline and
# one dose, on ~200 calibration-split prompts. 4 GPUs as instructed.
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
export HF_HOME=${HF_HOME}
echo "host=$(hostname) job=${SLURM_JOB_ID} gpus=${SLURM_GPUS_ON_NODE:-?} start=$(date -Is)"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
# One process per dtype: 282 GB of fp32 weights must be gone before bf16 loads,
# and only process exit guarantees that.
python -m cv_bench.anchors.numerics_fp32 --stage fp32 --n-prompts 200 --scale 0.5
python -m cv_bench.anchors.numerics_fp32 --stage bf16 --n-prompts 200 --scale 0.5
python -m cv_bench.anchors.numerics_fp32 --stage compare --n-prompts 200 --scale 0.5
echo "done=$(date -Is)"
