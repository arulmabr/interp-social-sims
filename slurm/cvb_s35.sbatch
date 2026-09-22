#!/bin/bash
#SBATCH --job-name=cvb_s35
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=03:00:00
#SBATCH --nice=7000
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/s35/%x_%j.out
# S3.5: one unsteered arm per game at temperature 1.0, chat64 protocol.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.s35 --model llama || exit $?
rc=$?
exit "$rc"
