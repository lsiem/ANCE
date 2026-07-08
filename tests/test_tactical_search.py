"""Tactical and mate-in-N search tests (D-13)."""

from __future__ import annotations

import threading

import chess

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.handcrafted import HandcraftedEval
from ance.eval.material import MaterialEval
from ance.search.negamax import search_root


def _never_stop() -> threading.Event:
    return threading.Event()


def test_mate_in_one_finds_mating_move() -> None:
    pos = Position(chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1"))
    result = search_root(pos, max_depth=2, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("a1a8")
    assert result.score >= MATE - 2


def test_mate_in_two_at_depth_four() -> None:
    """White has a forced mate within four plies from this queen+king setup."""
    fen = "6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1"
    pos = Position(chess.Board(fen))
    result = search_root(pos, max_depth=4, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.score >= MATE - 4
    after = pos.board.copy()
    after.push(result.best_move)
    assert after.is_check()


def test_hanging_queen_is_captured() -> None:
    fen = "4k3/8/8/4q3/8/8/8/4R3 w - - 0 1"
    pos = Position(chess.Board(fen))
    result = search_root(pos, max_depth=1, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("e1e5")


def test_knight_fork_finds_double_attack() -> None:
    """Ne5 forks black king on g8 and queen on f7."""
    fen = "6k1/5q2/8/4N3/8/8/8/4K3 w - - 0 1"
    pos = Position(chess.Board(fen))
    result = search_root(pos, max_depth=3, evaluator=HandcraftedEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("e5f7")


def test_horizon_capture_not_misplayed_at_low_depth() -> None:
    """One-ply hanging rook on the e-file must be taken even at main depth 1."""
    fen = "4k3/8/8/8/4r3/8/8/4R2K w - - 0 1"
    pos = Position(chess.Board(fen))
    result = search_root(pos, max_depth=1, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("e1e4")
