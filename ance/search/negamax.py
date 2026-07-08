"""Fail-soft alpha-beta negamax with ply-adjusted mate scoring (SRCH-02).

Extends the Phase 1 fixed-depth skeleton with alpha-beta pruning, ply-adjusted
mate propagation, and deterministic root move selection (D-10). Quiescence,
iterative deepening, and draw detection land in later Phase 2 plans.

This module imports only the `Evaluator` Protocol from `ance.eval.base` --
never any concrete evaluator class.
"""

from __future__ import annotations

import threading

import chess

from ance.board.position import Position
from ance.eval.base import MATE, Evaluator
from ance.search.types import SearchContext, SearchResult

# Benchmarked to keep a bare `go` well under a second in pure Python with a
# cheap bootstrap evaluator. Plan 02-04 retunes for iterative deepening.
DEFAULT_DEPTH = 3

NODE_POLL_INTERVAL = 2048


class SearchAborted(Exception):
    """Raised by `negamax` when a sampled node-count poll finds `stop_flag`
    set. Caught by `search_root`, which returns the best root move found
    before the abort."""


def _poll_stop(ctx: SearchContext) -> None:
    if ctx.counter[0] % NODE_POLL_INTERVAL == 0 and ctx.stop_flag.is_set():
        raise SearchAborted()


def negamax(
    pos: Position,
    depth: int,
    alpha: int,
    beta: int,
    ctx: SearchContext,
) -> int:
    """Fail-soft alpha-beta negamax. Returns centipawns, side-to-move relative."""
    ctx.counter[0] += 1
    _poll_stop(ctx)

    moves = pos.legal_moves()
    if not moves:
        if pos.is_check():
            return -(MATE - ctx.ply)
        return 0

    if depth == 0:
        return ctx.evaluator.evaluate(pos)

    best = -MATE - 1
    board = pos.board
    child_ply = ctx.ply + 1
    for move in moves:
        board.push(move)
        try:
            score = -negamax(
                pos,
                depth - 1,
                -beta,
                -alpha,
                SearchContext(
                    stop_flag=ctx.stop_flag,
                    counter=ctx.counter,
                    evaluator=ctx.evaluator,
                    ply=child_ply,
                    path_keys=ctx.path_keys,
                    game_history_keys=ctx.game_history_keys,
                    deadline=ctx.deadline,
                    max_depth=ctx.max_depth,
                    info_callback=ctx.info_callback,
                ),
            )
        finally:
            board.pop()
        if score > best:
            best = score
        if score >= beta:
            return score
        if score > alpha:
            alpha = score
    return best


def search_root(
    pos: Position,
    max_depth: int,
    evaluator: Evaluator,
    stop_flag: threading.Event,
    *,
    deadline: float | None = None,
) -> SearchResult:
    """Fixed-depth root search. Returns SearchResult with deterministic ties (D-10)."""
    if pos.has_no_legal_moves():
        return SearchResult(best_move=None, score=0, depth=max_depth, pv=[], nodes=0)

    moves = pos.legal_moves()
    best_move: chess.Move | None = None
    best_score = -MATE - 1
    counter = [0]
    board = pos.board

    for move in moves:
        if stop_flag.is_set():
            break
        board.push(move)
        try:
            ctx = SearchContext(
                stop_flag=stop_flag,
                counter=counter,
                evaluator=evaluator,
                ply=1,
                path_keys=[],
                game_history_keys=set(),
                deadline=deadline,
                max_depth=max_depth,
            )
            score = -negamax(pos, max_depth - 1, -MATE - 1, MATE + 1, ctx)
        except SearchAborted:
            break
        finally:
            if board.move_stack:
                board.pop()

        if score > best_score:
            best_score = score
            best_move = move

    if best_move is None:
        best_move = moves[0]
        if best_score == -MATE - 1:
            best_score = 0

    return SearchResult(
        best_move=best_move,
        score=best_score,
        depth=max_depth,
        pv=[best_move] if best_move is not None else [],
        nodes=counter[0],
    )
