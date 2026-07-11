"""Deterministic in-tree deadline polling regressions (SRCH-03, SRCH-04)."""

from __future__ import annotations

import threading

import pytest

from ance.board.position import Position
from ance.eval.base import MATE
from ance.eval.material import MaterialEval
import ance.search.negamax as search_module
from ance.search.negamax import SearchAborted, negamax, quiescence_search, search_root
from ance.search.types import SearchContext


def _expired_context() -> SearchContext:
    return SearchContext(
        stop_flag=threading.Event(),
        counter=[search_module.NODE_POLL_INTERVAL - 1],
        evaluator=MaterialEval(),
        deadline=0.0,
    )


def test_node_poll_interval_stays_inside_clock_safety_margin() -> None:
    assert search_module.NODE_POLL_INTERVAL == 512


def test_negamax_aborts_at_poll_boundary_for_expired_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_module.time, "monotonic", lambda: 1.0)

    with pytest.raises(SearchAborted):
        negamax(
            Position(),
            depth=1,
            alpha=-MATE - 1,
            beta=MATE + 1,
            ctx=_expired_context(),
        )


def test_quiescence_aborts_at_poll_boundary_for_expired_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(search_module.time, "monotonic", lambda: 1.0)

    with pytest.raises(SearchAborted):
        quiescence_search(
            Position(),
            alpha=-MATE - 1,
            beta=MATE + 1,
            ctx=_expired_context(),
        )


def test_deadline_during_iteration_retains_last_completed_depth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = [0.0]
    deadline = 1.0
    completed_depths: list[int] = []

    class ExpiringEvaluator:
        armed = False

        def evaluate(self, pos: Position) -> int:
            if self.armed:
                now[0] = deadline
            return 0

    evaluator = ExpiringEvaluator()

    def on_info(result, nps: int) -> None:
        completed_depths.append(result.depth)
        evaluator.armed = True

    monkeypatch.setattr(search_module, "NODE_POLL_INTERVAL", 1)
    monkeypatch.setattr(search_module.time, "monotonic", lambda: now[0])

    result = search_root(
        Position(),
        max_depth=2,
        evaluator=evaluator,
        stop_flag=threading.Event(),
        deadline=deadline,
        info_callback=on_info,
    )

    assert result.depth == 1
    assert completed_depths == [1]
