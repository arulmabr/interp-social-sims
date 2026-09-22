#!/bin/bash
#SBATCH --job-name=cvb_g4q
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=8
#SBATCH --mem=80G
#SBATCH --time=06:00:00
#SBATCH --nice=5000
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --signal=B:TERM@180
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g4/%x_%j.out
# G4q: the probe rebuild and dose-response on Qwen2-7B at layer 17, chat template.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.g4 --model qwen --variant reconstruction --layer 17 --phase sweep || exit $?
rc=$?
exit "$rc"
