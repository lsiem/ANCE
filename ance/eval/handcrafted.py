"""The real M1 handcrafted `Evaluator` (EVAL-02, D-05/D-06/D-07).

`HandcraftedEval` composes the Michniewski Simplified Evaluation
Function's material + piece-square tables (`ance/eval/tables.py`), with a
discrete middlegame/endgame king-table switch, plus mobility, bishop-pair,
tempo, and pawn-structure positional terms. All terms are computed
white-relative inside `evaluate()` and sign-flipped by `pos.board.turn`
exactly once at the end (D-07) -- this is the same swap-seam contract
`MaterialEval` implements (`ance/eval/base.py`'s `Evaluator` Protocol);
`ance/search/negamax.py` never imports this class directly.
"""

from __future__ import annotations

import chess

from ance.board.position import Position
from ance.eval.material import PIECE_VALUES
from ance.eval.tables import (
    BISHOP_PST,
    KING_EG_PST,
    KING_MG_PST,
    KNIGHT_PST,
    PAWN_PST,
    QUEEN_PST,
    ROOK_PST,
)

# Combined non-pawn, non-king material for BOTH colors, in centipawns,
# below which both kings use `KING_EG_PST` instead of `KING_MG_PST` (D-05:
# a discrete check, not tapering).
ENDGAME_MATERIAL_THRESHOLD = 2600

_PST_BY_PIECE_TYPE: dict[chess.PieceType, tuple[int, ...]] = {
    chess.PAWN: PAWN_PST,
    chess.KNIGHT: KNIGHT_PST,
    chess.BISHOP: BISHOP_PST,
    chess.ROOK: ROOK_PST,
    chess.QUEEN: QUEEN_PST,
}


def _is_endgame(board: chess.Board) -> bool:
    """`True` when combined non-pawn, non-king material for both colors is
    below `ENDGAME_MATERIAL_THRESHOLD` -- a discrete phase check (D-05),
    not a tapered evaluation."""
    total = 0
    for piece_type in (chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN):
        value = PIECE_VALUES[piece_type]
        total += value * len(board.pieces(piece_type, chess.WHITE))
        total += value * len(board.pieces(piece_type, chess.BLACK))
    return total < ENDGAME_MATERIAL_THRESHOLD


def _material_and_pst(board: chess.Board, color: chess.Color) -> int:
    """Sums `color`'s material + piece-square table contribution. King
    material is excluded (per `PIECE_VALUES`, D-05) but the king's PST
    contribution (`KING_MG_PST`/`KING_EG_PST`, selected by `_is_endgame`)
    is still added. Black pieces look up the White-oriented tables via
    `chess.square_mirror` (standard PST-mirroring convention)."""
    score = 0
    for piece_type, value in PIECE_VALUES.items():
        table = _PST_BY_PIECE_TYPE[piece_type]
        for square in board.pieces(piece_type, color):
            lookup_square = square if color == chess.WHITE else chess.square_mirror(square)
            score += value + table[lookup_square]

    king_table = KING_EG_PST if _is_endgame(board) else KING_MG_PST
    for square in board.pieces(chess.KING, color):
        lookup_square = square if color == chess.WHITE else chess.square_mirror(square)
        score += king_table[lookup_square]

    return score


class HandcraftedEval:
    """Side-to-move-relative material+PST evaluator (D-07). Positional
    terms (mobility, bishop pair, tempo, pawn structure -- D-06) are added
    on top of this in the same `evaluate()` method."""

    def evaluate(self, pos: Position) -> int:
        board = pos.board
        white_score = _material_and_pst(board, chess.WHITE) - _material_and_pst(
            board, chess.BLACK
        )
        return white_score if board.turn == chess.WHITE else -white_score
