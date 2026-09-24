#!/bin/bash
# Launch the 70B LoRA when, and only when, the 8B dry run clears the cloning bar.
#
# The step count is chosen from the dry run's own curve: the smallest probe at
# which BOTH the held-out and the train slope reach 0.9, applied identically to
# all three adapters because A5 requires one schedule. Cheapest option that
# meets the bar, which is what the autonomy amendment asks for.
set -u
REPO=${REPO}
SHARE=${ICLR_RUNROOT}/trackB
JOB=$1
cd "$REPO"

until sacct -j "$JOB" --format=State -X -n 2>/dev/null | grep -qE 'COMPLETED|FAILED|TIMEOUT|CANCELLED'; do sleep 30; done
state=$(sacct -j "$JOB" --format=State -X -n | head -1 | tr -d ' ')
echo "$(date -Is) dry run $JOB finished: $state"
[ "${state:0:9}" != "COMPLETED" ] && { echo "dry run did not complete; not launching the 70B"; exit 1; }

read -r PASS STEPS <<< "$(python - <<'PY'
import json, sys
from pathlib import Path
p = Path("${ICLR_RUNROOT}/trackB/b3_lora_dryrun_8b_v5/b3_lora.json")
if not p.exists():
    print("no 0"); sys.exit()
d = json.loads(p.read_text())
ok = bool(d.get("all_cloning_pass"))
# smallest probe where every adapter has both slopes at or above 0.9
best = 0
traces = {n: v.get("trace", []) for n, v in d.get("adapters", {}).items()}
steps = sorted({r["step"] for t in traces.values() for r in t})
for s in steps:
    rows = [r for t in traces.values() for r in t if r["step"] == s]
    if len(rows) == len(traces) and rows and all(
            r["heldout"]["slope"] >= 0.9 and r.get("train", {}).get("slope", 0) >= 0.9
            for r in rows):
        best = s
        break
print(f"{'yes' if ok else 'no'} {best or d.get('steps', 1500)}")
PY
)"
echo "cloning pass=$PASS  step count chosen=$STEPS"
[ "$PASS" != "yes" ] && { echo "cloning bar not met; the 70B is NOT launched, reporting instead"; exit 2; }

sbatch --job-name=cvb_b3_lora70b --partition=mit_normal_gpu --account=mit_amf_advanced_gpu \
  --qos=mit_amf_advanced_gpu --gres=gpu:4 --cpus-per-task=8 --mem=200G --time=24:00:00 \
  --exclude=node2119 \
  --requeue --open-mode=append \
  --output=logs/cvb_b3_lora70b_%j.out --error=logs/cvb_b3_lora70b_%j.err \
  --wrap="cd $REPO && export HF_HOME=${HF_HOME} && python -m cv_bench.anchors.lora --model llama70b --steps $STEPS --lr 1e-4 --accum 8 --tau 0.1186 --clone-every 250 --out $SHARE/b3_lora_70b"
