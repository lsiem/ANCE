"""Clock budgeting and flag-safety contracts (D-11 through D-14)."""

from __future__ import annotations

import sys
import threading
import time

import chess
import pytest

from ance.board.position import Position
from ance.eval.material import MaterialEval
import ance.search.negamax as search_module
from ance.search.types import MAX_PLY, SearchResult
from ance.tools import gauntlet
import ance.uci.loop as loop_module
from ance.uci.clock import compute_clock_budget
from ance.uci.parser import GoCommand
from tests.conftest import EngineProcess


def test_nominal_clock_budget_uses_remaining_time_and_increment() -> None:
    budget = compute_clock_budget(
        GoCommand(wtime=60_000, winc=1_000),
        chess.WHITE,
    )

    assert budget == (3_000.0, 12_000.0)


@pytest.mark.parametrize("remaining", [50, 200, 500, 1_000, 5_000, 60_000, 300_000])
@pytest.mark.parametrize("increment", [0, 100, 1_000, 5_000])
def test_clock_budget_invariants_hold_over_value_grid(
    remaining: int,
    increment: int,
) -> None:
    soft, hard = compute_clock_budget(
        GoCommand(wtime=remaining, winc=increment),
        chess.WHITE,
    )

    assert hard >= 20.0
    assert soft <= hard
    if remaining - 200 >= 20:
        assert hard <= remaining - 200


@pytest.mark.parametrize(
    "command",
    [
        GoCommand(wtime=0),
        GoCommand(wtime=-500),
        GoCommand(wtime=0, winc=-100),
        GoCommand(wtime=30),
    ],
)
def test_garbage_clock_values_clamp_to_floor(command: GoCommand) -> None:
    assert compute_clock_budget(command, chess.WHITE) == (20.0, 20.0)


def test_clock_budget_selects_movers_clock_and_falls_back_to_opponent() -> None:
    command = GoCommand(wtime=60_000, btime=30_000, winc=1_000, binc=500)

    assert compute_clock_budget(command, chess.BLACK) == (1_500.0, 6_000.0)
    assert compute_clock_budget(
        GoCommand(btime=30_000, binc=500),
        chess.WHITE,
    ) == (1_500.0, 6_000.0)
    assert compute_clock_budget(GoCommand(winc=100, binc=200), chess.WHITE) is None


@pytest.mark.parametrize(
    "command",
    [
        GoCommand(depth=4),
        GoCommand(movetime=300),
        GoCommand(infinite=True),
    ],
)
def test_non_clock_go_commands_have_no_clock_budget(command: GoCommand) -> None:
    assert compute_clock_budget(command, chess.WHITE) is None


class _DormantThread:
    def __init__(self, *, target: object, args: tuple[object, ...], daemon: bool) -> None:
        self.target = target
        self.args = args
        self.daemon = daemon

    def start(self) -> None:
        return


class _DormantTimer:
    def __init__(self, interval: float, function: object) -> None:
        self.interval = interval
        self.function = function
        self.daemon = False

    def start(self) -> None:
        return

    def cancel(self) -> None:
        return


def test_go_limit_precedence_and_clock_budget_threading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    threads: list[_DormantThread] = []
    timers: list[_DormantTimer] = []
    monkeypatch.setattr(loop_module, "active_job", None)
    monkeypatch.setattr(loop_module, "_stop_active_worker", lambda: None)
    monkeypatch.setattr(loop_module.time, "monotonic", lambda: 100.0)
    monkeypatch.setattr(
        loop_module.threading,
        "Thread",
        lambda **kwargs: threads.append(_DormantThread(**kwargs)) or threads[-1],
    )
    monkeypatch.setattr(
        loop_module.threading,
        "Timer",
        lambda interval, function: (
            timers.append(_DormantTimer(interval, function)) or timers[-1]
        ),
    )
    position = Position()

    loop_module.handle_go(GoCommand(depth=3, wtime=5_000), position)
    loop_module.handle_go(GoCommand(movetime=300, wtime=5_000), position)
    loop_module.handle_go(GoCommand(infinite=True, wtime=5_000), position)
    loop_module.handle_go(
        GoCommand(wtime=5_000, btime=5_000, winc=100, binc=100),
        position,
    )

    depth_args, movetime_args, infinite_args, clock_args = [
        thread.args for thread in threads
    ]
    assert depth_args[1] == 3
    assert depth_args[6:8] == (None, None)
    assert movetime_args[1] == MAX_PLY
    assert movetime_args[4] is timers[0]
    assert movetime_args[6:8] == (None, None)
    assert infinite_args[6:8] == (None, None)
    assert clock_args[6] == pytest.approx(101.04)
    assert clock_args[7] == pytest.approx(0.26)


def test_soft_budget_skips_doomed_next_iteration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched_depths: list[int] = []
    clock = iter([0.0, 0.1, 0.6])
    monkeypatch.setattr(search_module.time, "monotonic", lambda: next(clock))

    def fake_search(
        pos: Position,
        depth: int,
        *args: object,
    ) -> SearchResult:
        searched_depths.append(depth)
        move = pos.legal_moves()[0]
        return SearchResult(best_move=move, score=depth, depth=depth, pv=[move], nodes=1)

    monkeypatch.setattr(search_module, "_search_at_depth", fake_search)

    result = search_module.search_root(
        Position(),
        max_depth=3,
        evaluator=MaterialEval(),
        stop_flag=threading.Event(),
        soft_budget=1.0,
    )

    assert result.depth == 2
    assert searched_depths == [1, 2]


def test_none_soft_budget_preserves_iterative_deepening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    searched_depths: list[int] = []
    monkeypatch.setattr(search_module.time, "monotonic", lambda: 0.0)

    def fake_search(
        pos: Position,
        depth: int,
        *args: object,
    ) -> SearchResult:
        searched_depths.append(depth)
        move = pos.legal_moves()[0]
        return SearchResult(best_move=move, score=depth, depth=depth, pv=[move], nodes=1)

    monkeypatch.setattr(search_module, "_search_at_depth", fake_search)

    result = search_module.search_root(
        Position(),
        max_depth=3,
        evaluator=MaterialEval(),
        stop_flag=threading.Event(),
        soft_budget=None,
    )

    assert result.depth == 3
    assert searched_depths == [1, 2, 3]


def test_clocked_uci_go_returns_one_legal_bestmove_quickly(
    engine: EngineProcess,
) -> None:
    board = chess.Board()
    engine.send("position startpos")
    started = time.perf_counter()
    engine.send("go wtime 1000 btime 1000 winc 100 binc 100")
    lines: list[str] = []
    while time.perf_counter() - started < 2.0:
        line = engine.read_line(timeout=2.0 - (time.perf_counter() - started))
        lines.append(line)
        if line.startswith("bestmove "):
            break

    bestmoves = [line for line in lines if line.startswith("bestmove ")]
    assert len(bestmoves) == 1
    move = chess.Move.from_uci(bestmoves[0].split()[1])
    assert move in board.legal_moves
    assert time.perf_counter() - started < 2.0


@pytest.mark.slow
def test_clocked_game_never_flags(tmp_path) -> None:
    engine_argv = [sys.executable, "-m", "ance"]
    report = gauntlet.run_gauntlet(
        gauntlet.EngineSpec("ance-a", engine_argv),
        gauntlet.EngineSpec("ance-b", engine_argv),
        gauntlet.load_openings(gauntlet.DEFAULT_OPENINGS),
        n_games=1,
        tc_base_s=5.0,
        tc_inc_s=0.1,
        max_halfmoves=60,
        output_path=tmp_path / "clock-smoke.json",
        openings_path=gauntlet.DEFAULT_OPENINGS,
        command_line=(
            f"{sys.executable} -m ance.tools.gauntlet "
            "--games 1 --tc 5+0.1 --max-halfmoves 60 --runner arbiter"
        ),
    )

    assert report["status"] == "completed"
    assert report["completion"] == "complete"
    assert report["aggregate"]["time_forfeits"] == {"ance-a": 0, "ance-b": 0}
    assert len(report["games"]) == 1
    game = report["games"][0]
    assert game["reason"] != "time_forfeit"
    assert game["move_timings"]

    maxima = {"white": 0.0, "black": 0.0}
    overshoots = {"white": [], "black": []}
    for timing in game["move_timings"]:
        color = timing["color"]
        remaining_ms = round(timing["clock_before_s"] * 1_000)
        command = (
            GoCommand(wtime=remaining_ms, winc=100)
            if color == "white"
            else GoCommand(btime=remaining_ms, binc=100)
        )
        turn = chess.WHITE if color == "white" else chess.BLACK
        budget = compute_clock_budget(command, turn)
        assert budget is not None
        hard_ms = budget[1]
        elapsed = timing["elapsed_s"]
        maxima[color] = max(maxima[color], elapsed)
        overshoots[color].append(elapsed - hard_ms / 1_000)

    assert game["max_move_elapsed_s"] == pytest.approx(maxima)
    assert max(overshoots["white"], default=0.0) <= 0.3
    assert max(overshoots["black"], default=0.0) <= 0.3
