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


# D-06 positional terms, all combined white-relative below (D-07) before
# the single sign flip at the end of `HandcraftedEval.evaluate()`.
TEMPO_BONUS = 10
BISHOP_PAIR_BONUS = 30
MOBILITY_WEIGHT = 2
DOUBLED_PAWN_PENALTY = -10
ISOLATED_PAWN_PENALTY = -15


def _bishop_pair_term(board: chess.Board) -> int:
    """White-relative bishop-pair bonus: `+BISHOP_PAIR_BONUS` for White
    holding two or more bishops, `-BISHOP_PAIR_BONUS` for Black."""
    score = 0
    if len(board.pieces(chess.BISHOP, chess.WHITE)) >= 2:
        score += BISHOP_PAIR_BONUS
    if len(board.pieces(chess.BISHOP, chess.BLACK)) >= 2:
        score -= BISHOP_PAIR_BONUS
    return score


def _pawn_penalty(board: chess.Board, color: chess.Color) -> int:
    """Doubled + isolated pawn penalty for `color`, counting pawns per
    file via the bitboard `bit_count()` method (not a `bin(...).count()`
    string round-trip -- this runs per leaf at every node)."""
    pawns_bitboard = board.pieces_mask(chess.PAWN, color)
    file_counts = [(chess.BB_FILES[file] & pawns_bitboard).bit_count() for file in range(8)]

    penalty = 0
    for file, count in enumerate(file_counts):
        if count == 0:
            continue
        if count > 1:
            penalty += DOUBLED_PAWN_PENALTY * (count - 1)
        left_count = file_counts[file - 1] if file > 0 else 0
        right_count = file_counts[file + 1] if file < 7 else 0
        if left_count == 0 and right_count == 0:
            penalty += ISOLATED_PAWN_PENALTY * count
    return penalty


def _pawn_structure_term(board: chess.Board) -> int:
    """White-relative doubled/isolated pawn penalty."""
    return _pawn_penalty(board, chess.WHITE) - _pawn_penalty(board, chess.BLACK)


def _mobility_term(board: chess.Board) -> int:
    """White-relative mobility term: `MOBILITY_WEIGHT` times the side to
    move's own legal-move count minus the opponent's (obtained via the
    standard null-move idiom), converted to White's perspective. A null
    move is illegal while the side to move is in check (T-01-14) -- that
    case skips the null-move push entirely and falls back to `0` for the
    opponent-mobility sub-term rather than pushing an invalid null move.
    """
    stm = board.turn
    own_moves = len(list(board.legal_moves))

    if board.is_check():
        opponent_moves = 0
    else:
        board.push(chess.Move.null())
        try:
            opponent_moves = len(list(board.legal_moves))
        finally:
            board.pop()

    stm_relative = MOBILITY_WEIGHT * (own_moves - opponent_moves)
    return stm_relative if stm == chess.WHITE else -stm_relative


class HandcraftedEval:
    """Side-to-move-relative evaluator (D-07) combining material+PST
    (D-05) with mobility, bishop-pair, tempo, and pawn-structure
    positional terms (D-06). All terms are computed white-relative inside
    `evaluate()` and sign-flipped by `pos.board.turn` exactly once at the
    end."""

    def evaluate(self, pos: Position) -> int:
        board = pos.board
        stm = board.turn

        white_score = _material_and_pst(board, chess.WHITE) - _material_and_pst(
            board, chess.BLACK
        )
        white_score += _bishop_pair_term(board)
        white_score += _pawn_structure_term(board)
        white_score += _mobility_term(board)

        score = white_score if stm == chess.WHITE else -white_score
        score += TEMPO_BONUS
        return score
