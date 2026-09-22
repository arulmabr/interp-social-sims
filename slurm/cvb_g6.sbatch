#!/bin/bash
#SBATCH --job-name=cvb_g6
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=06:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g6/%x_%j.out
#
# G5 / S2.4: the eight logged SAE features, steered locally at the two published
# doses, chat64 settings so G2's chat64 arm is the baseline. Resumable per cell.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.g6 --model llama --levels 12
rc=$?
echo "$(date -u +%FT%TZ) exit=$rc"
exit $rc
