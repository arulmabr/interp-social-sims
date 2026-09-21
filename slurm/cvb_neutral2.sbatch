#!/bin/bash
#SBATCH --job-name=cvb_neutral2
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=03:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/neutral/%x_%j.out
#
# Neutral free generation, second pass: levels located per framing so they
# straddle the switching point. The first pass ran over the flat calibration
# range and every framing came back constant, which measures the range and not
# the label. Kept at neutral/free_llama_flatrange.jsonl.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0}"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.neutral --model llama --phase free --agents 8 --levels 10
srun python3 -u -m cv_bench.neutral --model llama --phase choose
