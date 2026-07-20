"""NNUE sparse refresh + incremental accumulator (performance path)."""

from __future__ import annotations

import chess
import pytest

from ance.board.position import Position
from ance.eval.nnue.eval import NnueEval
from ance.eval.nnue.features import active_feature_indices, encode_position_board
from ance.eval.nnue.inference import forward_cp_float, forward_from_accumulators


@pytest.fixture(scope="module")
def nnue() -> NnueEval:
    return NnueEval()


def test_sparse_matches_dense_on_startpos(nnue: NnueEval) -> None:
    pos = Position()
    assert nnue.evaluate(pos) == nnue.evaluate_dense_reference(pos)


def test_incremental_matches_refresh_after_moves(nnue: NnueEval) -> None:
    board = chess.Board()
    nnue.refresh(board)
    moves = ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"]
    for uci in moves:
        move = chess.Move.from_uci(uci)
        board.push(move)
        nnue.on_make(board, move)
        incremental = nnue.evaluate(Position(board))
        fresh = NnueEval()
        assert incremental == fresh.evaluate(Position(board))
        assert incremental == nnue.evaluate_dense_reference(Position(board))


def test_unmake_restores_accumulator(nnue: NnueEval) -> None:
    board = chess.Board()
    nnue.refresh(board)
    before = nnue.evaluate(Position(board))
    move = chess.Move.from_uci("e2e4")
    board.push(move)
    nnue.on_make(board, move)
    board.pop()
    nnue.on_unmake()
    assert nnue.evaluate(Position(board)) == before


def test_evaluate_refreshes_when_same_board_object_mutates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nnue = NnueEval()
    board = chess.Board()
    nnue.refresh(board)
    refresh_calls = 0
    original_refresh = nnue.refresh

    def _refresh_spy(live_board: chess.Board) -> None:
        nonlocal refresh_calls
        refresh_calls += 1
        original_refresh(live_board)

    monkeypatch.setattr(nnue, "refresh", _refresh_spy)
    board.push(chess.Move.from_uci("e2e4"))
    assert nnue.evaluate(Position(board)) == nnue.evaluate_dense_reference(Position(board))
    assert refresh_calls == 1


def test_encode_position_board_matches_fen_wrapper() -> None:
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4"
    board = chess.Board(fen)
    from ance.eval.nnue import features as feat

    a = encode_position_board(board)
    b = feat.encode_position(fen)
    assert (a[0] == b[0]).all() and (a[1] == b[1]).all()


def test_forward_from_accumulators_matches_dense(nnue: NnueEval) -> None:
    from ance.eval.nnue.inference import cp_from_nnue_output

    board = chess.Board()
    stm, opp = encode_position_board(board)
    dense = forward_cp_float(stm, opp, nnue.weights)
    nnue.refresh(board)
    assert nnue._acc_white is not None and nnue._acc_black is not None
    sparse = forward_from_accumulators(
        nnue._acc_white,
        nnue._acc_black,
        nnue._out_weight,
        nnue._out_bias,
    )
    # float32 reduction order differs; integer cp (D-13) must match
    assert cp_from_nnue_output(dense) == cp_from_nnue_output(sparse)
    assert abs(dense - sparse) < 1e-3


def test_active_feature_count_startpos() -> None:
    board = chess.Board()
    assert len(active_feature_indices(board, chess.WHITE)) == 32
    assert len(active_feature_indices(board, chess.BLACK)) == 32


def test_accumulator_matches_dense_on_random_game(nnue: NnueEval) -> None:
    """Dense reference vs incremental path over a short random playout."""
    import random

    rng = random.Random(0)
    board = chess.Board()
    nnue.refresh(board)
    for _ in range(24):
        if board.is_game_over(claim_draw=True):
            break
        move = rng.choice(list(board.legal_moves))
        board.push(move)
        nnue.on_make(board, move)
        pos = Position(board)
        assert nnue.evaluate(pos) == nnue.evaluate_dense_reference(pos)

