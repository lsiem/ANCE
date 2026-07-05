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

from ance.board.position import Position
from ance.uci.parser import tokenize
from ance.uci.protocol import send_bestmove, send_id, send_readyok, send_uciok

stop_flag = threading.Event()
worker: threading.Thread | None = None


def _trivial_bestmove(pos: Position, stop_flag: threading.Event) -> None:
    """Pick the first legal move -- the thinnest possible "search".

    No evaluator or negamax call exists yet (that substrate is built in
    Plan 01-03); this only proves the stdin-to-stdout threading loop.
    """
    moves = pos.legal_moves()
    move = moves[0] if moves else None
    send_bestmove(move.uci() if move is not None else None)


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
        "uci": handle_uci,
        "isready": handle_isready,
        "go": lambda: handle_go(pos),
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
            handler()
        # Any other leading token is silently skipped (D-11, applied from
        # the very first version of the loop, not bolted on later).


if __name__ == "__main__":
    main()
