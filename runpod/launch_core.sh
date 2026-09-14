#!/usr/bin/env bash
# End-to-end core study on a running vLLM pod: calibration gate (N1 x20) -> F1 -> F2 -> F3.
# The driver runs on this Mac against the pod's HTTPS endpoint (caffeinate keeps the Mac awake). Every session is
# resumable: rerunning the same command skips finished sessions and continues partial ones.
# Usage: runpod/launch_core.sh --pod-id <id> --model Qwen/Qwen3-8B [--variant deadline] [--cal-arm N1-B] [--skip-gate]
#        [--n-max 16] [--out runs/core] [--pool-sessions 150] [--board-sessions 30] [--noboard-sessions 10]
set -euo pipefail
cd "$(dirname "$0")/.."
MODEL="Qwen/Qwen3-8B"; VARIANT="base"; CAL_ARM="N1-B"; SKIP_GATE=0; POD=""; OUT="runs/core"; NMAX=16
POOL=150; BOARD=30; NOBOARD=10; GPU="NVIDIA H100 80GB HBM3"; CLOUD="SECURE"; GATE_ROOT=""
while [[ $# -gt 0 ]]; do case "$1" in
  --skip-gate) SKIP_GATE=1; shift;;
  --model) MODEL="$2"; shift 2;;
  --variant) VARIANT="$2"; shift 2;;
  --cal-arm) CAL_ARM="$2"; shift 2;;
  --pod-id) POD="$2"; shift 2;;
  --out) OUT="$2"; shift 2;;
  --n-max) NMAX="$2"; shift 2;;
  --pool-sessions) POOL="$2"; shift 2;;
  --board-sessions) BOARD="$2"; shift 2;;
  --noboard-sessions) NOBOARD="$2"; shift 2;;
  --gpu) GPU="$2"; shift 2;;
  --cloud) CLOUD="$2"; shift 2;;
  --gate-root) GATE_ROOT="$2"; shift 2;;   # evaluate the gate on an existing calibration dir instead of re-running it
  *) echo "unknown arg $1"; exit 2;;
esac; done
mkdir -p "$OUT"
LOG="$OUT/launch_$(date +%Y%m%d_%H%M%S).log"; exec > >(tee -a "$LOG") 2>&1
echo "== $(date -u +%FT%TZ) launch_core model=$MODEL variant=$VARIANT cal_arm=$CAL_ARM skip_gate=$SKIP_GATE n_max=$NMAX out=$OUT"
if [[ -z "$POD" ]]; then
  POD=$(python3 runpod/pod.py create --model "$MODEL" --gpu "$GPU" --cloud "$CLOUD" --name swarm-core | python3 -c 'import sys,json; print(json.load(sys.stdin)["pod_id"])')
  echo "pod_id=$POD"
fi
echo "$POD" > "$OUT/pod_id"
python3 - "$OUT" "$MODEL" "$VARIANT" "$CAL_ARM" "$GATE_ROOT" "$NMAX" <<'PY'
import hashlib, json, sys, subprocess, datetime
sys.path.insert(0, ".")
from harness import prompts
out, model, variant, cal_arm, gate_root, nmax = sys.argv[1:7]
sp = prompts.system_prompt(30, variant)
gates = None
if gate_root:
    try:
        gates = json.loads(subprocess.run(["python3", "analysis/gates.py", gate_root, "--arm", cal_arm, "--model", model, "--variant", variant], capture_output=True, text=True).stdout)
    except Exception as e:
        gates = {"error": str(e)}
json.dump({"frozen_at": datetime.datetime.utcnow().isoformat() + "Z", "model": model, "variant": variant, "T_MAX": 30,
           "system_prompt_sha256": hashlib.sha256(sp.encode()).hexdigest(), "system_prompt": sp, "n_max": nmax,
           "calibration_arm": cal_arm, "calibration_root": gate_root, "calibration_gates": gates}, open(out + "/FREEZE.json", "w"), indent=1)
print("wrote", out + "/FREEZE.json")
PY
BASE=$(python3 runpod/pod.py wait "$POD")
echo "base_url=$BASE"
caffeinate -i -w $$ &
RUN="python3 -m harness.run --backend vllm --base-url $BASE --model $MODEL --variant $VARIANT --out $OUT"
if [[ $SKIP_GATE -eq 0 ]]; then
  if [[ -n "$GATE_ROOT" ]]; then
    echo "== calibration gate evaluated on $GATE_ROOT ($CAL_ARM, $MODEL, variant $VARIANT)"
    GROOT="$GATE_ROOT"
  else
    echo "== calibration gate: $CAL_ARM x20 (variant $VARIANT)"
    $RUN --arm "$CAL_ARM" --sessions 20 --parallel-sessions 20
    GROOT="$OUT"
  fi
  if ! python3 analysis/gates.py "$GROOT" --arm "$CAL_ARM" --model "$MODEL" --variant "$VARIANT" --require-pass; then
    echo "!! calibration gate FAILED for $MODEL/$VARIANT. Pod $POD left running. Read $OUT/$CAL_ARM and choose the next variant or tier."
    exit 1
  fi
fi
echo "== F1: N1-pool x$POOL";              $RUN --arm N1-pool --sessions "$POOL" --parallel-sessions 40
echo "== F2: N4-noboard x$NOBOARD";        $RUN --arm N4-noboard --sessions "$NOBOARD" --parallel-sessions 10
echo "== F2: N4-board x$BOARD";            $RUN --arm N4-board --sessions "$BOARD" --parallel-sessions 10
for NM in $NMAX; do   # --n-max may list several values, e.g. "8 16"
  PAR=$(( 64 / NM )); [[ $PAR -lt 2 ]] && PAR=2
  echo "== F3: N${NM}-noboard x$NOBOARD";  $RUN --arm "N${NM}-noboard" --sessions "$NOBOARD" --parallel-sessions "$PAR"
  echo "== F3: N${NM}-board x$BOARD";      $RUN --arm "N${NM}-board" --sessions "$BOARD" --parallel-sessions "$PAR"
done
echo "== done $(date -u +%FT%TZ)"
python3 analysis/gates.py "$OUT" --arm N1-pool --variant "$VARIANT" || true
python3 analysis/km.py "$OUT" --pool-arms N1-pool --compare N4-noboard N4-board --N 4 --variant "$VARIANT" --out "$OUT/km_N4.png" || true
for NM in $NMAX; do
  python3 analysis/km.py "$OUT" --pool-arms N1-pool --compare "N${NM}-noboard" "N${NM}-board" --N "$NM" --variant "$VARIANT" --out "$OUT/km_N${NM}.png" || true
done
python3 analysis/board_flags.py "$OUT" > "$OUT/board_flags.json" || true
echo "== pod $POD is still running; terminate with: python3 runpod/pod.py terminate $POD"
