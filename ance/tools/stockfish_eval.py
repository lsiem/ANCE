"""Local Stockfish evaluation for live dashboards.

Uses the system ``stockfish`` binary via python-chess UCI. Scores are
white-relative centipawns (or mate distance) for a chess.com-style eval bar.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

import chess
import chess.engine


def find_stockfish(explicit: str | Path | None = None) -> str | None:
    if explicit is not None:
        path = Path(explicit)
        return str(path) if path.is_file() and os.access(path, os.X_OK) else None
    env = os.environ.get("ANCE_STOCKFISH")
    if env:
        path = Path(env)
        if path.is_file() and os.access(path, os.X_OK):
            return str(path)
    which = shutil.which("stockfish")
    return which


@dataclass(frozen=True)
class SfEval:
    """White-relative evaluation for UI display."""

    cp: int | None
    mate: int | None
    depth: int
    bestmove_uci: str | None
    pv_san: list[str]
    white_win_pct: float  # 0..100, chess.com-style bar fill from white's POV
    label: str  # e.g. "+1.2", "0.0", "M3", "#-2"

    def as_dict(self) -> dict:
        return {
            "cp": self.cp,
            "mate": self.mate,
            "depth": self.depth,
            "bestmove_uci": self.bestmove_uci,
            "pv_san": list(self.pv_san),
            "white_win_pct": self.white_win_pct,
            "label": self.label,
        }


def white_win_pct_from_cp(cp: int) -> float:
    """Map white-relative cp to a 0..100 win% bar (logistic, ~chess.com feel)."""
    # 400 cp ≈ 90% — same scale as common Elo/score mappings.
    from math import exp

    # Clamp extreme values so the bar never fully disappears.
    x = max(-1500, min(1500, cp)) / 400.0
    p = 1.0 / (1.0 + exp(-x))
    return 100.0 * p


def white_win_pct_from_mate(mate: int) -> float:
    """Mate-in-N for white (>0) or black (<0)."""
    if mate > 0:
        return 99.5
    if mate < 0:
        return 0.5
    return 50.0


def format_eval_label(cp: int | None, mate: int | None) -> str:
    if mate is not None:
        if mate > 0:
            return f"#{mate}"
        if mate < 0:
            return f"#-{abs(mate)}"
        return "#0"
    if cp is None:
        return "—"
    pawns = cp / 100.0
    if abs(pawns) < 0.05:
        return "0.0"
    return f"{pawns:+.1f}"


class StockfishAnalyzer:
    """Long-lived Stockfish process for repeated position evals."""

    def __init__(
        self,
        binary: str | None = None,
        *,
        depth: int = 14,
        movetime_ms: int | None = None,
        threads: int = 1,
        hash_mb: int = 64,
    ) -> None:
        path = find_stockfish(binary)
        if path is None:
            raise FileNotFoundError(
                "stockfish binary not found; install it or set ANCE_STOCKFISH"
            )
        self.binary = path
        self.depth = depth
        self.movetime_ms = movetime_ms
        self._engine = chess.engine.SimpleEngine.popen_uci(path)
        self._engine.configure({"Threads": threads, "Hash": hash_mb})

    def close(self) -> None:
        with __import__("contextlib").suppress(Exception):
            self._engine.quit()

    def __enter__(self) -> StockfishAnalyzer:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def evaluate(self, fen: str) -> SfEval:
        board = chess.Board(fen)
        if self.movetime_ms is not None:
            limit = chess.engine.Limit(time=self.movetime_ms / 1000.0)
        else:
            limit = chess.engine.Limit(depth=self.depth)

        info = self._engine.analyse(board, limit, multipv=1)
        if isinstance(info, list):
            info = info[0]

        score = info["score"].white()
        cp: int | None
        mate: int | None
        if score.is_mate():
            mate = score.mate()
            cp = None
            pct = white_win_pct_from_mate(mate or 0)
        else:
            mate = None
            cp = score.score(mate_score=100000)
            assert cp is not None
            pct = white_win_pct_from_cp(cp)

        pv = info.get("pv") or []
        pv_san: list[str] = []
        tmp = board.copy(stack=False)
        for move in pv[:6]:
            try:
                pv_san.append(tmp.san(move))
                tmp.push(move)
            except ValueError:
                break

        best = pv[0].uci() if pv else None
        depth = int(info.get("depth") or self.depth)
        return SfEval(
            cp=cp,
            mate=mate,
            depth=depth,
            bestmove_uci=best,
            pv_san=pv_san,
            white_win_pct=pct,
            label=format_eval_label(cp, mate),
        )
