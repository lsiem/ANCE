"""Tests for Stockfish fresh labeling (TRN-01)."""

from __future__ import annotations

import shutil

import pytest

from training.label.position_source import generate_position_set
from training.label.stockfish_labeler import (
    label_position,
    run_depth_benchmark,
)
import chess.engine

pytestmark = pytest.mark.skipif(
    shutil.which("stockfish") is None,
    reason="stockfish binary not on PATH",
)

QUEEN_UP_FEN = "rnb1kbnr/pppp1ppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


def test_label_position_returns_cp_or_mate_favoring_white() -> None:
    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:
        result = label_position(engine, QUEEN_UP_FEN, depth=6)

    if result["cp"] is not None:
        assert result["cp"] > 0
    else:
        assert result["mate"] is not None
        assert result["mate"] > 0


def test_depth_benchmark_returns_positive_rates() -> None:
    fens = [entry["fen"] for entry in generate_position_set(n_games=1, seed=0)]
    rates = run_depth_benchmark("stockfish", fens, candidate_depths=[6, 8])
    assert all(rate > 0 for rate in rates.values())
