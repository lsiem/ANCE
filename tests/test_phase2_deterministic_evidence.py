"""Six fast contracts for the bounded deterministic evidence collector."""

from __future__ import annotations

import json
import signal
import subprocess
from pathlib import Path

import pytest

from ance.tools import phase2_deterministic_evidence as evidence


class _FakeChild:
    def __init__(self, *, graceful: bool) -> None:
        self.pid = 4321
        self.graceful = graceful
        self.wait_timeouts: list[float] = []
        self.wait_calls = 0

    def poll(self) -> None:
        return None

    def wait(self, timeout: float) -> int:
        self.wait_timeouts.append(timeout)
        self.wait_calls += 1
        if not self.graceful and self.wait_calls == 1:
            raise subprocess.TimeoutExpired("collector", timeout)
        return 0


def _state() -> dict:
    bound = evidence.RuntimeBound(870, 60)
    return evidence._base_state(
        bound,
        supervisor_start=100.0,
        collector_commit="abc123",
        collector_command="exact collector command",
    )


def test_absolute_deadline_margin_arithmetic_and_wait_bounds() -> None:
    bound = evidence.RuntimeBound(870, 60)
    bound.validate()
    assert bound.work_seconds == 810
    assert evidence.remaining_time(150.0, lambda: 100.0) == 50.0
    assert evidence.remaining_time(90.0, lambda: 100.0) == 0.0
    assert min(evidence.GRACEFUL_WAIT_SECONDS, evidence.remaining_time(108.0, lambda: 100.0)) == 8.0
    assert min(evidence.FORCED_REAP_SECONDS, evidence.remaining_time(102.0, lambda: 100.0)) == 2.0


def test_timeout_terminates_process_group_and_writes_atomic_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = _FakeChild(graceful=False)
    signals: list[signal.Signals] = []
    monkeypatch.setattr(evidence.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        evidence.os, "killpg", lambda pgid, sig: signals.append(signal.Signals(sig))
    )
    result = evidence._terminate_process_group(
        child, hard_deadline=120.0, clock=lambda: 100.0
    )
    output, summary = tmp_path / "evidence.json", tmp_path / "summary.md"
    state = _state()
    evidence._write_failure(
        state, "collector child exceeded immutable work deadline", output, summary,
        clock=lambda: 110.0,
    )

    assert result == {"sigint_sent": True, "sigkill_sent": True, "reaped": True}
    assert signals == [signal.SIGINT, signal.SIGKILL]
    assert child.wait_timeouts == [15, 5]
    report = json.loads(output.read_text())
    assert report["status"] == "failed" and report["completion"] == "incomplete"
    assert not output.with_name(output.name + ".tmp").exists()
    assert not summary.with_name(summary.name + ".tmp").exists()


def test_external_interruption_terminates_process_group_and_writes_atomic_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = _FakeChild(graceful=True)
    signals: list[signal.Signals] = []
    monkeypatch.setattr(evidence.os, "getpgid", lambda pid: pid)
    monkeypatch.setattr(
        evidence.os, "killpg", lambda pgid, sig: signals.append(signal.Signals(sig))
    )
    result = evidence._terminate_process_group(
        child, hard_deadline=109.0, clock=lambda: 100.0
    )
    output, summary = tmp_path / "evidence.json", tmp_path / "summary.md"
    state = _state()
    evidence._write_failure(
        state, "external interruption SIGTERM", output, summary, clock=lambda: 105.0
    )

    assert result == {"sigint_sent": True, "sigkill_sent": False, "reaped": True}
    assert signals == [signal.SIGINT]
    assert child.wait_timeouts == [9.0]
    report = json.loads(output.read_text())
    assert report["reasons"] == ["external interruption SIGTERM"]
    assert "Artifact status: failed" in summary.read_text()


def test_completed_passed_artifact_refuses_rerun(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output, summary = tmp_path / "evidence.json", tmp_path / "summary.md"
    state = _state()
    state.update({"status": "passed", "completion": "complete"})
    state["timings"]["supervisor_elapsed_seconds"] = 1.0
    state["completed_utc"] = "2026-07-10T20:00:00+00:00"
    evidence._write_artifacts(state, output, summary)
    monkeypatch.setattr(
        evidence.subprocess,
        "Popen",
        lambda *args, **kwargs: pytest.fail("completed artifact reran child"),
    )

    assert evidence.main(
        [
            "--output", str(output),
            "--summary", str(summary),
            "--hard-wall-seconds", "870",
            "--reporting-margin-seconds", "60",
        ]
    ) == 0


def test_fixed_oracle_schema_has_exact_expectations() -> None:
    actual = [
        (
            case.id,
            case.requested_depth,
            case.expected_move,
            case.expected_score,
            case.expected_nodes,
        )
        for case in evidence.fixed_case_specs()
    ]
    assert actual == [
        ("rook_mate", 1, "a1a8", 29999, 29),
        ("rook_mate", 2, "a1a8", 29999, 273),
        ("queen_mate", 1, "h1a8", 29999, 42),
        ("queen_mate", 4, "h1a8", 29999, 8249),
        ("hanging_queen", 1, "e1e5", 500, 30),
        ("hanging_queen", 3, "e1e5", 500, 2890),
        ("knight_fork", 1, "e5f7", 0, 25),
        ("knight_fork", 3, "e5f7", 0, 4729),
        ("horizon_rook", 1, "e1e4", 500, 36),
        ("horizon_rook", 3, "e1e4", 500, 2209),
    ]


def test_atomic_terminal_summary_contains_required_content(tmp_path: Path) -> None:
    output, summary = tmp_path / "02-STRENGTH-EVIDENCE.json", tmp_path / "02-10-SUMMARY.md"
    state = _state()
    state.update({"status": "passed", "completion": "complete"})
    state["commands"] = {
        "collector_tests": {
            "command": "collector tests", "passed": 6, "deselected": 0,
            "elapsed_seconds": 0.1,
        },
        "focused": {
            "command": "focused tests", "passed": 73, "deselected": 2,
            "elapsed_seconds": 0.2,
        },
        "full_fast": {
            "command": "full fast tests", "passed": 139, "deselected": 2,
            "elapsed_seconds": 0.3,
        },
    }
    state["completed_utc"] = "2026-07-10T20:00:00+00:00"
    evidence._write_artifacts(state, output, summary)

    text = summary.read_text()
    for required in (
        "ab996ce", "99888cb", "abc123", "6 passed", "73 passed", "139 passed",
        "Hard wall: 870 seconds", "Reporting margin: 60 seconds",
        "1205.6582282920135", "18084.8734243802", "Phase 3", "cutechess",
        "02-STRENGTH-EVIDENCE.json", "Artifact status: passed",
    ):
        assert required in text
    assert evidence.validate_terminal_artifacts(output, summary)["status"] == "passed"
