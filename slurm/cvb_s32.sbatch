#!/bin/bash
#SBATCH --job-name=cvb_s32
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=08:00:00
#SBATCH --nice=6000
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g4/%x_%j.out
# S3.2: the rebuilt L48 probe at two doses under each position policy.
# Dose ids 0 (zero) and 10 (1.0 of the median residual norm).
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
for P in legacy_ramp all_prompt last; do
  srun python3 -u -m cv_bench.g4 --model llama --variant reconstruction --layer 48 \
       --phase sweep --positions "$P" --tag "s32_$P" --dose-ids 0,10 --directions probe
done
rc=$?
exit "$rc"
