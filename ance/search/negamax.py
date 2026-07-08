"""Fail-soft alpha-beta negamax with ply-adjusted mate scoring (SRCH-02).

Extends the Phase 1 fixed-depth skeleton with alpha-beta pruning, ply-adjusted
mate propagation, deterministic root move selection (D-10), and quiescence
search at the horizon (SRCH-04). Iterative deepening and draw detection land
in later Phase 2 plans.

This module imports only the `Evaluator` Protocol from `ance.eval.base` --
never any concrete evaluator class.
"""

from __future__ import annotations

import threading

import chess

from ance.board.position import Position
from ance.eval.base import MATE, Evaluator
from ance.search.types import SearchContext, SearchResult

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
    """Raised by `negamax` when a sampled node-count poll finds `stop_flag`
    set. Caught by `search_root`, which returns the best root move found
    before the abort."""


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


def quiescence_search(
    pos: Position,
    alpha: int,
    beta: int,
    ctx: SearchContext,
    qdepth: int = 0,
) -> int:
    """Stand-pat + capture/queen-promo qsearch with delta pruning (D-02, D-03)."""
    ctx.counter[0] += 1
    _poll_stop(ctx)

    if qdepth >= MAX_QDEPTH:
        return ctx.evaluator.evaluate(pos)

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

    stand_pat = ctx.evaluator.evaluate(pos)
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
    """Fail-soft alpha-beta negamax. Returns centipawns, side-to-move relative."""
    ctx.counter[0] += 1
    _poll_stop(ctx)

    moves = pos.legal_moves()
    if not moves:
        if pos.is_check():
            return -(MATE - ctx.ply)
        return 0

    if depth == 0:
        if pos.is_check():
            return quiescence_search(pos, alpha, beta, ctx)
        return quiescence_search(pos, alpha, beta, ctx)

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
