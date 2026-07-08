"""UCI info line contract tests (UCI-11, D-11)."""

from __future__ import annotations

import re
import time

import pytest

from tests.conftest import EngineProcess, send_lines
from tests.test_go_bestmove import BESTMOVE_RE, _assert_bestmove

INFO_DEPTH_RE = re.compile(
    r"^info depth (\d+) score (cp (-?\d+)|mate (-?\d+)) nodes (\d+) nps (\d+) pv (.*)$"
)


def _read_until_bestmove(engine: EngineProcess, timeout: float = 5.0) -> list[str]:
    lines: list[str] = []
    deadline = time.perf_counter() + timeout
    while time.perf_counter() < deadline:
        remaining = deadline - time.perf_counter()
        if remaining <= 0:
            pytest.fail("timed out waiting for bestmove")
        try:
            line = engine.read_line(timeout=remaining)
        except Exception:
            pytest.fail("timed out waiting for bestmove")
        lines.append(line)
        if line.startswith("bestmove "):
            break
    else:
        pytest.fail("timed out waiting for bestmove")
    return lines


def test_go_depth_emits_info_before_bestmove(engine: EngineProcess) -> None:
    engine.send("go depth 2")
    lines = _read_until_bestmove(engine, timeout=5.0)
    info_lines = [line for line in lines if line.startswith("info depth ")]
    assert info_lines, f"expected info lines, got {lines!r}"
    assert any(INFO_DEPTH_RE.match(line) and int(INFO_DEPTH_RE.match(line).group(1)) == 2 for line in info_lines)


def test_info_pv_matches_bestmove(engine: EngineProcess) -> None:
    engine.send("go depth 2")
    lines = _read_until_bestmove(engine, timeout=5.0)
    info_lines = [line for line in lines if line.startswith("info depth ")]
    bestmove_line = lines[-1]
    _assert_bestmove(bestmove_line)
    bestmove_move = bestmove_line.split()[1]
    final_info = info_lines[-1]
    match = INFO_DEPTH_RE.match(final_info)
    assert match is not None
    pv_tokens = match.group(7).split()
    assert pv_tokens
    assert pv_tokens[0] == bestmove_move


def test_bare_go_emits_multiple_info_depths_within_budget(engine: EngineProcess) -> None:
    start = time.perf_counter()
    engine.send("go")
    lines = _read_until_bestmove(engine, timeout=4.0)
    elapsed = time.perf_counter() - start
    info_depths = [
        int(INFO_DEPTH_RE.match(line).group(1))
        for line in lines
        if line.startswith("info depth ") and INFO_DEPTH_RE.match(line)
    ]
    assert elapsed < 3.5, f"bare go took {elapsed:.2f}s"
    assert len(info_depths) >= 2
    assert info_depths == sorted(info_depths)
    assert info_depths[-1] >= 2


def test_go_infinite_emits_info_until_stop(engine: EngineProcess) -> None:
    engine.send("go infinite")
    info_seen = False
    deadline = time.perf_counter() + 3.0
    while time.perf_counter() < deadline:
        line = engine.read_line(timeout=0.5)
        if line.startswith("info depth "):
            info_seen = True
            break
    assert info_seen, "go infinite must emit info lines while deepening"
    engine.send("stop")
    line = engine.read_line(timeout=2.0)
    _assert_bestmove(line)


def test_go_infinite_responds_to_stop_without_hang(engine: EngineProcess) -> None:
    engine.send("go infinite")
    time.sleep(0.15)
    stop_sent = time.perf_counter()
    engine.send("stop")
    line = engine.read_line(timeout=2.0)
    elapsed = time.perf_counter() - stop_sent
    _assert_bestmove(line)
    assert elapsed < 2.0
