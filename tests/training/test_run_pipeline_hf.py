"""Tests for the Hugging Face stream wiring in the pipeline CLI orchestrator."""

from __future__ import annotations

import json
import random
import time

import pytest

pytest.importorskip("torch")

import chess

from training import run_pipeline

pytestmark = pytest.mark.torch


def _fake_hf_samples(n: int, n_game_ids: int = 6) -> list[dict]:
    """Build n sample dicts over real distinct FENs via a seeded legal walk."""
    rng = random.Random(1234)
    samples: list[dict] = []
    seen_fens: set[str] = set()
    board = chess.Board()
    while len(samples) < n:
        if board.is_game_over():
            board = chess.Board()
        move = rng.choice(sorted(board.legal_moves, key=lambda m: m.uci()))
        board.push(move)
        fen = board.fen()
        if fen in seen_fens:
            continue
        seen_fens.add(fen)
        samples.append(
            {
                "fen": fen,
                "cp": float(rng.randint(-300, 300)),
                "game_result": None,
                "game_id": f"hf-{len(samples) % n_game_ids:04d}",
                "source": "lichess-hf",
            }
        )
    return samples


def test_ingest_hf_caps_samples_and_forwards_thresholds(monkeypatch) -> None:
    seen_kwargs: dict = {}

    def fake_iter(repo_id, *, max_positions, min_depth, min_knodes, n_buckets=1000):
        seen_kwargs.update(
            repo_id=repo_id,
            max_positions=max_positions,
            min_depth=min_depth,
            min_knodes=min_knodes,
        )
        yield from _fake_hf_samples(50)

    monkeypatch.setattr(run_pipeline, "iter_hf_samples", fake_iter)

    samples = run_pipeline._ingest_hf(
        "fake/repo",
        max_positions=10,
        min_depth=22,
        min_knodes=1500,
        deadline_monotonic=time.monotonic() + 60.0,
    )

    assert len(samples) <= 10
    assert seen_kwargs["repo_id"] == "fake/repo"
    assert seen_kwargs["min_depth"] == 22
    assert seen_kwargs["min_knodes"] == 1500


def test_run_bounded_hf_primary_no_stockfish(tmp_path, monkeypatch) -> None:
    fake_samples = _fake_hf_samples(60)
    assert len({s["game_id"] for s in fake_samples}) >= 4

    def fake_iter(repo_id, *, max_positions, min_depth, min_knodes, n_buckets=1000):
        yield from fake_samples[:max_positions]

    monkeypatch.setattr(run_pipeline, "iter_hf_samples", fake_iter)
    # Prove the HF-primary path needs no stockfish binary on PATH.
    monkeypatch.setattr(run_pipeline.shutil, "which", lambda name: None)

    result = run_pipeline.run_bounded(
        tmp_path,
        lichess_zst=None,
        fresh_n_games=0,
        depth=None,
        max_hours=0.1,
        hf_dataset="fake/repo",
        hf_max_positions=60,
        epochs=1,
    )

    assert (tmp_path / "net.safetensors").exists()
    assert result["net_path"] == str(tmp_path / "net.safetensors")

    hf_cache = tmp_path / "hf_samples.json"
    assert hf_cache.exists()
    rows = json.loads(hf_cache.read_text(encoding="utf-8"))
    assert rows
    assert all(row["source"] == "lichess-hf" for row in rows)


def test_run_bounded_reuses_hf_samples_cache(tmp_path, monkeypatch) -> None:
    fake_samples = _fake_hf_samples(60)

    def fake_iter(repo_id, *, max_positions, min_depth, min_knodes, n_buckets=1000):
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
        hf_max_positions=60,
        epochs=1,
    )
    assert (tmp_path / "hf_samples.json").exists()

    def raising_iter(*args, **kwargs):
        raise AssertionError("iter_hf_samples must not be called on resume")

    monkeypatch.setattr(run_pipeline, "iter_hf_samples", raising_iter)

    # Second run in the same out_dir must reuse hf_samples.json.
    run_pipeline.run_bounded(
        tmp_path,
        lichess_zst=None,
        fresh_n_games=0,
        depth=None,
        max_hours=0.1,
        hf_dataset="fake/repo",
        hf_max_positions=60,
        epochs=1,
    )
