"""Quiet-position filter + corpus mix guards (Phase 6)."""

from __future__ import annotations

import chess
import pytest

from training.data.quiet_filter import (
    enforce_corpus_mix,
    filter_quiet_samples,
    is_quiet_fen,
    ply_from_fen,
)


def test_ply_from_fen() -> None:
    assert ply_from_fen(chess.STARTING_FEN) == 0
    # After 1. e4 — Black to move, fullmove 1 → ply 1
    board = chess.Board()
    board.push_uci("e2e4")
    assert ply_from_fen(board.fen()) == 1


def test_rejects_check() -> None:
    check_fen = "rnbqkbnr/pppp1Qpp/8/4p3/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 2"
    board = chess.Board(check_fen)
    assert board.is_check()
    ok, reason = is_quiet_fen(
        check_fen,
        min_ply=0,
        bestmove_capture_fn=lambda b: False,
    )
    assert ok is False
    assert reason == "check"


def test_rejects_early_ply() -> None:
    ok, reason = is_quiet_fen(
        chess.STARTING_FEN,
        min_ply=8,
        bestmove_capture_fn=lambda b: False,
    )
    assert ok is False
    assert reason == "early_ply"


def test_rejects_capture_bestmove() -> None:
    fen = "4k3/8/8/4q3/8/8/8/4R3 w - - 0 1"
    # Force capture bestmove via injection (rook takes queen)
    ok, reason = is_quiet_fen(
        fen,
        min_ply=0,
        bestmove_capture_fn=lambda b: True,
    )
    assert ok is False
    assert reason == "capture_bestmove"


def test_filter_quiet_samples_stats() -> None:
    samples = [
        {"fen": chess.STARTING_FEN, "cp": 0.0, "source": "lichess"},
        {
            "fen": "rnbqkbnr/pppp1Qpp/8/4p3/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 2",
            "cp": -900.0,
            "source": "lichess",
        },
    ]
    kept, stats = filter_quiet_samples(
        samples,
        min_ply=8,
        skip_capture_filter=True,
    )
    assert stats.rejected_early_ply >= 1 or stats.rejected_check >= 1
    assert stats.kept + stats.rejected == len(samples)


def test_enforce_corpus_mix_caps_fresh() -> None:
    samples = [
        {"fen": "a", "cp": 0, "source": "lichess", "game_result": 1.0},
        {"fen": "b", "cp": 0, "source": "lichess", "game_result": 0.0},
        {"fen": "c", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "d", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "e", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "f", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "g", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "h", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "i", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "j", "cp": 0, "source": "fresh", "game_result": None},
    ]
    # Without strength_corpus, only fresh share is capped.
    out = enforce_corpus_mix(samples, max_fresh_share=0.10, strength_corpus=False)
    fresh_n = sum(1 for s in out if s.get("source") == "fresh")
    assert fresh_n <= 1


def test_enforce_strength_requires_results() -> None:
    samples = [
        {"fen": "a", "cp": 0, "source": "fresh", "game_result": None},
        {"fen": "b", "cp": 0, "source": "hf", "game_result": None},
    ]
    with pytest.raises(RuntimeError, match="has_result"):
        enforce_corpus_mix(samples, strength_corpus=True, min_has_result_rate=0.50)
