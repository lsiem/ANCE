"""Fail-soft alpha-beta negamax with quiescence, iterative deepening, and draw cuts.

This module imports only the `Evaluator` Protocol from `ance.eval.base` --
never any concrete evaluator class.
"""

from __future__ import annotations

import threading
import time

import chess
import chess.polyglot

from ance.board.position import Position
from ance.eval.base import MATE, Evaluator
from ance.search.ordering import (
    _capture_value,
    _mvv_lva_sort,
    new_history,
    new_killers,
    order_moves,
    update_history,
    update_killers,
)
from ance.search.transposition import (
    EXACT,
    LOWER,
    UPPER,
    TranspositionTable,
    score_from_tt,
    score_to_tt,
)
from ance.search.types import (
    DEFAULT_BARE_GO_MOVETIME_MS,
    MAX_PLY,
    MATE_THRESHOLD,
    SearchContext,
    SearchResult,
)

DEFAULT_DEPTH = 3
NODE_POLL_INTERVAL = 512
SOFT_GATE_FRACTION = 0.5
MAX_QDEPTH = 8
DELTA_MARGIN = 200


class SearchAborted(Exception):
    """Raised when stop_flag is set during search."""


def _poll_stop(ctx: SearchContext) -> None:
    if ctx.counter[0] % NODE_POLL_INTERVAL != 0:
        return
    if ctx.stop_flag.is_set() or (
        ctx.deadline is not None and time.monotonic() >= ctx.deadline
    ):
        raise SearchAborted()


def _child_ctx(ctx: SearchContext, ply: int) -> SearchContext:
    return SearchContext(
        stop_flag=ctx.stop_flag,
        counter=ctx.counter,
        evaluator=ctx.evaluator,
        ply=ply,
        path_keys=ctx.path_keys,
        game_history_keys=ctx.game_history_keys,
        deadline=ctx.deadline,
        max_depth=ctx.max_depth,
        info_callback=ctx.info_callback,
        tt=ctx.tt,
        killers=ctx.killers,
        history=ctx.history,
    )


def _build_game_history_keys(board: chess.Board) -> set[int]:
    keys: set[int] = set()
    temp = board.copy(stack=True)
    keys.add(chess.polyglot.zobrist_hash(temp))
    while temp.move_stack:
        temp.pop()
        keys.add(chess.polyglot.zobrist_hash(temp))
    return keys


def _is_draw_position(pos: Position, ctx: SearchContext, key: int) -> bool:
    board = pos.board
    if key in ctx.path_keys or key in ctx.game_history_keys:
        return True
    if board.is_fifty_moves():
        return True
    if board.is_insufficient_material():
        return True
    return False


def _qsearch_moves(board: chess.Board, moves: list[chess.Move]) -> list[chess.Move]:
    noisy: list[chess.Move] = []
    for move in moves:
        if board.is_capture(move) or move.promotion == chess.QUEEN:
            noisy.append(move)
    return _mvv_lva_sort(noisy, board)


def _clamped_eval(ctx: SearchContext, pos: Position) -> int:
    raw = ctx.evaluator.evaluate(pos)
    bound = MATE_THRESHOLD - 1
    return max(-bound, min(bound, raw))


def quiescence_search(
    pos: Position,
    alpha: int,
    beta: int,
    ctx: SearchContext,
    qdepth: int = 0,
) -> int:
    ctx.counter[0] += 1
    _poll_stop(ctx)

    board = pos.board
    key = chess.polyglot.zobrist_hash(board)
    if _is_draw_position(pos, ctx, key):
        return 0

    ctx.path_keys.append(key)
    try:
        moves = pos.legal_moves()
        if not moves:
            if pos.is_check():
                return -(MATE - ctx.ply)
            return 0

        if pos.is_check():
            best = -MATE - 1
            child_ply = ctx.ply + 1
            for move in moves:
                board.push(move)
                try:
                    score = -quiescence_search(
                        pos,
                        -beta,
                        -alpha,
                        _child_ctx(ctx, child_ply),
                        qdepth + 1,
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

        if qdepth >= MAX_QDEPTH:
            return _clamped_eval(ctx, pos)

        stand_pat = _clamped_eval(ctx, pos)
        if stand_pat >= beta:
            return stand_pat
        if stand_pat > alpha:
            alpha = stand_pat

        for move in _qsearch_moves(board, moves):
            capture_value = _capture_value(board, move)
            if stand_pat + capture_value + DELTA_MARGIN < alpha:
                continue
            board.push(move)
            try:
                score = -quiescence_search(
                    pos,
                    -beta,
                    -alpha,
                    _child_ctx(ctx, ctx.ply + 1),
                    qdepth + 1,
                )
            finally:
                board.pop()
            if score > alpha:
                alpha = score
            if score >= beta:
                return score
        return alpha
    finally:
        ctx.path_keys.pop()


def negamax(
    pos: Position,
    depth: int,
    alpha: int,
    beta: int,
    ctx: SearchContext,
) -> int:
    ctx.counter[0] += 1
    _poll_stop(ctx)

    board = pos.board
    key = chess.polyglot.zobrist_hash(board)
    if _is_draw_position(pos, ctx, key):
        return 0

    # depth-0 handoff: quiescence_search owns path_keys for the qsearch subtree.
    if depth == 0:
        return quiescence_search(pos, alpha, beta, ctx)

    alpha_orig = alpha
    hash_move: chess.Move | None = None
    if ctx.tt is not None:
        hit = ctx.tt.probe(key)
        if hit is not None:
            tt_depth, tt_score, tt_flag, hash_move = hit
            if tt_depth >= depth:
                score = score_from_tt(tt_score, ctx.ply)
                if tt_flag == EXACT:
                    return score
                if tt_flag == LOWER and score >= beta:
                    return score
                if tt_flag == UPPER and score <= alpha:
                    return score

    ctx.path_keys.append(key)
    try:
        moves = pos.legal_moves()
        if not moves:
            if pos.is_check():
                return -(MATE - ctx.ply)
            return 0

        best = -MATE - 1
        best_move: chess.Move | None = None
        child_ply = ctx.ply + 1
        killers_at_ply = (
            ctx.killers[ctx.ply]
            if ctx.killers is not None and ctx.ply <= MAX_PLY
            else (None, None)
        )
        for move in order_moves(
            moves,
            board,
            hash_move,
            killers_at_ply,
            ctx.history,
        ):
            board.push(move)
            try:
                score = -negamax(
                    pos,
                    depth - 1,
                    -beta,
                    -alpha,
                    _child_ctx(ctx, child_ply),
                )
            finally:
                board.pop()
            if score > best:
                best = score
                best_move = move
            if score >= beta:
                if not board.is_capture(move) and move.promotion is None:
                    if ctx.killers is not None and ctx.ply <= MAX_PLY:
                        update_killers(ctx.killers[ctx.ply], move)
                    if ctx.history is not None:
                        update_history(
                            ctx.history,
                            int(board.turn),
                            move,
                            depth,
                        )
                break
            if score > alpha:
                alpha = score
        if ctx.tt is not None:
            flag = LOWER if best >= beta else UPPER if best <= alpha_orig else EXACT
            ctx.tt.store(
                key,
                depth,
                score_to_tt(best, ctx.ply),
                flag,
                best_move,
            )
        return best
    finally:
        ctx.path_keys.pop()


def _search_at_depth(
    pos: Position,
    depth: int,
    evaluator: Evaluator,
    stop_flag: threading.Event,
    game_history_keys: set[int],
    deadline: float | None,
    prior_best: chess.Move | None,
    tt: TranspositionTable | None,
    killers: list[list[chess.Move | None]],
    history: list[list[list[int]]],
) -> SearchResult:
    moves = pos.legal_moves()
    if prior_best is not None and prior_best in moves:
        moves = [prior_best] + [m for m in moves if m != prior_best]

    best_move: chess.Move | None = None
    best_score = -MATE - 1
    counter = [0]
    board = pos.board

    for move in moves:
        if stop_flag.is_set():
            raise SearchAborted()
        if deadline is not None and time.monotonic() >= deadline:
            raise SearchAborted()
        board.push(move)
        try:
            ctx = SearchContext(
                stop_flag=stop_flag,
                counter=counter,
                evaluator=evaluator,
                ply=1,
                path_keys=[],
                game_history_keys=game_history_keys,
                deadline=deadline,
                max_depth=depth,
                tt=tt,
                killers=killers,
                history=history,
            )
            score = -negamax(pos, depth - 1, -MATE - 1, MATE + 1, ctx)
        except SearchAborted:
            raise
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
        depth=depth,
        pv=[best_move] if best_move is not None else [],
        nodes=counter[0],
    )


def search_root(
    pos: Position,
    max_depth: int,
    evaluator: Evaluator,
    stop_flag: threading.Event,
    *,
    deadline: float | None = None,
    soft_budget: float | None = None,
    info_callback=None,
    tt: TranspositionTable | None = None,
    killers: list[list[chess.Move | None]] | None = None,
    history: list[list[list[int]]] | None = None,
) -> SearchResult:
    """Iterative-deepening root search with last-completed-depth retention."""
    if pos.has_no_legal_moves():
        return SearchResult(best_move=None, score=0, depth=0, pv=[], nodes=0)

    if killers is None:
        killers = new_killers()
    if history is None:
        history = new_history()

    game_history_keys = _build_game_history_keys(pos.board)
    last_completed: SearchResult | None = None
    prior_best: chess.Move | None = None
    total_nodes = 0
    start_time = time.monotonic()
    target_depth = min(max_depth, MAX_PLY)

    for depth in range(1, target_depth + 1):
        if stop_flag.is_set():
            break
        if deadline is not None and time.monotonic() >= deadline:
            break
        if (
            soft_budget is not None
            and last_completed is not None
            and time.monotonic() - start_time >= SOFT_GATE_FRACTION * soft_budget
        ):
            break
        try:
            result = _search_at_depth(
                pos,
                depth,
                evaluator,
                stop_flag,
                game_history_keys,
                deadline,
                prior_best,
                tt,
                killers,
                history,
            )
        except SearchAborted:
            break
        total_nodes += result.nodes
        result.nodes = total_nodes
        last_completed = result
        prior_best = result.best_move
        if info_callback is not None:
            elapsed_ms = max(int((time.monotonic() - start_time) * 1000), 1)
            nps = total_nodes * 1000 // elapsed_ms
            info_callback(result, nps)

    if last_completed is not None:
        return last_completed

    moves = pos.legal_moves()
    return SearchResult(
        best_move=moves[0],
        score=0,
        depth=0,
        pv=[moves[0]],
        nodes=total_nodes,
    )
