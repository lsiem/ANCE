"""Exact iterative-deepening node and NPS accounting regressions (UCI-11)."""

from __future__ import annotations

import threading

import chess
import pytest

from ance.board.position import Position
from ance.eval.material import MaterialEval
import ance.search.negamax as search_module
from ance.search.negamax import SearchAborted, search_root
from ance.search.types import SearchResult


def test_completed_iterations_report_exact_cumulative_nodes_and_nps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_move = chess.Move.from_uci("g1h3")
    clock = iter((100.0, 101.0, 103.0, 106.0))
    callback_data: list[tuple[int, int, int]] = []

    def fake_search_at_depth(
        pos,
        depth,
        evaluator,
        stop_flag,
        game_history_keys,
        deadline,
        prior_best,
        tt,
    ) -> SearchResult:
        assert tt is None
        if depth == 4:
            raise SearchAborted()
        return SearchResult(
            best_move=root_move,
            score=depth,
            depth=depth,
            pv=[root_move],
            nodes=10,
        )

    def on_info(result: SearchResult, nps: int) -> None:
        callback_data.append((result.depth, result.nodes, nps))

    monkeypatch.setattr(search_module, "_search_at_depth", fake_search_at_depth)
    monkeypatch.setattr(search_module.time, "monotonic", lambda: next(clock))

    result = search_root(
        Position(),
        max_depth=4,
        evaluator=MaterialEval(),
        stop_flag=threading.Event(),
        info_callback=on_info,
    )

    assert [nodes for _, nodes, _ in callback_data] == [10, 20, 30]
    assert [nps for _, _, nps in callback_data] == [10, 6, 5]
    assert [depth for depth, _, _ in callback_data] == [1, 2, 3]
    assert result.depth == 3
    assert result.nodes == 30
