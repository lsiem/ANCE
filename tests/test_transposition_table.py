"""Transposition-table contracts and search integration (D-01..D-06, D-22)."""

from __future__ import annotations

import chess

from ance.eval.base import MATE
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
