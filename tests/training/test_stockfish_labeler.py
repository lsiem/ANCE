"""Tests for Stockfish fresh labeling (TRN-01)."""

from __future__ import annotations

import json
import shutil

import chess.engine
import pytest

from training.label.position_source import generate_position_set
from training.label.stockfish_labeler import (
    label_position,
    run_labeling_resumable,
    run_depth_benchmark,
)

STOCKFISH_ONLY = pytest.mark.skipif(
    shutil.which("stockfish") is None,
    reason="stockfish binary not on PATH",
)

QUEEN_UP_FEN = "rnb1kbnr/pppp1ppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"


@STOCKFISH_ONLY
def test_label_position_returns_cp_or_mate_favoring_white() -> None:
    with chess.engine.SimpleEngine.popen_uci("stockfish") as engine:
        result = label_position(engine, QUEEN_UP_FEN, depth=6)

    if result["cp"] is not None:
        assert result["cp"] > 0
    else:
        assert result["mate"] is not None
        assert result["mate"] > 0


@STOCKFISH_ONLY
def test_depth_benchmark_returns_positive_rates() -> None:
    fens = [entry["fen"] for entry in generate_position_set(n_games=1, seed=0)]
    rates = run_depth_benchmark("stockfish", fens, candidate_depths=[6, 8])
    assert all(rate > 0 for rate in rates.values())


def test_run_labeling_resumable_resumes_and_writes_progress_and_live_json(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    class _FakeEngineCtx:
        def __enter__(self) -> object:
            return object()

        def __exit__(self, exc_type, exc, tb) -> None:
            return None

    fens = ["fen-1", "fen-2", "fen-3"]
    progress_path = tmp_path / "labels.json"
    live_path = tmp_path / "live.json"
    progress_path.write_text(
        '[{"fen":"fen-1","mate":null,"cp":11}]\n', encoding="utf-8"
    )

    monkeypatch.setattr(
        chess.engine.SimpleEngine,
        "popen_uci",
        lambda _path: _FakeEngineCtx(),
    )
    monkeypatch.setattr(
        "training.label.stockfish_labeler.label_position",
        lambda _engine, fen, _depth: {"fen": fen, "mate": None, "cp": len(fen)},
    )

    results = run_labeling_resumable(
        "stockfish",
        fens,
        depth=8,
        progress_path=progress_path,
        live_path=live_path,
        save_every=1,
    )

    assert [row["fen"] for row in results] == fens
    assert len(results) == 3
    saved = json.loads(progress_path.read_text(encoding="utf-8"))
    assert isinstance(saved, list)
    assert [row["fen"] for row in saved] == fens
    assert all(set(row) == {"fen", "mate", "cp"} for row in saved)

    live = json.loads(live_path.read_text(encoding="utf-8"))
    assert set(live) == {
        "phase",
        "fen",
        "depth",
        "done",
        "total",
        "rate_per_s",
        "eta_s",
        "updated_utc",
    }
    assert live["phase"] == "labeling"
    assert live["depth"] == 8
    assert live["done"] == 3
    assert live["total"] == 3
