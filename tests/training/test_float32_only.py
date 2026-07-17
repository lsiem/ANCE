"""Structural guard: training graph stays float32-only."""

from __future__ import annotations

import re
from pathlib import Path

_DISALLOWED = re.compile(
    r"\b(?:"
    r"float64|double\(|\.double\(|\.to\(torch\.float64\)|"
    r"autocast|GradScaler|amp\."
    r")\b"
)


def test_training_modules_avoid_double_precision_and_amp() -> None:
    for relative in ("training/model.py", "training/train.py"):
        source = Path(relative).read_text()
        match = _DISALLOWED.search(source)
        assert match is None, f"{relative} references disallowed token: {match.group(0)!r}"
