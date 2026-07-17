"""Tests for 768-index feature encoding."""

from __future__ import annotations

import chess
import numpy as np

from training.data.features import NUM_FEATURES, encode_position


def test_startpos_has_32_active_features_per_perspective() -> None:
    stm, opp = encode_position(chess.STARTING_FEN)
    assert np.count_nonzero(stm) == 32
    assert np.count_nonzero(opp) == 32


def test_feature_indices_within_bounds() -> None:
    stm, opp = encode_position(chess.STARTING_FEN)
    for vector in (stm, opp):
        active = np.nonzero(vector)[0]
        assert active.min() >= 0
        assert active.max() < NUM_FEATURES


def test_perspective_flip_changes_indices_for_non_symmetric_position() -> None:
    fen = "rnb1kbnr/pppp1ppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"
    stm, opp = encode_position(fen)
    assert not np.array_equal(stm, opp)
