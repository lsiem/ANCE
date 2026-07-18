"""768-index perspective-relative board feature encoding.

Canonical board768 scheme for this phase — Phase 5's engine-side encoder
must mirror this bit-for-bit. Built directly on ``chess.Board``; does not
import ``ance.board.position.Position``.

Copied from ``training/data/features.py`` (plus engine-side index helpers)
so the engine never imports ``training/``.
"""

from __future__ import annotations

import numpy as np
import chess

NUM_FEATURES = 768


def piece_type_index(piece_type: int) -> int:
    return piece_type - 1


def relative_square(square: int, perspective: bool) -> int:
    if perspective == chess.WHITE:
        return square
    return square ^ 56


def feature_index(
    perspective: bool,
    piece_square: int,
    piece_type: int,
    piece_color: bool,
) -> int:
    relative_color = 0 if piece_color == perspective else 1
    return (
        relative_color * 384
        + piece_type_index(piece_type) * 64
        + relative_square(piece_square, perspective)
    )


def active_feature_indices(board: chess.Board, perspective: bool) -> list[int]:
    """Sparse active board768 indices for one color perspective."""
    indices: list[int] = []
    for square, piece in board.piece_map().items():
        indices.append(
            feature_index(
                perspective,
                square,
                piece.piece_type,
                piece.color,
            )
        )
    return indices


def encode_perspective(board: chess.Board, perspective: bool) -> np.ndarray:
    features = np.zeros(NUM_FEATURES, dtype=np.float32)
    for index in active_feature_indices(board, perspective):
        features[index] = 1.0
    return features


def encode_position_board(
    board: chess.Board,
) -> tuple[np.ndarray, np.ndarray]:
    """Encode STM/OPP perspectives directly from a board (no FEN round-trip)."""
    stm = board.turn
    opp = not stm
    return encode_perspective(board, stm), encode_perspective(board, opp)


def encode_position(fen: str) -> tuple[np.ndarray, np.ndarray]:
    """FEN convenience wrapper — kept for training/test parity helpers."""
    return encode_position_board(chess.Board(fen))
