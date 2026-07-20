"""Fresh Stockfish labeling via normalized UCI scores (TRN-01, D-02).

For large unrelated FEN sets, prefer many single-threaded Stockfish workers
over one multi-threaded engine (see Stockfish discussion #6610).

Workers are Python threads, each owning one Stockfish subprocess. Search time
is spent in those C++ processes (GIL is released on UCI I/O), so this scales
with CPU cores without ProcessPool spawn overhead.
"""

from __future__ import annotations

import json
import os
import queue
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import chess
import chess.engine

from training.progress import progress_bar
from training.run_manifest import record_event

_DEFAULT_HASH_MB = 64
_DEFAULT_THREADS = 1


def default_label_workers() -> int:
    """Use all logical CPUs; each worker runs Threads=1 Stockfish."""
    return max(1, os.cpu_count() or 1)


def configure_engine(
    engine: chess.engine.SimpleEngine,
    *,
    threads: int = _DEFAULT_THREADS,
    hash_mb: int = _DEFAULT_HASH_MB,
) -> None:
    engine.configure({"Threads": threads, "Hash": hash_mb})


def label_position(
    engine: chess.engine.SimpleEngine, fen: str, depth: int
) -> dict[str, str | int | None]:
    board = chess.Board(fen)
    info = engine.analyse(board, chess.engine.Limit(depth=depth))
    score = info["score"].relative
    if score.is_mate():
        return {"fen": fen, "mate": score.mate(), "cp": None}
    return {"fen": fen, "mate": None, "cp": score.score()}


def _open_engine(
    stockfish_path: str,
    *,
    threads: int,
    hash_mb: int,
) -> chess.engine.SimpleEngine:
    engine = chess.engine.SimpleEngine.popen_uci(stockfish_path)
    configure_engine(engine, threads=threads, hash_mb=hash_mb)
    return engine


def _close_engines(engines: list[chess.engine.SimpleEngine]) -> None:
    for engine in engines:
        try:
            engine.quit()
        except Exception:
            pass


def _load_progress(path: Path) -> list[dict]:
    """Load progress from a JSON array (legacy) or JSONL (append-friendly)."""
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if text[0] == "[":
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError(f"progress file must be a JSON list: {path}")
        return data
    results: list[dict] = []
    lines = text.splitlines()
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            if i == len(lines) - 1:
                break
            raise ValueError(f"invalid JSONL in progress file: {path}") from exc
        if not isinstance(row, dict):
            raise ValueError(f"progress JSONL rows must be objects: {path}")
        results.append(row)
    return results


def _ensure_jsonl_progress(path: Path, results: list[dict]) -> None:
    """Rewrite legacy JSON-array progress as JSONL once, for O(1) appends."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        text = path.read_text(encoding="utf-8").lstrip()
        if text and text[0] != "[":
            return
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        for row in results:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")
    tmp.replace(path)


def _append_progress_rows(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, separators=(",", ":")) + "\n")


def _write_live(
    live: Path,
    *,
    fen: str,
    depth: int,
    done: int,
    total: int,
    rate: float,
    workers: int,
) -> None:
    remaining = total - done
    live.parent.mkdir(parents=True, exist_ok=True)
    tmp_live = live.with_suffix(live.suffix + ".tmp")
    tmp_live.write_text(
        json.dumps(
            {
                "phase": "labeling",
                "fen": fen,
                "depth": depth,
                "done": done,
                "total": total,
                "rate_per_s": rate,
                "eta_s": remaining / rate if rate > 0 else None,
                "workers": workers,
                "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp_live.replace(live)


def _label_indexed(
    stockfish_path: str,
    indexed: list[tuple[int, str]],
    depth: int,
    *,
    workers: int,
    threads: int,
    hash_mb: int,
    on_label: Callable[[int, dict], None] | None = None,
) -> list[dict]:
    """Label indexed FENs; invoke ``on_label(index, label)`` in FEN order."""
    if not indexed:
        return []

    workers = max(1, min(workers, len(indexed)))
    if workers == 1:
        with _open_engine(
            stockfish_path, threads=threads, hash_mb=hash_mb
        ) as engine:
            ordered: list[dict] = []
            for index, fen in indexed:
                label = label_position(engine, fen, depth)
                ordered.append(label)
                if on_label is not None:
                    on_label(index, label)
            return ordered

    engines = [
        _open_engine(stockfish_path, threads=threads, hash_mb=hash_mb)
        for _ in range(workers)
    ]
    engine_pool: queue.Queue[chess.engine.SimpleEngine] = queue.Queue()
    for engine in engines:
        engine_pool.put(engine)

    def _work(item: tuple[int, str]) -> tuple[int, dict]:
        index, fen = item
        engine = engine_pool.get()
        try:
            return index, label_position(engine, fen, depth)
        finally:
            engine_pool.put(engine)

    try:
        # map() yields in input order so resume/JSONL stay contiguous.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            ordered = []
            for index, label in pool.map(_work, indexed, chunksize=8):
                ordered.append(label)
                if on_label is not None:
                    on_label(index, label)
            return ordered
    finally:
        _close_engines(engines)


def run_labeling(
    stockfish_path: str,
    fens: list[str],
    depth: int,
    *,
    workers: int = 1,
    threads: int = _DEFAULT_THREADS,
    hash_mb: int = _DEFAULT_HASH_MB,
) -> list[dict]:
    """Label FENs; order matches ``fens``. ``workers=1`` stays single-engine."""
    indexed = list(enumerate(fens))
    return _label_indexed(
        stockfish_path,
        indexed,
        depth,
        workers=workers,
        threads=threads,
        hash_mb=hash_mb,
    )


def run_labeling_resumable(
    stockfish_path: str,
    fens: list[str],
    depth: int,
    *,
    progress_path: str | Path,
    live_path: str | Path | None = None,
    save_every: int = 50,
    workers: int = 1,
    threads: int = _DEFAULT_THREADS,
    hash_mb: int = _DEFAULT_HASH_MB,
) -> list[dict]:
    """Label FENs with JSONL progress resume (for multi-hour 1M-scale runs)."""
    progress = Path(progress_path)
    live = Path(live_path) if live_path else None
    workers = max(1, workers)
    results = _load_progress(progress)
    start_index = len(results)
    if start_index >= len(fens):
        return results[: len(fens)]

    _ensure_jsonl_progress(progress, results)

    started = time.monotonic()
    flush_buffer: list[dict] = []
    last_fen = fens[start_index]
    done = start_index
    bar = progress_bar(
        total=len(fens),
        desc=f"stockfish d{depth}",
        unit="fen",
        initial=start_index,
    )

    def _flush(force: bool = False) -> None:
        nonlocal flush_buffer
        if not flush_buffer:
            return
        if not force and len(flush_buffer) < save_every:
            return
        _append_progress_rows(progress, flush_buffer)
        flush_buffer = []

    def _on_label(_index: int, label: dict) -> None:
        nonlocal last_fen, done
        results.append(label)
        flush_buffer.append(label)
        last_fen = str(label["fen"])
        done += 1
        bar.update(1)
        _flush(force=False)
        if live is not None:
            elapsed = time.monotonic() - started
            labeled = done - start_index
            rate = labeled / elapsed if elapsed > 0 else 0.0
            _write_live(
                live,
                fen=last_fen,
                depth=depth,
                done=done,
                total=len(fens),
                rate=rate,
                workers=workers,
            )
            bar.set_postfix(rate=f"{rate:.1f}/s", workers=workers)
        if done == len(fens):
            _flush(force=True)

    remaining = [(i, fens[i]) for i in range(start_index, len(fens))]
    try:
        _label_indexed(
            stockfish_path,
            remaining,
            depth,
            workers=workers,
            threads=threads,
            hash_mb=hash_mb,
            on_label=_on_label,
        )
    finally:
        bar.close()
    return results


def run_depth_benchmark(
    stockfish_path: str,
    fens: list[str],
    candidate_depths: list[int],
    *,
    workers: int = 1,
    threads: int = _DEFAULT_THREADS,
    hash_mb: int = _DEFAULT_HASH_MB,
) -> dict[int, float]:
    subset = fens[:20]
    rates: dict[int, float] = {}
    for depth in candidate_depths:
        start = time.perf_counter()
        run_labeling(
            stockfish_path,
            subset,
            depth,
            workers=workers,
            threads=threads,
            hash_mb=hash_mb,
        )
        elapsed = time.perf_counter() - start
        rates[depth] = len(subset) / elapsed if elapsed > 0 else 0.0
    return rates


def record_labeling_command(
    stockfish_path: str,
    depth: int,
    *,
    workers: int = 1,
    threads: int = _DEFAULT_THREADS,
    hash_mb: int = _DEFAULT_HASH_MB,
) -> str:
    return (
        f"{stockfish_path} -- chess.engine.SimpleEngine.analyse(depth={depth})"
        f" workers={workers} Threads={threads} Hash={hash_mb}"
    )


def run_and_record_labeling(
    stockfish_path: str,
    fens: list[str],
    depth: int,
    manifest_path: str,
    *,
    progress_path: str | None = None,
    live_path: str | None = None,
    workers: int = 1,
    threads: int = _DEFAULT_THREADS,
    hash_mb: int = _DEFAULT_HASH_MB,
) -> list[dict]:
    if progress_path is not None:
        results = run_labeling_resumable(
            stockfish_path,
            fens,
            depth,
            progress_path=progress_path,
            live_path=live_path,
            workers=workers,
            threads=threads,
            hash_mb=hash_mb,
        )
    else:
        results = run_labeling(
            stockfish_path,
            fens,
            depth,
            workers=workers,
            threads=threads,
            hash_mb=hash_mb,
        )
    record_event(
        manifest_path,
        event="fresh_labeling",
        command=record_labeling_command(
            stockfish_path,
            depth,
            workers=workers,
            threads=threads,
            hash_mb=hash_mb,
        ),
        depth=depth,
        n_positions=len(fens),
        workers=workers,
        threads=threads,
        hash_mb=hash_mb,
    )
    return results
