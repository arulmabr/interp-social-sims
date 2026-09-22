#!/bin/bash
#SBATCH --job-name=cvb_g3
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=02:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g3/%x_%j.out
#
# G3 / S3.4: label and option-order transfer, forward passes only. Resumable.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.g3 --model llama || exit $?
rc=$?
echo "$(date -u +%FT%TZ) exit=$rc"
exit $rc
