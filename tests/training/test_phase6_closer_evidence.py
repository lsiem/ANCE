"""Phase 6 evidence contract smoke (no overnight gauntlet)."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from importlib.machinery import SourceFileLoader


def test_write_evidence_schema(tmp_path, monkeypatch) -> None:
    mod_path = Path(
        ".planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py"
    )
    mod = SourceFileLoader("post_train_close_06", str(mod_path)).load_module()
    monkeypatch.setattr(mod, "EVIDENCE", tmp_path / "06-GAUNTLET-EVIDENCE.json")
    monkeypatch.setattr(mod, "CHECKPOINT", tmp_path / "ckpt.json")

    diagnostics = [
        SimpleNamespace(name="startpos_near_zero", ok=True, detail="cp=0"),
        SimpleNamespace(name="material_signs", ok=True, detail="ok"),
        SimpleNamespace(name="color_flip", ok=True, detail="ok"),
    ]
    depth_report = {
        "status": "completed",
        "aggregate": {
            "n_games": 1000,
            "wins": 400,
            "losses": 300,
            "draws": 300,
            "score_rate": 0.55,
            "elo": 35.0,
            "elo_ci_low": 5.0,
            "elo_ci_high": 65.0,
        },
    }
    evidence = mod._write_evidence(
        diagnostics=diagnostics,
        probe=None,
        depth_report=depth_report,
        clock_report=None,
        corpus_meta={"has_result_rate": 0.7},
    )
    assert evidence["gates_passed"] == ["D-12", "TOOL-04"]
    loaded = json.loads(mod.EVIDENCE.read_text())
    assert loaded["schema_version"] == 1
    assert "gauntlet" in loaded
    assert loaded["gauntlet"]["games"] == 1000
