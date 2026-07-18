"""Numpy ``NnueEval`` behind the ``Evaluator`` Protocol seam (EVAL-03).

Performance (NNUE best practice):
- Dual color accumulators (white / black perspective), not STM-only.
- Sparse full refresh and incremental make/unmake updates.
- No FEN round-trip in the evaluate hot path.

Search may call optional ``refresh`` / ``on_make`` / ``on_unmake`` via duck
typing; ``ance/search`` must never import this concrete class.
"""

from __future__ import annotations

import os
from pathlib import Path

import chess
import numpy as np

from ance.board.position import Position
from ance.eval.nnue.features import (
    active_feature_indices,
    encode_position_board,
)
from ance.eval.nnue.inference import (
    apply_feature_delta,
    cp_from_nnue_output,
    forward_cp_float,
    forward_from_accumulators,
    refresh_accumulator,
)
from nnue_format.io import load_net

_DEFAULT_NET = Path(__file__).with_name("net.safetensors")


class NnueEval:
    """Side-to-move-relative NNUE evaluator.

    Output is already STM-relative from the dual-perspective architecture —
    no extra turn flip (unlike HandcraftedEval's white-relative + sign flip).
    """

    def __init__(self) -> None:
        path = os.environ.get("ANCE_NNUE_PATH", str(_DEFAULT_NET))
        if not Path(path).is_file():
            raise FileNotFoundError(f"NNUE weights not found: {path}")
        self.weights, self.meta = load_net(path)  # strict D-08 validation inside
        self._ft_weight = np.ascontiguousarray(
            self.weights["ft.weight"], dtype=np.float32
        )
        self._ft_bias = np.ascontiguousarray(
            self.weights["ft.bias"], dtype=np.float32
        )
        self._out_weight = np.ascontiguousarray(
            self.weights["out.weight"], dtype=np.float32
        )
        self._out_bias = np.ascontiguousarray(
            self.weights["out.bias"], dtype=np.float32
        )
        self._acc_white: np.ndarray | None = None
        self._acc_black: np.ndarray | None = None
        self._idx_white: set[int] = set()
        self._idx_black: set[int] = set()
        self._stack: list[
            tuple[np.ndarray, np.ndarray, set[int], set[int]]
        ] = []
        self._board_id: int | None = None

    def refresh(self, board: chess.Board) -> None:
        """Full sparse rebuild of both color accumulators for ``board``."""
        idx_w = active_feature_indices(board, chess.WHITE)
        idx_b = active_feature_indices(board, chess.BLACK)
        self._acc_white = refresh_accumulator(
            idx_w, self._ft_weight, self._ft_bias
        )
        self._acc_black = refresh_accumulator(
            idx_b, self._ft_weight, self._ft_bias
        )
        self._idx_white = set(idx_w)
        self._idx_black = set(idx_b)
        self._stack.clear()
        self._board_id = id(board)

    def on_make(self, board: chess.Board, move: chess.Move) -> None:
        """Update accumulators after ``board.push(move)`` (board is post-move)."""
        if self._acc_white is None or self._acc_black is None:
            self.refresh(board)
            return
        if self._board_id is not None and self._board_id != id(board):
            self.refresh(board)
            return

        self._stack.append(
            (
                self._acc_white.copy(),
                self._acc_black.copy(),
                set(self._idx_white),
                set(self._idx_black),
            )
        )

        after_w = set(active_feature_indices(board, chess.WHITE))
        after_b = set(active_feature_indices(board, chess.BLACK))
        removed_w = list(self._idx_white - after_w)
        added_w = list(after_w - self._idx_white)
        removed_b = list(self._idx_black - after_b)
        added_b = list(after_b - self._idx_black)

        self._acc_white = apply_feature_delta(
            self._acc_white, removed_w, added_w, self._ft_weight
        )
        self._acc_black = apply_feature_delta(
            self._acc_black, removed_b, added_b, self._ft_weight
        )
        self._idx_white = after_w
        self._idx_black = after_b

    def on_unmake(self) -> None:
        """Restore accumulators after ``board.pop()``."""
        if self._stack:
            (
                self._acc_white,
                self._acc_black,
                self._idx_white,
                self._idx_black,
            ) = self._stack.pop()

    def evaluate(self, pos: Position) -> int:
        board = pos.board
        if (
            self._acc_white is None
            or self._acc_black is None
            or self._board_id != id(board)
        ):
            self.refresh(board)

        assert self._acc_white is not None and self._acc_black is not None
        if board.turn == chess.WHITE:
            acc_stm, acc_opp = self._acc_white, self._acc_black
        else:
            acc_stm, acc_opp = self._acc_black, self._acc_white

        raw = forward_from_accumulators(
            acc_stm,
            acc_opp,
            self._out_weight,
            self._out_bias,
        )
        return cp_from_nnue_output(raw)

    def evaluate_dense_reference(self, pos: Position) -> int:
        """Dense forward for tests — must match ``evaluate`` bit-for-bit."""
        stm, opp = encode_position_board(pos.board)
        raw = forward_cp_float(stm, opp, self.weights)
        return cp_from_nnue_output(raw)
