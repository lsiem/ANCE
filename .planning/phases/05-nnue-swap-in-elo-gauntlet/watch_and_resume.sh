#!/bin/bash
set -u
ROOT="/Users/lasse/Development/Projects/ANCE"
CK="$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json"
LOG="$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-progress.txt"
RUNNER="$ROOT/.venv/bin/python $ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/run_gauntlet_05_03.py"
cd "$ROOT"
while true; do
  n=$("$ROOT/.venv/bin/python" -c "import json;from pathlib import Path;s=json.loads(Path('$CK').read_text());print(len(s.get('games',[])))")
  st=$("$ROOT/.venv/bin/python" -c "import json;from pathlib import Path;s=json.loads(Path('$CK').read_text());print(s.get('status'))")
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "$ts games=$n status=$st" | tee -a "$LOG"
  if [ "$st" = "completed" ] && [ "$n" -ge 1000 ]; then
    echo "$ts DONE" | tee -a "$LOG"
    exit 0
  fi
  if ! pgrep -f "run_gauntlet_05_03.py" >/dev/null 2>&1; then
    echo "$ts RESUME" | tee -a "$LOG"
    nohup $RUNNER >> "$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-run.log" 2>&1 &
    disown || true
  fi
  sleep 300
done
