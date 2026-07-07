"""Tests for the self-play gauntlet tooling (TOOL-02).

Task 1 covers the fast building blocks (`RandomMover`, `play_game`) with a
cheap `MaterialEval` so the suite stays fast under `-m "not slow"`. Task 2
adds the `slow`-marked 100-game proof against the real `HandcraftedEval`.
"""

from __future__ import annotations

import chess
import pytest

from ance.eval.handcrafted import HandcraftedEval
from ance.eval.material import MaterialEval
from ance.tools.random_mover_gauntlet import (
    GAUNTLET_SEARCH_DEPTH,
    RandomMover,
    play_game,
    run_gauntlet,
)


def test_random_mover_picks_legal_move() -> None:
    board = chess.Board()
    move = RandomMover(seed=0).choose(board)
    assert move in list(board.legal_moves)


def test_random_mover_is_deterministic_per_seed() -> None:
    board = chess.Board()
    move_a = RandomMover(seed=7).choose(board)
    move_b = RandomMover(seed=7).choose(board)
    assert move_a == move_b

    # A different seed is not guaranteed to differ for every board, but for
    # the startpos with seed 7 vs. seed 8 it does -- pinned here to prove
    # the seed actually flows into the RNG rather than being ignored.
    move_c = RandomMover(seed=8).choose(board)
    assert move_a != move_c


def test_play_game_terminates_with_a_valid_result() -> None:
    result = play_game(
        ance_depth=2,
        ance_evaluator=MaterialEval(),
        ance_plays_white=True,
        seed=0,
        max_halfmoves=300,
    )
    assert result.result in {"1-0", "0-1", "1/2-1/2"}
    assert result.terminal_fen != ""


@pytest.mark.slow
def test_ance_beats_random_mover_100_of_100() -> None:
    result = run_gauntlet(n_games=100, ance_depth=GAUNTLET_SEARCH_DEPTH, evaluator=HandcraftedEval())
    assert result["wins"] == 100 and result["losses"] == 0, (
        f"ANCE failed to beat the random mover 100/100: {result['wins']} wins, "
        f"{result['losses']} losses, {result['draws']} draws. "
        f"Non-win games (seed/result/terminal_fen): {result['non_win_games']}"
    )
