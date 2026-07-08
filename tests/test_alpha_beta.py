"""Alpha-beta pruning and ply-adjusted mate scoring tests (SRCH-02)."""

from __future__ import annotations

import inspect
import threading

import chess

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.material import MaterialEval
from ance.eval.material import NaiveEval
from ance.search.negamax import negamax, search_root
from ance.search.types import SearchContext


def _never_stop() -> threading.Event:
    return threading.Event()


def _make_ctx(*, evaluator=None, ply: int = 0) -> SearchContext:
    return SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=evaluator or MaterialEval(),
        ply=ply,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )


def _negamax_unpruned(
    pos: Position,
    depth: int,
    evaluator,
    counter: list[int],
) -> int:
    """Brute-force negamax without alpha-beta cutoffs — node-count baseline."""
    counter[0] += 1
    moves = pos.legal_moves()
    if not moves:
        return -MATE if pos.is_check() else 0
    if depth == 0:
        return evaluator.evaluate(pos)
    best = -MATE - 1
    board = pos.board
    for move in moves:
        board.push(move)
        try:
            score = -_negamax_unpruned(pos, depth - 1, evaluator, counter)
        finally:
            board.pop()
        if score > best:
            best = score
    return best


def test_mate_in_one_ply_adjusted_score() -> None:
    pos = Position(chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1"))
    result = search_root(pos, max_depth=2, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("a1a8")
    assert result.score >= MATE - 2


def test_stalemate_scores_zero_at_terminal() -> None:
    fen = "7k/5Q2/6K1/8/8/8/8/8 b - - 0 1"
    pos = Position(chess.Board(fen))
    ctx = _make_ctx(ply=0)
    score = negamax(pos, depth=0, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_alpha_beta_visits_fewer_nodes_than_unpruned() -> None:
    fen = "r1bqkb1r/pppp1ppp/2n2n2/4p3/2B1P3/5N2/PPPP1PPP/RNBQK1R w KQkq - 4 4"
    pos = Position(chess.Board(fen))
    evaluator = MaterialEval()

    unpruned_counter = [0]
    _negamax_unpruned(pos, depth=3, evaluator=evaluator, counter=unpruned_counter)

    pruned_ctx = _make_ctx(evaluator=evaluator)
    negamax(pos, depth=3, alpha=-MATE - 1, beta=MATE + 1, ctx=pruned_ctx)

    assert pruned_ctx.counter[0] < unpruned_counter[0]


def test_search_root_deterministic_tie_break_first_move() -> None:
    pos = Position()
    evaluator = NaiveEval()
    legal_moves = list(pos.board.legal_moves)
    expected = legal_moves[0]

    first = search_root(
        pos.copy(), max_depth=1, evaluator=evaluator, stop_flag=_never_stop()
    )
    second = search_root(
        pos.copy(), max_depth=1, evaluator=evaluator, stop_flag=_never_stop()
    )
    assert first.best_move == expected
    assert second.best_move == expected
    assert first.best_move == second.best_move


def test_search_root_signature_has_no_rng_parameter() -> None:
    params = inspect.signature(search_root).parameters
    assert "rng" not in params
