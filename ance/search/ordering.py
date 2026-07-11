"""Main-search move ordering with bounded per-game heuristics (D-07..D-10)."""

from __future__ import annotations

import chess

from ance.search.types import MAX_PLY

HASH_MOVE_SCORE = 1_000_000
CAPTURE_BASE = 100_000
KILLER_0_SCORE = 90_000
KILLER_1_SCORE = 80_000
HISTORY_CAP = 79_000

_MVV_LVA = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 10000,
}


def _capture_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return _MVV_LVA[chess.PAWN]
    if move.promotion is not None:
        return _MVV_LVA[move.promotion]
    piece = board.piece_at(move.to_square)
    return _MVV_LVA[piece.piece_type] if piece is not None else 0


def _mvv_lva_sort(moves: list[chess.Move], board: chess.Board) -> list[chess.Move]:
    def key(move: chess.Move) -> tuple[int, int]:
        victim = _capture_value(board, move)
        attacker_piece = board.piece_at(move.from_square)
        attacker = _MVV_LVA[attacker_piece.piece_type] if attacker_piece else 0
        return (victim, -attacker)

    return sorted(moves, key=key, reverse=True)


def score_move(
    move: chess.Move,
    board: chess.Board,
    hash_move: chess.Move | None,
    killers_at_ply: list[chess.Move | None] | tuple[None, None],
    history: list[list[list[int]]] | None,
) -> int:
    """Return a score whose disjoint bands encode D-07 ordering."""
    if move == hash_move:
        return HASH_MOVE_SCORE
    if board.is_capture(move) or move.promotion is not None:
        attacker_piece = board.piece_at(move.from_square)
        attacker = _MVV_LVA[attacker_piece.piece_type] if attacker_piece else 0
        return CAPTURE_BASE + 100 * _capture_value(board, move) - attacker
    if move == killers_at_ply[0]:
        return KILLER_0_SCORE
    if move == killers_at_ply[1]:
        return KILLER_1_SCORE
    if history is None:
        return 0
    return history[int(board.turn)][move.from_square][move.to_square]


def order_moves(
    moves: list[chess.Move],
    board: chess.Board,
    hash_move: chess.Move | None,
    killers_at_ply: list[chess.Move | None] | tuple[None, None],
    history: list[list[list[int]]] | None,
) -> list[chess.Move]:
    """Order one legal move list with a single stable descending sort."""
    return sorted(
        moves,
        key=lambda move: score_move(
            move, board, hash_move, killers_at_ply, history
        ),
        reverse=True,
    )


def new_killers() -> list[list[chess.Move | None]]:
    return [[None, None] for _ in range(MAX_PLY + 1)]


def new_history() -> list[list[list[int]]]:
    return [[[0 for _ in range(64)] for _ in range(64)] for _ in range(2)]


def update_killers(slots: list[chess.Move | None], move: chess.Move) -> None:
    if move != slots[0]:
        slots[1] = slots[0]
        slots[0] = move


def update_history(
    history: list[list[list[int]]],
    side: int,
    move: chess.Move,
    depth: int,
) -> None:
    origin = move.from_square
    destination = move.to_square
    history[side][origin][destination] += depth * depth
    if history[side][origin][destination] <= HISTORY_CAP:
        return
    for colors in history:
        for origins in colors:
            for index, value in enumerate(origins):
                origins[index] = value // 2
