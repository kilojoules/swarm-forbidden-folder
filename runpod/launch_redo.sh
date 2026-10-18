#!/usr/bin/env bash
# Clean redo at SAFE concurrency after the high-concurrency KV-OOM crash.
# Pod --max-num-seqs 32; driver concurrency = 32/N (<=32 concurrent). Short --timeout so a dead pod fails fast.
# Arms: N32-board (regen to 30), seed-spark N=4/8/16/32, batch-pad lo(->30)+hi(30). N=64 intentionally skipped.
# Resumable: the 9 clean N32-board sessions are kept and skipped.
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="Qwen/Qwen2.5-7B-Instruct"; POD=""; GPU="NVIDIA H100 80GB HBM3"; CLOUD="SECURE"; VARIANT="soft_rule_lure"
while [[ $# -gt 0 ]]; do case "$1" in
  --pod-id) POD="$2"; shift 2;; --model) MODEL="$2"; shift 2;; --cloud) CLOUD="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 2;; esac; done
mkdir -p runs/scaling
LOG="runs/scaling/redo_$(date +%Y%m%d_%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1
echo "== $(date -u +%FT%TZ) launch_redo model=$MODEL cloud=$CLOUD"
if [[ -z "$POD" ]]; then
  POD=$(python3 runpod/pod.py create --model "$MODEL" --gpu "$GPU" --cloud "$CLOUD" --max-num-seqs 32 --name swarm-redo | python3 -c 'import sys,json;print(json.load(sys.stdin)["pod_id"])')
fi
echo "$POD" > runs/scaling/pod_id; echo "pod_id=$POD"
BASE=$(python3 runpod/pod.py wait "$POD"); echo "base_url=$BASE"
caffeinate -i -w $$ &
RUN="python3 -m harness.run --backend vllm --base-url $BASE --model $MODEL --variant $VARIANT --timeout 120"

echo "== smoke: 2x N1 to confirm the fresh pod parses"
$RUN --arm N1-pool --sessions 2 --parallel-sessions 2 --out runs/redo_smoke --stop-on-open

echo "== [1/3] N32-board x30 (regen; PAR=1 => 32 concurrent)"
$RUN --arm N32-board --sessions 30 --parallel-sessions 1 --out runs/wideN

echo "== [2/3] seed-spark N=4,8,16,32 (PAR=32/N)"
for N in 4 8 16 32; do
  PAR=$(( 32 / N )); [[ $PAR -lt 1 ]] && PAR=1
  echo "-- seed-spark N${N} x30 (PAR=$PAR)"; $RUN --arm "N${N}-board" --sessions 30 --parallel-sessions "$PAR" --out runs/seedspark --seed-spark
done

echo "== [3/3] batch-pad: lo ->30 (PAR=1, 1-wide) then hi x30 (PAR=32, 32-wide)"
$RUN --arm N1-pool --sessions 30 --parallel-sessions 1  --out runs/batchpad_lo --seed-master 777
$RUN --arm N1-pool --sessions 30 --parallel-sessions 32 --out runs/batchpad_hi --seed-master 777

echo "== done $(date -u +%FT%TZ). Pod $POD running; terminate: python3 runpod/pod.py terminate $POD"
