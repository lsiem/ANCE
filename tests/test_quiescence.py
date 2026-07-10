"""Quiescence search tests (SRCH-04, D-02 through D-05)."""

from __future__ import annotations

import threading

import chess
import chess.polyglot

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.material import MaterialEval
from ance.search.negamax import MAX_QDEPTH, negamax, quiescence_search, search_root
from ance.search.types import MATE_THRESHOLD, SearchContext


def _never_stop() -> threading.Event:
    return threading.Event()


def _make_ctx(*, ply: int = 0) -> SearchContext:
    return SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        ply=ply,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )


def test_hanging_queen_captured_at_horizon() -> None:
    """Re1xe5 wins the hanging queen — qsearch at depth-0 finds the capture."""
    fen = "4k3/8/8/4q3/8/8/8/4R3 w - - 0 1"
    pos = Position(chess.Board(fen))
    ctx = _make_ctx()
    score = negamax(pos, depth=0, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score >= 0

    result = search_root(pos, max_depth=1, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("e1e5")


def test_quiet_depth_zero_uses_stand_pat() -> None:
    """Symmetric material — stand-pat eval near zero without noisy capture expansion."""
    fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    pos = Position(chess.Board(fen))
    ctx = _make_ctx()
    score = negamax(pos, depth=0, alpha=-100, beta=100, ctx=ctx)
    assert -50 <= score <= 50


def test_delta_pruning_preserves_strong_stand_pat() -> None:
    """White up a queen — stand-pat already winning; qsearch should not blunder score."""
    fen = "4k3/8/8/8/8/8/8/4KQ2 w - - 0 1"
    pos = Position(chess.Board(fen))
    result = search_root(pos, max_depth=1, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.score > 800


def test_in_check_searches_evasions_not_stand_pat() -> None:
    """King in check must evade — finds blocking/capture move, not stand-pat eval."""
    fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
    pos = Position(chess.Board(fen))
    result = search_root(pos, max_depth=1, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move is not None
    after = pos.board.copy()
    after.push(result.best_move)
    assert not after.is_check()


def test_in_check_no_evasions_is_mate() -> None:
    """Fool's mate — zero evasions scores mate."""
    fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    pos = Position(chess.Board(fen))
    ctx = _make_ctx(ply=0)
    score = negamax(pos, depth=0, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score <= -MATE + 100


class _ConstantEval:
    def evaluate(self, pos: Position) -> int:
        return 123


class _HugeEval:
    def evaluate(self, pos: Position) -> int:
        return 10**6


def test_quiescence_clamps_pathological_evaluator_below_mate_window() -> None:
    """Eval cp cannot masquerade as mate — seam clamps below MATE_THRESHOLD."""
    pos = Position(chess.Board())
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=_HugeEval(),  # type: ignore[arg-type]
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    score = quiescence_search(pos, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert abs(score) < MATE_THRESHOLD


def test_qsearch_game_history_repetition_scores_draw() -> None:
    """Historical current zobrist in game_history_keys must score draw (0), not static eval."""
    fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
    pos = Position(chess.Board(fen))
    history_key = chess.polyglot.zobrist_hash(pos.board)
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=_ConstantEval(),
        ply=0,
        path_keys=[],
        game_history_keys={history_key},
        deadline=None,
        max_depth=0,
    )
    score = quiescence_search(pos, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_qsearch_at_cap_checkmate_scores_mate() -> None:
    """Fool's mate at MAX_QDEPTH must score mate, not capped static eval (123)."""
    fen = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
    pos = Position(chess.Board(fen))
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=_ConstantEval(),
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    score = quiescence_search(
        pos, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx, qdepth=MAX_QDEPTH
    )
    assert score <= -(MATE - 100)


def test_qsearch_at_cap_in_check_searches_evasions() -> None:
    """In-check at MAX_QDEPTH must search evasions, not return stand-pat static eval."""
    fen = "4k3/8/8/8/8/8/4q3/4K3 w - - 0 1"
    pos = Position(chess.Board(fen))
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=_ConstantEval(),
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    score = quiescence_search(
        pos, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx, qdepth=MAX_QDEPTH
    )
    assert score != 123
