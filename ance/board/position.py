"""`Position` -- the narrow adapter over `chess.Board` (D-00c).

Plan 01-01 only needs a fresh board plus legal-move access to prove the
threading loop end-to-end. Plan 01-02 fills this out with
`try_set_startpos()`, `try_set_fen()`, `try_push_uci_moves()`, and
`has_no_legal_moves()` for real `position`/`ucinewgame` handling and
malformed-input rejection (D-10).
"""

from __future__ import annotations

import chess


class Position:
    """Wraps a `chess.Board`. Never share one instance across threads --
    always `copy()` before handing a position to the search worker
    (`chess.Board` is not documented as thread-safe).
    """

    def __init__(self, board: chess.Board | None = None) -> None:
        self._board: chess.Board = board if board is not None else chess.Board()

    def legal_moves(self) -> list[chess.Move]:
        return list(self._board.legal_moves)

    def copy(self) -> "Position":
        return Position(self._board.copy())

    @property
    def board(self) -> chess.Board:
        return self._board
