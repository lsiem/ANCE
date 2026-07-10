"""Iterative deepening and draw-detection tests (SRCH-03, SRCH-07)."""

from __future__ import annotations

import threading
import time

import chess
import chess.polyglot

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.material import MaterialEval
from ance.search.negamax import (
    _build_game_history_keys,
    negamax,
    quiescence_search,
    search_root,
)
from ance.search.types import SearchContext


def _never_stop() -> threading.Event:
    return threading.Event()


def _real_history_board() -> chess.Board:
    board = chess.Board()
    for move_uci in ("g1f3", "g8f6", "f3g1", "f6g8", "g1f3"):
        board.push(chess.Move.from_uci(move_uci))
    return board


class _ConstantEval:
    def evaluate(self, pos: Position) -> int:
        return 123


def test_build_game_history_keys_reconstructs_every_prior_position() -> None:
    board = _real_history_board()
    fen_before = board.fen()
    stack_length_before = len(board.move_stack)
    expected_keys: set[int] = set()
    temp = board.copy(stack=True)
    while True:
        expected_keys.add(chess.polyglot.zobrist_hash(temp))
        if not temp.move_stack:
            break
        temp.pop()

    assert _build_game_history_keys(board) == expected_keys
    assert board.fen() == fen_before
    assert len(board.move_stack) == stack_length_before


def test_real_game_history_repetition_from_root_child_scores_draw() -> None:
    board = _real_history_board()
    history_keys = _build_game_history_keys(board)
    board.push(chess.Move.from_uci("g8f6"))
    pos = Position(board)
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=_ConstantEval(),
        ply=1,
        path_keys=[],
        game_history_keys=history_keys,
        deadline=None,
        max_depth=1,
    )

    score = negamax(pos, depth=1, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)

    assert score == 0


def test_id_returns_last_completed_depth_on_abort() -> None:
    pos = Position()
    stop_flag = threading.Event()
    result_holder: list = []

    def run() -> None:
        result_holder.append(
            search_root(
                pos,
                max_depth=4,
                evaluator=MaterialEval(),
                stop_flag=stop_flag,
            )
        )

    thread = threading.Thread(target=run)
    thread.start()
    time.sleep(0.001)
    stop_flag.set()
    thread.join(timeout=5.0)
    assert thread.is_alive() is False
    result = result_holder[0]
    assert result.best_move is not None
    assert result.depth >= 1
    assert result.depth < 4


def test_twofold_in_search_path_scores_draw() -> None:
    """Repeating the same position on the search path returns draw (0)."""
    board = chess.Board()
    board.push(chess.Move.from_uci("e2e4"))
    board.push(chess.Move.from_uci("e7e5"))
    board.push(chess.Move.from_uci("g1f3"))
    board.push(chess.Move.from_uci("g8f6"))
    pos = Position(board)
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    key = chess.polyglot.zobrist_hash(pos.board)
    ctx.path_keys.append(key)
    score = negamax(pos, depth=1, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_game_history_repetition_scores_draw() -> None:
    board = chess.Board()
    board.push(chess.Move.from_uci("e2e4"))
    board.push(chess.Move.from_uci("e7e5"))
    pos = Position(board)
    history_key = chess.polyglot.zobrist_hash(pos.board)
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        ply=0,
        path_keys=[],
        game_history_keys={history_key},
        deadline=None,
        max_depth=0,
    )
    score = negamax(pos, depth=1, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_fifty_move_rule_scores_draw() -> None:
    fen = "4k3/8/8/8/8/8/8/4K3 w - - 100 101"
    pos = Position(chess.Board(fen))
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    score = negamax(pos, depth=1, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_insufficient_material_scores_draw() -> None:
    fen = "4k3/8/8/8/8/8/8/4K3 w - - 0 1"
    pos = Position(chess.Board(fen))
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=MaterialEval(),
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    score = negamax(pos, depth=1, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_qsearch_path_repetition_scores_draw() -> None:
    """Capture e1e5 revisits a zobrist key already on path_keys — must score draw (0).

    FEN: 4k3/8/8/4q3/8/8/4R3/4K3 w - - 0 1
    Sequence: root (quiet) -> Re1xe5 lands on child key pre-seeded on the search path.
    """
    fen = "4k3/8/8/4q3/8/8/4R3/4K3 w - - 0 1"
    board = chess.Board(fen)
    capture = chess.Move.from_uci("e1e5")
    board.push(capture)
    child_key = chess.polyglot.zobrist_hash(board)
    board.pop()
    pos = Position(chess.Board(fen))
    ctx = SearchContext(
        stop_flag=_never_stop(),
        counter=[0],
        evaluator=_ConstantEval(),
        ply=0,
        path_keys=[child_key],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    score = quiescence_search(pos, alpha=-MATE - 1, beta=MATE + 1, ctx=ctx)
    assert score == 0


def test_mate_beats_draw() -> None:
    pos = Position(chess.Board("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1"))
    result = search_root(pos, max_depth=2, evaluator=MaterialEval(), stop_flag=_never_stop())
    assert result.best_move == chess.Move.from_uci("a1a8")
    assert result.score >= MATE - 2
