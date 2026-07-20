"""Quiet-position filtering for NNUE training samples (Phase 6 / P0).

Rules (Stockfish nnue-pytorch + arXiv:2412.17948):
- reject in-check
- reject when bestmove is a capture (smart fen skipping; needs UCI engine)
- reject when |static − qsearch| > margin (default 60 cp)
- reject early plies (default min_ply=8)
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass

import chess
import chess.engine

from ance.board.position import Position
from ance.eval.handcrafted import HandcraftedEval
from ance.search.negamax import quiescence_search
from ance.search.types import SearchContext
from training.progress import progress_bar

DEFAULT_QSEARCH_MARGIN = 60
DEFAULT_MIN_PLY = 8
DEFAULT_CAPTURE_SKIP_DEPTH = 6


@dataclass(frozen=True)
class QuietFilterStats:
    kept: int
    rejected_check: int
    rejected_early_ply: int
    rejected_capture_bestmove: int
    rejected_qsearch: int
    rejected_illegal: int

    @property
    def rejected(self) -> int:
        return (
            self.rejected_check
            + self.rejected_early_ply
            + self.rejected_capture_bestmove
            + self.rejected_qsearch
            + self.rejected_illegal
        )


def ply_from_fen(fen: str) -> int:
    """Fullmove-based ply estimate (side-to-move aware)."""
    fields = fen.split()
    if len(fields) < 6:
        return 0
    try:
        fullmove = max(1, int(fields[5]))
    except ValueError:
        return 0
    stm_is_black = fields[1] == "b"
    # After White's first move fullmove is still 1 with Black to move → ply 1.
    return (fullmove - 1) * 2 + (1 if stm_is_black else 0)


def _static_vs_qsearch_cp(board: chess.Board) -> tuple[int, int]:
    evaluator = HandcraftedEval()
    pos = Position(board)
    static_cp = int(evaluator.evaluate(pos))
    ctx = SearchContext(
        stop_flag=threading.Event(),
        counter=[0],
        evaluator=evaluator,
        ply=0,
        path_keys=[],
        game_history_keys=set(),
        deadline=None,
        max_depth=0,
    )
    q_cp = int(quiescence_search(pos, alpha=-50_000, beta=50_000, ctx=ctx))
    return static_cp, q_cp


def bestmove_is_capture(
    board: chess.Board,
    engine: chess.engine.SimpleEngine,
    *,
    depth: int = DEFAULT_CAPTURE_SKIP_DEPTH,
) -> bool:
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    pv = info.get("pv") or []
    if not pv:
        return False
    return board.is_capture(pv[0])


def is_quiet_fen(
    fen: str,
    *,
    min_ply: int = DEFAULT_MIN_PLY,
    qsearch_margin: int = DEFAULT_QSEARCH_MARGIN,
    engine: chess.engine.SimpleEngine | None = None,
    capture_skip_depth: int = DEFAULT_CAPTURE_SKIP_DEPTH,
    bestmove_capture_fn: Callable[[chess.Board], bool] | None = None,
) -> tuple[bool, str]:
    """Return (keep, reject_reason). reject_reason empty when kept."""
    try:
        board = chess.Board(fen)
    except ValueError:
        return False, "illegal"

    if board.is_check():
        return False, "check"

    if ply_from_fen(fen) < min_ply:
        return False, "early_ply"

    if bestmove_capture_fn is not None:
        if bestmove_capture_fn(board):
            return False, "capture_bestmove"
    elif engine is not None:
        if bestmove_is_capture(board, engine, depth=capture_skip_depth):
            return False, "capture_bestmove"

    static_cp, q_cp = _static_vs_qsearch_cp(board)
    if abs(static_cp - q_cp) > qsearch_margin:
        return False, "qsearch"

    return True, ""


def filter_quiet_samples(
    samples: list[dict],
    *,
    min_ply: int = DEFAULT_MIN_PLY,
    qsearch_margin: int = DEFAULT_QSEARCH_MARGIN,
    engine: chess.engine.SimpleEngine | None = None,
    capture_skip_depth: int = DEFAULT_CAPTURE_SKIP_DEPTH,
    bestmove_capture_fn: Callable[[chess.Board], bool] | None = None,
    skip_capture_filter: bool = False,
) -> tuple[list[dict], QuietFilterStats]:
    """Filter sample dicts that have a ``fen`` key."""
    kept: list[dict] = []
    rejected_check = 0
    rejected_early_ply = 0
    rejected_capture = 0
    rejected_qsearch = 0
    rejected_illegal = 0

    capture_fn = None if skip_capture_filter else bestmove_capture_fn
    eng = None if skip_capture_filter else engine

    for sample in progress_bar(samples, desc="quiet filter", unit="fen"):
        fen = sample.get("fen")
        if not fen:
            rejected_illegal += 1
            continue
        ok, reason = is_quiet_fen(
            fen,
            min_ply=min_ply,
            qsearch_margin=qsearch_margin,
            engine=eng,
            capture_skip_depth=capture_skip_depth,
            bestmove_capture_fn=capture_fn,
        )
        if ok:
            kept.append(sample)
            continue
        if reason == "check":
            rejected_check += 1
        elif reason == "early_ply":
            rejected_early_ply += 1
        elif reason == "capture_bestmove":
            rejected_capture += 1
        elif reason == "qsearch":
            rejected_qsearch += 1
        else:
            rejected_illegal += 1

    stats = QuietFilterStats(
        kept=len(kept),
        rejected_check=rejected_check,
        rejected_early_ply=rejected_early_ply,
        rejected_capture_bestmove=rejected_capture,
        rejected_qsearch=rejected_qsearch,
        rejected_illegal=rejected_illegal,
    )
    return kept, stats


def enforce_corpus_mix(
    samples: list[dict],
    *,
    max_fresh_share: float = 0.10,
    min_has_result_rate: float = 0.50,
    strength_corpus: bool = False,
) -> list[dict]:
    """Cap fresh share and require result coverage for strength runs."""
    if not samples:
        raise RuntimeError("merged sample set is empty after quiet filter")

    fresh = [s for s in samples if s.get("source") == "fresh"]
    non_fresh = [s for s in samples if s.get("source") != "fresh"]
    if fresh and 0 <= max_fresh_share < 1:
        # Keep all non-fresh; allow fresh up to share of the *final* mix.
        if non_fresh:
            max_fresh = int(
                len(non_fresh) * max_fresh_share / (1.0 - max_fresh_share)
            )
        else:
            max_fresh = 0 if strength_corpus else len(fresh)
        if len(fresh) > max_fresh:
            fresh = fresh[: max(0, max_fresh)]
        samples = non_fresh + fresh

    n_result = sum(1 for s in samples if s.get("game_result") is not None)
    rate = n_result / len(samples) if samples else 0.0
    if strength_corpus and rate < min_has_result_rate:
        raise RuntimeError(
            f"strength corpus requires has_result rate ≥ {min_has_result_rate:.0%}, "
            f"got {rate:.1%} ({n_result}/{len(samples)}). "
            "Provide --lichess-zst with Result+[%eval] games "
            "(e.g. download a month dump from https://database.lichess.org/)."
        )
    return samples
