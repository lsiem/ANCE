"""Zero-torch numpy forward for the (768→256)×2→1 NNUE (EVAL-03).

Weights are stored transposed at export (``(in, out)``); matmul is
``features @ weight + bias``. Never re-transpose at inference.
"""

from __future__ import annotations

import numpy as np


def forward_cp_float(
    stm: np.ndarray, opp: np.ndarray, weights: dict[str, np.ndarray]
) -> float:
    # Weights already transposed at export: features @ weight + bias
    stm_h = np.clip(stm @ weights["ft.weight"] + weights["ft.bias"], 0.0, 1.0)
    opp_h = np.clip(opp @ weights["ft.weight"] + weights["ft.bias"], 0.0, 1.0)
    combined = np.concatenate([stm_h, opp_h])  # (512,)
    # out.weight is (512, 1); squeeze to a Python float
    raw = combined @ weights["out.weight"] + weights["out.bias"]
    return float(np.asarray(raw).reshape(-1)[0])


def cp_from_nnue_output(raw: float) -> int:
    """Shared float→int conversion for D-13 parity (round-to-nearest)."""
    return int(round(raw))
