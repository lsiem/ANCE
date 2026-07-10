"""The non-blocking UCI reader/dispatch loop (D-00b/D-13).

The main thread's `for line in sys.stdin:` is a blocking readline -- that is
fine, because reading stdin is the *only* thing this thread ever does.
Search work always happens on a separate daemon worker thread spawned by
`go`, so `isready`/`quit` are answered immediately regardless of worker
state (UCI-02/UCI-12).

**Per-generation preemption and output policy.** Every `go` owns a distinct
`SearchJob`, cancellation Event, and optional movetime Timer. Events are only
ever set, never cleared or reused, so a timed-out stale worker cannot resume
when its replacement starts. A new `go` advances the generation before
preempting the old job. Both completed-depth `info` and final `bestmove`
output hold one generation lock across the current-generation check and
stdout write, making replacement and stale output mutually exclusive.

`stop` sets the current job's Event without invalidating its generation, so
that worker may emit exactly one final bestmove. `position`, `ucinewgame`,
and `quit` preserve the normal joined-worker flush; if their bounded join
times out, they invalidate the surviving generation before changing state.
"""

from __future__ import annotations

import sys
import threading
import time
from dataclasses import dataclass

import ance.debug as debug
from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.eval.handcrafted import HandcraftedEval
from ance.search.negamax import search_root
from ance.search.types import DEFAULT_BARE_GO_MOVETIME_MS, MAX_PLY, SearchResult
from ance.uci.parser import GoCommand, parse_go, parse_position, tokenize
from ance.uci.protocol import (
    send_bestmove,
    send_id,
    send_info_depth,
    send_info_string,
    send_readyok,
    send_uciok,
)

@dataclass
class SearchJob:
    generation: int
    stop_event: threading.Event
    thread: threading.Thread | None = None
    timer: threading.Timer | None = None


active_job: SearchJob | None = None
search_generation = 0
generation_lock = threading.Lock()

# The engine's real default evaluator (EVAL-02): Simplified Evaluation
# Function material+PST plus mobility/bishop-pair/tempo/pawn-structure
# terms (D-05/D-06), replacing Plan 01-03's bootstrap MaterialEval.
evaluator: Evaluator = HandcraftedEval()


def _stop_active_worker(
    timeout: float = 0.5,
    *,
    invalidate_on_timeout: bool = False,
) -> None:
    """Cancel and bounded-join the captured active job without reusing its token."""
    global search_generation
    job = active_job
    if job is None:
        return
    job.stop_event.set()
    if job.timer is not None:
        job.timer.cancel()
        job.timer = None
    thread = job.thread
    if thread is None or not thread.is_alive():
        return
    thread.join(timeout)
    if not thread.is_alive():
        return
    debug.log("ERROR: search worker did not stop within join timeout")
    if invalidate_on_timeout:
        with generation_lock:
            if search_generation == job.generation:
                search_generation += 1


def _emit_info(result: SearchResult, nps: int, my_generation: int) -> None:
    with generation_lock:
        if my_generation != search_generation:
            return
        send_info_depth(
            result.depth,
            result.score,
            result.nodes,
            nps,
            [move.uci() for move in result.pv],
        )


def _run_search(
    pos: Position,
    max_depth: int,
    evaluator_: Evaluator,
    stop_flag_: threading.Event,
    timer: threading.Timer | None,
    my_generation: int,
    deadline: float | None,
) -> None:
    """Runs on the daemon worker thread. Iterative-deepening search until
    stop, deadline, or max_depth. Emits one info line per completed depth."""
    move = None
    try:
        result = search_root(
            pos,
            max_depth=max_depth,
            evaluator=evaluator_,
            stop_flag=stop_flag_,
            deadline=deadline,
            info_callback=lambda result, nps: _emit_info(
                result, nps, my_generation
            ),
        )
        move = result.best_move
    finally:
        if timer is not None:
            timer.cancel()
        job = active_job
        if (
            job is not None
            and job.generation == my_generation
            and job.stop_event is stop_flag_
            and job.timer is timer
        ):
            job.timer = None

    with generation_lock:
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
    global active_job, search_generation
    with generation_lock:
        search_generation += 1
        my_generation = search_generation
    _stop_active_worker()

    stop_event = threading.Event()
    job = SearchJob(generation=my_generation, stop_event=stop_event)
    depth = cmd.depth if cmd.depth is not None else MAX_PLY
    deadline: float | None = None
    if cmd.infinite:
        deadline = None
    elif cmd.depth is None and cmd.movetime is None:
        deadline = time.monotonic() + DEFAULT_BARE_GO_MOVETIME_MS / 1000
    elif cmd.movetime is not None:
        depth = MAX_PLY

    if cmd.movetime is not None:
        job.timer = threading.Timer(cmd.movetime / 1000, stop_event.set)
        job.timer.daemon = True
        job.timer.start()

    job.thread = threading.Thread(
        target=_run_search,
        args=(
            pos.copy(),
            depth,
            evaluator,
            stop_event,
            job.timer,
            my_generation,
            deadline,
        ),
        daemon=True,
    )
    active_job = job
    debug.log(f"worker started (generation {my_generation}, depth {depth})")
    job.thread.start()


def handle_stop() -> None:
    job = active_job
    if job is not None:
        job.stop_event.set()


def handle_position(pos: Position, tokens: list[str]) -> None:
    """`tokens` is the full line's tokens (leading `position` word included).

    D-10's "reject and keep, never reject and reset" contract: a malformed
    `fen` clause returns before `moves` is even looked at, leaving `pos`
    exactly as it was before this command. A malformed `moves` clause is
    caught the same way, leaving `pos` at the just-set (valid) startpos/fen
    base -- `try_push_uci_moves` never partially commits (Position adapter,
    Task 1), so the whole command's net effect on `pos` is always either
    "fully applied" or "the last-known-good state", never a partial one.

    Stops and joins any active search worker first (D-13). A worker that
    joins normally flushes its best-so-far before the position changes; a
    worker that survives the bounded join is generation-invalidated.
    """
    _stop_active_worker(invalidate_on_timeout=True)
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
    # yet. Stop/join with the same joined-flush / timed-out-invalidation
    # contract as handle_position, then reset the board.
    _stop_active_worker(invalidate_on_timeout=True)
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
    # Same shared _stop_active_worker() helper at a longer timeout, in
    # place of a separate ad hoc join -- lets the worker unwind, then exits
    # cleanly (UCI-10/D-13: never deadlocks on a running search).
    _stop_active_worker(timeout=2.0, invalidate_on_timeout=True)
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
