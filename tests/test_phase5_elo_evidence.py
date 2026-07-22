"""Phase 5 TOOL-04 Elo evidence gates (D-09, D-10, D-11, D-12)."""

from __future__ import annotations

import json
import math
import os
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ance.tools import gauntlet


D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
# Smoke calibration (~143 s/game @ depth 3 with NNUE) projects ~40 h for 1000
# games — well above the RESEARCH 4–8 h estimate. Keep a 48 h watchdog so the
# overnight acceptance run can finish without HarnessTimeout.
BUDGET_SECONDS = 172_800


def assert_positive_elo_with_ci(report: dict) -> None:
    """Assert D-12: Elo point estimate > 0 and 95% CI lower bound > 0."""
    aggregate = report["aggregate"]
    elo = aggregate["elo"]
    elo_ci_low = aggregate["elo_ci_low"]
    assert elo > 0 and elo_ci_low > 0, (
        f"D-12 Elo gate failed: elo={elo}, elo_ci_low={elo_ci_low} "
        "(need elo > 0 and elo_ci_low > 0)"
    )


def assert_minimum_games(report: dict, n: int = 1000) -> None:
    """Assert D-10: fixed game count meets the acceptance minimum."""
    n_games = report["aggregate"]["n_games"]
    assert n_games >= n, (
        f"D-10 minimum games not met: n_games={n_games} < {n}"
    )


def load_evidence(path: str | Path) -> dict:
    """Load the committed TOOL-04 / D-12 evidence artifact."""
    evidence_path = Path(path)
    if not evidence_path.exists():
        raise FileNotFoundError(
            f"{evidence_path} is missing; run Phase 5 Plan 05-03 to generate it"
        )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    required = {"schema_version", "git_commit", "gauntlet", "gates_passed"}
    missing = required - evidence.keys()
    if missing:
        raise ValueError(f"evidence is missing required fields: {sorted(missing)}")
    return evidence


def test_assert_positive_elo_with_ci_accepts_and_names_d12() -> None:
    report = {
        "aggregate": {
            "elo": 25.0,
            "elo_ci_low": 5.0,
            "elo_ci_high": 45.0,
        }
    }

    assert_positive_elo_with_ci(report)
    report["aggregate"]["elo_ci_low"] = 0.0
    with pytest.raises(AssertionError, match="D-12"):
        assert_positive_elo_with_ci(report)


def test_assert_minimum_games_names_d10() -> None:
    report = {"aggregate": {"n_games": 999}}

    with pytest.raises(AssertionError, match="D-10"):
        assert_minimum_games(report, 1000)

    report["aggregate"]["n_games"] = 1000
    assert_minimum_games(report, 1000)


def test_load_evidence_parses_schema_and_explains_missing_artifact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    expected = {
        "schema_version": 1,
        "git_commit": "abc123",
        "gauntlet": {"games": 1000},
        "gates_passed": ["D-12", "TOOL-04"],
    }
    path.write_text(json.dumps(expected), encoding="utf-8")

    assert load_evidence(path) == expected
    with pytest.raises(FileNotFoundError, match="Plan 05-03"):
        load_evidence(tmp_path / "missing.json")


def test_thousand_game_evidence_gate_is_slow_marked() -> None:
    marks = getattr(
        test_phase5_thousand_game_nnue_vs_handcrafted_evidence,
        "pytestmark",
        [],
    )

    assert any(mark.name == "slow" for mark in marks)


@pytest.mark.slow
def test_phase5_thousand_game_nnue_vs_handcrafted_evidence(tmp_path: Path) -> None:
    net_path = Path("ance/eval/nnue/net.safetensors")
    assert net_path.is_file(), f"missing NNUE weights: {net_path}"

    checkpoint = Path(
        os.environ.get(
            "ANCE_PHASE5_GAUNTLET_CHECKPOINT",
            str(tmp_path / "phase5-1000-game-checkpoint.json"),
        )
    )
    evidence_path = Path(
        os.environ.get(
            "ANCE_PHASE5_GAUNTLET_EVIDENCE",
            ".planning/phases/05-nnue-swap-in-elo-gauntlet/"
            "05-GAUNTLET-EVIDENCE.json",
        )
    )
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
        str(checkpoint),
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
    started = time.monotonic()
    report = gauntlet.run_gauntlet(
        spec_nnue,
        spec_hc,
        gauntlet.load_openings(openings_path),
        n_games=D12_GAMES,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=MAX_HALFMOVES,
        output_path=checkpoint,
        deadline=time.monotonic() + BUDGET_SECONDS,
        openings_path=openings_path,
        command_line=shlex.join(command),
        search_depth=SEARCH_DEPTH,
    )
    wall_clock_elapsed_s = time.monotonic() - started

    assert_minimum_games(report, D12_GAMES)
    assert report["status"] == "completed"
    assert report["parameters"]["mode"] == "fixed_depth"
    assert report["parameters"]["search_depth"] == SEARCH_DEPTH
    env_a = report["parameters"]["engine_a"]["env"]
    env_b = report["parameters"]["engine_b"]["env"]
    assert env_a.get("ANCE_EVAL") == "nnue"
    assert env_b.get("ANCE_EVAL") == "handcrafted"
    assert env_a.keys() == env_b.keys() == {"ANCE_EVAL"}
    assert (
        report["parameters"]["engine_a"]["argv"]
        == report["parameters"]["engine_b"]["argv"]
    )

    aggregate = report["aggregate"]
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
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
            "elo": None if isinstance(aggregate["elo"], float) and math.isinf(aggregate["elo"]) else aggregate["elo"],
            "elo_ci_low": None if isinstance(aggregate["elo_ci_low"], float) and math.isinf(aggregate["elo_ci_low"]) else aggregate["elo_ci_low"],
            "elo_ci_high": None if isinstance(aggregate["elo_ci_high"], float) and math.isinf(aggregate["elo_ci_high"]) else aggregate["elo_ci_high"],
            "runner": runner,
            "command_line": report["command_line"],
            "elapsed_s": aggregate["elapsed_s"],
            "wall_clock_elapsed_s": wall_clock_elapsed_s,
            "status": report["status"],
            "checkpoint": str(checkpoint),
            "engine_a_env": env_a,
            "engine_b_env": env_b,
        },
        "gates_passed": ["D-12", "TOOL-04"] if d12_pass else [],
    }
    if not d12_pass:
        evidence["gates_failed"] = ["D-12", "TOOL-04"]

    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )

    assert_positive_elo_with_ci(report)
