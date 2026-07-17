"""Sigmoid-WDL training loop with MPS gate wiring (TRN-03, TRN-05, D-09).

Every tensor operation in this module stays at single-precision floating
point throughout — no wider-precision casts and no automatic mixed-precision
helpers — consistent with the project's MPS constraints.
"""

from __future__ import annotations

import os

import torch
from torch.utils.data import DataLoader

os.environ.setdefault("PYTORCH_ENABLE_MPS_FALLBACK", "1")

from training import mps_gate
from training.data.shards import ShardDataset
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


def save_checkpoint(
    model: NNUE,
    optimizer: torch.optim.Optimizer,
    epoch: int,
    path: str,
) -> None:
    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
            "epoch": epoch,
        },
        path,
    )


def load_checkpoint(
    model: NNUE,
    optimizer: torch.optim.Optimizer,
    path: str,
) -> int:
    """Load a checkpoint this pipeline wrote itself — never external `.pt` files."""
    payload = torch.load(path, weights_only=True, map_location="cpu")
    model.load_state_dict(payload["model_state_dict"])
    optimizer.load_state_dict(payload["optimizer_state_dict"])
    return int(payload["epoch"])


def run_training(
    train_shard_path: str,
    val_shard_path: str,
    k: float,
    epochs: int,
    checkpoint_dir: str,
    checkpoint_every_n_steps: int = 500,
) -> dict:
    device = preflight_mps_gate()
    model = NNUE().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)

    train_loader = DataLoader(ShardDataset(train_shard_path), batch_size=8, shuffle=True)
    val_loader = DataLoader(ShardDataset(val_shard_path), batch_size=8, shuffle=False)

    train_losses: list[float] = []
    val_losses: list[float] = []
    global_step = 0

    for epoch in range(epochs):
        model.train()
        epoch_losses: list[float] = []
        for stm, opp, eval_cp, game_result, has_result in train_loader:
            stm = stm.to(device)
            opp = opp.to(device)
            eval_cp = eval_cp.to(device)
            game_result = game_result.to(device)
            has_result = has_result.to(device)

            optimizer.zero_grad()
            output = model(stm, opp)
            loss = wdl_loss(output, eval_cp, game_result, has_result, k=k)
            loss.backward()
            optimizer.step()
            epoch_losses.append(float(loss.detach().cpu()))
            global_step += 1

            if global_step % checkpoint_every_n_steps == 0:
                save_checkpoint(
                    model,
                    optimizer,
                    epoch,
                    f"{checkpoint_dir}/step-{global_step}.pt",
                )

        train_losses.append(sum(epoch_losses) / max(len(epoch_losses), 1))

        model.eval()
        val_epoch_losses: list[float] = []
        with torch.no_grad():
            for stm, opp, eval_cp, game_result, has_result in val_loader:
                stm = stm.to(device)
                opp = opp.to(device)
                eval_cp = eval_cp.to(device)
                game_result = game_result.to(device)
                has_result = has_result.to(device)
                output = model(stm, opp)
                val_epoch_losses.append(
                    float(
                        wdl_loss(output, eval_cp, game_result, has_result, k=k)
                        .detach()
                        .cpu()
                    )
                )
        val_losses.append(sum(val_epoch_losses) / max(len(val_epoch_losses), 1))

    return {"train_losses": train_losses, "val_losses": val_losses, "device": device, "model": model, "optimizer": optimizer}
