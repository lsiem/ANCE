"""Phase 3 pre-TT search baseline contracts (D-20/D-21)."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from types import SimpleNamespace

import chess
import pytest

from ance.board.position import Position
from ance.eval.handcrafted import HandcraftedEval
from ance.search.negamax import search_root
from ance.search.types import MAX_PLY
from ance.tools import phase3_baseline


DEFAULT_BASELINE_PATH = Path(
    ".planning/phases/03-search-acceleration-time-management/03-BASELINE.json"
)


def _never_stop() -> threading.Event:
    return threading.Event()


def load_baseline(path: Path = DEFAULT_BASELINE_PATH) -> dict:
    """Load the Plan 03-01 artifact used by later D-21 comparisons."""
    if not path.exists():
        raise FileNotFoundError(
            f"Plan 03-01 baseline artifact is missing at {path}; "
            "run the Plan 03-01 collector first"
        )
    return json.loads(path.read_text(encoding="utf-8"))


def _fake_result(depth: int, nodes: int = 123) -> SimpleNamespace:
    return SimpleNamespace(
        best_move=chess.Move.from_uci("e2e4"),
        depth=depth,
        nodes=nodes,
    )


def test_collector_searches_every_baseline_fen_twice_with_fresh_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[tuple[str, int, threading.Event, float | None]] = []

    def search_spy(
        pos: Position,
        max_depth: int,
        evaluator: HandcraftedEval,
        stop_flag: threading.Event,
        *,
        deadline: float | None = None,
    ) -> SimpleNamespace:
        assert isinstance(evaluator, HandcraftedEval)
        calls.append((pos.board.fen(), max_depth, stop_flag, deadline))
        return _fake_result(2 if deadline is not None else max_depth)

    monkeypatch.setattr(phase3_baseline, "search_root", search_spy)
    monkeypatch.setattr(phase3_baseline, "_git_commit", lambda: "abc123")

    phase3_baseline.collect_baseline(
        movetime_ms=2000,
        fixed_depth=4,
        budget_seconds=30,
    )

    assert len(calls) == 2 * len(phase3_baseline.BASELINE_FENS)
    for index, (case_id, fen) in enumerate(phase3_baseline.BASELINE_FENS):
        timed, fixed = calls[index * 2 : index * 2 + 2]
        assert timed[0] == fen
        assert timed[1] == MAX_PLY
        assert timed[3] is not None
        assert fixed[0] == fen
        assert fixed[1] == phase3_baseline.FIXED_DEPTH_OVERRIDES.get(case_id, 4)
        assert fixed[3] is None
        assert timed[2] is not fixed[2]


def test_report_schema_records_parameters_and_measurements(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_search(
        pos: Position,
        max_depth: int,
        evaluator: HandcraftedEval,
        stop_flag: threading.Event,
        *,
        deadline: float | None = None,
    ) -> SimpleNamespace:
        del pos, evaluator, stop_flag
        return _fake_result(3 if deadline is not None else max_depth, nodes=456)

    monkeypatch.setattr(phase3_baseline, "search_root", fake_search)
    monkeypatch.setattr(phase3_baseline, "_git_commit", lambda: "deadbeef")

    report = phase3_baseline.collect_baseline(
        movetime_ms=17,
        fixed_depth=2,
        budget_seconds=30,
    )

    assert report["schema_version"] == 1
    assert report["git_commit"] == "deadbeef"
    assert report["captured_utc"]
    assert report["parameters"]["movetime_ms"] == 17
    assert report["parameters"]["fixed_depth"] == 2
    assert report["parameters"]["fixed_depth_overrides"] == {"kiwipete": 2}
    assert report["parameters"]["evaluator"] == "handcrafted"
    assert report["parameters"]["python"]
    assert set(report["positions"]) == {
        case_id for case_id, _ in phase3_baseline.BASELINE_FENS
    }
    for case_id, record in report["positions"].items():
        assert set(record) == {"fen", "timed", "fixed_depth"}
        assert record["timed"]["completed_depth"] == 3
        assert record["timed"]["nodes"] == 456
        assert record["timed"]["elapsed_seconds"] >= 0
        assert record["fixed_depth"]["nodes"] == 456
        assert record["fixed_depth"]["best_move"] == "e2e4"
        assert record["fixed_depth"]["depth"] == (
            phase3_baseline.FIXED_DEPTH_OVERRIDES.get(case_id, 2)
        )
        assert record["fixed_depth"]["elapsed_seconds"] >= 0


def test_atomic_json_write_replaces_sibling_temp_and_cleans_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "baseline.json"
    replacements: list[tuple[Path, Path]] = []
    real_replace = phase3_baseline.os.replace

    def replace_spy(source: Path, destination: Path) -> None:
        replacements.append((Path(source), Path(destination)))
        real_replace(source, destination)

    monkeypatch.setattr(phase3_baseline.os, "replace", replace_spy)
    phase3_baseline.atomic_write_json(output, {"ok": True})

    assert json.loads(output.read_text(encoding="utf-8")) == {"ok": True}
    assert replacements == [(output.with_name(output.name + ".tmp"), output)]

    monkeypatch.setattr(
        phase3_baseline.os,
        "replace",
        lambda source, destination: (_ for _ in ()).throw(OSError("injected")),
    )
    with pytest.raises(OSError, match="injected"):
        phase3_baseline.atomic_write_json(output, {"ok": False})
    assert not output.with_name(output.name + ".tmp").exists()
    assert json.loads(output.read_text(encoding="utf-8")) == {"ok": True}


def test_load_baseline_parses_json_and_names_plan_when_missing(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text('{"schema_version": 1}\n', encoding="utf-8")
    assert load_baseline(path) == {"schema_version": 1}

    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError, match="Plan 03-01"):
        load_baseline(missing)


def test_queen_mate_depth_two_keeps_tactical_oracle() -> None:
    pos = Position(chess.Board("6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1"))
    result = search_root(
        pos,
        max_depth=2,
        evaluator=HandcraftedEval(),
        stop_flag=_never_stop(),
    )
    assert result.best_move == chess.Move.from_uci("h1a8")
