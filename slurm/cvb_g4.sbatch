#!/bin/bash
#SBATCH --job-name=cvb_g4
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=12:00:00
#SBATCH --exclude=node2119
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@300
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g4/%x_%j.out
#
# One G4 replica = one (variant, layer). Four of them run at once.
#   sbatch --export=ALL,V=as_written,L=48 slurm/cvb_g4.sbatch
#
# Resumable: every cell is one fsynced record keyed by (game, dose, level).
# Requeue or a wall-clock kill costs the cell in flight and nothing else;
# resubmitting the same command continues from the next cell.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID variant=$V layer=$L restarts=${SLURM_RESTART_COUNT:-0}"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.g4 --model llama --variant "$V" --layer "$L" --phase sweep || exit $?
rc=$?
echo "$(date -u +%FT%TZ) exit=$rc"
exit $rc
