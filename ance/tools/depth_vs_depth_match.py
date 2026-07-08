"""Depth-vs-depth self-play mini-match (D-14).

Measures whether deeper search never plays measurably worse than a shallower
counterpart on the same evaluator, alternating colors for fairness.
"""

from __future__ import annotations

import threading

import chess

from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.search.negamax import search_root


def play_depth_match_game(
    shallow_depth: int,
    deep_depth: int,
    evaluator: Evaluator,
    deep_plays_white: bool,
    seed: int,
    max_halfmoves: int = 300,
) -> str:
    """Returns game result from the deeper side's perspective."""
    pos = Position()
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
        return "1/2-1/2"

    result = pos.board.result()
    if deep_color == chess.WHITE:
        return result
    if result == "1-0":
        return "0-1"
    if result == "0-1":
        return "1-0"
    return "1/2-1/2"


def run_depth_match(
    shallow_depth: int,
    deep_depth: int,
    n_games: int,
    evaluator: Evaluator,
) -> dict:
    """Play ``n_games`` games and return deeper-side scoring stats."""
    wins = draws = losses = 0
    for seed in range(n_games):
        deep_white = seed % 2 == 0
        outcome = play_depth_match_game(
            shallow_depth, deep_depth, evaluator, deep_white, seed
        )
        if outcome == "1/2-1/2":
            draws += 1
        elif (outcome == "1-0" and deep_white) or (outcome == "0-1" and not deep_white):
            wins += 1
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
