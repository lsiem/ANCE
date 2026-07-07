"""The non-blocking UCI reader/dispatch loop (D-00b/D-13).

The main thread's `for line in sys.stdin:` is a blocking readline -- that is
fine, because reading stdin is the *only* thing this thread ever does.
Search work always happens on a separate daemon worker thread spawned by
`go`, so `isready`/`quit` are answered immediately regardless of worker
state (UCI-02/UCI-12).

**Preemption policy (cross-AI review, HIGH consensus across both rounds).**
A second `go` (or a `position`/`ucinewgame`) arriving while a worker is
already running never spawns a concurrent worker: `_stop_active_worker()`
signals `stop_flag`, joins the prior worker with a bounded timeout, and
unconditionally clears `stop_flag` before proceeding. `position`/
`ucinewgame` do not touch `search_generation`, so a worker they preempt is
still the "current" generation when it finishes and its flushed best-so-far
`bestmove` is legitimately emitted (D-13's "stale search always fully
flushed before the position it was searching becomes outdated"). A *new*
`go`, by contrast, bumps `search_generation` **before** calling
`_stop_active_worker()`, so the worker it preempts is numerically stale
the instant the new `go` begins -- once superseded, that worker's result is
unconditionally dropped (logged, never sent to stdout) instead of racing
the new worker's output onto stdout, independent of whether `join(timeout)`
itself succeeds or times out (round-2 HIGH hardening: `search_generation`
equality, not join timing, is the one correctness mechanism).

A `go movetime <ms>` search's `threading.Timer` deadline is held at module
scope (`movetime_timer`) precisely so a *later*, unrelated preemption can
reach and cancel it -- and the search-runner also cancels its own timer in
a `finally` block on every exit path -- so a stale timer from an earlier
`go` can never fire `stop_flag.set()` into a later, unrelated search.
"""

from __future__ import annotations

import os
import random
import sys
import threading

import ance.debug as debug
from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.eval.material import MaterialEval
from ance.search.negamax import DEFAULT_DEPTH, search_root
from ance.uci.parser import GoCommand, parse_go, parse_position, tokenize
from ance.uci.protocol import (
    send_bestmove,
    send_id,
    send_info_string,
    send_readyok,
    send_uciok,
)

stop_flag = threading.Event()
worker: threading.Thread | None = None

# Monotonic counter gating send_bestmove (round-2 HIGH hardening) -- see
# module docstring. Bumped by handle_go only, never by position/ucinewgame.
search_generation = 0

# Held at module scope (not local to handle_go) so _stop_active_worker() can
# reach and cancel a leftover timer from a preempted `go movetime` search.
movetime_timer: threading.Timer | None = None

# Bootstrap evaluator (D-05 material values only) proving the search<->eval
# wiring; Plan 01-04 swaps this for the real HandcraftedEval.
evaluator: Evaluator = MaterialEval()

# Seedable tie-break RNG (D-04); reseeded by handle_ucinewgame (D-17).
rng = random.Random(int(os.environ.get("ANCE_SEED", "0")))


def _stop_active_worker(timeout: float = 0.5) -> None:
    """Stop -> join -> clear -> cancel-timer. The cross-AI review's HIGH-
    consensus preemption policy: on a new `go` while a worker is alive, or
    on `position`/`ucinewgame` arriving during an active search, always
    stop and join the prior worker before proceeding. `stop_flag.clear()`
    and the `movetime_timer` cancellation run unconditionally (even if no
    worker was alive) so the next search always starts unpolluted.
    """
    global movetime_timer
    if worker is not None and worker.is_alive():
        stop_flag.set()
        worker.join(timeout)
        if worker.is_alive():
            # Escalated visibility for a genuinely stuck worker -- proceeds
            # to clear/cancel regardless; search_generation gating (not
            # this join) is what keeps a stale worker from emitting later.
            debug.log("ERROR: search worker did not stop within join timeout")
    stop_flag.clear()
    if movetime_timer is not None:
        movetime_timer.cancel()
        movetime_timer = None


def _run_search(
    pos: Position,
    depth: int,
    evaluator_: Evaluator,
    stop_flag_: threading.Event,
    rng_: random.Random,
    infinite: bool,
    timer: threading.Timer | None,
    my_generation: int,
) -> None:
    """Runs on the daemon worker thread. Calls `search_root` exactly once;
    `go infinite` (D-16) additionally idles on `stop_flag_.wait()` *after*
    the search completes, holding the result until `stop` arrives. The
    `finally` block cancels `timer` on every exit path (normal completion,
    an infinite wait woken by `stop`, or an exception) so a movetime
    deadline can never outlive the search it belongs to. `send_bestmove` is
    only reached if `my_generation` still equals the current
    `search_generation` -- a superseded worker's result is dropped and
    logged instead.
    """
    global movetime_timer
    move = None
    try:
        move = search_root(pos, depth, evaluator_, stop_flag_, rng_)
        if infinite:
            stop_flag_.wait()
    finally:
        if timer is not None:
            timer.cancel()
        if movetime_timer is timer:
            movetime_timer = None

    if my_generation == search_generation:
        debug.log(f"worker (generation {my_generation}) sending bestmove")
        send_bestmove(move.uci() if move is not None else None)
    else:
        debug.log(
            f"dropped stale bestmove from generation {my_generation} "
            f"(current generation {search_generation})"
        )


def handle_uci() -> None:
    send_id()
    send_uciok()


def handle_isready() -> None:
    # Answered from the reader thread, never gated behind a running search.
    send_readyok()


def handle_go(cmd: GoCommand, pos: Position) -> None:
    global worker, search_generation, movetime_timer
    # Bumped BEFORE preempting the prior worker (round-2 HIGH hardening):
    # any prior worker is numerically stale the instant this go begins,
    # independent of whether _stop_active_worker()'s join succeeds.
    search_generation += 1
    my_generation = search_generation
    _stop_active_worker()

    depth = cmd.depth if cmd.depth is not None else DEFAULT_DEPTH

    timer: threading.Timer | None = None
    if cmd.movetime is not None:
        timer = threading.Timer(cmd.movetime / 1000, stop_flag.set)
        timer.daemon = True
        movetime_timer = timer
        timer.start()

    worker = threading.Thread(
        target=_run_search,
        args=(
            pos.copy(),
            depth,
            evaluator,
            stop_flag,
            rng,
            cmd.infinite,
            timer,
            my_generation,
        ),
        daemon=True,
    )
    debug.log(f"worker started (generation {my_generation}, depth {depth})")
    worker.start()


def handle_stop() -> None:
    stop_flag.set()


def handle_position(pos: Position, tokens: list[str]) -> None:
    """`tokens` is the full line's tokens (leading `position` word included).

    D-10's "reject and keep, never reject and reset" contract: a malformed
    `fen` clause returns before `moves` is even looked at, leaving `pos`
    exactly as it was before this command. A malformed `moves` clause is
    caught the same way, leaving `pos` at the just-set (valid) startpos/fen
    base -- `try_push_uci_moves` never partially commits (Position adapter,
    Task 1), so the whole command's net effect on `pos` is always either
    "fully applied" or "the last-known-good state", never a partial one.

    Stops and joins any active search worker first (D-13) -- a stale
    search's flushed best-so-far bestmove is always emitted before the
    position it was searching becomes outdated (this doesn't bump
    search_generation, so that flush is not dropped as stale).
    """
    _stop_active_worker()
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
    # No-op reset of per-game state in M1 (D-17) -- no TT/history exists
    # yet. Stops/joins any active worker first (same D-13 flush contract as
    # handle_position), resets the board, and reseeds the tie-break RNG.
    _stop_active_worker()
    pos.try_set_startpos()
    rng.seed(int(os.environ.get("ANCE_SEED", "0")))


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
    # Same shared _stop_active_worker() helper at a longer timeout, in
    # place of a separate ad hoc join -- lets the worker unwind, then exits
    # cleanly (UCI-10/D-13: never deadlocks on a running search).
    _stop_active_worker(timeout=2.0)
    sys.exit(0)


def main() -> None:
    pos = Position()
    dispatch = {
        "uci": lambda tokens: handle_uci(),
        "isready": lambda tokens: handle_isready(),
        "go": lambda tokens: handle_go(parse_go(tokens[1:]), pos),
        "stop": lambda tokens: handle_stop(),
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
