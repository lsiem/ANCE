"""Fresh Stockfish labeling via normalized UCI scores (TRN-01, D-02)."""

from __future__ import annotations

import json
import time
from pathlib import Path

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


def run_labeling_resumable(
    stockfish_path: str,
    fens: list[str],
    depth: int,
    *,
    progress_path: str | Path,
    live_path: str | Path | None = None,
    save_every: int = 50,
) -> list[dict]:
    """Label FENs with JSON progress resume (for multi-hour 1M-scale runs)."""
    progress = Path(progress_path)
    live = Path(live_path) if live_path else None
    results: list[dict] = []
    if progress.exists():
        results = json.loads(progress.read_text(encoding="utf-8"))
    start_index = len(results)
    if start_index >= len(fens):
        return results[: len(fens)]

    started = time.monotonic()
    with chess.engine.SimpleEngine.popen_uci(stockfish_path) as engine:
        for index in range(start_index, len(fens)):
            fen = fens[index]
            label = label_position(engine, fen, depth)
            results.append(label)
            done = index + 1
            if live is not None:
                elapsed = time.monotonic() - started
                rate = (done - start_index) / elapsed if elapsed > 0 else 0.0
                remaining = len(fens) - done
                live.parent.mkdir(parents=True, exist_ok=True)
                live.write_text(
                    json.dumps(
                        {
                            "phase": "labeling",
                            "fen": fen,
                            "depth": depth,
                            "done": done,
                            "total": len(fens),
                            "rate_per_s": rate,
                            "eta_s": remaining / rate if rate > 0 else None,
                            "updated_utc": time.strftime(
                                "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                            ),
                        },
                        indent=2,
                    )
                    + "\n",
                    encoding="utf-8",
                )
            if done % save_every == 0 or done == len(fens):
                progress.parent.mkdir(parents=True, exist_ok=True)
                tmp = progress.with_suffix(".tmp")
                tmp.write_text(json.dumps(results) + "\n", encoding="utf-8")
                tmp.replace(progress)
    return results


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
    *,
    progress_path: str | None = None,
    live_path: str | None = None,
) -> list[dict]:
    if progress_path is not None:
        results = run_labeling_resumable(
            stockfish_path,
            fens,
            depth,
            progress_path=progress_path,
            live_path=live_path,
        )
    else:
        results = run_labeling(stockfish_path, fens, depth)
    record_event(
        manifest_path,
        event="fresh_labeling",
        command=record_labeling_command(stockfish_path, depth),
        depth=depth,
        n_positions=len(fens),
    )
    return results
