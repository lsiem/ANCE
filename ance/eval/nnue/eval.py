"""Numpy ``NnueEval`` behind the ``Evaluator`` Protocol seam (EVAL-03)."""

from __future__ import annotations

import os
from pathlib import Path

from ance.board.position import Position
from ance.eval.nnue.features import encode_position
from ance.eval.nnue.inference import cp_from_nnue_output, forward_cp_float
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

    def evaluate(self, pos: Position) -> int:
        board = pos.board
        stm, opp = encode_position(board.fen())
        raw = forward_cp_float(stm, opp, self.weights)
        return cp_from_nnue_output(raw)
