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
from ance.search.types import (
    DEFAULT_BARE_GO_MOVETIME_MS,
    MAX_PLY,
    MATE_THRESHOLD,
    SearchContext,
    SearchResult,
)

DEFAULT_DEPTH = 3
NODE_POLL_INTERVAL = 2048
MAX_QDEPTH = 8
DELTA_MARGIN = 200

_MVV_LVA = {
    chess.PAWN: 100,
    chess.KNIGHT: 320,
    chess.BISHOP: 330,
    chess.ROOK: 500,
    chess.QUEEN: 900,
    chess.KING: 10000,
}


class SearchAborted(Exception):
    """Raised when stop_flag is set during search."""


def _poll_stop(ctx: SearchContext) -> None:
    if ctx.counter[0] % NODE_POLL_INTERVAL == 0 and ctx.stop_flag.is_set():
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
    )


def _build_game_history_keys(board: chess.Board) -> set[int]:
    keys: set[int] = set()
    temp = board.copy(stack=False)
    keys.add(chess.polyglot.zobrist_hash(temp))
    while temp.move_stack:
        temp.pop()
        keys.add(chess.polyglot.zobrist_hash(temp))
    return keys


def _is_draw_position(pos: Position, ctx: SearchContext) -> bool:
    board = pos.board
    key = chess.polyglot.zobrist_hash(board)
    if key in ctx.path_keys or key in ctx.game_history_keys:
        return True
    if board.is_fifty_moves():
        return True
    if board.is_insufficient_material():
        return True
    return False


def _capture_value(board: chess.Board, move: chess.Move) -> int:
    if board.is_en_passant(move):
        return _MVV_LVA[chess.PAWN]
    if move.promotion is not None:
        return _MVV_LVA[move.promotion]
    piece = board.piece_at(move.to_square)
    return _MVV_LVA[piece.piece_type] if piece is not None else 0


def _mvv_lva_sort(moves: list[chess.Move], board: chess.Board) -> list[chess.Move]:
    def key(move: chess.Move) -> tuple[int, int]:
        victim = _capture_value(board, move)
        attacker_piece = board.piece_at(move.from_square)
        attacker = _MVV_LVA[attacker_piece.piece_type] if attacker_piece else 0
        return (victim, -attacker)

    return sorted(moves, key=key, reverse=True)


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

    if qdepth >= MAX_QDEPTH:
        return _clamped_eval(ctx, pos)

    board = pos.board
    if pos.is_check():
        moves = pos.legal_moves()
        if not moves:
            return -(MATE - ctx.ply)
        best = -MATE - 1
        child_ply = ctx.ply + 1
        for move in moves:
            board.push(move)
            try:
                score = -quiescence_search(
                    pos, -beta, -alpha, _child_ctx(ctx, child_ply), qdepth + 1
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

    stand_pat = _clamped_eval(ctx, pos)
    if stand_pat >= beta:
        return stand_pat
    if stand_pat > alpha:
        alpha = stand_pat

    for move in _qsearch_moves(board, pos.legal_moves()):
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
    if _is_draw_position(pos, ctx):
        return 0

    ctx.path_keys.append(chess.polyglot.zobrist_hash(board))
    try:
        moves = pos.legal_moves()
        if not moves:
            if pos.is_check():
                return -(MATE - ctx.ply)
            return 0

        if depth == 0:
            return quiescence_search(pos, alpha, beta, ctx)

        best = -MATE - 1
        child_ply = ctx.ply + 1
        for move in moves:
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
            if score >= beta:
                return score
            if score > alpha:
                alpha = score
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
    info_callback,
    nodes_at_start: int,
    start_time: float,
) -> SearchResult:
    moves = pos.legal_moves()
    if prior_best is not None and prior_best in moves:
        moves = [prior_best] + [m for m in moves if m != prior_best]

    best_move: chess.Move | None = None
    best_score = -MATE - 1
    counter = [nodes_at_start]
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
                info_callback=info_callback,
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

    result = SearchResult(
        best_move=best_move,
        score=best_score,
        depth=depth,
        pv=[best_move] if best_move is not None else [],
        nodes=counter[0],
    )
    if info_callback is not None:
        elapsed_ms = max(int((time.monotonic() - start_time) * 1000), 1)
        nps = result.nodes * 1000 // elapsed_ms
        info_callback(result, nps)
    return result


def search_root(
    pos: Position,
    max_depth: int,
    evaluator: Evaluator,
    stop_flag: threading.Event,
    *,
    deadline: float | None = None,
    info_callback=None,
) -> SearchResult:
    """Iterative-deepening root search with last-completed-depth retention."""
    if pos.has_no_legal_moves():
        return SearchResult(best_move=None, score=0, depth=0, pv=[], nodes=0)

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
        try:
            result = _search_at_depth(
                pos,
                depth,
                evaluator,
                stop_flag,
                game_history_keys,
                deadline,
                prior_best,
                info_callback,
                total_nodes,
                start_time,
            )
        except SearchAborted:
            break
        last_completed = result
        prior_best = result.best_move
        total_nodes += result.nodes

    if last_completed is not None:
        last_completed.nodes = total_nodes
        return last_completed

    moves = pos.legal_moves()
    return SearchResult(
        best_move=moves[0],
        score=0,
        depth=0,
        pv=[moves[0]],
        nodes=total_nodes,
    )
