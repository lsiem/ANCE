"""Zero-torch numpy forward for the (768→256)×2→1 NNUE (EVAL-03).

Weights are stored transposed at export (``(in, out)``); dense matmul is
``features @ weight + bias``. Sparse/incremental paths sum feature columns
of ``ft.weight`` (shape ``(768, 256)``) into a 256-d accumulator.
"""

from __future__ import annotations

import numpy as np

HIDDEN = 256


def refresh_accumulator(
    indices: list[int],
    ft_weight: np.ndarray,
    ft_bias: np.ndarray,
) -> np.ndarray:
    """Full sparse refresh: bias + sum of active feature columns."""
    acc = ft_bias.astype(np.float32, copy=True)
    if indices:
        # ft_weight[i] is the column for feature i → shape (256,)
        acc = acc + ft_weight[indices].sum(axis=0)
    return acc


def apply_feature_delta(
    acc: np.ndarray,
    removed: list[int],
    added: list[int],
    ft_weight: np.ndarray,
) -> np.ndarray:
    """Incremental accumulator update (exact for linear feature transformer)."""
    out = acc
    if removed:
        out = out - ft_weight[removed].sum(axis=0)
    if added:
        out = out + ft_weight[added].sum(axis=0)
    return out


def forward_from_accumulators(
    acc_stm: np.ndarray,
    acc_opp: np.ndarray,
    out_weight: np.ndarray,
    out_bias: np.ndarray,
) -> float:
    """Clipped-ReLU both halves and apply the output layer."""
    stm_h = np.clip(acc_stm, 0.0, 1.0)
    opp_h = np.clip(acc_opp, 0.0, 1.0)
    combined = np.concatenate([stm_h, opp_h])
    raw = combined @ out_weight + out_bias
    return float(np.asarray(raw).reshape(-1)[0])


def forward_cp_float(
    stm: np.ndarray, opp: np.ndarray, weights: dict[str, np.ndarray]
) -> float:
    """Dense reference path (parity / tests). Prefer sparse refresh in engine."""
    stm_h = np.clip(stm @ weights["ft.weight"] + weights["ft.bias"], 0.0, 1.0)
    opp_h = np.clip(opp @ weights["ft.weight"] + weights["ft.bias"], 0.0, 1.0)
    combined = np.concatenate([stm_h, opp_h])  # (512,)
    raw = combined @ weights["out.weight"] + weights["out.bias"]
    return float(np.asarray(raw).reshape(-1)[0])


def cp_from_nnue_output(raw: float) -> int:
    """Shared float→int conversion for D-13 parity (round-to-nearest)."""
    return int(round(raw))
