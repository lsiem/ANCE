"""Shared torch/numpy NNUE parity oracles (tests only — EVAL-03 / D-13).

Torch imports are allowed here under ``tests/`` only. Production ``ance/``
must never import this module or ``training/``.
"""

from __future__ import annotations

import chess
import numpy as np
import torch

from nnue_format import io as nnue_io
from training.data.features import encode_position
from training.model import NNUE


def load_torch_nnue_from_safetensors(path: str) -> NNUE:
    """Rebuild a torch ``NNUE`` from exported (in, out) safetensors weights."""
    arrays, _meta = nnue_io.load_net(path)
    model = NNUE()
    state = {
        "ft.weight": torch.from_numpy(np.ascontiguousarray(arrays["ft.weight"].T)),
        "ft.bias": torch.from_numpy(np.ascontiguousarray(arrays["ft.bias"])),
        "output.weight": torch.from_numpy(np.ascontiguousarray(arrays["out.weight"].T)),
        "output.bias": torch.from_numpy(np.ascontiguousarray(arrays["out.bias"])),
    }
    model.load_state_dict(state)
    model.eval()
    return model


def torch_cp_int(model: NNUE, fen: str) -> int:
    stm_np, opp_np = encode_position(fen)
    stm = torch.from_numpy(stm_np).unsqueeze(0)
    opp = torch.from_numpy(opp_np).unsqueeze(0)
    with torch.no_grad():
        raw = float(model(stm, opp).item())
    return int(round(raw))


def numpy_cp_int(nnue_eval: object, fen: str) -> int:
    from ance.board.position import Position

    return nnue_eval.evaluate(Position(chess.Board(fen)))  # type: ignore[attr-defined]
