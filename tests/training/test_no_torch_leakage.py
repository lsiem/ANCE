"""Structural tests enforcing the training/engine boundary."""

from __future__ import annotations

import re
from pathlib import Path

_TORCH_IMPORT = re.compile(r"^\s*(?:import\s+torch\b|from\s+torch\b)")
_TRAINING_IMPORT = re.compile(r"^\s*(?:import\s+training\b|from\s+training\b)")


def _assert_no_matching_lines(path: Path, pattern: re.Pattern[str], label: str) -> None:
    source = path.read_text()
    offenders = [
        line.strip()
        for line in source.splitlines()
        if pattern.match(line)
    ]
    assert not offenders, f"{label} must not import {pattern.pattern!r}: {offenders}"


def test_nnue_format_modules_never_import_torch() -> None:
    for relative in ("nnue_format/schema.py", "nnue_format/io.py"):
        _assert_no_matching_lines(
            Path(relative),
            _TORCH_IMPORT,
            relative,
        )


def test_ance_never_imports_training_package() -> None:
    ance_root = Path("ance")
    for path in sorted(ance_root.rglob("*.py")):
        source = path.read_text()
        offenders = [
            line.strip()
            for line in source.splitlines()
            if _TRAINING_IMPORT.match(line)
        ]
        assert not offenders, f"{path} must not import training: {offenders}"
