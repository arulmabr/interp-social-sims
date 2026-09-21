#!/bin/bash
#SBATCH --job-name=cvb_choose
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=00:30:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/neutral/%x_%j.out
#
# Choose the neutral framing from what cvb_neutral wrote. CPU only; it reads
# jsonl and writes framing_choice.json, which G3 consumes.
set -u
export ICLR_RUNROOT=/orcd/data/gabrieli/001/guna23/iclr_risk_2027
cd /home/guna23/shrey/risk
python3 -u -m cv_bench.neutral --model llama --phase choose
