#!/bin/bash
#SBATCH --job-name=cvb_g5bjudge
#SBATCH --partition=mit_preemptable
#SBATCH --account=mit_general
#SBATCH --qos=normal
#SBATCH --cpus-per-task=2
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH --exclude=node2119
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --output=/orcd/data/gabrieli/001/guna23/iclr_risk_2027/g5b/%x_%j.out
#
# G5b's two CPU phases, after the generations land.
#   measures  S1.6's four judge-independent text measures. No API, no cost.
#   judge     the three reachable judges of V2 under App. A.3.5's rubric.
#             Keys are read from ~/secrets/working_apis at the moment of use and
#             are never printed, logged or written. Resumable per (text, judge).
# No GPU: this is HTTP and arithmetic.
set -u
echo "$(date -u +%FT%TZ) node=$SLURMD_NODENAME job=$SLURM_JOB_ID"
export ICLR_RUNROOT=/orcd/data/gabrieli/001/guna23/iclr_risk_2027
# The measures phase loads the sentence encoder for S1.6's category spread.
# cv_bench modules do os.environ.setdefault("HF_HOME", <project cache>) at
# import, so leaving HF_HOME unset is not enough -- the module would set it to
# the cache that holds the 70B and not the encoder. Set it explicitly to the
# cache the encoder is actually in; this job loads nothing else from HF.
export HF_HOME="$HOME/.cache/huggingface"
export HF_HUB_OFFLINE=1
cd /home/guna23/shrey/risk
python3 -u -m cv_bench.g5b --model llama --phase measures || exit $?
python3 -u -m cv_bench.g5b --model llama --phase judge --max-usd 50 || exit $?
rc=$?
echo "$(date -u +%FT%TZ) exit=$rc"
exit "$rc"
