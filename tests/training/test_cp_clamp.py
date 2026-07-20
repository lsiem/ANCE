"""Training cp soft-clamp (Phase 6)."""

from __future__ import annotations

from training.data.cp_clamp import clamp_training_cp, cp_from_label


def test_clamp_midrange_unchanged() -> None:
    assert clamp_training_cp(123.0) == 123.0
    assert clamp_training_cp(-450.0) == -450.0


def test_clamp_extremes() -> None:
    assert clamp_training_cp(50_000.0) == 10_000.0
    assert clamp_training_cp(-99_999.0) == -10_000.0


def test_cp_from_label_mate_clamped() -> None:
    assert cp_from_label({"mate": 1, "cp": None}) == 10_000.0
    assert cp_from_label({"mate": -1, "cp": None}) == -10_000.0


def test_cp_from_label_raw_cp_clamped() -> None:
    assert cp_from_label({"cp": 50_000, "mate": None}) == 10_000.0
