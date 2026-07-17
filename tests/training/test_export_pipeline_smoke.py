"""End-to-end train → export → zero-torch load smoke test."""

from __future__ import annotations

import pytest
import torch

pytest.importorskip("torch")

from nnue_format import io as nnue_io
from nnue_format import schema
from training.export import export_checkpoint
from training.model import NNUE, NUM_FEATURES
from training.train import preflight_mps_gate, wdl_loss


def test_train_export_roundtrip_smoke(tmp_path) -> None:
    device = preflight_mps_gate()
    torch.manual_seed(0)
    model = NNUE().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)

    for _ in range(5):
        batch = 4
        stm = torch.randn(batch, NUM_FEATURES, dtype=torch.float32, device=device)
        opp = torch.randn(batch, NUM_FEATURES, dtype=torch.float32, device=device)
        eval_cp = torch.randn(batch, dtype=torch.float32, device=device) * 100.0
        game_result = torch.rand(batch, dtype=torch.float32, device=device)
        has_result = torch.ones(batch, dtype=torch.float32, device=device)

        optimizer.zero_grad()
        loss = wdl_loss(
            model(stm, opp), eval_cp, game_result, has_result, k=400.0
        )
        loss.backward()
        optimizer.step()

    out_path = tmp_path / "net.safetensors"
    export_checkpoint(model, k_scale=400.0, path=str(out_path))
    arrays, meta = nnue_io.load_net(str(out_path))

    assert arrays["ft.weight"].shape == (768, 256)
    assert arrays["out.weight"].shape == (512, 1)
    assert meta["arch_id"] == schema.ARCH_ID
