"""Tests for the MPS availability gate (D-09, TRN-05)."""

from __future__ import annotations

import pytest

pytest.importorskip("torch")

from training.mps_gate import cpu_vs_mps_parity_check, select_device


def test_select_device_returns_cpu_or_mps() -> None:
    assert select_device() in {"cpu", "mps"}


def test_parity_check_noop_on_cpu() -> None:
    cpu_vs_mps_parity_check("cpu")


@pytest.mark.skipif(
    select_device() != "mps",
    reason="MPS parity only meaningful when MPS is the selected device",
)
def test_parity_check_on_mps_with_default_model() -> None:
    device = select_device()
    cpu_vs_mps_parity_check(device)
