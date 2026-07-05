"""The non-blocking UCI reader/dispatch loop (D-00b/D-13).

The main thread's `for line in sys.stdin:` is a blocking readline -- that is
fine, because reading stdin is the *only* thing this thread ever does.
Search work always happens on a separate daemon worker thread spawned by
`go`, so `isready`/`quit` are answered immediately regardless of worker
state (UCI-02/UCI-12). This wave-1 worker is deliberately trivial (picks the
first legal move, no search or evaluator yet -- Plan 01-03 replaces it with
the real fixed-depth negamax substrate behind the Evaluator seam) and
carries no preemption guard against a second `go` arriving mid-search; that
race becomes safety-critical only once real search exists (Plan 01-03 Task 3).
"""

from __future__ import annotations

import sys
import threading

import ance.debug as debug
from ance.board.position import Position
from ance.uci.parser import parse_position, tokenize
from ance.uci.protocol import (
    send_bestmove,
    send_id,
    send_info_string,
    send_readyok,
    send_uciok,
)

stop_flag = threading.Event()
worker: threading.Thread | None = None


def _trivial_bestmove(pos: Position, stop_flag: threading.Event) -> None:
    """Pick the first legal move -- the thinnest possible "search".

    No evaluator or negamax call exists yet (that substrate is built in
    Plan 01-03); this only proves the stdin-to-stdout threading loop.
    """
    debug.log("worker started")
    moves = pos.legal_moves()
    move = moves[0] if moves else None
    send_bestmove(move.uci() if move is not None else None)
    debug.log("worker stopped")


def handle_uci() -> None:
    send_id()
    send_uciok()


def handle_isready() -> None:
    # Answered from the reader thread, never gated behind a running search.
    send_readyok()


def handle_go(pos: Position) -> None:
    global worker
    stop_flag.clear()
    worker = threading.Thread(
        target=_trivial_bestmove, args=(pos.copy(), stop_flag), daemon=True
    )
    worker.start()


def handle_position(pos: Position, tokens: list[str]) -> None:
    """`tokens` is the full line's tokens (leading `position` word included).

    D-10's "reject and keep, never reject and reset" contract: a malformed
    `fen` clause returns before `moves` is even looked at, leaving `pos`
    exactly as it was before this command. A malformed `moves` clause is
    caught the same way, leaving `pos` at the just-set (valid) startpos/fen
    base -- `try_push_uci_moves` never partially commits (Position adapter,
    Task 1), so the whole command's net effect on `pos` is always either
    "fully applied" or "the last-known-good state", never a partial one.
    """
    cmd = parse_position(tokens[1:])
    if cmd is None:
        send_info_string("invalid position command, board unchanged")
        debug.log(f"rejected malformed position command: {tokens!r}")
        return
    if cmd.kind == "startpos":
        pos.try_set_startpos()
    else:
        if not pos.try_set_fen(cmd.fen):
            send_info_string("invalid position command, board unchanged")
            debug.log(f"rejected malformed fen: {cmd.fen!r}")
            return
    if cmd.moves and not pos.try_push_uci_moves(cmd.moves):
        send_info_string("invalid position command, board unchanged")
        debug.log(f"rejected illegal move list: {cmd.moves!r}")


def handle_ucinewgame(pos: Position) -> None:
    # No-op reset of per-game state in M1 (D-17) -- no TT/history exists yet.
    pos.try_set_startpos()


def handle_setoption(tokens: list[str]) -> None:
    """Accept and silently discard `setoption` (D-09).

    An explicit handler -- rather than relying on the generic
    unknown-leading-token skip (D-11) -- consumes the whole line
    (`name ... value ...` included) with no partial parsing and no side
    effects, per the cross-AI review finding: forward-compatible with a
    real `setoption` handler landing in v2 (CFG-01) without risking the
    dispatcher misinterpreting trailing tokens as a new command.
    """
    return


def handle_ponder() -> None:
    """`ponder`/`ponderhit` explicit no-ops.

    Pondering itself is unsupported this phase, but GUIs send these
    unconditionally; an explicit (accepted-and-ignored) handler avoids
    GUI-side ponder-related warnings that D-11's generic unknown-token skip
    would not itself cause any problem for, but which an explicit handler
    documents intentionally rather than leaving to incidental behavior.
    """
    return


def handle_debug(tokens: list[str]) -> None:
    """`debug on`/`debug off` toggles the stderr-only diagnostic channel
    (D-18). Logging the toggle itself is deliberate -- it makes `debug on`
    immediately observable on stderr rather than only affecting later
    events, which is genuinely useful when diagnosing a hang (the very
    scenario this channel exists for).
    """
    enabled = len(tokens) > 1 and tokens[1] == "on"
    debug.set_enabled(enabled)
    debug.log(f"debug logging {'enabled' if enabled else 'disabled'}")


def handle_quit() -> None:
    # Set the flag, let the worker unwind, then exit cleanly -- bounded
    # join means quit never deadlocks on a running search (UCI-10/D-13).
    stop_flag.set()
    if worker is not None:
        worker.join(timeout=2.0)
    sys.exit(0)


def main() -> None:
    pos = Position()
    dispatch = {
        "uci": lambda tokens: handle_uci(),
        "isready": lambda tokens: handle_isready(),
        "go": lambda tokens: handle_go(pos),
        "position": lambda tokens: handle_position(pos, tokens),
        "ucinewgame": lambda tokens: handle_ucinewgame(pos),
        "setoption": lambda tokens: handle_setoption(tokens),
        "ponder": lambda tokens: handle_ponder(),
        "ponderhit": lambda tokens: handle_ponder(),
        "debug": lambda tokens: handle_debug(tokens),
    }
    for line in sys.stdin:
        tokens = tokenize(line.strip())
        if not tokens:
            continue
        command = tokens[0]
        if command == "quit":
            handle_quit()
            continue
        handler = dispatch.get(command)
        if handler is not None:
            handler(tokens)
        # Any other leading token is silently skipped (D-11, applied from
        # the very first version of the loop, not bolted on later).


if __name__ == "__main__":
    main()
