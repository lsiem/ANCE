"""Phase 3 statistical gauntlet evidence gates (D-14, D-17, D-19)."""

from __future__ import annotations

import json
import sys
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
    del tmp_path
    raise NotImplementedError("Task 2 supplies the real 100-game evidence gate")
