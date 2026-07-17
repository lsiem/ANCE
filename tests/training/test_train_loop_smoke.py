"""Tests for the sigmoid-WDL training smoke loop."""

from __future__ import annotations

import pytest

pytest.importorskip("torch")

from training.train import preflight_mps_gate, train_smoke


def test_train_smoke_loss_decreases() -> None:
    losses = train_smoke(steps=30)
    assert sum(losses[-5:]) / 5 < sum(losses[:5]) / 5


def test_preflight_mps_gate_returns_valid_device() -> None:
    assert preflight_mps_gate() in {"cpu", "mps"}
