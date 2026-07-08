"""Search context and result types (SRCH-02+)."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Callable

import chess

from ance.eval.base import Evaluator

DEFAULT_BARE_GO_MOVETIME_MS = 2000
MAX_PLY = 64


@dataclass
class SearchContext:
    stop_flag: threading.Event
    counter: list[int]
    evaluator: Evaluator
    ply: int = 0
    path_keys: list[int] = field(default_factory=list)
    game_history_keys: set[int] = field(default_factory=set)
    deadline: float | None = None
    max_depth: int = 0
    info_callback: Callable[..., None] | None = None


@dataclass
class SearchResult:
    best_move: chess.Move | None
    score: int
    depth: int
    pv: list[chess.Move] = field(default_factory=list)
    nodes: int = 0
