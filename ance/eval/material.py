"""Bootstrap `Evaluator` implementations proving the swap seam (D-00a).

`MaterialEval` sums the Simplified Evaluation Function's piece values
(D-05) with no positional terms -- the full PST/mobility/pawn-structure
terms (D-06) are Plan 01-04's job. `NaiveEval` always returns `0` and
exists purely so Task 2's structural test can prove
`ance/search/negamax.py` depends only on the `Evaluator` Protocol, never a
concrete class.
"""

from __future__ import annotations

import chess

from ance.board.position import Position

# Simplified Evaluation Function piece values (D-05); king excluded (its
# value is implicit in checkmate detection, never summed as material).
PIECE_VALUES: dict[chess.PieceType, int] = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
}


class MaterialEval:
    """Side-to-move-relative material count only -- no positional terms."""

    def evaluate(self, pos: Position) -> int:
        board = pos.board
        stm = board.turn
        score = 0
        for piece_type, value in PIECE_VALUES.items():
            score += value * len(board.pieces(piece_type, stm))
            score -= value * len(board.pieces(piece_type, not stm))
        return score


class NaiveEval:
    """Always scores `0`. Used only to prove the swap seam structurally
    (Task 2) and to force root-move ties for the RNG tie-break test."""

    def evaluate(self, pos: Position) -> int:
        return 0
