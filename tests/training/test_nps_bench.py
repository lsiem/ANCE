"""nps bench smoke (Phase 6 accumulator verify)."""

from __future__ import annotations

from pathlib import Path

import pytest

from training.nps_bench import run_nps_bench


@pytest.mark.skipif(
    not Path("ance/eval/nnue/net.safetensors").is_file(),
    reason="engine net not present",
)
def test_nps_bench_returns_both_sides() -> None:
    payload = run_nps_bench(depth=2)
    assert payload["handcrafted"]["nodes"] > 0
    assert payload["nnue"]["nodes"] > 0
    assert payload["handcrafted"]["nps"] > 0
    assert payload["nnue"]["nps"] > 0
