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

    def try_set_startpos(self) -> None:
        """Reset to a fresh startpos. Always succeeds (D-17: ucinewgame,
        and the `startpos` half of `position`)."""
        self._board = chess.Board()

    def try_set_fen(self, fen: str) -> bool:
        """Set the board from a FEN string. Builds the candidate board in a
        local variable first (01-RESEARCH.md Pattern 2 / D-10's "reject and
        keep, never reject and reset" pitfall) -- `self._board` is only
        assigned on success, so a malformed FEN leaves the live board
        completely untouched.
        """
        try:
            candidate = chess.Board(fen)
        except ValueError:
            return False
        self._board = candidate
        return True

    def try_push_uci_moves(self, moves: list[str]) -> bool:
        """Replay a list of UCI moves on a local copy of the board, only
        committing the copy back to `self._board` if every move applies
        cleanly. `except ValueError` covers both `chess.InvalidMoveError`
        (bad syntax) and `chess.IllegalMoveError` (illegal here) -- both
        subclass `ValueError` in python-chess 1.11.2 (01-RESEARCH.md
        Pattern 2). A partially-applied move list can never leak into
        `self._board` (T-01-04 mitigation).
        """
        candidate = self._board.copy()
        for move in moves:
            try:
                candidate.push_uci(move)
            except ValueError:
                return False
        self._board = candidate
        return True

    def has_no_legal_moves(self) -> bool:
        """Checkmate or stalemate -- the two reachable-by-move-sequence
        zero-legal-move states (Assumption A3, 01-RESEARCH.md). Deliberately
        narrower than `is_game_over()`, which also covers non-zero-legal-move
        draws (insufficient material, 75-move, fivefold repetition) that
        should still route through a real search, not `bestmove (none)`.
        """
        return self._board.is_checkmate() or self._board.is_stalemate()

    def is_check(self) -> bool:
        return self._board.is_check()
