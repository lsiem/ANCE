"""Smoke test for the NNUE training dashboard HTML generator."""

from __future__ import annotations

import json

import chess

from ance.tools.training_dashboard import generate


def test_training_dashboard_generate_contains_loss_curves(tmp_path) -> None:
    metrics_path = tmp_path / "metrics.json"
    live_path = tmp_path / "training-live.json"
    out_path = tmp_path / "training-dashboard.html"

    metrics_path.write_text(
        json.dumps(
            {
                "updated_utc": "2026-07-18T12:00:00Z",
                "status": "running",
                "epoch": 2,
                "epochs": 10,
                "global_step": 128,
                "train_losses": [0.72, 0.55],
                "val_losses": [0.68, 0.51],
                "learning_rates": [1e-3, 1e-3],
                "best_val_loss": 0.51,
                "best_epoch": 2,
                "batch_size": 256,
                "lr": 1e-3,
                "weight_decay": 1e-4,
                "k": 400,
                "device": "cpu",
                "stopped_early": False,
                "early_stop_reason": None,
                "sample_fen": chess.STARTING_FEN,
                "checkpoint_dir": str(tmp_path),
                "best_checkpoint": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    live_path.write_text(
        json.dumps(
            {
                "phase": "labeling",
                "fen": "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq e3 0 1",
                "depth": 14,
                "done": 100,
                "total": 1000,
                "rate_per_s": 12.5,
                "eta_s": 72.0,
                "updated_utc": "2026-07-18T12:00:01Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    info = generate(metrics_path, out_path, live_path=live_path)
    html = out_path.read_text(encoding="utf-8")

    assert info["out"] == str(out_path)
    assert "train" in html.lower()
    assert "Train loss" in html
    assert "Val loss" in html
    assert "0.510000" in html or "0.51" in html
    assert "labeling" in html.lower()
    assert "<svg" in html
