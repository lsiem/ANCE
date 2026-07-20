#!/bin/bash
# Cloud-adapted watcher: resume gauntlet if the runner dies; exit when complete.
set -u
ROOT="/workspace"
CK="$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json"
LOG="$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-progress.txt"
PY="$ROOT/.venv/bin/python"
RUNNER="$PY $ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/run_gauntlet_05_03.py"
export PATH="/usr/games:$PATH"
export PYTHONUNBUFFERED=1
cd "$ROOT"
while true; do
  if [ -f "$CK" ]; then
    n=$("$PY" -c "import json;from pathlib import Path;s=json.loads(Path('$CK').read_text());print(len(s.get('games',[])))")
    st=$("$PY" -c "import json;from pathlib import Path;s=json.loads(Path('$CK').read_text());print(s.get('status'))")
  else
    n=0
    st=missing
  fi
  ts=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  echo "$ts games=$n status=$st" | tee -a "$LOG"
  if [ "$st" = "completed" ] && [ "$n" -ge 1000 ]; then
    echo "$ts DONE — running finalize" | tee -a "$LOG"
    "$PY" "$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/finalize_05_03_evidence.py"
    exit 0
  fi
  if ! pgrep -f "run_gauntlet_05_03.py" >/dev/null 2>&1; then
    echo "$ts RESUME" | tee -a "$LOG"
    nohup $RUNNER >> "$ROOT/.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-run.log" 2>&1 &
    disown || true
  fi
  sleep 300
done
