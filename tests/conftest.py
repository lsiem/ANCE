"""Shared pytest fixtures for driving ANCE as a real UCI subprocess.

Every test in this suite talks to the engine over real stdin/stdout pipes
(never imports engine internals directly for I/O behavior) so a hang or
protocol bug is caught the same way a real GUI would hit it. The reader
side always runs on a background thread + Queue -- never a bare blocking
`readline()` in the test itself -- so a genuinely hung engine fails the
test with a clear timeout instead of hanging the whole suite.
"""

from __future__ import annotations

import os
import queue
import subprocess
import sys
import threading
from collections.abc import Iterator

import pytest


class EngineProcess:
    """Wraps a `python -m ance` subprocess with non-blocking stdout/stderr
    readers -- stderr is the D-18 debug channel, kept on its own queue so
    tests can assert on it independently of the protocol stdout stream.
    """

    def __init__(self, process: subprocess.Popen) -> None:
        self.process = process
        self._lines: queue.Queue[str] = queue.Queue()
        self._stderr_lines: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._pump_stdout, daemon=True)
        self._reader.start()
        self._stderr_reader = threading.Thread(target=self._pump_stderr, daemon=True)
        self._stderr_reader.start()

    def _pump_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line.rstrip("\n"))

    def _pump_stderr(self) -> None:
        assert self.process.stderr is not None
        for line in self.process.stderr:
            self._stderr_lines.put(line.rstrip("\n"))

    def send(self, line: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def read_line(self, timeout: float = 2.0) -> str:
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            pytest.fail(f"engine produced no output within {timeout}s")

    def has_stderr_output(self, timeout: float = 0.3) -> bool:
        """Non-failing check for stderr output -- `timeout` should be short
        for the negative case (proving *absence*), since a genuine absence
        always waits out the full timeout.
        """
        try:
            self._stderr_lines.get(timeout=timeout)
            return True
        except queue.Empty:
            return False

    def wait(self, timeout: float = 2.0) -> int:
        return self.process.wait(timeout=timeout)


def send_lines(engine: EngineProcess, lines: list[str]) -> None:
    """Write each line with `flush=True` so multi-line integration tests
    (e.g. a `position` command followed by `go`) stay readable as a plain
    list of strings instead of one embedded-`\\n` string.
    """
    for line in lines:
        engine.send(line)


@pytest.fixture
def engine() -> Iterator[EngineProcess]:
    # Explicitly strip ANCE_DEBUG from the child's env (rather than
    # inheriting whatever the test-runner's shell happens to have set) so
    # the "debug off by default" test is deterministic regardless of the
    # developer's own shell environment.
    env = {k: v for k, v in os.environ.items() if k != "ANCE_DEBUG"}
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
