"""λ schedule + fen-skipping smoke (Phase 6)."""

from __future__ import annotations

from training.data.shards import ShardDataset
from training.train import _lambda_at_epoch, wdl_loss
import torch


def test_lambda_interpolates() -> None:
    assert _lambda_at_epoch(0, 5, 1.0, 0.75) == 1.0
    assert abs(_lambda_at_epoch(4, 5, 1.0, 0.75) - 0.75) < 1e-9
    mid = _lambda_at_epoch(2, 5, 1.0, 0.75)
    assert 0.75 < mid < 1.0


def test_wdl_loss_respects_lambda() -> None:
    out = torch.zeros(4)
    eval_cp = torch.zeros(4)
    game_result = torch.ones(4)
    has_result = torch.ones(4)
    # With λ=1 pure eval target (~0.5 for cp=0); with λ=0 pure result (1.0)
    loss_eval = wdl_loss(out, eval_cp, game_result, has_result, k=400.0, lambda_=1.0)
    loss_result = wdl_loss(out, eval_cp, game_result, has_result, k=400.0, lambda_=0.0)
    assert float(loss_result) > float(loss_eval)


def test_shard_dataset_fen_skip_keeps_length(tmp_path) -> None:
    import numpy as np

    path = tmp_path / "t.npz"
    n = 32
    np.savez(
        path,
        stm_features=np.zeros((n, 768), dtype=np.float32),
        opp_features=np.zeros((n, 768), dtype=np.float32),
        cp=np.zeros(n, dtype=np.float32),
        game_result=np.full(n, 0.5, dtype=np.float32),
        has_result=np.ones(n, dtype=np.bool_),
    )
    ds = ShardDataset(str(path), random_fen_skipping=3, seed=0)
    assert len(ds) == n
    # Sampling should succeed
    batch = [ds[i] for i in range(8)]
    assert len(batch) == 8
