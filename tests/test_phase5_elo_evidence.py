"""Phase 5 TOOL-04 Elo evidence gates (D-09, D-10, D-11, D-12)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160


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
    pytest.skip("Task 2")
