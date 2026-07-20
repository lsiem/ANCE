"""Smoke test for the live gauntlet dashboard HTML generator."""

from __future__ import annotations

import json

import chess

from ance.tools.gauntlet_dashboard import generate


def test_gauntlet_dashboard_polls_api_without_meta_refresh(tmp_path) -> None:
    checkpoint = tmp_path / "05-gauntlet-checkpoint.json"
    live = tmp_path / "05-gauntlet-live.json"
    out = tmp_path / "05-gauntlet-dashboard.html"

    checkpoint.write_text(
        json.dumps(
            {
                "status": "running",
                "parameters": {
                    "n_games": 1000,
                    "mode": "fixed_depth",
                    "search_depth": 3,
                    "engine_a": {
                        "name": "nnue",
                        "env": {"ANCE_EVAL": "nnue"},
                    },
                    "engine_b": {
                        "name": "handcrafted",
                        "env": {"ANCE_EVAL": "handcrafted"},
                    },
                },
                "aggregate": {
                    "wins": 2,
                    "draws": 1,
                    "losses": 1,
                    "score_rate": 0.625,
                    "elo": 80.0,
                    "elo_ci_low": -20.0,
                    "elo_ci_high": 180.0,
                    "elapsed_s": 120.0,
                },
                "games": [
                    {"outcome": "win", "elapsed_s": 30, "moves": 40, "a_is_white": True},
                    {"outcome": "loss", "elapsed_s": 30, "moves": 42, "a_is_white": False},
                    {"outcome": "draw", "elapsed_s": 30, "moves": 50, "a_is_white": True},
                    {"outcome": "win", "elapsed_s": 30, "moves": 38, "a_is_white": False},
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
    live.write_text(
        json.dumps(
            {
                "fen": chess.STARTING_FEN,
                "game_index": 4,
                "n_games": 1000,
                "halfmoves": 0,
                "turn": "white",
                "white": "nnue",
                "black": "handcrafted",
                "thinking": False,
                "updated_utc": "2026-07-20T12:00:00Z",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    info = generate(checkpoint, out, live_path=live)
    html = out.read_text(encoding="utf-8")

    assert info["n_done"] == 4
    assert info["payload"]["change_key"]
    assert info["payload"]["wins"] == 2
    assert "Results mix" in html
    assert "/api.json" in html
    assert "charts on change" in html or "poll 4s" in html
    assert 'http-equiv="refresh"' not in html
    assert "animation: false" in html
    assert "update('none')" in html or 'update("none")' in html
    assert "<svg" in html
