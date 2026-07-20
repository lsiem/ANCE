"""Pre-gauntlet diagnostics (Phase 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from training.diagnostics_eval import run_diagnostics


@pytest.mark.skipif(
    not Path("ance/eval/nnue/net.safetensors").is_file(),
    reason="engine net not present",
)
def test_diagnostics_run_against_packaged_net() -> None:
    results = run_diagnostics("ance/eval/nnue/net.safetensors")
    assert len(results) == 3
    # Weak nets may fail material signs; still must return structured results.
    assert all(hasattr(r, "ok") and hasattr(r, "name") for r in results)
