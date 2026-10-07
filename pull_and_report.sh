#!/bin/bash
# Pull full grid + run the frozen report — run when GRID_COMPLETE fires
set -e
cd /Users/kilojoules/swarm/swarm-forbidden-folder
rm -rf runs/grid
mkdir -p runs
scp -o "StrictHostKeyChecking=no" -o "UserKnownHostsFile=/dev/null" -P 37565 -r root@185.216.23.194:/workspace/runs/grid runs/grid
echo "pulled: $(find runs/grid -name summary.json | wc -l) summaries"
python3 analysis/deadpeer_report.py --runs runs/grid 2>&1 | tee runs/grid/REPORT.txt || python3 analysis/deadpeer_report.py runs/grid 2>&1 | tee runs/grid/REPORT.txt
