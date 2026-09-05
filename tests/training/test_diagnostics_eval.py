"""Pre-gauntlet diagnostics (Phase 6)."""

from __future__ import annotations

from pathlib import Path

import pytest

from training.diagnostics_eval import check_material_signs, run_diagnostics


class _PolarityOnlyEval:
    """Rook-up scores above queen-up, but both are clearly positive."""

    def evaluate(self, position) -> int:
        fen = position.board.fen()
        if "4KR2" in fen:
            return 160
        if "4KQ2" in fen:
            return 138
        return 0


def test_material_signs_accepts_positive_polarity_without_queen_gt_rook() -> None:
    result = check_material_signs(_PolarityOnlyEval())
    assert result.ok
    assert "rook_up=160" in result.detail
    assert "queen_up=138" in result.detail


@pytest.mark.skipif(
    not Path("ance/eval/nnue/net.safetensors").is_file(),
    reason="engine net not present",
)
def test_diagnostics_run_against_packaged_net() -> None:
    results = run_diagnostics("ance/eval/nnue/net.safetensors")
    assert len(results) == 3
    # Weak nets may fail material signs; still must return structured results.
    assert all(hasattr(r, "ok") and hasattr(r, "name") for r in results)
    by_name = {r.name: r for r in results}
    assert by_name["startpos_near_zero"].ok
    assert by_name["color_flip"].ok
    assert by_name["material_signs"].ok
