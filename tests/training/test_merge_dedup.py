"""Tests for FEN deduplication across sample streams."""

from __future__ import annotations

from training.data.merge import merge_and_dedup


def test_merge_dedup_keeps_first_and_removes_fen_duplicates() -> None:
    shared_fen = "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1"
    stream_a = [
        {
            "fen": shared_fen,
            "cp": 10,
            "game_id": "g1",
            "source": "lichess",
        },
        {
            "fen": "fen-unique-a",
            "cp": 20,
            "game_id": "g1",
            "source": "lichess",
        },
    ]
    stream_b = [
        {
            "fen": shared_fen,
            "cp": 999,
            "game_id": "g2",
            "source": "stockfish_fresh",
        },
        {
            "fen": "fen-unique-b",
            "cp": 30,
            "game_id": "g2",
            "source": "stockfish_fresh",
        },
    ]

    merged = merge_and_dedup([stream_a, stream_b])
    by_fen = {sample["fen"]: sample for sample in merged}

    assert by_fen[shared_fen]["cp"] == 10
    assert len(merged) == 3
