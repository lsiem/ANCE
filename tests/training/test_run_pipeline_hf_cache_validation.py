"""HF cache validation tests that do not require importing real torch."""

from __future__ import annotations

import importlib
import json
import sys
import types
from pathlib import Path


def _fake_hf_samples(prefix: str) -> list[dict]:
    return [
        {
            "fen": f"8/8/8/8/8/8/8/K6k w - - 0 {ply}",
            "cp": float(ply),
            "game_result": None,
            "game_id": f"{prefix}-{ply:04d}",
            "source": "lichess-hf",
        }
        for ply in range(1, 9)
    ]


def _import_run_pipeline(monkeypatch):
    fake_kfit = types.ModuleType("training.data.kfit")
    fake_kfit.fit_k_from_samples = lambda samples, min_result_rows=10: 400.0
    fake_kfit.sigmoid = lambda *args, **kwargs: None

    fake_shards = types.ModuleType("training.data.shards")
    fake_shards.build_shard = lambda samples, path: Path(path).write_text(
        json.dumps({"n_samples": len(samples)}),
        encoding="utf-8",
    )

    fake_train = types.ModuleType("training.train")
    fake_train.preflight_mps_gate = lambda: "cpu"

    def run_training(*args, **kwargs):
        return {
            "model": object(),
            "val_losses": [0.1],
            "train_losses": [0.2],
            "device": "cpu",
            "stopped_early": False,
            "global_step": 1,
            "best_epoch": 0,
            "best_val_loss": 0.1,
            "early_stop_reason": None,
            "batch_size": kwargs["batch_size"],
        }

    fake_train.run_training = run_training

    fake_export = types.ModuleType("training.export")
    fake_export.export_checkpoint = (
        lambda model, k_scale, path, extra_meta=None: Path(path).write_text(
            json.dumps({"k_scale": k_scale, "meta": extra_meta or {}}),
            encoding="utf-8",
        )
    )

    monkeypatch.setitem(sys.modules, "training.train", fake_train)
    monkeypatch.setitem(sys.modules, "training.export", fake_export)
    monkeypatch.setitem(sys.modules, "training.data.kfit", fake_kfit)
    monkeypatch.setitem(sys.modules, "training.data.shards", fake_shards)
    monkeypatch.delitem(sys.modules, "training.run_pipeline", raising=False)

    return importlib.import_module("training.run_pipeline")


def test_latest_manifest_event_returns_latest_matching_entry(tmp_path, monkeypatch) -> None:
    run_pipeline = _import_run_pipeline(monkeypatch)
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {"event": "hf_ingest", "repo_id": "old/repo"},
                {"event": "merge", "n_samples": 8},
                {"event": "hf_ingest", "repo_id": "new/repo"},
            ]
        ),
        encoding="utf-8",
    )

    assert run_pipeline._latest_manifest_event(manifest, event="hf_ingest") == {
        "event": "hf_ingest",
        "repo_id": "new/repo",
    }
    assert run_pipeline._latest_manifest_event(manifest, event="shards") is None
    assert run_pipeline._latest_manifest_event(tmp_path / "missing.json", event="hf_ingest") is None


def test_can_reuse_hf_cache_requires_all_manifest_fields_to_match(tmp_path, monkeypatch) -> None:
    run_pipeline = _import_run_pipeline(monkeypatch)
    manifest = tmp_path / "run_manifest.json"
    manifest.write_text(
        json.dumps(
            [
                {
                    "event": "hf_ingest",
                    "repo_id": "fake/repo",
                    "max_positions": 6,
                    "min_depth": 22,
                    "min_knodes": 1500,
                }
            ]
        ),
        encoding="utf-8",
    )

    assert run_pipeline._can_reuse_hf_cache(
        manifest,
        repo_id="fake/repo",
        max_positions=6,
        min_depth=22,
        min_knodes=1500,
    )
    assert not run_pipeline._can_reuse_hf_cache(
        manifest,
        repo_id="other/repo",
        max_positions=6,
        min_depth=22,
        min_knodes=1500,
    )
    assert not run_pipeline._can_reuse_hf_cache(
        manifest,
        repo_id="fake/repo",
        max_positions=7,
        min_depth=22,
        min_knodes=1500,
    )
    assert not run_pipeline._can_reuse_hf_cache(
        manifest,
        repo_id="fake/repo",
        max_positions=6,
        min_depth=23,
        min_knodes=1500,
    )
    assert not run_pipeline._can_reuse_hf_cache(
        manifest,
        repo_id="fake/repo",
        max_positions=6,
        min_depth=22,
        min_knodes=1501,
    )


def test_invalidate_hf_derived_outputs_removes_known_files(tmp_path, monkeypatch) -> None:
    run_pipeline = _import_run_pipeline(monkeypatch)

    for name in ("merged_samples.json", "train.npz", "val.npz", "net.safetensors"):
        (tmp_path / name).write_text("stale", encoding="utf-8")

    run_pipeline._invalidate_hf_derived_outputs(tmp_path)

    for name in ("merged_samples.json", "train.npz", "val.npz", "net.safetensors"):
        assert not (tmp_path / name).exists()

    run_pipeline._invalidate_hf_derived_outputs(tmp_path)


def test_run_bounded_reuses_hf_cache_when_manifest_matches(tmp_path, monkeypatch) -> None:
    run_pipeline = _import_run_pipeline(monkeypatch)
    fake_samples = _fake_hf_samples("cached")
    calls: list[tuple[str, int, int, int]] = []

    def fake_iter(repo_id, *, max_positions, min_depth, min_knodes, n_buckets=1000, deadline_monotonic=None):
        calls.append((repo_id, max_positions, min_depth, min_knodes))
        yield from fake_samples[:max_positions]

    monkeypatch.setattr(run_pipeline, "iter_hf_samples", fake_iter)
    monkeypatch.setattr(run_pipeline.shutil, "which", lambda name: None)

    run_pipeline.run_bounded(
        tmp_path,
        lichess_zst=None,
        fresh_n_games=0,
        depth=None,
        max_hours=0.1,
        hf_dataset="fake/repo",
        hf_max_positions=6,
        hf_min_depth=22,
        hf_min_knodes=1500,
        epochs=1,
    )

    assert len(calls) == 1
    cached_rows = json.loads((tmp_path / "hf_samples.json").read_text(encoding="utf-8"))
    assert cached_rows

    run_pipeline.run_bounded(
        tmp_path,
        lichess_zst=None,
        fresh_n_games=0,
        depth=None,
        max_hours=0.1,
        hf_dataset="fake/repo",
        hf_max_positions=6,
        hf_min_depth=22,
        hf_min_knodes=1500,
        epochs=1,
    )

    assert len(calls) == 1
    assert json.loads((tmp_path / "hf_samples.json").read_text(encoding="utf-8")) == cached_rows


def test_run_bounded_reingests_hf_cache_when_manifest_mismatches(tmp_path, monkeypatch) -> None:
    run_pipeline = _import_run_pipeline(monkeypatch)
    first_samples = _fake_hf_samples("first")
    second_samples = _fake_hf_samples("second")
    calls: list[tuple[str, int, int, int]] = []

    def fake_iter(repo_id, *, max_positions, min_depth, min_knodes, n_buckets=1000, deadline_monotonic=None):
        calls.append((repo_id, max_positions, min_depth, min_knodes))
        samples = first_samples if len(calls) == 1 else second_samples
        yield from samples[:max_positions]

    monkeypatch.setattr(run_pipeline, "iter_hf_samples", fake_iter)
    monkeypatch.setattr(run_pipeline.shutil, "which", lambda name: None)

    run_pipeline.run_bounded(
        tmp_path,
        lichess_zst=None,
        fresh_n_games=0,
        depth=None,
        max_hours=0.1,
        hf_dataset="fake/repo",
        hf_max_positions=6,
        hf_min_depth=20,
        hf_min_knodes=1000,
        epochs=1,
    )

    (tmp_path / "merged_samples.json").write_text("stale", encoding="utf-8")
    (tmp_path / "net.safetensors").write_text("stale", encoding="utf-8")

    run_pipeline.run_bounded(
        tmp_path,
        lichess_zst=None,
        fresh_n_games=0,
        depth=None,
        max_hours=0.1,
        hf_dataset="fake/repo",
        hf_max_positions=6,
        hf_min_depth=21,
        hf_min_knodes=1000,
        epochs=1,
    )

    assert len(calls) == 2
    assert json.loads((tmp_path / "hf_samples.json").read_text(encoding="utf-8"))[0]["game_id"].startswith(
        "second-"
    )
    assert json.loads((tmp_path / "merged_samples.json").read_text(encoding="utf-8"))[0]["game_id"].startswith(
        "second-"
    )
    assert (tmp_path / "net.safetensors").read_text(encoding="utf-8") != "stale"

    manifest = json.loads((tmp_path / "run_manifest.json").read_text(encoding="utf-8"))
    hf_events = [event for event in manifest if event.get("event") == "hf_ingest"]
    assert hf_events[-1]["repo_id"] == "fake/repo"
    assert hf_events[-1]["min_depth"] == 21
