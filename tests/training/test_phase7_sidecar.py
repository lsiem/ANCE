"""Phase 7 sidecar writer and install helper contract (no M4 train)."""

from __future__ import annotations

import json
from importlib.machinery import SourceFileLoader
from pathlib import Path

import pytest

from nnue_format.schema import ARCH_ID, FEATURE_SET

_HELPER = Path(".planning/phases/07-nnue-strength-recovery/install_phase7_net.py")

REQUIRED_SIDECAR_KEYS = (
    "phase",
    "from_scratch",
    "arch_id",
    "feature_set",
    "hf_max_positions",
    "lichess_month",
    "min_has_result_rate",
    "n_merged",
    "has_result_rate",
    "best_elo",
    "best_elo_epoch",
    "best_val_loss",
    "k_scale",
    "installed_utc",
)

PINNED_ARGV_PAIRS = (
    ("--hf-max-positions", "750000"),
    ("--lichess-max-samples", "80000"),
    ("--min-has-result-rate", "0.15"),
    ("--elo-probe-every", "5"),
    ("--elo-probe-games", "12"),
    ("--random-fen-skipping", "2"),
    ("--epochs", "30"),
    ("--early-stop-patience", "6"),
    ("--fresh-n-games", "0"),
    ("--start-lambda", "1.0"),
    ("--end-lambda", "0.75"),
)


def _load_helper(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    if not _HELPER.is_file():
        pytest.fail("install_phase7_net.py missing")
    mod = SourceFileLoader("install_phase7_net", str(_HELPER)).load_module()
    monkeypatch.setattr(mod, "SIDECAR_PATH", tmp_path / "07-NET-SIDECAR.json")
    monkeypatch.setattr(mod, "ENGINE_NET", tmp_path / "engine_net.safetensors")
    monkeypatch.setattr(mod, "PHASE_DIR", tmp_path)
    return mod


def test_write_sidecar_phase7_from_scratch_arch_lock(tmp_path, monkeypatch) -> None:
    mod = _load_helper(tmp_path, monkeypatch)
    mod.write_sidecar({})
    loaded = json.loads(mod.SIDECAR_PATH.read_text(encoding="utf-8"))
    assert loaded["phase"] == 7
    assert loaded["from_scratch"] is True
    assert loaded["arch_id"] == ARCH_ID
    assert loaded["feature_set"] == FEATURE_SET


def test_write_sidecar_rfc_json_and_required_keys(tmp_path, monkeypatch) -> None:
    mod = _load_helper(tmp_path, monkeypatch)
    mod.write_sidecar({"best_elo": float("nan"), "best_val_loss": float("inf")})
    raw = mod.SIDECAR_PATH.read_text(encoding="utf-8")
    assert "NaN" not in raw
    assert "Infinity" not in raw
    loaded = json.loads(raw)
    for key in REQUIRED_SIDECAR_KEYS:
        assert key in loaded
    json.dumps(loaded, allow_nan=False)
    assert loaded["best_elo"] is None
    assert loaded["best_val_loss"] is None
    assert loaded["hf_max_positions"] == 750000
    assert loaded["lichess_month"] == "2013-01"
    assert loaded["min_has_result_rate"] == 0.15
    assert loaded["arch_id"] == ARCH_ID
    assert loaded["feature_set"] == FEATURE_SET


def test_install_export_copies_to_monkeypatched_engine_net(tmp_path, monkeypatch) -> None:
    mod = _load_helper(tmp_path, monkeypatch)
    src = tmp_path / "export.safetensors"
    src.write_bytes(b"fake-safetensors-bytes")
    mod.install_export(src)
    assert mod.ENGINE_NET.is_file()
    assert mod.ENGINE_NET.read_bytes() == b"fake-safetensors-bytes"
    packaged = Path("ance/eval/nnue/net.safetensors")
    assert packaged.resolve() != mod.ENGINE_NET.resolve()


def test_sidecar_identity_payload_rejects_wrong_phase_or_not_from_scratch(
    tmp_path, monkeypatch
) -> None:
    mod = _load_helper(tmp_path, monkeypatch)
    assert mod.sidecar_identity_payload({"phase": 7, "from_scratch": True}) is True
    assert mod.sidecar_identity_payload({"phase": "7", "from_scratch": True}) is True
    assert mod.sidecar_identity_payload({"phase": 6, "from_scratch": True}) is False
    assert mod.sidecar_identity_payload({"phase": 7, "from_scratch": False}) is False
    assert mod.sidecar_identity_payload({"phase": 7, "from_scratch": 1}) is False
    assert mod.sidecar_identity_payload({"from_scratch": True}) is False


def test_m4_pipeline_argv_pinned_flags_omit_resume(tmp_path, monkeypatch) -> None:
    mod = _load_helper(tmp_path, monkeypatch)
    argv = list(mod.M4_PIPELINE_ARGV)
    argv_s = [str(part) for part in argv]
    for flag, value in PINNED_ARGV_PAIRS:
        assert flag in argv_s
        idx = argv_s.index(flag)
        assert argv_s[idx + 1] == value
    assert "--resume-from-checkpoint" not in argv_s
