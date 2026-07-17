"""Fresh Stockfish labeling via normalized UCI scores (TRN-01, D-02)."""

from __future__ import annotations

import time

import chess
import chess.engine

from training.run_manifest import record_event


def label_position(
    engine: chess.engine.SimpleEngine, fen: str, depth: int
) -> dict[str, str | int | None]:
    board = chess.Board(fen)
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].relative
    if score.is_mate():
        return {"fen": fen, "mate": score.mate(), "cp": None}
    return {"fen": fen, "mate": None, "cp": score.score()}


def run_labeling(stockfish_path: str, fens: list[str], depth: int) -> list[dict]:
    with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
        return [label_position(engine, fen, depth) for fen in fens]


def run_depth_benchmark(
    stockfish_path: str,
    fens: list[str],
    candidate_depths: list[int],
) -> dict[int, float]:
    subset = fens[:20]
    rates: dict[int, float] = {}
    for depth in candidate_depths:
        start = time.perf_counter()
        run_labeling(stockfish_path, subset, depth)
        elapsed = time.perf_counter() - start
        rates[depth] = len(subset) / elapsed if elapsed > 0 else 0.0
    return rates


def record_labeling_command(stockfish_path: str, depth: int) -> str:
    return f"{stockfish_path} -- chess.engine.SimpleEngine.analyse(depth={depth})"


def run_and_record_labeling(
    stockfish_path: str,
    fens: list[str],
    depth: int,
    manifest_path: str,
) -> list[dict]:
    results = run_labeling(stockfish_path, fens, depth)
    record_event(
        manifest_path,
        event="fresh_labeling",
        command=record_labeling_command(stockfish_path, depth),
        depth=depth,
        n_positions=len(fens),
    )
    return results
