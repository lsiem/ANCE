"""`go`/`stop`/`quit` wired through real fixed-depth negamax search (Task 3,
01-03-PLAN.md) -- the real substrate replacing the Walking Skeleton's
"first legal move" placeholder.

Every test drives ANCE as a real piped subprocess (`tests.conftest.EngineProcess`)
-- exactly how a UCI GUI or gauntlet driver would exercise it -- except one:
`test_stale_generation_worker_never_emits_bestmove_after_being_superseded`
is a unit-level test against `ance.uci.loop`'s internals, because the
`search_generation` invariant it proves is only observable by directly
controlling thread interleaving that a subprocess test cannot reliably
force in real time.
"""

from __future__ import annotations

import os
import queue
import random
import re
import subprocess
import sys
import threading
import time
from collections.abc import Iterator

import chess
import pytest

from ance.board.position import Position
from ance.eval.material import MaterialEval
from tests.conftest import EngineProcess, send_lines

BESTMOVE_RE = re.compile(r"^bestmove ([a-h][1-8][a-h][1-8][qrbn]?|\(none\))$")

# Fool's Mate FEN (from Plan 01-02's test_has_no_legal_moves_true_for_checkmate) --
# the zero-legal-move position D-12's `bestmove (none)` handling is proven against.
FOOLS_MATE_FEN = "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"


@pytest.fixture
def seeded_engine() -> Iterator[EngineProcess]:
    """Same subprocess wiring as `tests.conftest.engine`, but with
    `ANCE_SEED=42` forced into the child's environment -- needed only by
    `test_ucinewgame_produces_deterministic_bestmove` (D-10), which asserts
    the engine picks the same root move on repeated startpos depth-1 searches.
    """
    env = {k: v for k, v in os.environ.items() if k != "ANCE_DEBUG"}
    env["ANCE_SEED"] = "42"
    process = subprocess.Popen(
        [sys.executable, "-m", "ance"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
        env=env,
    )
    engine_process = EngineProcess(process)
    try:
        yield engine_process
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2.0)


def _assert_bestmove(line: str) -> str:
    assert BESTMOVE_RE.match(line), f"unexpected line: {line!r}"
    return line


def _read_bestmove(engine: EngineProcess, timeout: float = 5.0) -> str:
    """Read stdout until a bestmove line, skipping intervening info lines."""
    deadline = time.perf_counter() + timeout
    while True:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            pytest.fail(f"timed out waiting for bestmove within {timeout}s")
        line = engine.read_line(timeout=remaining)
        if line.startswith("bestmove "):
            return _assert_bestmove(line)
        if line.startswith("info "):
            continue
        pytest.fail(f"unexpected line while waiting for bestmove: {line!r}")


def _read_readyok_skipping_info(engine: EngineProcess, timeout: float = 1.0) -> str:
    deadline = time.perf_counter() + timeout
    while True:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            pytest.fail(f"timed out waiting for readyok within {timeout}s")
        line = engine.read_line(timeout=remaining)
        if line == "readyok":
            return line
        if line.startswith("info "):
            continue
        pytest.fail(f"unexpected line while waiting for readyok: {line!r}")


def _assert_no_further_output(engine: EngineProcess, timeout: float) -> None:
    """Proves *silence* on stdout for `timeout` seconds -- used to prove a
    superseded/stale search never emits a second, stray `bestmove` line.
    """
    try:
        line = engine._lines.get(timeout=timeout)
    except queue.Empty:
        return
    pytest.fail(f"unexpected extra output: {line!r}")


def test_go_depth_honored(engine):
    engine.send("go depth 2")
    _read_bestmove(engine, timeout=5.0)


def test_bare_go_uses_movetime_budget_and_completes_within_three_seconds(engine):
    start = time.perf_counter()
    engine.send("go")
    lines = []
    while True:
        line = engine.read_line(timeout=4.0)
        lines.append(line)
        if line.startswith("bestmove "):
            break
    elapsed = time.perf_counter() - start
    _assert_bestmove(lines[-1])
    assert elapsed < 3.5, f"bare go took {elapsed:.3f}s, expected under 3.5s"
    info_lines = [line for line in lines if line.startswith("info depth ")]
    assert len(info_lines) >= 1


def test_bare_go_completes_within_three_seconds_with_handcrafted_eval(engine):
    """Bare `go` uses the ~2s movetime budget (D-09) with iterative deepening."""
    start = time.perf_counter()
    engine.send("go")
    _read_bestmove(engine, timeout=4.0)
    elapsed = time.perf_counter() - start
    assert elapsed < 3.5, f"bare go took {elapsed:.3f}s, expected under 3.5s"


def test_go_movetime_aborts_promptly(engine):
    engine.send("go movetime 200")
    _read_bestmove(engine, timeout=1.0)


def test_go_clock_params_parsed_without_crash(engine):
    engine.send("go wtime 300000 btime 300000 winc 0 binc 0")
    _read_bestmove(engine, timeout=4.0)
    engine.send("isready")
    _read_readyok_skipping_info(engine, timeout=1.0)


def test_stop_is_prompt_during_go_infinite(engine):
    engine.send("go infinite")
    time.sleep(0.1)
    stop_sent_at = time.perf_counter()
    engine.send("stop")
    _read_bestmove(engine, timeout=2.0)
    elapsed = time.perf_counter() - stop_sent_at
    assert elapsed < 1.0, f"bestmove took {elapsed:.3f}s after stop, expected under 1.0s"


def test_stop_signals_current_search_and_emits_exactly_one_legal_bestmove(
    monkeypatch,
):
    import ance.uci.loop as loop_module
    from ance.search.types import SearchResult
    from ance.uci.parser import GoCommand

    entered = threading.Event()
    captured_events: list[threading.Event] = []
    sent: list[str | None] = []

    def search_until_stopped(pos, max_depth, evaluator, stop_flag, **kwargs):
        captured_events.append(stop_flag)
        entered.set()
        assert stop_flag.wait(timeout=1.0)
        move = chess.Move.from_uci("e2e4")
        return SearchResult(best_move=move, score=0, depth=1, pv=[move], nodes=1)

    monkeypatch.setattr(loop_module, "search_root", search_until_stopped)
    monkeypatch.setattr(loop_module, "send_bestmove", lambda move: sent.append(move))
    monkeypatch.setattr(loop_module, "search_generation", 0)
    if hasattr(loop_module, "active_job"):
        monkeypatch.setattr(loop_module, "active_job", None)
    if hasattr(loop_module, "worker"):
        monkeypatch.setattr(loop_module, "worker", None)
    if hasattr(loop_module, "stop_flag"):
        loop_module.stop_flag.clear()

    loop_module.handle_go(GoCommand(infinite=True), Position())
    assert entered.wait(timeout=0.5)
    loop_module.handle_stop()

    active_thread = (
        loop_module.active_job.thread
        if hasattr(loop_module, "active_job")
        else loop_module.worker
    )
    assert active_thread is not None
    active_thread.join(timeout=0.5)
    assert not active_thread.is_alive()
    assert captured_events[0].is_set()
    assert sent == ["e2e4"]


def test_quit_never_deadlocks_during_go_infinite(engine):
    engine.send("go infinite")
    time.sleep(0.1)
    engine.send("quit")
    exit_code = engine.wait(timeout=3.0)
    assert exit_code == 0


def test_zero_legal_move_position_returns_bestmove_none(engine):
    send_lines(engine, [f"position fen {FOOLS_MATE_FEN}", "go"])
    line = _read_bestmove(engine, timeout=2.0)
    assert line == "bestmove (none)"


def test_ucinewgame_produces_deterministic_bestmove(seeded_engine):
    engine = seeded_engine
    engine.send("go depth 1")
    first = _read_bestmove(engine, timeout=2.0)

    engine.send("ucinewgame")
    engine.send("go depth 1")
    second = _read_bestmove(engine, timeout=2.0)

    # D-10: root tie-break is deterministic (first-best-found), not RNG-driven.
    # After ucinewgame resets to startpos, the same depth-1 search picks the
    # same first legal move every time.
    assert first == second


def test_overlapping_go_yields_two_bestmoves_in_order(engine):
    """cross-AI review's HIGH-consensus preemption finding (all three
    reviewers' round-1 #1 concern), proven against the round-2-hardened
    design: overlapping `go`s must never race two workers writing
    concurrently to stdout. The round-2 `search_generation` gate (closing
    the threat model's T-01-13 "stray stale bestmove" gap) makes the
    *first* go's superseded result unconditionally dropped rather than
    raced onto stdout -- so exactly ONE bestmove (the second go's) is the
    correct, hardened, observable behavior, not two. (The plan's own
    success_criteria/threat_model consistently specify "at most one
    bestmove... per go" and "never emits a duplicate/stale bestmove" --
    this test asserts that hardened contract.)
    """
    engine.send("go depth 5")
    engine.send("go depth 1")
    _read_bestmove(engine, timeout=3.0)
    _assert_no_further_output(engine, timeout=0.4)
    engine.send("isready")
    _read_readyok_skipping_info(engine, timeout=1.0)


def test_position_during_active_search_yields_exactly_one_bestmove_and_stays_responsive(
    engine,
):
    engine.send("go movetime 2000")
    time.sleep(0.1)
    engine.send("position startpos moves e2e4")
    _read_bestmove(engine, timeout=2.5)
    _assert_no_further_output(engine, timeout=0.4)
    engine.send("isready")
    _read_readyok_skipping_info(engine, timeout=1.0)


def test_isready_returns_promptly_during_active_search(engine):
    engine.send("go infinite")
    engine.send("isready")
    _read_readyok_skipping_info(engine, timeout=1.0)


def test_ucinewgame_during_active_search(engine):
    engine.send("go movetime 2000")
    time.sleep(0.1)
    engine.send("ucinewgame")
    _read_bestmove(engine, timeout=2.5)
    _assert_no_further_output(engine, timeout=0.4)

    send_lines(engine, ["position startpos", "go depth 1"])
    _read_bestmove(engine, timeout=2.0)

    engine.send("isready")
    _read_readyok_skipping_info(engine, timeout=1.0)


def test_stale_generation_worker_never_emits_bestmove_after_being_superseded(
    monkeypatch,
):
    import ance.uci.loop as loop_module

    sent: list[str | None] = []
    monkeypatch.setattr(loop_module, "send_bestmove", lambda move: sent.append(move))

    release = threading.Event()
    entered = threading.Event()

    from ance.search.types import SearchResult

    def blocking_search_root(pos, max_depth, evaluator, stop_flag, **kwargs):
        # Simulates a worker still finishing (blocked) when a new `go` has
        # already arrived and moved search_generation on.
        entered.set()
        assert release.wait(timeout=2.0)
        return SearchResult(
            best_move=chess.Move.from_uci("e2e4"),
            score=0,
            depth=max_depth,
        )

    monkeypatch.setattr(loop_module, "search_root", blocking_search_root)

    pos = Position()
    evaluator = MaterialEval()

    # --- Superseded case: search_generation is bumped from the test body
    # while the runner is "in flight" inside blocking_search_root -- this
    # simulates _stop_active_worker()'s join(timeout) having elapsed while
    # the worker was still alive (round-2 HIGH finding).
    monkeypatch.setattr(loop_module, "search_generation", 1)
    runner = threading.Thread(
        target=loop_module._run_search,
        args=(
            pos,
            1,
            evaluator,
            threading.Event(),
            None,
            1,
            None,
            loop_module.transposition_table,
        ),
    )
    runner.start()
    assert entered.wait(timeout=0.5)
    monkeypatch.setattr(loop_module, "search_generation", 2)
    release.set()
    runner.join(timeout=2.0)
    assert not runner.is_alive()
    assert sent == [], "superseded worker must never emit a bestmove"

    # --- Control case: generation unchanged -> the stub IS called,
    # proving the gate isn't just permanently closed.
    sent.clear()
    release.clear()
    entered.clear()
    monkeypatch.setattr(loop_module, "search_generation", 5)
    runner2 = threading.Thread(
        target=loop_module._run_search,
        args=(
            pos,
            1,
            evaluator,
            threading.Event(),
            None,
            5,
            None,
            loop_module.transposition_table,
        ),
    )
    runner2.start()
    assert entered.wait(timeout=0.5)
    release.set()
    runner2.join(timeout=2.0)
    assert not runner2.is_alive()
    assert sent == ["e2e4"], "non-superseded worker must emit its bestmove"


def test_go_movetime_timer_cancelled_on_preemption_does_not_stop_next_search(engine):
    engine.send("go movetime 2000")
    engine.send("go depth 1")
    start = time.perf_counter()
    _read_bestmove(engine, timeout=2.0)
    elapsed = time.perf_counter() - start
    assert elapsed < 1.0, f"second bestmove took {elapsed:.3f}s, expected well under 1.0s"
    # No further, unexpected bestmove line should follow later (e.g. around
    # the ~2s mark where the first search's stale timer would otherwise
    # have fired had _stop_active_worker() not cancelled it).
    _assert_no_further_output(engine, timeout=0.4)


def test_go_movetime_short_timer_cancelled_before_next_search_completes(engine):
    engine.send("go movetime 100")
    engine.send("go depth 3")
    start = time.perf_counter()
    _read_bestmove(engine, timeout=2.0)
    elapsed = time.perf_counter() - start
    # If the first search's 100ms timer had bled its stop_flag.set() into
    # this second search, it would have aborted suspiciously close to the
    # 100ms mark instead of running depth 3 to its natural (noticeably
    # longer -- see test_bare_go_uses_default_depth_and_completes_under_a_second
    # and test_go_movetime_aborts_promptly, both of which establish depth 3
    # takes meaningfully more than 100-200ms) completion.
    assert elapsed > 0.15, f"second search finished suspiciously fast: {elapsed:.3f}s"
