"""Tests for the (768→256)×2→1 NNUE architecture (D-06)."""

from __future__ import annotations

import pytest
import torch

pytest.importorskip("torch")

from training.model import ClippedReLU, NNUE, HIDDEN, NUM_FEATURES


def test_nnue_forward_batch_shape() -> None:
    batch = 4
    stm = torch.randn(batch, NUM_FEATURES, dtype=torch.float32)
    opp = torch.randn(batch, NUM_FEATURES, dtype=torch.float32)
    output = NNUE()(stm, opp)
    assert output.shape == (batch,)


def test_clipped_relu_bounds() -> None:
    relu = ClippedReLU()
    x = torch.tensor([-1.0, 0.0, 0.5, 1.0, 2.0], dtype=torch.float32)
    y = relu(x)
    assert torch.allclose(y, torch.tensor([0.0, 0.0, 0.5, 1.0, 1.0]))


def test_hidden_width_locked() -> None:
    assert HIDDEN == 256
