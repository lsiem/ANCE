"""Fixed-size Zobrist transposition table (D-01 through D-06).

Mate-score conversion belongs exclusively at this module boundary so stored
scores are node-relative while callers continue to use root-relative scores.
"""

from __future__ import annotations

import chess

from ance.search.types import MATE_THRESHOLD

EXACT, LOWER, UPPER = 0, 1, 2
TT_SIZE_POW2 = 1 << 20

TTEntry = tuple[int, int, int, int, chess.Move | None]
TTProbe = tuple[int, int, int, chess.Move | None]


class TranspositionTable:
    """Single-slot, depth-preferred transposition table.

    Entries retain the full key to reject index collisions (D-05). Tuple
    construction followed by one list-slot assignment is atomic under CPython's
    GIL, so a bounded-join stale UCI worker can only publish a well-formed entry;
    no hot-path lock is needed. A fully saturated default table may consume
    roughly 150-250 MB in CPython, acceptable within the project's 24 GB budget.
    """

    def __init__(self, size_pow2: int = TT_SIZE_POW2) -> None:
        if size_pow2 <= 0 or size_pow2 & (size_pow2 - 1):
            raise ValueError("transposition table size must be a positive power of two")
        self._mask = size_pow2 - 1
        self._entries: list[TTEntry | None] = [None] * size_pow2

    def probe(self, key: int) -> TTProbe | None:
        entry = self._entries[key & self._mask]
        if entry is None or entry[0] != key:
            return None
        return entry[1], entry[2], entry[3], entry[4]

    def store(
        self,
        key: int,
        depth: int,
        score: int,
        flag: int,
        best_move: chess.Move | None,
    ) -> None:
        index = key & self._mask
        existing = self._entries[index]
        if existing is None or depth >= existing[1]:
            self._entries[index] = (key, depth, score, flag, best_move)

    def clear(self) -> None:
        """Drop all entries by reallocating the fixed-size slot list (D-06)."""
        self._entries = [None] * (self._mask + 1)


def score_to_tt(score: int, ply: int) -> int:
    """Convert a root-relative score to a node-relative stored score."""
    if score > MATE_THRESHOLD:
        return score + ply
    if score < -MATE_THRESHOLD:
        return score - ply
    return score


def score_from_tt(tt_score: int, ply: int) -> int:
    """Convert a node-relative stored score back to the current root."""
    if tt_score > MATE_THRESHOLD:
        return tt_score - ply
    if tt_score < -MATE_THRESHOLD:
        return tt_score + ply
    return tt_score
