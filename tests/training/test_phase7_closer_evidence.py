"""Phase 7 closer evidence contract (no overnight gauntlet)."""

from __future__ import annotations

import json
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import SimpleNamespace

_CLOSER = Path(".planning/phases/07-nnue-strength-recovery/post_train_close_07.py")
_PHASE6_EVIDENCE = Path(
    ".planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json"
)


def _load_closer(tmp_path, monkeypatch):
    mod = SourceFileLoader("post_train_close_07", str(_CLOSER)).load_module()
    monkeypatch.setattr(mod, "EVIDENCE", tmp_path / "07-GAUNTLET-EVIDENCE.json")
    monkeypatch.setattr(mod, "CHECKPOINT", tmp_path / "ckpt.json")
    monkeypatch.setattr(mod, "SIDECAR", tmp_path / "07-NET-SIDECAR.json")
    monkeypatch.setattr(mod, "LOG", tmp_path / "07-post-train-close.log")
    monkeypatch.setattr(mod, "STATE", tmp_path / "07-post-train-close-state.json")
    monkeypatch.setattr(mod, "LIVE", tmp_path / "07-gauntlet-live.json")
    monkeypatch.setattr(mod, "PHASE_DIR", tmp_path)
    return mod


def _ok_diagnostics() -> list[SimpleNamespace]:
    return [
        SimpleNamespace(name="startpos_near_zero", ok=True, detail="cp=0"),
        SimpleNamespace(name="material_signs", ok=True, detail="ok"),
        SimpleNamespace(name="color_flip", ok=True, detail="ok"),
    ]


def test_write_evidence_schema(tmp_path, monkeypatch) -> None:
    mod = _load_closer(tmp_path, monkeypatch)
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
        diagnostics=_ok_diagnostics(),
        probe=None,
        depth_report=depth_report,
        clock_report=None,
        corpus_meta={"has_result_rate": 0.7},
    )
    assert evidence["gates_passed"] == ["D-12", "TOOL-04"]
    loaded = json.loads(mod.EVIDENCE.read_text())
    assert loaded["schema_version"] == 1
    assert "probe_smoke" in loaded
    assert "compare_phase6" in loaded
    assert "blocked" in loaded
    assert loaded["gauntlet"]["games"] == 1000
    assert loaded["compare_phase6"] == mod.PHASE6_BASELINE


def test_shutout_probe_serializes_without_nan(tmp_path, monkeypatch) -> None:
    mod = _load_closer(tmp_path, monkeypatch)
    probe = {
        "status": "completed",
        "aggregate": {
            "n_games": 200,
            "wins": 0,
            "losses": 200,
            "draws": 0,
            "score_rate": 0.0,
            "wilson_low": 0.0,
            "wilson_high": 0.0188,
            "elo": float("-inf"),
            "elo_ci_low": float("-inf"),
            "elo_ci_high": -686.6,
            "elapsed_s": 28142.0,
        },
    }
    evidence = mod._write_evidence(
        diagnostics=_ok_diagnostics(),
        probe=probe,
        depth_report=None,
        clock_report=None,
        corpus_meta={"n_merged": 19866},
    )
    raw = mod.EVIDENCE.read_text()
    assert "Infinity" not in raw
    assert "NaN" not in raw
    loaded = json.loads(raw)
    assert loaded["probe_200"]["n_games"] == 200
    assert loaded["probe_200"]["wins"] == 0
    assert loaded["probe_200"]["elo"] is None
    assert loaded["probe_200"]["elo_ci_low"] is None
    assert loaded["gates_failed"] == ["D-12", "TOOL-04"]
    assert evidence["probe_200"]["elo"] is None


def test_blocked_without_sidecar(tmp_path, monkeypatch) -> None:
    mod = _load_closer(tmp_path, monkeypatch)

    def _forbid(*_a, **_k):
        raise AssertionError("must not start diagnostics or play without sidecar")

    monkeypatch.setattr(mod, "run_diagnostics", _forbid)
    monkeypatch.setattr(mod, "run_elo_probe", _forbid)
    monkeypatch.setattr(mod.gauntlet, "run_gauntlet", _forbid)

    rc = mod.main()
    assert rc != 0
    loaded = json.loads(mod.EVIDENCE.read_text())
    assert loaded["blocked"]["reason"] == "phase7_net_not_installed"
    assert loaded["gauntlet"]["status"] == "blocked"
    assert loaded["gauntlet"]["depth"] == 3
    assert loaded["probe_smoke"] is None
    assert loaded["probe_200"] is None
    assert "D-14" in loaded["gates_failed"]
    assert "TOOL-04" in loaded["gates_failed"]


def test_smoke_abort_skips_200(tmp_path, monkeypatch) -> None:
    mod = _load_closer(tmp_path, monkeypatch)
    mod.SIDECAR.write_text(
        json.dumps({"phase": 7, "from_scratch": True}) + "\n", encoding="utf-8"
    )

    def _ok_diag(_net: str):
        return _ok_diagnostics()

    def _smoke_or_forbid(_net, *, n_games, **_kwargs):
        if n_games >= 200:
            raise AssertionError("200-game probe must not start after smoke abort")
        return {
            "status": "completed",
            "aggregate": {
                "n_games": n_games,
                "wins": 0,
                "losses": n_games,
                "draws": 0,
                "score_rate": 0.0,
                "wilson_low": 0.0,
                "wilson_high": 0.2,
                "elo": float("-inf"),
                "elo_ci_low": float("-inf"),
                "elo_ci_high": -400.0,
                "elapsed_s": 1.0,
            },
        }

    def _forbid_gauntlet(*_a, **kwargs):
        raise AssertionError(
            f"1000-game gauntlet must not start after smoke abort: {kwargs}"
        )

    monkeypatch.setattr(mod, "run_diagnostics", _ok_diag)
    monkeypatch.setattr(mod, "run_elo_probe", _smoke_or_forbid)
    monkeypatch.setattr(mod.gauntlet, "run_gauntlet", _forbid_gauntlet)

    rc = mod.main()
    assert rc != 0
    loaded = json.loads(mod.EVIDENCE.read_text())
    assert loaded["probe_smoke"] is not None
    assert loaded["probe_smoke"]["wins"] == 0
    assert loaded["probe_smoke"]["elo"] is None
    assert loaded["probe_200"] is None
    assert "TOOL-04" in loaded["gates_failed"]
    assert "D-10" in loaded["gates_failed"] or "D-11" in loaded["gates_failed"]


def test_compare_phase6_matches_phase6_baseline(tmp_path, monkeypatch) -> None:
    mod = _load_closer(tmp_path, monkeypatch)
    phase6 = json.loads(_PHASE6_EVIDENCE.read_text(encoding="utf-8"))
    baseline = mod.PHASE6_BASELINE
    assert baseline["probe_200_wins"] == phase6["probe_200"]["wins"]
    assert baseline["probe_200_losses"] == phase6["probe_200"]["losses"]
    assert baseline["probe_200_draws"] == phase6["probe_200"]["draws"]
    assert baseline["elo_ci_high"] == phase6["probe_200"]["elo_ci_high"]
    assert baseline["n_merged"] == phase6["corpus"]["n_merged"]
    assert baseline["best_elo"] == phase6["corpus"]["best_elo"]
    written = mod._write_evidence(
        diagnostics=_ok_diagnostics(),
        probe=None,
        depth_report=None,
        clock_report=None,
        corpus_meta=None,
    )
    assert written["compare_phase6"] == baseline
