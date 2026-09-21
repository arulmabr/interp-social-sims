#!/bin/bash
#SBATCH --job-name=cvb_monitor
#SBATCH --partition=mit_normal
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=1
#SBATCH --mem=4G
#SBATCH --time=11:45:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/monitor_%j.out
#
# The monitor, off the login node (FRIDAY amendment item 5).
#
# Survives three things:
#   a dropped connection   it is a batch job; nothing is tied to a terminal
#   preemption / node loss --requeue, and the cycle state lives in
#                          $RUNROOT/monitor_state.json, so a requeued job
#                          resumes where it stopped
#   the wall clock         the partition caps at 12 h, so the job resubmits
#                          itself before it ends
#
# To stop it: touch $RUNROOT/monitor.stop  (then scancel the running job).
set -u
REPO=/home/guna23/shrey/risk
RUNROOT=/orcd/data/gabrieli/001/guna23/iclr_risk_2027
cd "$REPO" || exit 1

if [ -f "$RUNROOT/monitor.stop" ]; then
  echo "$(date -u +%FT%TZ) monitor.stop present; not starting, not rechaining"
  exit 0
fi

echo "$(date -u +%FT%TZ) monitor start job=$SLURM_JOB_ID restarts=${SLURM_RESTART_COUNT:-0} node=$(hostname)"

# Leave 10 minutes so the chain is submitted before the wall clock lands on us.
# `timeout` takes ONE unit suffix, so this is seconds: 11 h 35 m.
started=$(date +%s)
timeout --signal=TERM 41700 python3 -u -m cv_bench.monitor
rc=$?
ran=$(( $(date +%s) - started ))
echo "$(date -u +%FT%TZ) monitor loop exited rc=$rc after ${ran}s"

# Chain, unless someone asked it to stop. rc=124 is the expected timeout exit.
# A loop that died in under two minutes is a startup failure, not a wall clock:
# chaining it would spin the queue, so stop and leave the log to be read.
if [ "$ran" -lt 120 ]; then
  echo "$(date -u +%FT%TZ) loop exited after ${ran}s (rc=$rc): startup failure, not chaining"
  exit "$rc"
fi
if [ ! -f "$RUNROOT/monitor.stop" ]; then
  next=$(sbatch --parsable "$REPO/slurm/cvb_monitor.sbatch")
  echo "$(date -u +%FT%TZ) chained next monitor job: $next"
fi
exit 0
