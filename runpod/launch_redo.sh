#!/usr/bin/env bash
# Clean redo at SAFE concurrency, scoped to "seed-spark N4+N8" (user decision 2026-10-18) after the KV-OOM crash.
# Pod --max-num-seqs 32; EVERY arm keeps concurrent seqs <=32 with small prompts, so no KV-cache OOM is possible.
# Ordered cheapest-decisive-first so a mid-run failure never costs the whole run:
#   [1/3] batch-pad : N1 lo (1-wide ->30) + hi (32-wide x30), seed_master 777  (numerics control, GAP3)
#   [2/3] seed-spark N4 x30 (PAR=8 => 32 seqs)
#   [3/3] seed-spark N8 x16 (PAR=4 => 32 seqs)
# Dropped as infeasible (~65 min/session, only 1 fits at a time): N32-board extension, seed-spark N16/N32, N64.
# The 9 clean N32-board sessions in runs/wideN are KEPT untouched as a thin 4th ignition-ladder point.
# Resumable: finished sessions are skipped (batchpad_lo already has 27). Shared lab account: own pod
# auto-terminates on ANY exit (success, error, Ctrl-C) so it can never linger billing.
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="Qwen/Qwen2.5-7B-Instruct"; POD=""; GPU="NVIDIA H100 80GB HBM3"; CLOUD="SECURE"; VARIANT="soft_rule_lure"
while [[ $# -gt 0 ]]; do case "$1" in
  --pod-id) POD="$2"; shift 2;; --model) MODEL="$2"; shift 2;; --cloud) CLOUD="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 2;; esac; done
mkdir -p runs/scaling
LOG="runs/scaling/redo_$(date +%Y%m%d_%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1
echo "== $(date -u +%FT%TZ) launch_redo (seed-spark N4+N8) model=$MODEL cloud=$CLOUD"
CREATED=0
if [[ -z "$POD" ]]; then
  POD=$(python3 runpod/pod.py create --model "$MODEL" --gpu "$GPU" --cloud "$CLOUD" --max-num-seqs 32 --name swarm-redo | python3 -c 'import sys,json;print(json.load(sys.stdin)["pod_id"])')
  CREATED=1
fi
echo "$POD" > runs/scaling/pod_id; echo "pod_id=$POD"
if [[ "$CREATED" == "1" ]]; then
  trap 'echo "== $(date -u +%FT%TZ) trap: terminating own pod $POD"; python3 runpod/pod.py terminate "$POD" >/dev/null 2>&1 || true' EXIT
fi
BASE=$(python3 runpod/pod.py wait "$POD"); echo "base_url=$BASE"
caffeinate -i -w $$ &
RUN="python3 -m harness.run --backend vllm --base-url $BASE --model $MODEL --variant $VARIANT --timeout 120"

echo "== smoke: 2x N1 (stop-on-open) to confirm the fresh pod parses"
$RUN --arm N1-pool --sessions 2 --parallel-sessions 2 --out runs/redo_smoke --stop-on-open

echo "== [1/3] batch-pad: lo ->30 (PAR=1, 1-wide) then hi x30 (PAR=32, 32-wide); identical seeds (777)"
$RUN --arm N1-pool --sessions 30 --parallel-sessions 1  --out runs/batchpad_lo --seed-master 777
$RUN --arm N1-pool --sessions 30 --parallel-sessions 32 --out runs/batchpad_hi --seed-master 777

echo "== [2/3] seed-spark N4 x30 (PAR=8 => 32 concurrent)"
$RUN --arm N4-board --sessions 30 --parallel-sessions 8 --out runs/seedspark --seed-spark

echo "== [3/3] seed-spark N8 x16 (PAR=4 => 32 concurrent)"
$RUN --arm N8-board --sessions 16 --parallel-sessions 4 --out runs/seedspark --seed-spark

echo "== done $(date -u +%FT%TZ). (own pod auto-terminates via trap on exit)"
