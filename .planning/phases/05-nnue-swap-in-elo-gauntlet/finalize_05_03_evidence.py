#!/usr/bin/env python3
"""Write 05-GAUNTLET-EVIDENCE.json from the durable checkpoint (post-run)."""

from __future__ import annotations

import json
import math
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path


def _json_num(value: float) -> float | None:
    """Serialize inf/nan as null for strict JSON consumers."""
    if isinstance(value, (int, float)) and (math.isinf(value) or math.isnan(value)):
        return None
    return value

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from ance.tools import gauntlet  # noqa: E402

CHECKPOINT = Path(
    ".planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json"
)
EVIDENCE = Path(
    ".planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json"
)
SEARCH_DEPTH = 3


def main() -> int:
    if not CHECKPOINT.is_file():
        print(f"missing checkpoint: {CHECKPOINT}", file=sys.stderr)
        return 1
    report = json.loads(CHECKPOINT.read_text(encoding="utf-8"))
    if report.get("status") != "completed":
        print(f"checkpoint status={report.get('status')}", file=sys.stderr)
        return 1
    aggregate = report["aggregate"]
    if aggregate.get("n_games", 0) < 1000:
        print(f"n_games={aggregate.get('n_games')} < 1000", file=sys.stderr)
        return 1

    env_a = report["parameters"]["engine_a"]["env"]
    env_b = report["parameters"]["engine_b"]["env"]
    runner = gauntlet.detect_runner()
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    d12_pass = aggregate["elo"] > 0 and aggregate["elo_ci_low"] > 0
    evidence = {
        "schema_version": 1,
        "git_commit": git_commit,
        "captured_utc": datetime.now(UTC).isoformat(),
        "gauntlet": {
            "games": aggregate["n_games"],
            "mode": report["parameters"]["mode"],
            "depth": SEARCH_DEPTH,
            "wins": aggregate["wins"],
            "losses": aggregate["losses"],
            "draws": aggregate["draws"],
            "score_rate": aggregate["score_rate"],
            "wilson_low": aggregate["wilson_low"],
            "wilson_high": aggregate["wilson_high"],
            "elo": _json_num(aggregate["elo"]),
            "elo_ci_low": _json_num(aggregate["elo_ci_low"]),
            "elo_ci_high": _json_num(aggregate["elo_ci_high"]),
            "runner": runner,
            "command_line": report.get("command_line"),
            "elapsed_s": aggregate["elapsed_s"],
            "status": report["status"],
            "checkpoint": str(CHECKPOINT),
            "engine_a_env": env_a,
            "engine_b_env": env_b,
        },
        "gates_passed": ["D-12", "TOOL-04"] if d12_pass else [],
    }
    if not d12_pass:
        evidence["gates_failed"] = ["D-12", "TOOL-04"]
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {EVIDENCE} d12_pass={d12_pass}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
