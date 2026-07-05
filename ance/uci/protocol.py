"""Format engine -> GUI UCI response lines.

Every `print` call passes `flush=True` (D-14) -- stdout is piped by every
real GUI/gauntlet, and unflushed output is the single most common way an
engine appears to "hang" (see 01-RESEARCH.md Pitfall: forgetting flush).
"""

from __future__ import annotations

ENGINE_NAME = "ANCE 0.1"
ENGINE_AUTHOR = "Lasse Siemoneit"


def send_id() -> None:
    """Emit the `id name`/`id author` lines. Zero `option` lines follow (D-09)."""
    print(f"id name {ENGINE_NAME}", flush=True)
    print(f"id author {ENGINE_AUTHOR}", flush=True)


def send_uciok() -> None:
    print("uciok", flush=True)


def send_readyok() -> None:
    print("readyok", flush=True)


def send_bestmove(move_uci: str | None) -> None:
    """Emit exactly one `bestmove` line -- required after every `go`.

    `move_uci=None` emits `bestmove (none)` (Stockfish convention, D-12) for
    the zero-legal-move case. This walking-skeleton worker always finds a
    move on a fresh board, but the convention is wired from day one so the
    real search substrate (Plan 01-03) doesn't have to renegotiate it.
    """
    if move_uci is None:
        print("bestmove (none)", flush=True)
    else:
        print(f"bestmove {move_uci}", flush=True)


def send_info_string(message: str) -> None:
    print(f"info string {message}", flush=True)
