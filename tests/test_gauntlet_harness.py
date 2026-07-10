"""TOOL-03 gauntlet arbiter contracts (D-14 through D-19)."""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

import chess
import pytest

from ance.tools import gauntlet


class _ScriptedEngine:
    def __init__(self, moves: list[str]) -> None:
        self.moves = iter(moves)
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


def test_arbiter_referees_wall_clock_and_credits_increment_after_move(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    white = _ScriptedEngine(["e2e4"])
    black = _ScriptedEngine(["e7e5"])
    clock = iter([0.0, 0.75, 0.75, 1.85])
    monkeypatch.setattr(gauntlet.time, "monotonic", lambda: next(clock))

    record = gauntlet.play_gauntlet_game(
        white,
        black,
        chess.STARTING_FEN,
        tc_base_s=1.0,
        tc_inc_s=0.5,
        max_halfmoves=20,
        game_key="g0",
        stop_event=None,
        deadline=None,
    )

    assert record["outcome"] == "time_forfeit"
    assert record["result"] == "1-0"
    assert record["forfeited_by"] == "black"
    assert record["moves"] == 1
    assert black.limits[0].white_clock == pytest.approx(0.75)


def test_game_index_controls_opening_and_color_parity(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    engine_a = _ScriptedEngine([])
    engine_b = _ScriptedEngine([])
    launched = iter([engine_a, engine_b])
    calls: list[tuple[object, object, str, object]] = []
    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv: next(launched),
    )

    def play_spy(
        white: object,
        black: object,
        opening: str,
        *args: object,
        game_key: object,
        **kwargs: object,
    ) -> dict[str, object]:
        calls.append((white, black, opening, game_key))
        return _draw_record()

    monkeypatch.setattr(gauntlet, "play_gauntlet_game", play_spy)
    openings = [chess.Board().fen() for _ in range(4)]

    gauntlet.run_gauntlet(
        gauntlet.EngineSpec("A", ["engine-a"]),
        gauntlet.EngineSpec("B", ["engine-b"]),
        openings,
        n_games=8,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=20,
        output_path=tmp_path / "parity.json",
    )

    assert [call[2] for call in calls] == [
        openings[(index // 2) % 4] for index in range(8)
    ]
    assert [call[0] is engine_a for call in calls] == [
        index % 2 == 0 for index in range(8)
    ]
    assert engine_a.quit_called and engine_b.quit_called


def test_wilson_interval_matches_reference_and_contains_score() -> None:
    low, high = gauntlet.wilson_ci(50, 100)
    assert low == pytest.approx(0.4038, abs=1e-3)
    assert high == pytest.approx(0.5962, abs=1e-3)
    for points in (1.0, 10.5, 49.5, 99.0):
        low, high = gauntlet.wilson_ci(points, 100)
        assert low <= points / 100 <= high


def test_checkpoint_is_atomic_and_resume_only_plays_missing_games(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    output = tmp_path / "resume.json"
    specs = (
        gauntlet.EngineSpec("A", ["engine-a"]),
        gauntlet.EngineSpec("B", ["engine-b"]),
    )
    openings = [chess.STARTING_FEN]
    played: list[int] = []
    replacements: list[tuple[object, object]] = []
    original_replace = gauntlet.os.replace
    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv: _ScriptedEngine([]),
    )
    monkeypatch.setattr(
        gauntlet.os,
        "replace",
        lambda src, dst: (replacements.append((src, dst)), original_replace(src, dst))[1],
    )

    def interrupted_play(*args: object, game_key: object, **kwargs: object) -> dict:
        index = int(str(game_key).rsplit("-", 1)[1])
        if index == 5:
            raise gauntlet.HarnessTimeout("test interruption")
        played.append(index)
        return _draw_record()

    monkeypatch.setattr(gauntlet, "play_gauntlet_game", interrupted_play)
    with pytest.raises(gauntlet.HarnessTimeout):
        gauntlet.run_gauntlet(
            *specs,
            openings,
            n_games=8,
            tc_base_s=30.0,
            tc_inc_s=0.3,
            max_halfmoves=20,
            output_path=output,
        )
    assert played == [0, 1, 2, 3, 4]
    assert len(replacements) >= 6

    played.clear()
    monkeypatch.setattr(
        gauntlet,
        "play_gauntlet_game",
        lambda *args, game_key, **kwargs: (
            played.append(int(str(game_key).rsplit("-", 1)[1])),
            _draw_record(),
        )[1],
    )
    report = gauntlet.run_gauntlet(
        *specs,
        openings,
        n_games=8,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=20,
        output_path=output,
    )
    assert played == [5, 6, 7]
    assert report["status"] == "completed"

    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv: pytest.fail("engine launched before parameter validation"),
    )
    with pytest.raises(ValueError, match="incompatible"):
        gauntlet.run_gauntlet(
            gauntlet.EngineSpec("changed", ["different"]),
            specs[1],
            openings,
            n_games=8,
            tc_base_s=30.0,
            tc_inc_s=0.3,
            max_halfmoves=20,
            output_path=output,
        )


def test_report_has_complete_d19_contract(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    launched = iter([_ScriptedEngine([]), _ScriptedEngine([])])
    monkeypatch.setattr(
        gauntlet.chess.engine.SimpleEngine,
        "popen_uci",
        lambda argv: next(launched),
    )
    outcomes = iter(
        [
            {**_draw_record(), "outcome": "win", "result": "1-0"},
            _draw_record(),
            {**_draw_record(), "outcome": "loss", "result": "1-0"},
        ]
    )
    monkeypatch.setattr(
        gauntlet, "play_gauntlet_game", lambda *args, **kwargs: next(outcomes)
    )

    report = gauntlet.run_gauntlet(
        gauntlet.EngineSpec("A", ["a"]),
        gauntlet.EngineSpec("B", ["b"]),
        [chess.STARTING_FEN],
        n_games=3,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=20,
        output_path=tmp_path / "report.json",
        command_line="python -m ance.tools.gauntlet --games 3 --tc 30+0.3",
    )
    aggregate = report["aggregate"]

    assert aggregate["wins"] == aggregate["losses"] == aggregate["draws"] == 1
    assert aggregate["score_rate"] == pytest.approx(0.5)
    assert aggregate["draw_rate"] == pytest.approx(1 / 3)
    assert aggregate["wilson_low"] < 0.5 < aggregate["wilson_high"]
    assert aggregate["time_forfeits"] == {"A": 0, "B": 0}
    assert report["parameters"]["n_games"] == 3
    assert report["parameters"]["tc"] == "30+0.3"
    assert report["command_line"].endswith("--games 3 --tc 30+0.3")


def test_cutechess_command_and_runner_detection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    command = gauntlet.build_cutechess_command(
        gauntlet.EngineSpec("A", [sys.executable, "-m", "ance"]),
        gauntlet.EngineSpec("B", [sys.executable, "-m", "ance"]),
        "30+0.3",
        tmp_path / "openings.epd",
        games=2,
        rounds=4,
        pgnout=tmp_path / "games.pgn",
    )
    joined = " ".join(command)
    assert command[0] == "cutechess-cli"
    assert command.count("-engine") == 2
    assert "-each" in command and "tc=30+0.3" in command
    assert "-openings" in command and "format=epd" in command
    assert "-games" in command and command[command.index("-games") + 1] == "2"
    assert "-repeat" in command
    assert "shell=True" not in joined

    monkeypatch.setattr(gauntlet.shutil, "which", lambda name: None)
    assert gauntlet.detect_runner() == "arbiter"


def test_fixed_opening_file_is_balanced_and_parseable() -> None:
    path = Path(gauntlet.__file__).with_name("openings.epd")
    openings = gauntlet.load_openings(path)
    assert len(openings) == 30
    piece_values = {
        chess.PAWN: 1,
        chess.KNIGHT: 3,
        chess.BISHOP: 3,
        chess.ROOK: 5,
        chess.QUEEN: 9,
        chess.KING: 0,
    }
    for fen in openings:
        board = chess.Board(fen)
        assert not board.is_game_over(claim_draw=True)
        assert not board.is_check()
        assert len(list(board.legal_moves)) >= 20
        white_material = sum(
            piece_values[piece.piece_type]
            for piece in board.piece_map().values()
            if piece.color == chess.WHITE
        )
        black_material = sum(
            piece_values[piece.piece_type]
            for piece in board.piece_map().values()
            if piece.color == chess.BLACK
        )
        assert white_material == black_material


@pytest.mark.slow
def test_two_game_arbiter_smoke_completes(tmp_path: Path) -> None:
    output = tmp_path / "real-engine-smoke.json"
    engine_argv = [sys.executable, "-m", "ance"]
    report = gauntlet.run_gauntlet(
        gauntlet.EngineSpec("ance-a", engine_argv),
        gauntlet.EngineSpec("ance-b", engine_argv),
        gauntlet.load_openings(Path(gauntlet.__file__).with_name("openings.epd")),
        n_games=2,
        tc_base_s=60.0,
        tc_inc_s=1.0,
        max_halfmoves=20,
        output_path=output,
        openings_path=Path(gauntlet.__file__).with_name("openings.epd"),
        command_line=(
            f"{sys.executable} -m ance.tools.gauntlet "
            "--games 2 --tc 60+1 --max-halfmoves 20"
        ),
    )
    persisted = json.loads(output.read_text(encoding="utf-8"))

    assert report["status"] == persisted["status"] == "completed"
    assert report["completion"] == "complete"
    assert report["aggregate"]["time_forfeits"] == {
        "ance-a": 0,
        "ance-b": 0,
    }
    assert {
        "wins",
        "losses",
        "draws",
        "score_rate",
        "draw_rate",
        "wilson_low",
        "wilson_high",
        "time_forfeits",
        "n_games",
        "elapsed_s",
    } <= report["aggregate"].keys()
    assert [game["index"] for game in report["games"]] == [0, 1]
    assert [game["a_is_white"] for game in report["games"]] == [True, False]
    assert [game["opening_index"] for game in report["games"]] == [0, 0]
