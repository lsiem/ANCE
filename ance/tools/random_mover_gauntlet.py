"""Self-play gauntlet: ANCE's real `search_root` + evaluator, in-process
(not over a UCI pipe -- this is a measurement tool, not a protocol test),
against a uniformly-random legal-move opponent (TOOL-02).
"""

from __future__ import annotations

import random
import threading
from typing import NamedTuple

import chess

from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.search.negamax import search_root


class RandomMover:
    """Uniformly-random legal-move chooser, seeded for reproducibility."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def choose(self, board: chess.Board) -> chess.Move:
        return self._rng.choice(list(board.legal_moves))


class GameResult(NamedTuple):
    """Outcome of a single `play_game()` call: the python-chess result
    string plus the final position's FEN, so a non-win game can be
    diagnosed later without replaying it (cross-AI review finding)."""

    result: str
    terminal_fen: str


def play_game(
    ance_depth: int,
    ance_evaluator: Evaluator,
    ance_plays_white: bool,
    seed: int,
    max_halfmoves: int = 300,
) -> GameResult:
    """Plays one game between ANCE (`search_root` + `ance_evaluator`) and a
    seeded `RandomMover`, alternating turns until `pos.board.is_game_over()`
    or the `max_halfmoves` safety cap is hit (T-01-11: guarantees this
    function always terminates even if a bug ever produced a pathological
    non-terminating line; a cap-hit is treated as `"1/2-1/2"` to keep this
    function total).

    Each ANCE move gets a fresh, un-set `threading.Event()` since this
    harness never needs to interrupt a search, and a fresh
    `random.Random(seed)` for negamax's root tie-break RNG.
    """
    pos = Position()
    halfmoves = 0
    ance_color = chess.WHITE if ance_plays_white else chess.BLACK

    while not pos.board.is_game_over() and halfmoves < max_halfmoves:
        if pos.board.turn == ance_color:
            move = search_root(pos, ance_depth, ance_evaluator, threading.Event(), random.Random(seed))
        else:
            move = RandomMover(seed).choose(pos.board)
        if move is None:
            break
        pos.board.push(move)
        halfmoves += 1

    result = pos.board.result() if pos.board.is_game_over() else "1/2-1/2"
    return GameResult(result=result, terminal_fen=pos.board.fen())
