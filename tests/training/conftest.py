"""Pytest helpers for the training-phase test package.

The main ``tests/`` suite stays torch-free so ``pytest tests/`` never
requires the training toolchain. Torch-dependent modules call
``pytest.importorskip("torch")`` at the top of their own file (not here as
an autouse fixture) so numpy-only tests like ``test_nnue_format_roundtrip``
always collect and run even when torch is absent.
"""

from __future__ import annotations

import pytest


def require_torch() -> None:
    """Skip the calling module cleanly when PyTorch is not installed."""
    pytest.importorskip("torch")
