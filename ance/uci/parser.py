"""Minimal UCI line tokenizing.

Plan 01-02/01-03 grow this into `parse_go()`/`parse_position()` with typed
`GoCommand`/`PositionCommand` structs; this walking-skeleton plan only needs
whitespace tokenizing to dispatch on the leading command word.
"""

from __future__ import annotations


def tokenize(line: str) -> list[str]:
    """Split a raw UCI line into whitespace-separated tokens."""
    return line.split()
