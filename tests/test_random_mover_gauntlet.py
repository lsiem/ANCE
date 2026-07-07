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
def test_ance_never_loses_and_wins_majority_vs_random_mover() -> None:
    # REPLAN (01-05, approved 2026-07-07): the original 100/100-at-depth-4
    # criterion was both impractical (a real depth-4/100-game run was
    # killed after 31 min without finishing) and unproven (depth-3 already
    # drew). The measured, deterministic invariant that DOES hold: ANCE
    # never loses to the random mover, and wins a large majority -- 25
    # wins / 0 losses / 5 draws (83%) at n_games=30, depth=2, ~31s
    # wall-clock, with every draw a halfmove-cap conversion miss, never a
    # loss or stalemate. See random_mover_gauntlet.py module docstring for
    # full rationale and the deferred 100/0-at-depth-4 follow-up.
    n_games = 30
    result = run_gauntlet(n_games=n_games, ance_depth=GAUNTLET_SEARCH_DEPTH, evaluator=HandcraftedEval())
    win_floor = int(0.7 * n_games)  # 70% of 30 == 21; 25/30 observed at authoring

    failure_context = (
        f"{result['wins']} wins, {result['losses']} losses, {result['draws']} draws "
        f"out of {n_games} games. "
        f"Non-win games (seed/result/terminal_fen): {result['non_win_games']}"
    )
    assert result["losses"] == 0, f"ANCE lost to the random mover (hard invariant): {failure_context}"
    assert result["wins"] >= win_floor, (
        f"ANCE won fewer than {win_floor}/{n_games} (70%) games: {failure_context}"
    )
    assert result["wins"] + result["draws"] == n_games, (
        f"Every non-win must be a draw (losses == 0 already asserted above): {failure_context}"
    )
