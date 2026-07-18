#!/usr/bin/env python3
"""Durable Phase 5 TOOL-04 gauntlet runner (checkpoint/resume).

Runs outside pytest so Cursor shell teardown cannot kill the overnight job.
After completion, re-run the slow pytest gate; run_gauntlet resumes from the
completed checkpoint and writes 05-GAUNTLET-EVIDENCE.json.
"""

from __future__ import annotations

import os
import shlex
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from ance.tools import gauntlet  # noqa: E402

D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
BUDGET_SECONDS = 172_800
CHECKPOINT = Path(
    os.environ.get(
        "ANCE_PHASE5_GAUNTLET_CHECKPOINT",
        ".planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json",
    )
)
LOG = Path(
    ".planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-run.log"
)


def main() -> int:
    openings_path = gauntlet.DEFAULT_OPENINGS
    spec_nnue = gauntlet.EngineSpec(
        "nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}
    )
    spec_hc = gauntlet.EngineSpec(
        "handcrafted", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
    )
    runner = gauntlet.detect_runner()
    command = [
        sys.executable,
        "-m",
        "ance.tools.gauntlet",
        "--games",
        str(D12_GAMES),
        "--tc",
        "30+0.3",
        "--depth",
        str(SEARCH_DEPTH),
        "--openings",
        str(openings_path),
        "--output",
        str(CHECKPOINT),
        "--max-halfmoves",
        str(MAX_HALFMOVES),
        "--engine-a",
        shlex.join(ENGINE_ARGV),
        "--engine-b",
        shlex.join(ENGINE_ARGV),
        "--engine-a-name",
        spec_nnue.name,
        "--engine-b-name",
        spec_hc.name,
        "--runner",
        runner,
        "--budget-seconds",
        str(BUDGET_SECONDS),
    ]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"runner start {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n")
        log.write(f"command {shlex.join(command)}\n")
        log.flush()
    report = gauntlet.run_gauntlet(
        spec_nnue,
        spec_hc,
        gauntlet.load_openings(openings_path),
        n_games=D12_GAMES,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=MAX_HALFMOVES,
        output_path=CHECKPOINT,
        deadline=time.monotonic() + BUDGET_SECONDS,
        openings_path=openings_path,
        command_line=shlex.join(command),
        search_depth=SEARCH_DEPTH,
    )
    with LOG.open("a", encoding="utf-8") as log:
        log.write(
            f"runner done status={report.get('status')} "
            f"games={report.get('aggregate', {}).get('n_games')} "
            f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}\n"
        )
    print(report.get("status"), report.get("aggregate"))
    return 0 if report.get("status") == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
