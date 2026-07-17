"""Round-trip tests for the zero-torch nnue_format contract."""

from __future__ import annotations

import numpy as np
import pytest

from nnue_format import schema
from nnue_format.io import load_net, save_net


def _synthetic_arrays() -> dict[str, np.ndarray]:
    return {
        name: np.random.randn(*shape).astype(np.float32)
        for name, shape in schema.EXPECTED_SHAPES.items()
    }


def test_nnue_format_roundtrip_zero_torch(tmp_path) -> None:
    arrays = _synthetic_arrays()
    meta = {"arch_id": schema.ARCH_ID, "feature_set": schema.FEATURE_SET}
    path = tmp_path / "net.safetensors"

    save_net(arrays, meta, str(path))
    loaded_arrays, loaded_meta = load_net(str(path))

    for key, array in arrays.items():
        assert np.allclose(array, loaded_arrays[key])
    assert loaded_meta["arch_id"] == schema.ARCH_ID


def test_load_net_rejects_wrong_arch_id(tmp_path) -> None:
    arrays = _synthetic_arrays()
    meta = {"arch_id": "wrong-arch", "feature_set": schema.FEATURE_SET}
    path = tmp_path / "bad.safetensors"
    save_net(arrays, meta, str(path))

    with pytest.raises(ValueError, match="arch_id mismatch"):
        load_net(str(path))
