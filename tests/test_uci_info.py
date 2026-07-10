"""UCI info line contract tests (UCI-11, D-11)."""

from __future__ import annotations

import re
import time

import pytest

from ance.eval.base import MATE
from ance.uci.protocol import send_info_depth
from tests.conftest import EngineProcess, send_lines
from tests.test_go_bestmove import BESTMOVE_RE, _assert_bestmove, _read_bestmove

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
    _read_bestmove(engine, timeout=2.0)


def _final_info_mate_score(lines: list[str]) -> int:
    info_lines = [line for line in lines if line.startswith("info depth ")]
    assert info_lines, f"expected info lines, got {lines!r}"
    match = INFO_DEPTH_RE.match(info_lines[-1])
    assert match is not None, info_lines[-1]
    assert match.group(4) is not None, info_lines[-1]
    return int(match.group(4))


def test_send_info_depth_mate_in_one_ply_emits_full_move(capsys: pytest.CaptureFixture[str]) -> None:
    send_info_depth(depth=1, score=MATE - 1, nodes=1, nps=1, pv_uci=["a1a8"])
    assert "score mate 1" in capsys.readouterr().out


def test_send_info_depth_mate_in_three_plies_emits_two_full_moves(capsys: pytest.CaptureFixture[str]) -> None:
    send_info_depth(depth=4, score=MATE - 3, nodes=1, nps=1, pv_uci=["g6g7"])
    assert "score mate 2" in capsys.readouterr().out


def test_send_info_depth_being_mated_in_two_plies_emits_negative_one(capsys: pytest.CaptureFixture[str]) -> None:
    send_info_depth(depth=2, score=-(MATE - 2), nodes=1, nps=1, pv_uci=["e1e2"])
    assert "score mate -1" in capsys.readouterr().out


def test_send_info_depth_being_mated_in_four_plies_emits_negative_two(capsys: pytest.CaptureFixture[str]) -> None:
    send_info_depth(depth=4, score=-(MATE - 4), nodes=1, nps=1, pv_uci=["e1e2"])
    assert "score mate -2" in capsys.readouterr().out


def test_send_info_depth_plain_cp_unchanged(capsys: pytest.CaptureFixture[str]) -> None:
    send_info_depth(depth=3, score=137, nodes=1, nps=1, pv_uci=["e2e4"])
    assert "score cp 137" in capsys.readouterr().out


def test_mate_in_one_position_reports_score_mate_one_on_wire(engine: EngineProcess) -> None:
    fen = "6k1/5ppp/8/8/8/8/8/R3K3 w - - 0 1"
    send_lines(engine, [f"position fen {fen}", "isready", "go depth 2"])
    assert engine.read_line(timeout=1.0) == "readyok"
    lines = _read_until_bestmove(engine, timeout=10.0)
    assert _final_info_mate_score(lines) == 1
    _assert_bestmove(lines[-1])
    assert lines[-1].split()[1] == "a1a8"


def test_queen_mate_position_reports_score_mate_one_on_wire(engine: EngineProcess) -> None:
    """Queen+h1 delivers immediate mate — wire reports mate 1 (one full move).

    Multi-ply plies-to-full-moves conversion (e.g. MATE-3 -> score mate 2) is
    covered by the capsys unit tests above; this FEN is mate-in-1 at depth 4.
    """
    fen = "6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1"
    send_lines(engine, [f"position fen {fen}", "isready", "go depth 4"])
    assert engine.read_line(timeout=1.0) == "readyok"
    lines = _read_until_bestmove(engine, timeout=15.0)
    assert _final_info_mate_score(lines) == 1
    _assert_bestmove(lines[-1])
    assert lines[-1].split()[1] == "h1a8"
