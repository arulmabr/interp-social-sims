#!/bin/bash
#SBATCH --job-name=cvb_analyse
#SBATCH --partition=mit_normal
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=4
#SBATCH --mem=16G
#SBATCH --time=04:00:00
#SBATCH --exclude=node2119
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/instr/%x_%j.out
#
# The CPU analysis that follows a GPU job, so a result does not sit unread on
# disk waiting for someone to be at a terminal. Idempotent: every step
# recomputes from files and overwrites its own output.
set -u
export ICLR_RUNROOT=/orcd/data/gabrieli/001/guna23/iclr_risk_2027
cd /home/guna23/shrey/risk
echo "$(date -u +%FT%TZ) analyse start job=$SLURM_JOB_ID step=${STEP:-instr}"
case "${STEP:-instr}" in
  instr)   python3 -u -m cv_bench.instr_analyse ;;
  g2)      python3 -u -m cv_bench.g2_summary ;;
  g4report) python3 -u -m cv_bench.g4_report ;;
  *)       echo "unknown STEP=${STEP}"; exit 2 ;;
esac
rc=$?
echo "$(date -u +%FT%TZ) analyse exit=$rc"
exit "$rc"
