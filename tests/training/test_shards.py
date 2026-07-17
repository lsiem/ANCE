"""Tests for NPZ shard build/load."""

from __future__ import annotations

import numpy as np
import pytest
import torch

pytest.importorskip("torch")

from training.data.shards import ShardDataset, build_shard
from training.label.position_source import generate_position_set


def _samples_with_labels() -> list[dict]:
    samples = generate_position_set(n_games=1, seed=3)
    for index, sample in enumerate(samples):
        sample["cp"] = float(index * 10)
        sample["game_result"] = 0.5
    return samples


def test_build_and_load_shard_roundtrip(tmp_path) -> None:
    samples = _samples_with_labels()
    shard_path = tmp_path / "shard.npz"
    build_shard(samples, str(shard_path))
    loaded = np.load(shard_path)
    assert loaded["stm_features"].shape == (len(samples), 768)
    assert loaded["cp"].shape == (len(samples),)


def test_shard_dataset_yields_correct_tensor_dtypes(tmp_path) -> None:
    samples = _samples_with_labels()
    shard_path = tmp_path / "shard.npz"
    build_shard(samples, str(shard_path))
    dataset = ShardDataset(str(shard_path))
    stm, opp, cp, game_result, has_result = dataset[0]
    assert stm.dtype == torch.float32
    assert opp.dtype == torch.float32
    assert cp.dtype == torch.float32
