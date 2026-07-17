"""Zero-torch NNUE weights I/O (D-07, TRN-04)."""

from __future__ import annotations

import json
from typing import Any

import numpy as np
from safetensors import safe_open
from safetensors.numpy import save_file

from nnue_format import schema


def save_net(arrays: dict[str, np.ndarray], meta: dict[str, str], path: str) -> None:
    """Serialize float32 weight arrays and string metadata to a safetensors file."""
    header_meta: dict[str, str] = {
        key: (value if isinstance(value, str) else json.dumps(value))
        for key, value in meta.items()
    }
    save_file(
        {key: array.astype(np.float32) for key, array in arrays.items()},
        path,
        metadata=header_meta,
    )


def load_net(path: str) -> tuple[dict[str, np.ndarray], dict[str, str]]:
    """Load and validate a safetensors NNUE weights file."""
    with safe_open(path, framework="numpy") as handle:
        meta: dict[str, Any] = handle.metadata() or {}
        arrays = {key: handle.get_tensor(key) for key in handle.keys()}

    if meta.get("arch_id") != schema.ARCH_ID:
        raise ValueError(
            f"arch_id mismatch: expected {schema.ARCH_ID}, got {meta.get('arch_id')}"
        )
    if meta.get("feature_set") != schema.FEATURE_SET:
        raise ValueError(
            f"feature_set mismatch: expected {schema.FEATURE_SET}, "
            f"got {meta.get('feature_set')}"
        )

    for name, expected_shape in schema.EXPECTED_SHAPES.items():
        if name not in arrays:
            raise ValueError(f"missing required array: {name}")
        actual_shape = tuple(arrays[name].shape)
        if actual_shape != expected_shape:
            raise ValueError(
                f"{name} shape mismatch: expected {expected_shape}, got {actual_shape}"
            )

    return arrays, meta
