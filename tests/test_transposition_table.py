"""Transposition-table contracts and search integration (D-01..D-06, D-22)."""

from __future__ import annotations

import threading
import time

import chess
import pytest

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.handcrafted import HandcraftedEval
from ance.eval.material import MaterialEval
from ance.search.negamax import search_root
from ance.search.transposition import (
    EXACT,
    LOWER,
    TT_SIZE_POW2,
    UPPER,
    TranspositionTable,
    score_from_tt,
    score_to_tt,
)


def test_store_probe_and_absent_key() -> None:
    table = TranspositionTable(16)
    move = chess.Move.from_uci("e2e4")

    assert table.probe(7) is None
    table.store(7, depth=4, score=123, flag=EXACT, best_move=move)

    assert table.probe(7) == (4, 123, EXACT, move)


def test_depth_preferred_replacement_and_empty_slot() -> None:
    table = TranspositionTable(16)
    deep_move = chess.Move.from_uci("e2e4")
    shallow_move = chess.Move.from_uci("d2d4")

    table.store(3, depth=5, score=50, flag=LOWER, best_move=deep_move)
    table.store(3, depth=3, score=30, flag=UPPER, best_move=shallow_move)
    assert table.probe(3) == (5, 50, LOWER, deep_move)

    table.store(3, depth=5, score=55, flag=EXACT, best_move=shallow_move)
    assert table.probe(3) == (5, 55, EXACT, shallow_move)

    table.store(4, depth=1, score=10, flag=EXACT, best_move=None)
    assert table.probe(4) == (1, 10, EXACT, None)


def test_full_key_verification_rejects_index_collision() -> None:
    table = TranspositionTable(16)
    key = 5
    colliding_key = key + 16

    table.store(key, depth=2, score=20, flag=EXACT, best_move=None)
    assert table.probe(colliding_key) is None

    table.store(colliding_key, depth=2, score=30, flag=EXACT, best_move=None)
    assert table.probe(key) is None
    assert table.probe(colliding_key) == (2, 30, EXACT, None)


def test_mate_scores_are_node_relative_at_the_table_boundary() -> None:
    assert score_to_tt(MATE - 3, ply=2) == MATE - 1
    assert score_from_tt(MATE - 1, ply=4) == MATE - 5
    assert score_to_tt(-(MATE - 3), ply=2) == -(MATE - 1)
    assert score_from_tt(-(MATE - 1), ply=4) == -(MATE - 5)
    assert score_to_tt(321, ply=7) == 321
    assert score_from_tt(-321, ply=7) == -321

    for score in (MATE - 6, -(MATE - 6), 42):
        assert score_from_tt(score_to_tt(score, ply=3), ply=3) == score


def test_clear_removes_all_entries() -> None:
    table = TranspositionTable(16)
    for key in range(16):
        table.store(key, depth=1, score=key, flag=EXACT, best_move=None)

    table.clear()

    assert all(table.probe(key) is None for key in range(16))


def test_default_size_is_locked_to_one_mebibyte_of_slots() -> None:
    assert TT_SIZE_POW2 == 1 << 20


def _never_stop() -> threading.Event:
    return threading.Event()


def test_tt_reduces_nodes_at_fixed_depth_on_italian_position() -> None:
    fen = "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 3"
    without_tt = search_root(
        Position(chess.Board(fen)),
        max_depth=4,
        evaluator=HandcraftedEval(),
        stop_flag=_never_stop(),
        tt=None,
    )
    with_tt = search_root(
        Position(chess.Board(fen)),
        max_depth=4,
        evaluator=HandcraftedEval(),
        stop_flag=_never_stop(),
        tt=TranspositionTable(),
    )

    assert with_tt.best_move == without_tt.best_move
    assert with_tt.nodes < without_tt.nodes


def test_cold_tt_search_is_reproducible_on_kiwipete() -> None:
    fen = "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1"

    first = search_root(
        Position(chess.Board(fen)),
        max_depth=2,
        evaluator=MaterialEval(),
        stop_flag=_never_stop(),
        tt=TranspositionTable(),
    )
    second = search_root(
        Position(chess.Board(fen)),
        max_depth=2,
        evaluator=MaterialEval(),
        stop_flag=_never_stop(),
        tt=TranspositionTable(),
    )

    assert second.nodes == first.nodes
    assert second.best_move == first.best_move


def test_mate_score_stays_stable_across_completed_depths_with_shared_tt() -> None:
    fen = "6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1"
    completed_scores: list[int] = []

    search_root(
        Position(chess.Board(fen)),
        max_depth=5,
        evaluator=MaterialEval(),
        stop_flag=_never_stop(),
        tt=TranspositionTable(),
        info_callback=lambda result, _nps: completed_scores.append(result.score),
    )

    first_mate = next(
        index for index, score in enumerate(completed_scores) if score >= MATE - 5
    )
    assert completed_scores[first_mate:]
    assert len(set(completed_scores[first_mate:])) == 1


@pytest.mark.parametrize(
    ("fen", "depth", "expected_move", "evaluator"),
    [
        ("6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1", 2, "a1a8", MaterialEval()),
        ("6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1", 4, "h1a8", MaterialEval()),
        ("4k3/8/8/4q3/8/8/8/4R3 w - - 0 1", 3, "e1e5", MaterialEval()),
        ("6k1/5q2/8/4N3/8/8/8/4K3 w - - 0 1", 3, "e5f7", HandcraftedEval()),
        ("4k3/8/8/8/4r3/8/8/4R2K w - - 0 1", 3, "e1e4", MaterialEval()),
    ],
)
def test_tt_preserves_phase2_tactical_best_moves(
    fen: str,
    depth: int,
    expected_move: str,
    evaluator,
) -> None:
    without_tt = search_root(
        Position(chess.Board(fen)),
        max_depth=depth,
        evaluator=evaluator,
        stop_flag=_never_stop(),
        tt=None,
    )
    with_tt = search_root(
        Position(chess.Board(fen)),
        max_depth=depth,
        evaluator=evaluator,
        stop_flag=_never_stop(),
        tt=TranspositionTable(),
    )

    assert without_tt.best_move == chess.Move.from_uci(expected_move)
    assert with_tt.best_move == without_tt.best_move


def test_aborted_search_does_not_store_partial_node() -> None:
    class SpyTable(TranspositionTable):
        def __init__(self) -> None:
            super().__init__(16)
            self.store_calls: list[tuple[int, int]] = []

        def store(self, key, depth, score, flag, best_move) -> None:
            self.store_calls.append((key, depth))
            super().store(key, depth, score, flag, best_move)

    table = SpyTable()
    result = search_root(
        Position(),
        max_depth=4,
        evaluator=MaterialEval(),
        stop_flag=_never_stop(),
        deadline=time.monotonic() - 1.0,
        tt=table,
    )

    assert result.depth == 0
    assert table.store_calls == []
