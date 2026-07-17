"""Tests for Lichess [%eval] sign correction and resilient ingestion."""

from __future__ import annotations

import io

import chess.pgn
import zstandard

from training.data.lichess_ingest import extract_samples, iter_games


def test_black_to_move_eval_sign_flipped() -> None:
    pgn = """
[Event "test"]
[Result "1-0"]

1. e4 { [%eval 1.50] } 1-0
"""
    game = chess.pgn.read_game(io.StringIO(pgn))
    assert game is not None
    samples = extract_samples(game, game_id="lichess-001")
    assert len(samples) == 1
    assert samples[0]["cp"] == -150


def test_malformed_game_is_skipped_not_raised(tmp_path) -> None:
    corrupt_pgn = "[Event \"x\"]\n[Result \"1-0\"]\n1. e4 { broken"
    zst_path = tmp_path / "corrupt.pgn.zst"
    compressed = zstandard.ZstdCompressor().compress(corrupt_pgn.encode("utf-8"))
    zst_path.write_bytes(compressed)

    games = list(iter_games(str(zst_path)))
    assert isinstance(games, list)
