"""Clock budgeting and flag-safety contracts (D-11 through D-14)."""

from __future__ import annotations

import chess
import pytest

from ance.uci.clock import compute_clock_budget
from ance.uci.parser import GoCommand


def test_nominal_clock_budget_uses_remaining_time_and_increment() -> None:
    budget = compute_clock_budget(
        GoCommand(wtime=60_000, winc=1_000),
        chess.WHITE,
    )

    assert budget == (3_000.0, 12_000.0)


@pytest.mark.parametrize("remaining", [50, 200, 500, 1_000, 5_000, 60_000, 300_000])
@pytest.mark.parametrize("increment", [0, 100, 1_000, 5_000])
def test_clock_budget_invariants_hold_over_value_grid(
    remaining: int,
    increment: int,
) -> None:
    soft, hard = compute_clock_budget(
        GoCommand(wtime=remaining, winc=increment),
        chess.WHITE,
    )

    assert hard >= 20.0
    assert soft <= hard
    if remaining - 200 >= 20:
        assert hard <= remaining - 200


@pytest.mark.parametrize(
    "command",
    [
        GoCommand(wtime=0),
        GoCommand(wtime=-500),
        GoCommand(wtime=0, winc=-100),
        GoCommand(wtime=30),
    ],
)
def test_garbage_clock_values_clamp_to_floor(command: GoCommand) -> None:
    assert compute_clock_budget(command, chess.WHITE) == (20.0, 20.0)


def test_clock_budget_selects_movers_clock_and_falls_back_to_opponent() -> None:
    command = GoCommand(wtime=60_000, btime=30_000, winc=1_000, binc=500)

    assert compute_clock_budget(command, chess.BLACK) == (1_500.0, 6_000.0)
    assert compute_clock_budget(
        GoCommand(btime=30_000, binc=500),
        chess.WHITE,
    ) == (1_500.0, 6_000.0)
    assert compute_clock_budget(GoCommand(winc=100, binc=200), chess.WHITE) is None


@pytest.mark.parametrize(
    "command",
    [
        GoCommand(depth=4),
        GoCommand(movetime=300),
        GoCommand(infinite=True),
    ],
)
def test_non_clock_go_commands_have_no_clock_budget(command: GoCommand) -> None:
    assert compute_clock_budget(command, chess.WHITE) is None
