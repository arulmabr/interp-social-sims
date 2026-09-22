#!/bin/bash
#SBATCH --job-name=cvb_b2_recovery
#SBATCH --partition=mit_normal
#SBATCH --account=mit_amf_advanced_cpu
#SBATCH --qos=normal
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=02:00:00
#SBATCH --requeue
#SBATCH --open-mode=append
#SBATCH --array=0-17
#SBATCH --output=logs/cvb_b2_recovery_%A_%a.out
#SBATCH --error=logs/cvb_b2_recovery_%A_%a.err

# B2 recovery study. CPU only: no GPU-hours against the shared 400-hour cap.
# 18 configurations = 3 template-noise levels x 3 numerical-noise levels
# x 2 dominated-trial policies (BD9).
set -euo pipefail
cd "${SLURM_SUBMIT_DIR}"
export OMP_NUM_THREADS=4 MKL_NUM_THREADS=4

# Centred on B2-cal's measured template noise of 2.13, not the 0.5 the first
# study called primary -- it was low by a factor of four. Numerical noise 0 is
# the primary configuration because unbatched reads measured bit-identical;
# 0.1 and 0.25 are sensitivity rows for batched reads only (author item 3).
TEMPLATE=(2.13 2.13 2.13 1.0 1.0 1.0 3.0 3.0 3.0)
NUMERICAL=(0.0 0.1 0.25)

i=${SLURM_ARRAY_TASK_ID}
policy_idx=$(( i / 9 ))
rest=$(( i % 9 ))
t=${TEMPLATE[$rest]}
n=${NUMERICAL[$(( rest % 3 ))]}
if [ "${policy_idx}" -eq 0 ]; then POLICY=exclude; else POLICY=lapse; fi

echo "task=${i} template=${t} numerical=${n} policy=${POLICY} host=$(hostname) start=$(date -Is)"
python -m cv_bench.estimator.recovery \
  --template-noise "${t}" --numerical-noise "${n}" --policy "${POLICY}" \
  --reps 20 --seed $(( i + 1 )) --observe logit --fitted-scale
echo "done=$(date -Is)"
