"""Shared pytest fixtures for driving ANCE as a real UCI subprocess.

Every test in this suite talks to the engine over real stdin/stdout pipes
(never imports engine internals directly for I/O behavior) so a hang or
protocol bug is caught the same way a real GUI would hit it. The reader
side always runs on a background thread + Queue -- never a bare blocking
`readline()` in the test itself -- so a genuinely hung engine fails the
test with a clear timeout instead of hanging the whole suite.
"""

from __future__ import annotations

import queue
import subprocess
import sys
import threading
from collections.abc import Iterator

import pytest


class EngineProcess:
    """Wraps a `python -m ance` subprocess with a non-blocking line reader."""

    def __init__(self, process: subprocess.Popen) -> None:
        self.process = process
        self._lines: queue.Queue[str] = queue.Queue()
        self._reader = threading.Thread(target=self._pump_stdout, daemon=True)
        self._reader.start()

    def _pump_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            self._lines.put(line.rstrip("\n"))

    def send(self, line: str) -> None:
        assert self.process.stdin is not None
        self.process.stdin.write(line + "\n")
        self.process.stdin.flush()

    def read_line(self, timeout: float = 2.0) -> str:
        try:
            return self._lines.get(timeout=timeout)
        except queue.Empty:
            pytest.fail(f"engine produced no output within {timeout}s")

    def wait(self, timeout: float = 2.0) -> int:
        return self.process.wait(timeout=timeout)


@pytest.fixture
def engine() -> Iterator[EngineProcess]:
    process = subprocess.Popen(
        [sys.executable, "-m", "ance"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    engine_process = EngineProcess(process)
    try:
        yield engine_process
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=2.0)
