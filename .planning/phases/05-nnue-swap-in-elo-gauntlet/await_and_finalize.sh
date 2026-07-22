#!/usr/bin/env bash
# Poll until clean 05-03 gauntlet hits 1000 completed games, then finalize evidence.
set -euo pipefail
cd /workspace
STATUS=/tmp/gauntlet_await_status.txt
COMPLETE=/tmp/gauntlet_COMPLETE
LOG=/tmp/finalize_05_03.log

while true; do
  ts=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
  set +e
  /workspace/.venv/bin/python - <<'PY'
import json
from pathlib import Path

p = Path(".planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json")
d = json.loads(p.read_text())
a = d.get("aggregate") or {}
n = a.get("n_games") or 0
e = a.get("elapsed_s") or 0
r = (e / n) if n else 0
eta = ((1000 - n) * r / 3600) if n and n < 1000 else 0.0
line = (
    f"games={n}/1000 "
    f"WLD={a.get('wins')}-{a.get('losses')}-{a.get('draws')} "
    f"elo={a.get('elo')} eta_h={eta:.2f} status={d.get('status')}"
)
print(line)
Path("/tmp/gauntlet_await_status.txt").write_text(
    f"{n} {d.get('status')} {a.get('wins')} {a.get('losses')} "
    f"{a.get('draws')} {a.get('elo')}\n"
)
if d.get("status") == "completed" and n >= 1000:
    raise SystemExit(42)
PY
  ec=$?
  set -e
  echo "$ts exit=$ec"
  if [ "$ec" -eq 42 ]; then
    echo COMPLETE
    /workspace/.venv/bin/python \
      /workspace/.planning/phases/05-nnue-swap-in-elo-gauntlet/finalize_05_03_evidence.py \
      | tee "$LOG"
    echo FINALIZED > "$COMPLETE"
    break
  fi
  if ! pgrep -f "run_gauntlet_05_03.py" >/dev/null; then
    echo "WARN: runner missing at $ts"
  fi
  sleep 600
done
echo AWAIT_DONE
