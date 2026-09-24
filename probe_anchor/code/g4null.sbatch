#!/bin/bash
#SBATCH --job-name=cvb_g4null
#SBATCH --partition=${SLURM_PARTITION}
#SBATCH --account=${SLURM_ACCOUNT}
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:2
#SBATCH --time=01:30:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=${ICLR_RUNROOT}/g4null/%x_%j.out
set -u
mkdir -p ${ICLR_RUNROOT}/g4null
cd ${REPO}
export ICLR_RUNROOT=${ICLR_RUNROOT}
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
srun python3 -m cv_bench.g4null --phase collect --layer 50 --game lottery || exit $?
srun python3 -m cv_bench.g4null --phase verify  --layer 50 --game lottery || exit $?
srun python3 -m cv_bench.g4null --phase null    --layer 50 --game lottery || exit $?
echo "[g4null] done"
