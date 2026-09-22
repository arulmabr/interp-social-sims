#!/bin/bash
#SBATCH --job-name=cvb_instr
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
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/instr/%x_%j.out
#
# The instrument check (FRIDAY amendment item 2), the residual norms G4's dose
# grid is expressed in, and the token-cap measurement.
#
# Resumable: every phase writes through cv_bench.resume.JsonlSink, one fsynced
# record per unit of work, keyed by the work itself. Requeue, preemption or a
# wall-clock kill loses at most the unit in flight; rerunning this script
# continues from the next one.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0}"
nvidia-smi --query-gpu=index,name,memory.total --format=csv,noheader
export HF_HOME=/orcd/data/gabrieli/001/guna23/hf_cache
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
srun python3 -u -m cv_bench.instr --model llama --phase all --agents 20
rc=$?
echo "$(date -u +%FT%TZ) exit=$rc"
exit $rc
