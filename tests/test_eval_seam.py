"""Tests proving the Evaluator seam (D-00a) is a real, swappable boundary.

Task 1 tests `MaterialEval`'s side-to-move-relative symmetry/sign behavior.
Task 2 adds `search_root`/`negamax` behavior tests plus the structural proof
that `ance/search/negamax.py` never imports a concrete evaluator class --
the seam is only "real" (not cosmetic, per project ARCHITECTURE.md
Anti-Pattern 3) if search depends solely on the `Evaluator` Protocol.
"""

from __future__ import annotations

import random

import chess

from ance.board.position import Position
from ance.eval.material import MaterialEval, NaiveEval


def test_material_eval_symmetric_position_scores_zero() -> None:
    pos = Position()
    assert MaterialEval().evaluate(pos) == 0

    # Push a null move so it's black to move on an otherwise-identical
    # board -- proving side-to-move relative symmetry (D-07), not just
    # "white == black material".
    pos.board.push(chess.Move.null())
    assert MaterialEval().evaluate(pos) == 0


def test_material_eval_reflects_material_difference_stm_relative() -> None:
    # Black is missing its queen.
    fen = "rnb1kbnr/pppp1ppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

    white_to_move = Position(chess.Board(fen))
    assert MaterialEval().evaluate(white_to_move) > 0

    black_to_move = Position(chess.Board(fen))
    black_to_move.board.turn = chess.BLACK
    assert MaterialEval().evaluate(black_to_move) < 0
