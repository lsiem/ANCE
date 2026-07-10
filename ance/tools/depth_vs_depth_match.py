"""Depth-vs-depth self-play mini-match (D-14).

Measures whether deeper search never plays measurably worse than a shallower
counterpart on the same evaluator, alternating colors for fairness.
"""

from __future__ import annotations

import threading
from typing import Literal

import chess

from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.search.negamax import search_root

DepthMatchOutcome = Literal["win", "draw", "loss"]

OPENING_LINES: tuple[tuple[str, ...], ...] = (
    ("e2e4", "e7e5", "g1f3", "b8c6"),
    ("d2d4", "d7d5", "c2c4", "e7e6"),
    ("c2c4", "e7e5", "b1c3", "g8f6"),
    ("g1f3", "d7d5", "d2d4", "g8f6"),
    ("b2b3", "e7e5", "c1b2", "b8c6"),
    ("g2g3", "d7d5", "f1g2", "g8f6"),
    ("f2f4", "d7d5", "g1f3", "g8f6"),
    ("b1c3", "d7d5", "e2e4", "d5e4"),
)


def _opening_for_seed(seed: int) -> tuple[str, ...]:
    """Select one reproducible opening line for ``seed``."""
    return OPENING_LINES[seed % len(OPENING_LINES)]


def _apply_opening(pos: Position, line: tuple[str, ...]) -> None:
    """Validate and apply a predefined UCI opening line."""
    for move_uci in line:
        pos.board.push_uci(move_uci)


def play_depth_match_game(
    shallow_depth: int,
    deep_depth: int,
    evaluator: Evaluator,
    deep_plays_white: bool,
    seed: int,
    max_halfmoves: int = 300,
) -> DepthMatchOutcome:
    """Returns game result from the deeper side's perspective."""
    pos = Position()
    _apply_opening(pos, _opening_for_seed(seed))
    halfmoves = 0
    deep_color = chess.WHITE if deep_plays_white else chess.BLACK

    while not pos.board.is_game_over() and halfmoves < max_halfmoves:
        depth = deep_depth if pos.board.turn == deep_color else shallow_depth
        move = search_root(
            pos, max_depth=depth, evaluator=evaluator, stop_flag=threading.Event()
        ).best_move
        if move is None:
            break
        pos.board.push(move)
        halfmoves += 1

    if not pos.board.is_game_over():
        return "draw"

    result = pos.board.result()
    if result == "1/2-1/2":
        return "draw"
    deep_won = (deep_color == chess.WHITE and result == "1-0") or (
        deep_color == chess.BLACK and result == "0-1"
    )
    return "win" if deep_won else "loss"


def run_depth_match(
    shallow_depth: int,
    deep_depth: int,
    n_games: int,
    evaluator: Evaluator,
    seed: int = 0,
    max_halfmoves: int = 300,
) -> dict:
    """Play ``n_games`` games and return deeper-side scoring stats."""
    if n_games <= 0:
        raise ValueError("n_games must be positive")

    wins = draws = losses = 0
    for game_index in range(n_games):
        deep_white = game_index % 2 == 0
        outcome = play_depth_match_game(
            shallow_depth,
            deep_depth,
            evaluator,
            deep_white,
            seed + game_index,
            max_halfmoves,
        )
        if outcome == "win":
            wins += 1
        elif outcome == "draw":
            draws += 1
        else:
            losses += 1

    score_rate = (wins + 0.5 * draws) / n_games
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score_rate": score_rate,
        "n_games": n_games,
    }
