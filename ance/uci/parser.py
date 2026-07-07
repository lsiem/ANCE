"""Minimal UCI line tokenizing plus typed command parsers.

`parse_position()`/`PositionCommand` (Plan 01-02) handle real `position`
command parsing. `parse_go()`/`GoCommand` (Plan 01-03) parse every
documented `go` sub-parameter into a typed field -- including the clock
params (`wtime`/`btime`/`winc`/`binc`) and `nodes` that this phase does not
yet act on -- so a real GUI/gauntlet that always sends `wtime`/`btime`
never crashes the parser (D-11, 01-RESEARCH.md "go param parsing that
crashes on unimplemented clock/nodes params").
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


@dataclass(frozen=True)
class GoCommand:
    depth: int | None = None
    movetime: int | None = None
    infinite: bool = False
    wtime: int | None = None
    btime: int | None = None
    winc: int | None = None
    binc: int | None = None
    nodes: int | None = None


# Sub-tokens that take a single following integer argument, mapped to the
# GoCommand field they populate. `searchmoves`/`ponder` are spec-legal but
# take no simple integer argument (searchmoves takes a move list to the end
# of the line, ponder takes none) -- neither is acted on this phase; both
# fall through harmlessly since they never appear as a *key* in this map
# and are simply skipped as unrecognized-but-tolerated tokens (D-11).
_INT_PARAMS = {
    "depth": "depth",
    "movetime": "movetime",
    "wtime": "wtime",
    "btime": "btime",
    "winc": "winc",
    "binc": "binc",
    "nodes": "nodes",
}


def parse_go(tokens: list[str]) -> GoCommand:
    """Parse the tokens *following* the leading `go` word. Every documented
    `go` sub-parameter is parsed into a field even though Phase 1 only acts
    on `depth`/`movetime`/bare-default/`infinite` (UCI-08's real clock
    budgeting is Phase 3) -- this is what keeps a real GUI's
    `go wtime ... btime ... winc ... binc ...` from crashing the parser.
    Tokens outside this grammar (or a value that fails `int()`) are simply
    skipped rather than raising (D-11).
    """
    fields: dict[str, int | bool] = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == "infinite":
            fields["infinite"] = True
            i += 1
            continue
        field_name = _INT_PARAMS.get(token)
        if field_name is not None and i + 1 < len(tokens):
            try:
                fields[field_name] = int(tokens[i + 1])
            except ValueError:
                pass
            i += 2
            continue
        i += 1
    return GoCommand(**fields)
