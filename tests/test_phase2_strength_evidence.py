"""Fast contracts for the bounded, resumable Phase 2 strength evidence CLI."""

from __future__ import annotations

import json
import signal
import threading
from pathlib import Path
from typing import Any, Callable

import pytest

from ance.tools import phase2_strength_evidence as evidence


def _argv(output: Path, *extra: str) -> list[str]:
    return [
        "--output",
        str(output),
        "--seed",
        "20260710",
        "--depth-games",
        "30",
        "--random-games",
        "30",
        "--max-halfmoves",
        "80",
        "--budget-seconds",
        "7200",
        *extra,
    ]


def _game_record(index: int, seed: int, outcome: str) -> dict[str, Any]:
    return {"index": index, "seed": seed, "outcome": outcome}


def _install_success_harnesses(
    monkeypatch: pytest.MonkeyPatch,
    calls: dict[str, list[dict[str, Any]]],
    *,
    depth_outcome: str = "draw",
    random_result: str = "1-0",
) -> None:
    def depth_runner(**kwargs: Any) -> dict[str, Any]:
        calls["depth"].append(kwargs)
        wins = sum(g["outcome"] == "win" for g in kwargs["game_records"])
        draws = sum(g["outcome"] == "draw" for g in kwargs["game_records"])
        losses = sum(g["outcome"] == "loss" for g in kwargs["game_records"])
        for index in range(kwargs["start_game"], kwargs["n_games"]):
            record = _game_record(index, kwargs["seed"] + index, depth_outcome)
            if depth_outcome == "win":
                wins += 1
            elif depth_outcome == "draw":
                draws += 1
            else:
                losses += 1
            aggregate = {
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "n_games": index + 1,
                "score_rate": (wins + 0.5 * draws) / (index + 1),
            }
            kwargs["on_game_complete"](index, record, aggregate)
        return aggregate

    def random_runner(**kwargs: Any) -> dict[str, Any]:
        calls["random"].append(kwargs)
        records = kwargs["game_records"]
        wins = sum(g["outcome"] == "win" for g in records)
        draws = sum(g["outcome"] == "draw" for g in records)
        losses = sum(g["outcome"] == "loss" for g in records)
        non_win_games: list[dict[str, Any]] = []
        for index in range(kwargs["start_game"], kwargs["n_games"]):
            ance_white = index % 2 == 0
            won = (random_result == "1-0") == ance_white
            outcome = "win" if won else "loss"
            record = {
                "index": index,
                "seed": kwargs["seed"] + index,
                "outcome": outcome,
                "result": random_result,
                "terminal_fen": f"fen-{index}",
            }
            if won:
                wins += 1
            else:
                losses += 1
                non_win_games.append(record)
            aggregate = {
                "wins": wins,
                "draws": draws,
                "losses": losses,
                "non_win_games": non_win_games,
                "n_games": index + 1,
            }
            kwargs["on_game_complete"](index, record, aggregate)
        return aggregate

    monkeypatch.setattr(evidence, "run_depth_match", depth_runner)
    monkeypatch.setattr(evidence, "run_gauntlet", random_runner)


def test_cli_forwards_fixed_parameters_and_one_shared_budget(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evidence.json"
    calls: dict[str, list[dict[str, Any]]] = {"depth": [], "random": []}
    _install_success_harnesses(monkeypatch, calls, random_result="1-0")

    assert evidence.main(_argv(output)) == 1  # alternating fixed result creates losses

    depth = calls["depth"][0]
    random = calls["random"][0]
    assert (depth["n_games"], random["n_games"]) == (30, 30)
    assert (depth["shallow_depth"], depth["deep_depth"], random["ance_depth"]) == (2, 3, 4)
    assert depth["seed"] == random["seed"] == 20260710
    assert depth["max_halfmoves"] == random["max_halfmoves"] == 80
    assert depth["deadline"] == random["deadline"]
    assert depth["stop_event"] is random["stop_event"]
    assert isinstance(depth["stop_event"], threading.Event)
    assert depth["deadline"] > 0


@pytest.mark.parametrize(("flag", "value"), [("--depth-games", "29"), ("--random-games", "29")])
def test_minimum_samples_are_rejected_before_play(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flag: str,
    value: str,
) -> None:
    output = tmp_path / "evidence.json"
    monkeypatch.setattr(
        evidence, "run_depth_match", lambda **kwargs: pytest.fail("depth harness called")
    )
    monkeypatch.setattr(
        evidence, "run_gauntlet", lambda **kwargs: pytest.fail("random harness called")
    )

    assert evidence.main(_argv(output, flag, value)) == 1
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["completion"] == "incomplete"
    assert "at least 30" in " ".join(report["reasons"])


@pytest.mark.parametrize(
    ("depth_outcome", "random_result", "expected"),
    [
        ("draw", "alternating-win", 0),
        ("loss", "alternating-win", 1),
        ("draw", "1-0", 1),
    ],
)
def test_threshold_classification_and_report_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    depth_outcome: str,
    random_result: str,
    expected: int,
) -> None:
    output = tmp_path / "evidence.json"
    calls: dict[str, list[dict[str, Any]]] = {"depth": [], "random": []}

    def random_runner(**kwargs: Any) -> dict[str, Any]:
        calls["random"].append(kwargs)
        wins = draws = losses = 0
        for index in range(kwargs["start_game"], kwargs["n_games"]):
            ance_white = index % 2 == 0
            raw = ("1-0" if ance_white else "0-1") if random_result == "alternating-win" else random_result
            won = (raw == "1-0") == ance_white
            outcome = "win" if won else "loss"
            wins += won
            losses += not won
            record = {
                "index": index,
                "seed": kwargs["seed"] + index,
                "outcome": outcome,
                "result": raw,
                "terminal_fen": f"fen-{index}",
            }
            kwargs["on_game_complete"](
                index,
                record,
                {
                    "wins": wins,
                    "draws": draws,
                    "losses": losses,
                    "non_win_games": [] if won else [record],
                    "n_games": index + 1,
                },
            )
        return {"wins": wins, "draws": draws, "losses": losses, "non_win_games": [], "n_games": 30}

    _install_success_harnesses(monkeypatch, calls, depth_outcome=depth_outcome)
    monkeypatch.setattr(evidence, "run_gauntlet", random_runner)

    assert evidence.main(_argv(output)) == expected
    report = json.loads(output.read_text())
    assert report["parameters"] == {
        "seed": 20260710,
        "depth_games": 30,
        "random_games": 30,
        "max_halfmoves": 80,
        "budget_seconds": 7200.0,
        "shallow_depth": 2,
        "deep_depth": 3,
        "random_depth": 4,
    }
    assert len(report["suites"]["depth_match"]["games"]) == 30
    assert len(report["suites"]["random_gauntlet"]["games"]) == 30
    assert report["decision_replacement"]["original"]
    assert report["decision_replacement"]["projection"]
    assert report["decision_replacement"]["replacement"]
    assert report["elapsed_seconds"]["total"] < 7200
    assert report["completion"] == "complete"
    assert report["status"] == ("passed" if expected == 0 else "failed")
    if random_result == "alternating-win":
        assert report["confidence"]["zero_loss_upper_95"] == pytest.approx(
            1 - 0.05 ** (1 / 30)
        )


def test_atomic_checkpoint_after_every_game_and_suite(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evidence.json"
    calls: dict[str, list[dict[str, Any]]] = {"depth": [], "random": []}
    writes: list[dict[str, Any]] = []
    _install_success_harnesses(monkeypatch, calls)
    real_write = evidence.atomic_write_json

    def write_spy(path: Path, state: dict[str, Any]) -> None:
        writes.append(json.loads(json.dumps(state)))
        real_write(path, state)

    monkeypatch.setattr(evidence, "atomic_write_json", write_spy)
    assert evidence.main(_argv(output)) in {0, 1}

    completed_counts = [
        (
            state["suites"]["depth_match"]["completed_games"],
            state["suites"]["random_gauntlet"]["completed_games"],
        )
        for state in writes
    ]
    for count in range(1, 31):
        assert (count, 0) in completed_counts
        assert (30, count) in completed_counts
    assert any(
        state["suites"]["depth_match"]["status"] == "completed"
        and state["suites"]["random_gauntlet"]["status"] == "pending"
        for state in writes
    )
    assert output.with_suffix(output.suffix + ".tmp").exists() is False


def _compatible_checkpoint(output: Path, depth_done: int, random_done: int) -> None:
    state = evidence.new_checkpoint(
        evidence.EvidenceParameters(
            seed=20260710,
            depth_games=30,
            random_games=30,
            max_halfmoves=80,
            budget_seconds=7200.0,
        )
    )
    depth_games = [_game_record(i, 20260710 + i, "draw") for i in range(depth_done)]
    state["suites"]["depth_match"].update(
        {
            "status": "completed" if depth_done == 30 else "running",
            "completed_games": depth_done,
            "games": depth_games,
            "aggregate": {
                "wins": 0,
                "draws": depth_done,
                "losses": 0,
                "n_games": depth_done,
                "score_rate": 0.5 if depth_done else 0.0,
            },
        }
    )
    random_games = [_game_record(i, 20260710 + i, "win") for i in range(random_done)]
    state["suites"]["random_gauntlet"].update(
        {
            "status": "completed" if random_done == 30 else ("running" if random_done else "pending"),
            "completed_games": random_done,
            "games": random_games,
            "aggregate": {
                "wins": random_done,
                "draws": 0,
                "losses": 0,
                "non_win_games": [],
                "n_games": random_done,
            },
        }
    )
    evidence.atomic_write_json(output, state)


@pytest.mark.parametrize(
    ("depth_done", "random_done", "expected_depth_start", "expected_random_start"),
    [(10, 0, 10, 0), (30, 7, None, 7)],
)
def test_resume_skips_completed_games_and_suites(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    depth_done: int,
    random_done: int,
    expected_depth_start: int | None,
    expected_random_start: int,
) -> None:
    output = tmp_path / "evidence.json"
    _compatible_checkpoint(output, depth_done, random_done)
    calls: dict[str, list[dict[str, Any]]] = {"depth": [], "random": []}
    _install_success_harnesses(monkeypatch, calls)

    evidence.main(_argv(output))

    if expected_depth_start is None:
        assert calls["depth"] == []
    else:
        assert calls["depth"][0]["start_game"] == expected_depth_start
        assert [g["index"] for g in calls["depth"][0]["game_records"]] == list(
            range(expected_depth_start)
        )
    assert calls["random"][0]["start_game"] == expected_random_start


@pytest.mark.parametrize(("status", "completion", "exit_code"), [("passed", "complete", 0), ("failed", "complete", 1)])
def test_completed_checkpoint_is_reclassified_without_replay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    status: str,
    completion: str,
    exit_code: int,
) -> None:
    output = tmp_path / "evidence.json"
    _compatible_checkpoint(output, 30, 30)
    state = json.loads(output.read_text())
    state.update({"status": status, "completion": completion})
    evidence.atomic_write_json(output, state)
    monkeypatch.setattr(evidence, "run_depth_match", lambda **kwargs: pytest.fail("replayed depth"))
    monkeypatch.setattr(evidence, "run_gauntlet", lambda **kwargs: pytest.fail("replayed random"))

    assert evidence.main(_argv(output)) == exit_code


def test_mismatch_requires_restart_and_duplicate_callbacks_fail(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evidence.json"
    _compatible_checkpoint(output, 10, 0)
    called = False

    def depth_runner(**kwargs: Any) -> dict[str, Any]:
        nonlocal called
        called = True
        pytest.fail("incompatible checkpoint must fail before play")

    monkeypatch.setattr(evidence, "run_depth_match", depth_runner)
    assert evidence.main(_argv(output, "--seed", "99")) == 1
    assert called is False

    with pytest.raises(ValueError, match="expected game index"):
        evidence.append_game_checkpoint(
            json.loads(output.read_text()),
            "depth_match",
            8,
            _game_record(8, 99, "draw"),
            {},
            output,
        )


@pytest.mark.parametrize("raised", [evidence.HarnessTimeout("expired"), KeyboardInterrupt()])
def test_timeout_and_keyboard_interrupt_persist_failed_incomplete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    raised: BaseException,
) -> None:
    output = tmp_path / "evidence.json"

    def depth_runner(**kwargs: Any) -> dict[str, Any]:
        kwargs["on_game_complete"](
            0,
            _game_record(0, 20260710, "draw"),
            {"wins": 0, "draws": 1, "losses": 0, "n_games": 1, "score_rate": 0.5},
        )
        raise raised

    monkeypatch.setattr(evidence, "run_depth_match", depth_runner)
    monkeypatch.setattr(evidence, "run_gauntlet", lambda **kwargs: pytest.fail("random called"))

    assert evidence.main(_argv(output)) == 1
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["completion"] == "incomplete"
    assert report["suites"]["depth_match"]["completed_games"] == 1
    assert len(report["suites"]["depth_match"]["games"]) == 1


@pytest.mark.parametrize("sig", [signal.SIGINT, signal.SIGTERM])
def test_signal_handler_sets_shared_event_and_persists_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    sig: signal.Signals,
) -> None:
    output = tmp_path / "evidence.json"

    def depth_runner(**kwargs: Any) -> dict[str, Any]:
        evidence._handle_signal(sig, None)
        pytest.fail("signal handler did not interrupt")

    monkeypatch.setattr(evidence, "run_depth_match", depth_runner)
    assert evidence.main(_argv(output)) == 1
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["completion"] == "incomplete"
    assert "signal" in " ".join(report["reasons"]).lower()


def test_mark_interrupted_preserves_games_without_play(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = tmp_path / "evidence.json"
    _compatible_checkpoint(output, 10, 0)
    monkeypatch.setattr(evidence, "run_depth_match", lambda **kwargs: pytest.fail("played depth"))
    monkeypatch.setattr(evidence, "run_gauntlet", lambda **kwargs: pytest.fail("played random"))

    assert evidence.main(
        ["--output", str(output), "--mark-interrupted", "process hard timeout after 7260s"]
    ) == 1
    report = json.loads(output.read_text())
    assert report["status"] == "failed"
    assert report["completion"] == "incomplete"
    assert report["suites"]["depth_match"]["completed_games"] == 10
    assert "process hard timeout" in " ".join(report["reasons"])
