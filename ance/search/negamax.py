"""Fixed-depth negamax (D-01) -- the minimal move-selection substrate that
exercises the Evaluator seam (D-00a) before Phase 2 layers alpha-beta,
quiescence, and iterative deepening onto this exact skeleton. No pruning,
no move ordering -- every legal move at every ply is searched in full.

**Search remains the sole mate scorer in Phase 1.** A checkmate leaf scores
a flat ``-(MATE)`` and a stalemate leaf scores ``0``, with no
ply-adjustment -- the ``±(MATE - ply)`` refinement described in the
Evaluator Protocol's docstring only matters once mate scores propagate
through multiple plies via Phase 2's iterative deepening + transposition
table. No Phase 1 evaluator ever returns a mate score itself. A future
NNUE-based evaluator must implement mate scoring inside its own
`evaluate()` if it needs to change this, or accept that search stays the
sole mate scorer -- a documented Phase 1 tradeoff (cross-AI review), not a
gap.

This module imports only the `Evaluator` Protocol from `ance.eval.base` --
never any concrete evaluator class. `tests/test_eval_seam.py`'s
structural swap-seam test proves this by reading this file's source text
and asserting no concrete evaluator class name appears in it.
"""

from __future__ import annotations

import random
import threading

import chess

from ance.board.position import Position
from ance.eval.base import MATE, Evaluator

# Benchmarked (Task 3) to keep a bare `go` well under a second in pure
# Python with a cheap bootstrap evaluator (D-02, 01-RESEARCH.md Assumption
# A1). Plan 01-04 Task 3 re-benchmarks once the real, costlier handcrafted
# evaluator lands and may tune this constant down.
DEFAULT_DEPTH = 3

# D-13: sampled polling, not a stop_flag check on every negamax call --
# checking every node would dominate runtime at these leaf counts for no
# latency benefit at Phase 1's shallow, fixed depths.
NODE_POLL_INTERVAL = 2048


class SearchAborted(Exception):
    """Raised by `negamax` when a sampled node-count poll finds `stop_flag`
    set. Caught by `search_root`, which returns the best root move found
    before the abort (D-03)."""


def negamax(
    pos: Position,
    depth: int,
    evaluator: Evaluator,
    stop_flag: threading.Event,
    counter: list[int],
) -> int:
    """Returns a centipawn score, side-to-move relative, for `pos` searched
    `depth` plies deep. `counter[0]` is shared mutable node-visit state
    across the whole search tree (a one-element list so nested calls all
    increment the same counter) -- `search_root` owns and resets it per
    root move.
    """
    counter[0] += 1
    if counter[0] % NODE_POLL_INTERVAL == 0 and stop_flag.is_set():
        raise SearchAborted()

    moves = pos.legal_moves()
    if not moves:
        # Checkmate vs. stalemate -- the only two zero-legal-move states
        # reachable by a legal move sequence (Position.has_no_legal_moves).
        return -MATE if pos.is_check() else 0

    if depth == 0:
        return evaluator.evaluate(pos)  # THE seam.

    best = -MATE - 1
    board = pos.board
    for move in moves:
        board.push(move)
        try:
            score = -negamax(pos, depth - 1, evaluator, stop_flag, counter)
        finally:
            board.pop()
        if score > best:
            best = score
    return best


def search_root(
    pos: Position,
    depth: int,
    evaluator: Evaluator,
    stop_flag: threading.Event,
    rng: random.Random,
) -> chess.Move | None:
    """Returns the chosen root move, or `None` on zero legal moves (the UCI
    layer converts that to `bestmove (none)`, D-12 -- this function never
    decides the wire format itself). Checks `stop_flag` at the start of
    every root-move iteration (D-13's "at each root move" half) and
    collects every move tying for the best score into `best_moves`,
    returning a uniform random choice among them (D-04) for reproducible-
    with-a-seed variety against a random-mover opponent.
    """
    if pos.has_no_legal_moves():
        return None

    moves = pos.legal_moves()
    best_moves: list[chess.Move] = []
    best_score = -MATE - 1
    counter = [0]
    board = pos.board
    for move in moves:
        if stop_flag.is_set():
            break  # D-03: return best-so-far.
        board.push(move)
        try:
            score = -negamax(pos, depth - 1, evaluator, stop_flag, counter)
        except SearchAborted:
            board.pop()
            break
        board.pop()
        if score > best_score:
            best_score, best_moves = score, [move]
        elif score == best_score:
            best_moves.append(move)

    if best_moves:
        return rng.choice(best_moves)
    # Aborted before evaluating a single root move -- fall back to the
    # first legal move rather than returning None (moves is non-empty here
    # since has_no_legal_moves() already returned False above).
    return moves[0]
