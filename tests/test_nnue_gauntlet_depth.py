"""TOOL-04 gauntlet fixed-depth + EngineSpec.env + Elo reporting contracts."""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import chess
import pytest

from ance.tools import gauntlet

ENGINE_ARGV = [sys.executable, "-m", "ance"]


class _ScriptedEngine:
    def __init__(self, moves: list[str] | None = None) -> None:
        self.moves = iter(moves or [])
        self.limits: list[object] = []
        self.game_keys: list[object] = []
        self.quit_called = False

    def play(self, board: chess.Board, limit: object, *, game: object) -> object:
        self.limits.append(limit)
        self.game_keys.append(game)
        return SimpleNamespace(move=chess.Move.from_uci(next(self.moves)))

    def quit(self) -> None:
        self.quit_called = True


def _draw_record() -> dict[str, object]:
    return {
        "outcome": "draw",
        "result": "1/2-1/2",
        "reason": "halfmove_cap",
        "moves": 0,
        "forfeited_by": None,
        "elapsed_s": 0.0,
    }


def test_fixed_depth_uses_limit_depth_not_clocks() -> None:
    white = _ScriptedEngine(["e2e4"])
    black = _ScriptedEngine(["e7e5"])

    gauntlet.play_gauntlet_game(
        white,
        black,
        chess.STARTING_FEN,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=2,
        game_key="g0",
        stop_event=None,
        deadline=None,
        search_depth=3,
    )

    assert white.limits[0].depth == 3
    assert white.limits[0].white_clock is None
    assert white.limits[0].black_clock is None
    assert black.limits[0].depth == 3
    assert black.limits[0].white_clock is None


def test_run_gauntlet_merges_distinct_engine_envs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured_envs: list[dict[str, str]] = []
    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv, **kwargs: (
            captured_envs.append(dict(kwargs.get("env") or {})),
            _ScriptedEngine(),
        )[1],
    )
    monkeypatch.setattr(
        gauntlet, "play_gauntlet_game", lambda *args, **kwargs: _draw_record()
    )

    gauntlet.run_gauntlet(
        gauntlet.EngineSpec(
            "hc", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
        ),
        gauntlet.EngineSpec("nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}),
        [chess.STARTING_FEN],
        n_games=2,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=20,
        output_path=tmp_path / "env.json",
        search_depth=3,
    )

    assert len(captured_envs) == 2
    assert captured_envs[0]["ANCE_EVAL"] == "handcrafted"
    assert captured_envs[1]["ANCE_EVAL"] == "nnue"
    assert captured_envs[0]["ANCE_EVAL"] != captured_envs[1]["ANCE_EVAL"]


def test_checkpoint_parameters_record_depth_mode_and_env_diff(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv, **kwargs: _ScriptedEngine(),
    )
    monkeypatch.setattr(
        gauntlet, "play_gauntlet_game", lambda *args, **kwargs: _draw_record()
    )

    report = gauntlet.run_gauntlet(
        gauntlet.EngineSpec(
            "hc", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
        ),
        gauntlet.EngineSpec("nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}),
        [chess.STARTING_FEN],
        n_games=2,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=20,
        output_path=tmp_path / "params.json",
        search_depth=3,
    )
    params = report["parameters"]

    assert params["mode"] == "fixed_depth"
    assert params["search_depth"] == 3
    assert params["engine_a"]["argv"] == params["engine_b"]["argv"] == ENGINE_ARGV
    assert params["engine_a"]["env"]["ANCE_EVAL"] == "handcrafted"
    assert params["engine_b"]["env"]["ANCE_EVAL"] == "nnue"
    a_env = dict(params["engine_a"]["env"])
    b_env = dict(params["engine_b"]["env"])
    assert set(a_env) == set(b_env) == {"ANCE_EVAL"}
    assert a_env["ANCE_EVAL"] != b_env["ANCE_EVAL"]


def test_aggregate_includes_logistic_elo_and_wilson_ci_bounds() -> None:
    # 6 wins / 10 games → 60% score rate (no draws).
    games = [
        {
            "outcome": "win" if i < 6 else "loss",
            "a_is_white": True,
            "forfeited_by": None,
            "elapsed_s": 0.0,
        }
        for i in range(10)
    ]
    aggregate = gauntlet._aggregate(
        games,
        gauntlet.EngineSpec("A", ["a"]),
        gauntlet.EngineSpec("B", ["b"]),
    )

    assert "elo" in aggregate
    assert "elo_ci_low" in aggregate
    assert "elo_ci_high" in aggregate
    assert aggregate["elo_ci_low"] < aggregate["elo"] < aggregate["elo_ci_high"]
    assert aggregate["score_rate"] == pytest.approx(0.6)


def test_cli_depth_sets_search_depth_and_ignores_clock_tc(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args: object, **kwargs: object) -> dict[str, object]:
        captured["search_depth"] = kwargs.get("search_depth")
        captured["tc_base_s"] = args[4] if len(args) > 4 else kwargs.get("tc_base_s")
        return {
            "aggregate": {"wins": 0, "losses": 0, "draws": 0},
            "parameters": {"search_depth": kwargs.get("search_depth"), "mode": "fixed_depth"},
            "status": "completed",
        }

    monkeypatch.setattr(gauntlet, "run_gauntlet", fake_run)
    monkeypatch.setattr(gauntlet, "load_openings", lambda path: [chess.STARTING_FEN])

    output = tmp_path / "cli-depth.json"
    rc = gauntlet.main(
        [
            "--games",
            "2",
            "--tc",
            "30+0.3",
            "--depth",
            "3",
            "--output",
            str(output),
            "--runner",
            "arbiter",
            "--openings",
            str(tmp_path / "dummy.epd"),
        ]
    )

    assert rc == 0
    assert captured["search_depth"] == 3


def test_omitting_search_depth_preserves_clock_limits() -> None:
    white = _ScriptedEngine(["e2e4"])
    black = _ScriptedEngine(["e7e5"])

    gauntlet.play_gauntlet_game(
        white,
        black,
        chess.STARTING_FEN,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=2,
        game_key="clock",
        stop_event=None,
        deadline=None,
    )

    assert white.limits[0].depth is None
    assert white.limits[0].white_clock == pytest.approx(30.0)
    assert white.limits[0].black_clock == pytest.approx(30.0)
    assert black.limits[0].depth is None
