"""Tests for by-game split and FEN leakage assertion."""

from __future__ import annotations

import pytest

from training.data.split import assert_no_fen_leakage, split_by_game


def _synthetic_samples(n_games: int = 20, samples_per_game: int = 5) -> list[dict]:
    samples: list[dict] = []
    for game_index in range(n_games):
        game_id = f"game-{game_index:03d}"
        for sample_index in range(samples_per_game):
            samples.append(
                {
                    "fen": f"fen-{game_id}-{sample_index}",
                    "cp": sample_index,
                    "game_id": game_id,
                    "source": "lichess",
                }
            )
    return samples


def test_split_is_disjoint_by_game() -> None:
    samples = _synthetic_samples(n_games=20, samples_per_game=5)
    train, val = split_by_game(samples, val_fraction=0.05, seed=42)
    assert_no_fen_leakage(train, val)

    train_ids = {sample["game_id"] for sample in train}
    val_ids = {sample["game_id"] for sample in val}
    assert train_ids.isdisjoint(val_ids)
    assert train_ids | val_ids == {sample["game_id"] for sample in samples}


def test_assert_no_fen_leakage_catches_genuine_leak() -> None:
    shared_fen = "shared-fen"
    train = [{"fen": shared_fen, "game_id": "g1"}]
    val = [{"fen": shared_fen, "game_id": "g2"}]
    with pytest.raises(AssertionError, match="FENs leaked"):
        assert_no_fen_leakage(train, val)
