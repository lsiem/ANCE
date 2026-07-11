"""Deterministic regressions for per-generation UCI worker ownership."""

from __future__ import annotations

import threading

import chess
import pytest

import ance.uci.loop as loop_module
from ance.board.position import Position
from ance.search.types import SearchResult
from ance.uci.parser import GoCommand


@pytest.fixture(autouse=True)
def reset_loop_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(loop_module, "search_generation", 0)
    if hasattr(loop_module, "active_job"):
        monkeypatch.setattr(loop_module, "active_job", None)
    if hasattr(loop_module, "worker"):
        monkeypatch.setattr(loop_module, "worker", None)
    if hasattr(loop_module, "stop_flag"):
        loop_module.stop_flag.clear()
    if hasattr(loop_module, "movetime_timer"):
        monkeypatch.setattr(loop_module, "movetime_timer", None)


def _result(move_uci: str, depth: int) -> SearchResult:
    move = chess.Move.from_uci(move_uci)
    return SearchResult(best_move=move, score=depth, depth=depth, pv=[move], nodes=depth)


def test_timed_out_worker_keeps_unique_cancel_token_and_cannot_emit_after_replacement(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    started = [threading.Event(), threading.Event()]
    release = [threading.Event(), threading.Event()]
    finished = [threading.Event(), threading.Event()]
    supplied_events: list[threading.Event] = []
    threads: list[threading.Thread] = []
    records: list[tuple[str, str]] = []
    moves = ["e2e4", "d2d4"]

    def controlled_search(pos, max_depth, evaluator, stop_flag, *, info_callback, **kwargs):
        index = len(supplied_events)
        supplied_events.append(stop_flag)
        threads.append(threading.current_thread())
        started[index].set()
        assert release[index].wait(timeout=1.0)
        result = _result(moves[index], index + 1)
        info_callback(result, 100 + index)
        finished[index].set()
        return result

    monkeypatch.setattr(loop_module, "search_root", controlled_search)
    monkeypatch.setattr(
        loop_module,
        "send_info_depth",
        lambda depth, score, nodes, nps, pv: records.append(("info", pv[0])),
    )
    monkeypatch.setattr(
        loop_module,
        "send_bestmove",
        lambda move: records.append(("bestmove", move or "(none)")),
    )

    original_stop = loop_module._stop_active_worker

    def force_short_join(*args, **kwargs):
        kwargs["timeout"] = 0.01
        return original_stop(*args, **kwargs)

    monkeypatch.setattr(loop_module, "_stop_active_worker", force_short_join)

    position = Position()
    loop_module.handle_go(GoCommand(depth=1), position)
    assert started[0].wait(timeout=0.5)
    loop_module.handle_go(GoCommand(depth=1), position)
    assert started[1].wait(timeout=0.5)

    old_event, new_event = supplied_events
    old_was_set = old_event.is_set()
    new_began_unset = not new_event.is_set()

    release[0].set()
    assert finished[0].wait(timeout=0.5)
    release[1].set()
    assert finished[1].wait(timeout=0.5)
    for thread in threads:
        thread.join(timeout=0.5)
        assert not thread.is_alive()

    assert old_event is not new_event
    assert old_was_set is True
    assert new_began_unset is True
    assert records == [("info", "d2d4"), ("bestmove", "d2d4")]


def test_info_gate_rechecks_generation_after_waiting_for_lock(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[tuple[int, list[str]]] = []
    monkeypatch.setattr(
        loop_module,
        "send_info_depth",
        lambda depth, score, nodes, nps, pv: records.append((depth, pv)),
    )
    monkeypatch.setattr(loop_module, "search_generation", 1)

    result = _result("e2e4", 1)
    with loop_module.generation_lock:
        emitter = threading.Thread(
            target=loop_module._emit_info,
            args=(result, 100, 1),
        )
        emitter.start()
        loop_module.search_generation = 2

    emitter.join(timeout=0.5)
    assert not emitter.is_alive()
    assert records == []


FOOLS_MATE_FEN = (
    "rnb1kbnr/pppp1ppp/8/4p3/6Pq/5P2/PPPPP2P/RNBQKBNR w KQkq - 1 3"
)


def test_worker_exception_emits_generation_gated_fallback_bestmove(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[tuple[str, str]] = []
    logs: list[str] = []

    def raising_search(*args, **kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(loop_module, "search_root", raising_search)
    monkeypatch.setattr(
        loop_module,
        "send_bestmove",
        lambda move: records.append(("bestmove", move or "(none)")),
    )
    monkeypatch.setattr(loop_module.debug, "log", lambda msg: logs.append(msg))

    position = Position()
    expected_move = position.legal_moves()[0].uci()

    loop_module.handle_go(GoCommand(depth=1), position)
    thread = loop_module.active_job.thread
    assert thread is not None
    thread.join(timeout=1.0)
    assert not thread.is_alive()

    assert len(records) == 1
    assert records[0][0] == "bestmove"
    assert records[0][1] == expected_move
    assert any("ERROR: search worker failed" in entry for entry in logs)


def test_worker_exception_fallback_none_on_mate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    records: list[str] = []

    def raising_search(*args, **kwargs):
        raise RuntimeError("probe")

    monkeypatch.setattr(loop_module, "search_root", raising_search)
    monkeypatch.setattr(
        loop_module,
        "send_bestmove",
        lambda move: records.append(move or "(none)"),
    )
    monkeypatch.setattr(loop_module.debug, "log", lambda _msg: None)

    position = Position()
    assert position.try_set_fen(FOOLS_MATE_FEN) is True

    loop_module.handle_go(GoCommand(depth=1), position)
    thread = loop_module.active_job.thread
    assert thread is not None
    thread.join(timeout=1.0)
    assert not thread.is_alive()

    assert records == ["(none)"]


def test_stale_worker_exception_emits_no_fallback_bestmove(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = threading.Event()
    release = threading.Event()
    records: list[str] = []

    def blocking_raise(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=1.0)
        raise RuntimeError("probe")

    monkeypatch.setattr(loop_module, "search_root", blocking_raise)
    monkeypatch.setattr(
        loop_module,
        "send_bestmove",
        lambda move: records.append(move or "(none)"),
    )
    monkeypatch.setattr(loop_module.debug, "log", lambda _msg: None)

    position = Position()
    stop_event = threading.Event()
    my_generation = 1
    monkeypatch.setattr(loop_module, "search_generation", my_generation)

    thread = threading.Thread(
        target=loop_module._run_search,
        args=(
            position.copy(),
            1,
            loop_module.evaluator,
            stop_event,
            None,
            my_generation,
            None,
            loop_module.transposition_table,
            loop_module.killer_moves,
            loop_module.history_table,
        ),
        daemon=True,
    )
    thread.start()
    assert entered.wait(timeout=0.5)

    loop_module.search_generation = 2
    release.set()
    thread.join(timeout=1.0)
    assert not thread.is_alive()
    assert records == []
