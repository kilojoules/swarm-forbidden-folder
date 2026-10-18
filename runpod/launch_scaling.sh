#!/usr/bin/env bash
# Decisive-core scaling experiments on one vLLM pod (Qwen2.5-7B-Instruct bf16), ordered cheapest-decisive-first:
#   1. batch-pad   : N1-pool at 1-wide vs 64-wide batches (isolates the vLLM batch-numerics confound, GAP3)
#   2. core-wideN  : board N={2,32,64}x30 + noboard N={2,32,64}x10 (6-point log ladder: pins L1/L2/L3/L5)
#   3. seed-spark  : board N={4,8,16,32,64}x30 with one pre-opened agent (cascade size / R_eff vs N)
# Every session is resumable: re-running this script skips finished sessions and continues partial ones.
# Driver runs on this Mac against the pod's HTTPS endpoint; caffeinate keeps the Mac awake.
# Usage: runpod/launch_scaling.sh [--pod-id <id>] [--model Qwen/Qwen2.5-7B-Instruct] [--cloud SECURE|COMMUNITY]
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="Qwen/Qwen2.5-7B-Instruct"; POD=""; GPU="NVIDIA H100 80GB HBM3"; CLOUD="SECURE"; VARIANT="soft_rule_lure"
while [[ $# -gt 0 ]]; do case "$1" in
  --pod-id) POD="$2"; shift 2;;
  --model) MODEL="$2"; shift 2;;
  --gpu) GPU="$2"; shift 2;;
  --cloud) CLOUD="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 2;;
esac; done
mkdir -p runs/scaling
LOG="runs/scaling/launch_$(date +%Y%m%d_%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1
echo "== $(date -u +%FT%TZ) launch_scaling model=$MODEL cloud=$CLOUD variant=$VARIANT"
if [[ -z "$POD" ]]; then
  POD=$(python3 runpod/pod.py create --model "$MODEL" --gpu "$GPU" --cloud "$CLOUD" --name swarm-scaling | python3 -c 'import sys,json; print(json.load(sys.stdin)["pod_id"])')
fi
echo "$POD" > runs/scaling/pod_id; echo "pod_id=$POD"
BASE=$(python3 runpod/pod.py wait "$POD")
echo "base_url=$BASE"
caffeinate -i -w $$ &
RUN="python3 -m harness.run --backend vllm --base-url $BASE --model $MODEL --variant $VARIANT"

echo "== smoke: 2x N1 (stop-on-open) to confirm endpoint + parsing"
$RUN --arm N1-pool --sessions 2 --parallel-sessions 2 --out runs/scaling_smoke --stop-on-open

echo "== [1/3] core-wideN: board x30 + noboard x10 at ~64-wide (PAR=64/N), N=2,32,64"
for N in 2 32 64; do
  PAR=$(( 128 / N )); [[ $PAR -lt 1 ]] && PAR=1    # saturate the pod's 128-seq capacity; fewer idle gaps between synchronous rounds
  echo "-- N${N}-noboard x10 (PAR=$PAR)"; $RUN --arm "N${N}-noboard" --sessions 10 --parallel-sessions "$PAR" --out runs/wideN
  echo "-- N${N}-board   x30 (PAR=$PAR)"; $RUN --arm "N${N}-board"   --sessions 30 --parallel-sessions "$PAR" --out runs/wideN
done

echo "== [2/3] seed-spark: board x30 with one pre-opened agent, at ~64-wide, N=4,8,16,32,64"
for N in 4 8 16 32 64; do
  PAR=$(( 128 / N )); [[ $PAR -lt 1 ]] && PAR=1
  echo "-- N${N}-board seed-spark x30 (PAR=$PAR)"; $RUN --arm "N${N}-board" --sessions 30 --parallel-sessions "$PAR" --out runs/seedspark --seed-spark
done

# batch-pad LAST (the deliberately-serial 1-wide arm must not block the science); 30 is ample for the rate contrast
echo "== [3/3] batch-pad: N1-pool x30, 1-wide (lo) then 64-wide (hi); identical seeds, only batch width differs"
$RUN --arm N1-pool --sessions 30 --parallel-sessions 1  --out runs/batchpad_lo --seed-master 777
$RUN --arm N1-pool --sessions 30 --parallel-sessions 64 --out runs/batchpad_hi --seed-master 777

echo "== done $(date -u +%FT%TZ). Pod $POD still running."
echo "== terminate with: python3 runpod/pod.py terminate $POD"
