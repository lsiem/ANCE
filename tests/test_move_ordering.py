"""Move-ordering contracts for hash, MVV-LVA, killers, and history (D-07..D-10)."""

from __future__ import annotations

import importlib
import threading

import chess
import chess.polyglot

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.handcrafted import HandcraftedEval
from ance.eval.material import MaterialEval
from ance.search.negamax import _qsearch_moves, search_root
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
from ance.search.transposition import EXACT, TranspositionTable
from ance.search.types import SearchContext


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


def _never_stop() -> threading.Event:
    return threading.Event()


def test_tt_hash_move_is_searched_first_at_matching_node(
    monkeypatch,
) -> None:
    negamax_module = importlib.import_module("ance.search.negamax")
    original_negamax = negamax_module.negamax
    pos = Position()
    hash_move = chess.Move.from_uci("d2d4")
    table = TranspositionTable(16)
    table.store(
        chess.polyglot.zobrist_hash(pos.board),
        depth=0,
        score=0,
        flag=EXACT,
        best_move=hash_move,
    )
    searched: list[chess.Move] = []

    def child_spy(pos, depth, alpha, beta, ctx):
        del depth, alpha, beta, ctx
        searched.append(pos.board.peek())
        return 0

    monkeypatch.setattr(negamax_module, "negamax", child_spy)
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        tt=table,
        killers=new_killers(),
        history=new_history(),
    )

    original_negamax(pos, depth=1, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)

    assert searched[0] == hash_move


def test_quiet_beta_cutoff_updates_killer_and_history_but_capture_does_not(
    monkeypatch,
) -> None:
    negamax_module = importlib.import_module("ance.search.negamax")
    original_negamax = negamax_module.negamax
    monkeypatch.setattr(negamax_module, "negamax", lambda *args, **kwargs: -10)

    quiet_pos = Position()
    quiet_killers = new_killers()
    quiet_history = new_history()
    expected_quiet = order_moves(
        quiet_pos.legal_moves(),
        quiet_pos.board,
        None,
        quiet_killers[0],
        quiet_history,
    )[0]
    quiet_ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        killers=quiet_killers,
        history=quiet_history,
    )

    original_negamax(quiet_pos, depth=3, alpha=-MATE - 1, beta=0, ctx=quiet_ctx)

    assert quiet_killers[0][0] == expected_quiet
    assert (
        quiet_history[int(chess.WHITE)][expected_quiet.from_square][
            expected_quiet.to_square
        ]
        == 9
    )

    capture_pos = Position(chess.Board("4k3/8/8/4q3/8/8/8/4R2K w - - 0 1"))
    capture_killers = new_killers()
    capture_history = new_history()
    capture_ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        killers=capture_killers,
        history=capture_history,
    )

    original_negamax(capture_pos, depth=3, alpha=-MATE - 1, beta=0, ctx=capture_ctx)

    assert all(slots == [None, None] for slots in capture_killers)
    assert not any(value for colors in capture_history for origins in colors for value in origins)


def test_search_shares_killer_and_history_tables_across_all_contexts(
    monkeypatch,
) -> None:
    negamax_module = importlib.import_module("ance.search.negamax")
    original_negamax = negamax_module.negamax
    killers = new_killers()
    history = new_history()
    observed: list[SearchContext] = []

    def context_spy(pos, depth, alpha, beta, ctx):
        observed.append(ctx)
        return original_negamax(pos, depth, alpha, beta, ctx)

    monkeypatch.setattr(negamax_module, "negamax", context_spy)

    search_root(
        Position(),
        max_depth=2,
        evaluator=MaterialEval(),
        stop_flag=_never_stop(),
        killers=killers,
        history=history,
    )

    assert observed
    assert {ctx.ply for ctx in observed}.issuperset({1, 2})
    assert all(ctx.killers is killers for ctx in observed)
    assert all(ctx.history is history for ctx in observed)


def test_ordering_without_tt_beats_phase2_italian_node_count() -> None:
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 3"

    result = search_root(
        Position(chess.Board(fen)),
        max_depth=4,
        evaluator=HandcraftedEval(),
        stop_flag=_never_stop(),
        tt=None,
        killers=new_killers(),
        history=new_history(),
    )

    assert result.nodes < 501_208


def test_ucinewgame_resets_killers_and_history() -> None:
    import ance.uci.loop as loop

    old_killers = loop.killer_moves
    old_history = loop.history_table
    old_killers[2][0] = chess.Move.from_uci("e2e4")
    old_history[int(chess.WHITE)][chess.E2][chess.E4] = 99

    loop.handle_ucinewgame(Position())

    assert loop.killer_moves is not old_killers
    assert loop.history_table is not old_history
    assert all(slots == [None, None] for slots in loop.killer_moves)
    assert not any(
        value
        for colors in loop.history_table
        for origins in colors
        for value in origins
    )
