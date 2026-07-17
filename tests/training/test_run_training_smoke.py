"""Tests for DataLoader-driven training and checkpoint roundtrip."""

from __future__ import annotations

import math

import pytest
import torch

pytest.importorskip("torch")

from training.data.shards import build_shard
from training.label.position_source import generate_position_set
from training.model import NNUE
from training.train import load_checkpoint, run_training, save_checkpoint


def _labeled_samples(seed: int, n_games: int = 2) -> list[dict]:
    samples = generate_position_set(n_games=n_games, seed=seed)
    for index, sample in enumerate(samples):
        sample["cp"] = float((index % 5) * 25 - 50)
        sample["game_result"] = 0.5 + (index % 3) * 0.1
    return samples


def test_run_training_val_loss_tracked_and_checkpoint_roundtrips(tmp_path) -> None:
    train_samples = _labeled_samples(seed=1, n_games=2)
    val_samples = _labeled_samples(seed=2, n_games=2)
    train_shard = tmp_path / "train.npz"
    val_shard = tmp_path / "val.npz"
    build_shard(train_samples, str(train_shard))
    build_shard(val_samples, str(val_shard))

    result = run_training(
        str(train_shard),
        str(val_shard),
        k=400.0,
        epochs=3,
        checkpoint_dir=str(tmp_path),
    )

    assert len(result["val_losses"]) == 3
    assert all(math.isfinite(value) for value in result["val_losses"])

    model = result["model"]
    optimizer = result["optimizer"]
    ckpt = tmp_path / "manual.pt"
    save_checkpoint(model, optimizer, epoch=3, path=str(ckpt))

    fresh_model = NNUE()
    fresh_optimizer = torch.optim.Adam(fresh_model.parameters(), lr=1e-3)
    load_checkpoint(fresh_model, fresh_optimizer, str(ckpt))

    for key, tensor in model.state_dict().items():
        assert torch.allclose(tensor.cpu(), fresh_model.state_dict()[key].cpu())
