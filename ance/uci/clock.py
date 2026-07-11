"""Pure UCI clock budgeting for D-11 through D-13 and UCI-08/SRCH-08."""

from __future__ import annotations

import chess

from ance.uci.parser import GoCommand

SAFETY_MARGIN_MS = 200
MIN_BUDGET_MS = 20
MOVES_TO_GO_ESTIMATE = 25
INC_CREDIT = 0.6
HARD_SOFT_MULTIPLIER = 4
MAX_REMAINING_FRACTION = 3


def compute_clock_budget(
    cmd: GoCommand,
    turn: chess.Color,
) -> tuple[float, float] | None:
    """Return soft/hard millisecond budgets for the side to move."""
    mover_remaining = cmd.wtime if turn == chess.WHITE else cmd.btime
    opponent_remaining = cmd.btime if turn == chess.WHITE else cmd.wtime
    remaining_value = (
        mover_remaining if mover_remaining is not None else opponent_remaining
    )
    if remaining_value is None:
        return None

    mover_increment = cmd.winc if turn == chess.WHITE else cmd.binc
    opponent_increment = cmd.binc if turn == chess.WHITE else cmd.winc
    increment_value = (
        mover_increment if mover_increment is not None else opponent_increment
    )
    remaining = float(max(0, remaining_value))
    increment = float(max(0, increment_value or 0))

    soft = remaining / MOVES_TO_GO_ESTIMATE + INC_CREDIT * increment
    hard = min(
        soft * HARD_SOFT_MULTIPLIER,
        remaining / MAX_REMAINING_FRACTION,
        remaining - SAFETY_MARGIN_MS,
    )
    hard = max(float(MIN_BUDGET_MS), hard)
    soft = max(float(MIN_BUDGET_MS), min(soft, hard))
    return soft, hard
