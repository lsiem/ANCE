"""Capture the pre-TT Phase 3 search baseline for D-20/D-21 comparisons."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import platform
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any

import chess

from ance.board.position import Position
from ance.eval.handcrafted import HandcraftedEval
from ance.search.negamax import search_root
from ance.search.types import MAX_PLY


DEFAULT_OUTPUT = Path(
    ".planning/phases/03-search-acceleration-time-management/03-BASELINE.json"
)

BASELINE_FENS: list[tuple[str, str]] = [
    ("startpos", chess.STARTING_FEN),
    (
        "kiwipete",
        "r3k2r/p1ppqpb1/bn2pnp1/3PN3/1p2P3/2N2Q1p/PPPBBPPP/R3K2R w KQkq - 0 1",
    ),
    (
        "italian",
        "r1bqkbnr/pppp1ppp/2n5/4p3/2B1P3/5N2/PPPP1PPP/RNBQK2R b KQkq - 0 3",
    ),
    (
        "rook_endgame",
        "8/2p5/3p4/KP5r/1R3p1k/8/4P1P1/8 w - - 0 1",
    ),
    ("hanging_queen", "4k3/8/8/4q3/8/8/8/4R3 w - - 0 1"),
    ("queen_mate", "6k1/5ppp/8/8/8/8/8/6KQ w - - 0 1"),
]

# Kiwipete's Phase 2 search does not finish depth 3 within the 900-second
# evidence watchdog with HandcraftedEval. Keep it as the timed branching
# stress case, but use depth 2 for its reproducible node-count comparison.
FIXED_DEPTH_OVERRIDES: dict[str, int] = {"kiwipete": 2}


class BaselineBudgetExceeded(TimeoutError):
    """Raised when the collector exceeds its overall watchdog budget."""


def _utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    """Atomically replace *path* and remove a torn sibling temp on failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _ensure_budget(deadline: float) -> None:
    if time.monotonic() >= deadline:
        raise BaselineBudgetExceeded("overall baseline collector budget exceeded")


def collect_baseline(
    *,
    movetime_ms: int,
    fixed_depth: int,
    budget_seconds: float,
) -> dict[str, Any]:
    """Measure timed and deterministic searches from fresh state per FEN."""
    started = time.monotonic()
    budget_deadline = started + budget_seconds
    active_stop: list[threading.Event | None] = [None]

    def expire_active_search() -> None:
        stop_flag = active_stop[0]
        if stop_flag is not None:
            stop_flag.set()

    watchdog = threading.Timer(budget_seconds, expire_active_search)
    watchdog.daemon = True
    watchdog.start()
    positions: dict[str, Any] = {}
    evaluator = HandcraftedEval()
    try:
        for case_id, fen in BASELINE_FENS:
            _ensure_budget(budget_deadline)
            pos = Position(chess.Board(fen))
            case_fixed_depth = FIXED_DEPTH_OVERRIDES.get(case_id, fixed_depth)

            timed_stop = threading.Event()
            active_stop[0] = timed_stop
            timed_started = time.monotonic()
            timed_result = search_root(
                pos,
                max_depth=MAX_PLY,
                evaluator=evaluator,
                stop_flag=timed_stop,
                deadline=min(
                    timed_started + movetime_ms / 1000,
                    budget_deadline,
                ),
            )
            timed_ended = time.monotonic()
            _ensure_budget(budget_deadline)

            fixed_stop = threading.Event()
            active_stop[0] = fixed_stop
            fixed_started = time.monotonic()
            fixed_result = search_root(
                Position(chess.Board(fen)),
                max_depth=case_fixed_depth,
                evaluator=evaluator,
                stop_flag=fixed_stop,
            )
            fixed_ended = time.monotonic()
            _ensure_budget(budget_deadline)

            positions[case_id] = {
                "fen": fen,
                "timed": {
                    "completed_depth": timed_result.depth,
                    "nodes": timed_result.nodes,
                    "elapsed_seconds": max(0.0, timed_ended - timed_started),
                },
                "fixed_depth": {
                    "nodes": fixed_result.nodes,
                    "best_move": (
                        fixed_result.best_move.uci()
                        if fixed_result.best_move is not None
                        else ""
                    ),
                    "depth": fixed_result.depth,
                    "elapsed_seconds": max(0.0, fixed_ended - fixed_started),
                },
            }
    finally:
        active_stop[0] = None
        watchdog.cancel()

    return {
        "schema_version": 1,
        "git_commit": _git_commit(),
        "captured_utc": _utc_now(),
        "parameters": {
            "movetime_ms": movetime_ms,
            "fixed_depth": fixed_depth,
            "fixed_depth_overrides": FIXED_DEPTH_OVERRIDES,
            "evaluator": "handcrafted",
            "python": platform.python_version(),
        },
        "positions": positions,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--movetime-ms", type=int, default=2000)
    parser.add_argument("--fixed-depth", type=int, default=4)
    parser.add_argument("--budget-seconds", type=float, default=900)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.movetime_ms <= 0 or args.fixed_depth <= 0 or args.budget_seconds <= 0:
        print("error: movetime, depth, and budget must be positive", file=sys.stderr)
        return 2
    try:
        report = collect_baseline(
            movetime_ms=args.movetime_ms,
            fixed_depth=args.fixed_depth,
            budget_seconds=args.budget_seconds,
        )
        atomic_write_json(args.output, report)
    except (BaselineBudgetExceeded, OSError) as exc:
        temporary = args.output.with_name(args.output.name + ".tmp")
        if temporary.exists():
            temporary.unlink()
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
