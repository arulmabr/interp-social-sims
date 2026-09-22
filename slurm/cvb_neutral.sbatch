#!/bin/bash
#SBATCH --job-name=cvb_neutral
#SBATCH --partition=ou_bcs_low
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=04:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/neutral/%x_%j.out
#
# Neutral labels for S3.4 (FRIDAY amendment item 4). Unsteered model,
# calibration prompts only. Resumable through cv_bench.resume.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.neutral --model llama --phase all --agents 8 --levels 10 || exit $?
rc=$?
echo "$(date -u +%FT%TZ) exit=$rc"
exit $rc
