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


def test_enforce_strength_allows_015_when_enough_results() -> None:
    """3 of 20 results pass at 0.15; 2 of 20 still raises (D-02)."""
    three_of_twenty = [
        *[
            {"fen": f"hf-{i}", "cp": 0, "source": "lichess-hf", "game_result": None}
            for i in range(17)
        ],
        *[
            {"fen": f"lic-{i}", "cp": 0, "source": "lichess", "game_result": 1.0}
            for i in range(3)
        ],
    ]
    enforce_corpus_mix(three_of_twenty, strength_corpus=True, min_has_result_rate=0.15)

    two_of_twenty = [
        *[
            {"fen": f"hf-{i}", "cp": 0, "source": "lichess-hf", "game_result": None}
            for i in range(18)
        ],
        {"fen": "lic-0", "cp": 0, "source": "lichess", "game_result": 1.0},
        {"fen": "lic-1", "cp": 0, "source": "lichess", "game_result": 0.0},
    ]
    with pytest.raises(RuntimeError, match="has_result"):
        enforce_corpus_mix(two_of_twenty, strength_corpus=True, min_has_result_rate=0.15)


def test_tracer_padded_hf_plus_modest_fill_passes_mix_015() -> None:
    """One padded official-card HF row plus modest Lichess fill at 0.15."""
    from training.data.hf_ingest import row_to_sample

    card_fen = "2bq1rk1/pr3ppn/1p2p3/7P/2pP1B1P/2P5/PPQ2PB1/R3R1K1 w - -"
    hf_row = {
        "fen": card_fen,
        "line": "e2e4",
        "depth": 30,
        "knodes": 5,
        "cp": 20,
        "mate": None,
    }
    hf_sample = row_to_sample(hf_row)
    assert hf_sample is not None
    assert hf_sample["fen"].endswith(" 0 16")
    assert hf_sample["game_result"] is None

    samples = [hf_sample]
    samples.extend(
        {"fen": f"hf-{i}", "cp": 0, "source": "lichess-hf", "game_result": None}
        for i in range(16)
    )
    samples.extend(
        {"fen": f"lic-{i}", "cp": 0, "source": "lichess", "game_result": 1.0}
        for i in range(3)
    )
    assert len(samples) == 20
    assert sum(1 for s in samples if s.get("game_result") is not None) == 3
    enforce_corpus_mix(samples, strength_corpus=True, min_has_result_rate=0.15)


_KEEPABLE_LATE = [
    "6k1/5ppp/8/8/8/8/5PPP/6K1 w - - 0 30",
    "4k3/4p3/8/8/8/8/4P3/4K3 w - - 0 20",
    "4k3/8/8/8/8/8/8/4K3 w - - 0 20",
]


def test_filter_quiet_samples_max_kept_truncates() -> None:
    samples = [
        {"fen": _KEEPABLE_LATE[0], "cp": 0.0, "source": "lichess-hf"},
        {"fen": _KEEPABLE_LATE[1], "cp": 0.0, "source": "lichess"},
        {"fen": _KEEPABLE_LATE[2], "cp": 0.0, "source": "lichess-hf"},
    ]
    kept, stats = filter_quiet_samples(
        samples,
        min_ply=0,
        bestmove_capture_fn=lambda b: False,
        max_kept=2,
    )
    assert len(kept) == 2
    assert stats.truncated is True
    assert stats.kept_by_source == {"lichess-hf": 1, "lichess": 1}


def test_filter_quiet_samples_kept_by_source_unknown() -> None:
    samples = [
        {"fen": _KEEPABLE_LATE[0], "cp": 0.0},
        {"fen": _KEEPABLE_LATE[1], "cp": 0.0, "source": "lichess"},
        {"fen": _KEEPABLE_LATE[2], "cp": 0.0, "source": "lichess"},
    ]
    kept, stats = filter_quiet_samples(
        samples,
        min_ply=0,
        bestmove_capture_fn=lambda b: False,
        max_kept=2,
    )
    assert len(kept) == 2
    assert stats.kept_by_source.get("unknown") == 1
    assert stats.kept_by_source.get("lichess") == 1


def test_reject_reason_strings_unchanged() -> None:
    check_fen = "rnbqkbnr/pppp1Qpp/8/4p3/4P3/8/PPPP1PPP/RNB1KBNR b KQkq - 0 2"
    _, check_reason = is_quiet_fen(
        check_fen, min_ply=0, bestmove_capture_fn=lambda b: False
    )
    _, early_reason = is_quiet_fen(
        chess.STARTING_FEN, min_ply=8, bestmove_capture_fn=lambda b: False
    )
    _, capture_reason = is_quiet_fen(
        "4k3/8/8/4q3/8/8/8/4R3 w - - 0 1",
        min_ply=0,
        bestmove_capture_fn=lambda b: True,
    )
    _, qsearch_reason = is_quiet_fen(
        "4k3/8/8/4q3/8/8/8/4R3 w - - 0 20",
        min_ply=0,
        bestmove_capture_fn=lambda b: False,
    )
    _, illegal_reason = is_quiet_fen(
        "not-a-fen", min_ply=0, bestmove_capture_fn=lambda b: False
    )
    assert check_reason == "check"
    assert early_reason == "early_ply"
    assert capture_reason == "capture_bestmove"
    assert qsearch_reason == "qsearch"
    assert illegal_reason == "illegal"
