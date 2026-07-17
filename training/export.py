"""Export trained NNUE weights to nnue_format safetensors (D-07, TRN-04)."""

from __future__ import annotations

import numpy as np

from nnue_format import io as nnue_io
from nnue_format import schema
from training.model import NNUE


def export_checkpoint(
    model: NNUE,
    k_scale: float,
    path: str,
    extra_meta: dict[str, str] | None = None,
) -> None:
    state = model.state_dict()
    arrays = {
        "ft.weight": state["ft.weight"].T.contiguous().cpu().numpy().astype(np.float32),
        "ft.bias": state["ft.bias"].cpu().numpy().astype(np.float32),
        "out.weight": state["output.weight"].T.contiguous().cpu().numpy().astype(np.float32),
        "out.bias": state["output.bias"].cpu().numpy().astype(np.float32),
    }
    meta = {
        "arch_id": schema.ARCH_ID,
        "feature_set": schema.FEATURE_SET,
        "k_scale": str(k_scale),
        "format_version": "1",
        **(extra_meta or {}),
    }
    nnue_io.save_net(arrays, meta, path)
