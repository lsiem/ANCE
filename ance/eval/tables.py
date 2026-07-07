"""Pinned Michniewski Simplified Evaluation Function piece-square tables
(D-05, EVAL-02).

Transcribed verbatim from 01-RESEARCH.md's "Appendix: Simplified
Evaluation Function Tables (pinned)" -- the single in-repo source of
truth for every literal value (fetched from chessprogramming.org at
planning time, not re-fetched here).

Each table is a flat 64-tuple indexed with python-chess's
``chess.square(file, rank)`` convention (index 0 = a1, index 7 = h1,
index 56 = a8, index 63 = h8). The appendix prints each table with rank 8
first and rank 1 last (the standard "board diagram" layout) -- the
opposite row order from this module's tuple indexing, so the row order is
reversed here during transcription: the appendix's last printed row
(rank 1) becomes indices 0..7, and its first printed row (rank 8) becomes
indices 56..63.

A Black piece on the same physical square looks up
``TABLE[chess.square_mirror(square)]`` -- standard PST-mirroring
convention, applied in ``ance/eval/handcrafted.py``, not here.
"""

from __future__ import annotations

# fmt: off
PAWN_PST: tuple[int, ...] = (
    0,  0,  0,  0,  0,  0,  0,  0,   # rank 1
    5, 10, 10, -20, -20, 10, 10,  5,  # rank 2
    5, -5, -10,  0,   0, -10, -5,  5,  # rank 3
    0,  0,  0, 20,  20,  0,  0,  0,   # rank 4
    5,  5, 10, 25,  25, 10,  5,  5,   # rank 5
   10, 10, 20, 30,  30, 20, 10, 10,   # rank 6
   50, 50, 50, 50,  50, 50, 50, 50,   # rank 7
    0,  0,  0,  0,   0,  0,  0,  0,   # rank 8
)

KNIGHT_PST: tuple[int, ...] = (
    -50, -40, -30, -30, -30, -30, -40, -50,  # rank 1
    -40, -20,   0,   5,   5,   0, -20, -40,  # rank 2
    -30,   5,  10,  15,  15,  10,   5, -30,  # rank 3
    -30,   0,  15,  20,  20,  15,   0, -30,  # rank 4
    -30,   5,  15,  20,  20,  15,   5, -30,  # rank 5
    -30,   0,  10,  15,  15,  10,   0, -30,  # rank 6
    -40, -20,   0,   0,   0,   0, -20, -40,  # rank 7
    -50, -40, -30, -30, -30, -30, -40, -50,  # rank 8
)

BISHOP_PST: tuple[int, ...] = (
    -20, -10, -10, -10, -10, -10, -10, -20,  # rank 1
    -10,   5,   0,   0,   0,   0,   5, -10,  # rank 2
    -10,  10,  10,  10,  10,  10,  10, -10,  # rank 3
    -10,   0,  10,  10,  10,  10,   0, -10,  # rank 4
    -10,   5,   5,  10,  10,   5,   5, -10,  # rank 5
    -10,   0,   5,  10,  10,   5,   0, -10,  # rank 6
    -10,   0,   0,   0,   0,   0,   0, -10,  # rank 7
    -20, -10, -10, -10, -10, -10, -10, -20,  # rank 8
)

ROOK_PST: tuple[int, ...] = (
     0,  0,  0,  5,  5,  0,  0,  0,  # rank 1
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 2
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 3
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 4
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 5
    -5,  0,  0,  0,  0,  0,  0, -5,  # rank 6
     5, 10, 10, 10, 10, 10, 10,  5,  # rank 7
     0,  0,  0,  0,  0,  0,  0,  0,  # rank 8
)

QUEEN_PST: tuple[int, ...] = (
    -20, -10, -10, -5, -5, -10, -10, -20,  # rank 1
    -10,   0,   5,  0,  0,   0,   0, -10,  # rank 2
    -10,   5,   5,  5,  5,   5,   0, -10,  # rank 3
      0,   0,   5,  5,  5,   5,   0,  -5,  # rank 4
     -5,   0,   5,  5,  5,   5,   0,  -5,  # rank 5
    -10,   0,   5,  5,  5,   5,   0, -10,  # rank 6
    -10,   0,   0,  0,  0,   0,   0, -10,  # rank 7
    -20, -10, -10, -5, -5, -10, -10, -20,  # rank 8
)

KING_MG_PST: tuple[int, ...] = (
     20,  30,  10,   0,   0,  10,  30,  20,  # rank 1
     20,  20,   0,   0,   0,   0,  20,  20,  # rank 2
    -10, -20, -20, -20, -20, -20, -20, -10,  # rank 3
    -20, -30, -30, -40, -40, -30, -30, -20,  # rank 4
    -30, -40, -40, -50, -50, -40, -40, -30,  # rank 5
    -30, -40, -40, -50, -50, -40, -40, -30,  # rank 6
    -30, -40, -40, -50, -50, -40, -40, -30,  # rank 7
    -30, -40, -40, -50, -50, -40, -40, -30,  # rank 8
)

KING_EG_PST: tuple[int, ...] = (
    -50, -30, -30, -30, -30, -30, -30, -50,  # rank 1
    -30, -30,   0,   0,   0,   0, -30, -30,  # rank 2
    -30, -10,  20,  30,  30,  20, -10, -30,  # rank 3
    -30, -10,  30,  40,  40,  30, -10, -30,  # rank 4
    -30, -10,  30,  40,  40,  30, -10, -30,  # rank 5
    -30, -10,  20,  30,  30,  20, -10, -30,  # rank 6
    -30, -20, -10,   0,   0, -10, -20, -30,  # rank 7
    -50, -40, -30, -20, -20, -30, -40, -50,  # rank 8
)
# fmt: on
