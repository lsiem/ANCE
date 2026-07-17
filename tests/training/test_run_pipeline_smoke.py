"""Tests for the pipeline CLI orchestrator."""

from __future__ import annotations

import pytest

pytest.importorskip("torch")

from nnue_format import io as nnue_io
from nnue_format import schema
from training import run_pipeline


def test_run_pipeline_smoke_flag_completes_fast(tmp_path) -> None:
    exit_code = run_pipeline.main(["--smoke", "--out-dir", str(tmp_path)])
    assert exit_code == 0
    arrays, meta = nnue_io.load_net(str(tmp_path / "net.safetensors"))
    assert meta["arch_id"] == schema.ARCH_ID
    assert arrays["ft.weight"].shape == schema.EXPECTED_SHAPES["ft.weight"]
