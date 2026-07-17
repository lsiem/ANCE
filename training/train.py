"""Sigmoid-WDL training loop with MPS gate wiring (TRN-03, TRN-05, D-09).

Every tensor operation in this module stays at single-precision floating
point throughout — no wider-precision casts and no automatic mixed-precision
helpers — consistent with the project's MPS constraints.
"""

from __future__ import annotations

import os

import torch

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from training import mps_gate
from training.model import NNUE, NUM_FEATURES


def wdl_loss(
    model_out_cp: torch.Tensor,
    eval_cp: torch.Tensor,
    game_result: torch.Tensor,
    has_result: torch.Tensor,
    k: float,
    lambda_: float = 0.5,
) -> torch.Tensor:
    wdl_model = torch.sigmoid(model_out_cp / k)
    wdl_eval_target = torch.sigmoid(eval_cp / k)
    effective_lambda = torch.where(
        has_result.bool(),
        torch.full_like(eval_cp, lambda_),
        torch.ones_like(eval_cp),
    )
    target = effective_lambda * wdl_eval_target + (1 - effective_lambda) * game_result
    return ((wdl_model - target) ** 2).mean()


def preflight_mps_gate() -> str:
    device = mps_gate.select_device()
    mps_gate.cpu_vs_mps_parity_check(device, model_factory=NNUE)
    return device


def train_smoke(steps: int = 20, batch_size: int = 8, seed: int = 0) -> list[float]:
    torch.manual_seed(seed)
    device = preflight_mps_gate()
    model = NNUE().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-2)
    losses: list[float] = []

    stm = torch.randn(batch_size, NUM_FEATURES, dtype=torch.float32, device=device)
    opp = torch.randn(batch_size, NUM_FEATURES, dtype=torch.float32, device=device)
    eval_cp = torch.randn(batch_size, dtype=torch.float32, device=device) * 200.0
    game_result = torch.rand(batch_size, dtype=torch.float32, device=device)
    has_result = torch.ones(batch_size, dtype=torch.float32, device=device)

    for _ in range(steps):
        optimizer.zero_grad()
        output = model(stm, opp)
        loss = wdl_loss(output, eval_cp, game_result, has_result, k=400.0)
        loss.backward()
        optimizer.step()
        losses.append(float(loss.detach().cpu()))

    return losses
