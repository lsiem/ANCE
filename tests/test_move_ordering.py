"""Move-ordering contracts for hash, MVV-LVA, killers, and history (D-07..D-10)."""

from __future__ import annotations

import chess

from ance.search.negamax import _qsearch_moves
from ance.search.ordering import (
    HISTORY_CAP,
    KILLER_1_SCORE,
    new_history,
    new_killers,
    order_moves,
    score_move,
    update_history,
    update_killers,
)


def _ordering_board() -> chess.Board:
    board = chess.Board(None)
    board.turn = chess.WHITE
    board.set_piece_at(chess.A1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.H8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.A2, chess.Piece(chess.PAWN, chess.WHITE))
    board.set_piece_at(chess.A3, chess.Piece(chess.ROOK, chess.WHITE))
    board.set_piece_at(chess.C2, chess.Piece(chess.BISHOP, chess.WHITE))
    board.set_piece_at(chess.B3, chess.Piece(chess.QUEEN, chess.BLACK))
    board.set_piece_at(chess.D3, chess.Piece(chess.ROOK, chess.BLACK))
    return board


def test_order_moves_respects_all_score_bands() -> None:
    board = _ordering_board()
    hash_move = chess.Move.from_uci("a1b1")
    pawn_takes_queen = chess.Move.from_uci("a2b3")
    rook_takes_queen = chess.Move.from_uci("a3b3")
    bishop_takes_rook = chess.Move.from_uci("c2d3")
    killer_0 = chess.Move.from_uci("b1c3")
    killer_1 = chess.Move.from_uci("c1d2")
    quiet_high = chess.Move.from_uci("d2e4")
    quiet_low = chess.Move.from_uci("e2e3")
    history = new_history()
    history[int(board.turn)][quiet_high.from_square][quiet_high.to_square] = 17
    history[int(board.turn)][quiet_low.from_square][quiet_low.to_square] = 3

    ordered = order_moves(
        [
            quiet_low,
            killer_1,
            rook_takes_queen,
            quiet_high,
            bishop_takes_rook,
            hash_move,
            killer_0,
            pawn_takes_queen,
        ],
        board,
        hash_move,
        [killer_0, killer_1],
        history,
    )

    assert ordered == [
        hash_move,
        pawn_takes_queen,
        rook_takes_queen,
        bishop_takes_rook,
        killer_0,
        killer_1,
        quiet_high,
        quiet_low,
    ]


def test_killers_shift_deduplicate_and_stay_ply_local() -> None:
    killers = new_killers()
    first = chess.Move.from_uci("e2e4")
    second = chess.Move.from_uci("d2d4")

    update_killers(killers[3], first)
    update_killers(killers[3], second)
    assert killers[3] == [second, first]

    update_killers(killers[3], second)
    assert killers[3] == [second, first]
    assert killers[2] == [None, None]

    board = chess.Board()
    ordered = order_moves([first, second], board, None, killers[2], new_history())
    assert ordered == [first, second]


def test_history_adds_depth_squared_and_ages_the_whole_table() -> None:
    history = new_history()
    move = chess.Move.from_uci("e2e4")
    other = chess.Move.from_uci("d2d4")
    side = int(chess.WHITE)

    update_history(history, side, move, depth=3)
    assert history[side][move.from_square][move.to_square] == 9

    history[side][move.from_square][move.to_square] = HISTORY_CAP
    history[side][other.from_square][other.to_square] = 11
    update_history(history, side, move, depth=1)

    assert history[side][move.from_square][move.to_square] == (HISTORY_CAP + 1) // 2
    assert history[side][other.from_square][other.to_square] == 5
    assert max(value for colors in history for origins in colors for value in origins) < (
        KILLER_1_SCORE
    )


def test_qsearch_keeps_phase2_mvv_lva_only_ordering() -> None:
    board = _ordering_board()
    pawn_takes_queen = chess.Move.from_uci("a2b3")
    rook_takes_queen = chess.Move.from_uci("a3b3")
    bishop_takes_rook = chess.Move.from_uci("c2d3")
    quiet = chess.Move.from_uci("a1b1")

    assert _qsearch_moves(
        board,
        [quiet, bishop_takes_rook, rook_takes_queen, pawn_takes_queen],
    ) == [pawn_takes_queen, rook_takes_queen, bishop_takes_rook]


def test_quiet_queen_promotion_uses_capture_band() -> None:
    board = chess.Board("7k/P7/8/8/8/8/8/K7 w - - 0 1")
    promotion = chess.Move.from_uci("a7a8q")
    killer = chess.Move.from_uci("a1b1")

    assert score_move(promotion, board, None, [killer, None], new_history()) > score_move(
        killer,
        board,
        None,
        [killer, None],
        new_history(),
    )
