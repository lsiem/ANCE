"""Minimal UCI line tokenizing plus typed command parsers.

Plan 01-03 grows this further with `parse_go()`/`GoCommand`; this plan adds
`parse_position()`/`PositionCommand` for real `position` command handling.
"""

from __future__ import annotations

from dataclasses import dataclass


def tokenize(line: str) -> list[str]:
    """Split a raw UCI line into whitespace-separated tokens."""
    return line.split()


@dataclass(frozen=True)
class PositionCommand:
    kind: str  # "startpos" | "fen"
    fen: str | None
    moves: list[str]


def parse_position(tokens: list[str]) -> PositionCommand | None:
    """Parse the tokens *following* the leading `position` word (i.e.
    `tokens[0]` here is `startpos` or `fen`, per the UCI grammar). Splits on
    the literal `moves` token if present. Returns `None` on a grammar-level
    malformed command (missing `startpos`/`fen` keyword) -- the caller emits
    an `info string` and leaves the board untouched (D-10); a syntactically
    well-formed but semantically bad FEN string is returned as-is and
    rejected downstream by `Position.try_set_fen()`.
    """
    body = tokens
    moves: list[str] = []
    if "moves" in body:
        idx = body.index("moves")
        moves = body[idx + 1 :]
        body = body[:idx]
    if not body:
        return None
    if body[0] == "startpos":
        return PositionCommand(kind="startpos", fen=None, moves=moves)
    if body[0] == "fen":
        # A well-formed FEN is 6 space-separated fields; join whatever is
        # present so a truncated/malformed FEN still reaches
        # `Position.try_set_fen()` and gets rejected via `ValueError`
        # rather than crashing the parser itself.
        fen = " ".join(body[1:7])
        return PositionCommand(kind="fen", fen=fen, moves=moves)
    return None
