#!/bin/bash
#SBATCH --job-name=cvb_g4b
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --gres=gpu:a100:2
#SBATCH --cpus-per-task=8
#SBATCH --mem=128G
#SBATCH --time=01:30:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g4b/%x_%j.out
#
# G4b's readout gradient, both layers, both games, computed in this session.
# Track B's B3.1 is being rebuilt after a labelling bug; this is the
# Friday-session version of the same defined quantity, to be reconciled.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID"
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
for L in 48 50; do
  srun python3 -u -m cv_bench.g4b --fallback --layer $L --game both
done
rc=$?
exit "$rc"
