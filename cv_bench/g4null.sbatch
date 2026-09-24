#!/bin/bash
#SBATCH --job-name=cvb_g4null
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=8
#SBATCH --gres=gpu:2
#SBATCH --time=01:30:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g4null/%x_%j.out
set -u
mkdir -p /orcd/data/gabrieli/001/guna23/iclr_risk_2027/g4null
cd /home/guna23/shrey/risk
export ICLR_RUNROOT=/orcd/data/gabrieli/001/guna23/iclr_risk_2027
nvidia-smi --query-gpu=name,memory.total --format=csv,noheader
srun python3 -m cv_bench.g4null --phase collect --layer 50 --game lottery || exit $?
srun python3 -m cv_bench.g4null --phase verify  --layer 50 --game lottery || exit $?
srun python3 -m cv_bench.g4null --phase null    --layer 50 --game lottery || exit $?
echo "[g4null] done"
