"""Phase 3 statistical gauntlet evidence gates (D-14, D-17, D-19)."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pytest

from ance.tools import gauntlet


D14_GAMES = 100
D14_TC = "30+0.3"
D17_GAMES = 100
D17_TC = "30+0.3"
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160


def assert_zero_forfeits(report: dict) -> None:
    """Assert D-14's zero-time-forfeit acceptance gate."""
    forfeits = report["aggregate"]["time_forfeits"]
    offenders = {name: count for name, count in forfeits.items() if count}
    assert not offenders, f"D-14 time forfeits detected: {offenders}"


def assert_sanity_ci_contains_half(report: dict) -> None:
    """Assert D-17's identical-engine Wilson interval contains 50%."""
    aggregate = report["aggregate"]
    low = aggregate["wilson_low"]
    high = aggregate["wilson_high"]
    assert low <= 0.50 <= high, (
        "D-17 Wilson 95% score interval does not contain 0.50: "
        f"[{low}, {high}]"
    )


def load_evidence(path: str | Path) -> dict:
    """Load the committed D-14/D-17 evidence artifact."""
    evidence_path = Path(path)
    if not evidence_path.exists():
        raise FileNotFoundError(
            f"{evidence_path} is missing; run Phase 3 Plan 03-06 to generate it"
        )
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    required = {"schema_version", "git_commit", "gauntlet", "gates_passed"}
    missing = required - evidence.keys()
    if missing:
        raise ValueError(f"evidence is missing required fields: {sorted(missing)}")
    return evidence


def test_d17_sanity_ci_helper_accepts_half_and_names_failed_gate() -> None:
    report = {
        "aggregate": {
            "score_rate": 0.52,
            "n_games": 100,
            "wilson_low": 0.43,
            "wilson_high": 0.61,
        }
    }

    assert_sanity_ci_contains_half(report)
    report["aggregate"]["wilson_high"] = 0.49
    with pytest.raises(AssertionError, match="D-17"):
        assert_sanity_ci_contains_half(report)


def test_d14_zero_forfeit_helper_names_offending_engine() -> None:
    report = {"aggregate": {"time_forfeits": {"ance": 0, "ance-b": 0}}}

    assert_zero_forfeits(report)
    report["aggregate"]["time_forfeits"]["ance-b"] = 1
    with pytest.raises(AssertionError, match=r"D-14.*ance-b"):
        assert_zero_forfeits(report)


def test_load_evidence_parses_schema_and_explains_missing_artifact(
    tmp_path: Path,
) -> None:
    path = tmp_path / "evidence.json"
    expected = {
        "schema_version": 1,
        "git_commit": "abc123",
        "gauntlet": {"games": 100},
        "gates_passed": ["D-14", "D-17"],
    }
    path.write_text(json.dumps(expected), encoding="utf-8")

    assert load_evidence(path) == expected
    with pytest.raises(FileNotFoundError, match="Plan 03-06"):
        load_evidence(tmp_path / "missing.json")


def test_hundred_game_evidence_gate_is_slow_marked() -> None:
    marks = getattr(test_phase3_hundred_game_blitz_evidence_d14_d17, "pytestmark", [])

    assert any(mark.name == "slow" for mark in marks)


@pytest.mark.slow
def test_phase3_hundred_game_blitz_evidence_d14_d17(tmp_path: Path) -> None:
    checkpoint = Path(
        os.environ.get(
            "ANCE_PHASE3_GAUNTLET_CHECKPOINT",
            tmp_path / "phase3-100-game-checkpoint.json",
        )
    )
    evidence_path = Path(
        os.environ.get(
            "ANCE_PHASE3_GAUNTLET_EVIDENCE",
            ".planning/phases/03-search-acceleration-time-management/"
            "03-GAUNTLET-EVIDENCE.json",
        )
    )
    openings_path = gauntlet.DEFAULT_OPENINGS
    spec_a = gauntlet.EngineSpec("ance-a", list(ENGINE_ARGV))
    spec_b = gauntlet.EngineSpec("ance-b", list(ENGINE_ARGV))
    command = [
        sys.executable,
        "-m",
        "ance.tools.gauntlet",
        "--games",
        str(D14_GAMES),
        "--tc",
        D14_TC,
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
        spec_a.name,
        "--engine-b-name",
        spec_b.name,
        "--runner",
        "arbiter",
        "--budget-seconds",
        "18000",
    ]
    started = time.monotonic()
    report = gauntlet.run_gauntlet(
        spec_a,
        spec_b,
        gauntlet.load_openings(openings_path),
        n_games=D14_GAMES,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=MAX_HALFMOVES,
        output_path=checkpoint,
        deadline=time.monotonic() + 18_000,
        openings_path=openings_path,
        command_line=shlex.join(command),
    )
    wall_clock_elapsed_s = time.monotonic() - started

    assert_zero_forfeits(report)
    assert_sanity_ci_contains_half(report)
    assert report["status"] == "completed"
    assert report["aggregate"]["n_games"] == D17_GAMES

    aggregate = report["aggregate"]
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        text=True,
    ).strip()
    evidence = {
        "schema_version": 1,
        "git_commit": git_commit,
        "captured_utc": datetime.now(UTC).isoformat(),
        "gauntlet": {
            "games": aggregate["n_games"],
            "tc": D14_TC,
            "wins": aggregate["wins"],
            "losses": aggregate["losses"],
            "draws": aggregate["draws"],
            "score_rate": aggregate["score_rate"],
            "draw_rate": aggregate["draw_rate"],
            "wilson_low": aggregate["wilson_low"],
            "wilson_high": aggregate["wilson_high"],
            "time_forfeits": aggregate["time_forfeits"],
            "command_line": report["command_line"],
            "elapsed_s": aggregate["elapsed_s"],
            "wall_clock_elapsed_s": wall_clock_elapsed_s,
            "status": report["status"],
        },
        "gates_passed": ["D-14", "D-17"],
    }
    evidence_path.parent.mkdir(parents=True, exist_ok=True)
    evidence_path.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )
