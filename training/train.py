"""Sigmoid-WDL training loop with MPS gate wiring (TRN-03, TRN-05, D-09).

Every tensor operation in this module stays at single-precision floating
point throughout — no wider-precision casts and no automatic mixed-precision
helpers — consistent with the project's MPS constraints.
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

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
    # Avoid 0 * NaN when game_result is missing (fresh-only labels).
    mixed = lambda_ * wdl_eval_target + (1 - lambda_) * game_result
    target = torch.where(has_result.bool(), mixed, wdl_eval_target)
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
    *,
    extra: dict | None = None,
) -> None:
    payload = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "epoch": epoch,
    }
    if extra:
        payload.update(extra)
    torch.save(payload, path)


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


def _write_metrics(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    # Keep training-live.json in sync so the dashboard does not stay stuck
    # on a completed labeling sidecar after training starts.
    live_path = path.parent / "training-live.json"
    live_tmp = live_path.with_suffix(live_path.suffix + ".tmp")
    live_payload = {
        "phase": "training",
        "status": payload.get("status"),
        "fen": payload.get("sample_fen"),
        "epoch": payload.get("epoch"),
        "epochs": payload.get("epochs"),
        "global_step": payload.get("global_step"),
        "best_val_loss": payload.get("best_val_loss"),
        "best_epoch": payload.get("best_epoch"),
        "device": payload.get("device"),
        "updated_utc": payload.get("updated_utc"),
    }
    live_tmp.write_text(json.dumps(live_payload, indent=2) + "\n", encoding="utf-8")
    live_tmp.replace(live_path)


def _lambda_at_epoch(
    epoch_index: int,
    epochs: int,
    start_lambda: float,
    end_lambda: float,
) -> float:
    if epochs <= 1:
        return float(end_lambda)
    t = epoch_index / (epochs - 1)
    return float(start_lambda + (end_lambda - start_lambda) * t)


def run_training(
    train_shard_path: str,
    val_shard_path: str,
    k: float,
    epochs: int,
    checkpoint_dir: str,
    checkpoint_every_n_steps: int = 500,
    deadline_monotonic: float | None = None,
    *,
    batch_size: int = 256,
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    early_stop_patience: int = 5,
    metrics_path: str | None = None,
    sample_fen: str | None = None,
    start_lambda: float = 1.0,
    end_lambda: float = 0.75,
    random_fen_skipping: int = 0,
    resume_from_checkpoint: str | None = None,
    elo_probe_every: int = 0,
    elo_probe_games: int = 100,
    export_dir: str | None = None,
) -> dict:
    """Train NNUE with AdamW, cosine LR, best-val/best-elo export, early stopping."""
    from training.export import export_checkpoint

    device = preflight_mps_gate()
    model = NNUE().to(device)
    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=lr,
        weight_decay=weight_decay,
    )
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(epochs, 1),
        eta_min=lr * 0.05,
    )

    if resume_from_checkpoint:
        load_checkpoint(model, optimizer, resume_from_checkpoint)
        for state in optimizer.state.values():
            for k, v in state.items():
                if isinstance(v, torch.Tensor):
                    state[k] = v.to(device)

    train_loader = DataLoader(
        ShardDataset(
            train_shard_path,
            random_fen_skipping=random_fen_skipping,
        ),
        batch_size=batch_size,
        shuffle=True,
    )
    val_loader = DataLoader(
        ShardDataset(val_shard_path, random_fen_skipping=0),
        batch_size=batch_size,
        shuffle=False,
    )

    train_losses: list[float] = []
    val_losses: list[float] = []
    learning_rates: list[float] = []
    lambdas: list[float] = []
    elo_probes: list[dict] = []
    global_step = 0
    stopped_early = False
    early_stop_reason: str | None = None
    best_val = float("inf")
    best_epoch = -1
    best_elo = float("-inf")
    best_elo_epoch = -1
    epochs_without_improve = 0
    best_path = Path(checkpoint_dir) / "best.pt"
    best_elo_path = Path(checkpoint_dir) / "best_elo.pt"
    export_root = Path(export_dir) if export_dir else Path(checkpoint_dir)
    best_elo_net = export_root / "best_elo.safetensors"
    metrics_file = (
        Path(metrics_path) if metrics_path else Path(checkpoint_dir) / "metrics.json"
    )

    os.makedirs(checkpoint_dir, exist_ok=True)
    export_root.mkdir(parents=True, exist_ok=True)

    def _metrics_payload(
        *,
        status: str,
        epoch_num: int,
    ) -> dict:
        return {
            "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "status": status,
            "epoch": epoch_num,
            "epochs": epochs,
            "global_step": global_step,
            "train_losses": train_losses,
            "val_losses": val_losses,
            "learning_rates": learning_rates,
            "lambdas": lambdas,
            "elo_probes": elo_probes,
            "best_val_loss": None if best_epoch < 0 else best_val,
            "best_epoch": best_epoch,
            "best_elo": None if best_elo_epoch < 0 else best_elo,
            "best_elo_epoch": best_elo_epoch,
            "batch_size": batch_size,
            "lr": lr,
            "weight_decay": weight_decay,
            "start_lambda": start_lambda,
            "end_lambda": end_lambda,
            "random_fen_skipping": random_fen_skipping,
            "k": k,
            "device": device,
            "stopped_early": stopped_early,
            "early_stop_reason": early_stop_reason,
            "sample_fen": sample_fen,
            "checkpoint_dir": checkpoint_dir,
            "best_checkpoint": str(best_path) if best_path.exists() else None,
            "best_elo_checkpoint": str(best_elo_path) if best_elo_path.exists() else None,
        }

    for epoch in range(epochs):
        if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
            stopped_early = True
            early_stop_reason = "deadline"
            break

        lam = _lambda_at_epoch(epoch, epochs, start_lambda, end_lambda)
        lambdas.append(lam)

        model.train()
        epoch_losses: list[float] = []
        for stm, opp, eval_cp, game_result, has_result in train_loader:
            if deadline_monotonic is not None and time.monotonic() >= deadline_monotonic:
                stopped_early = True
                early_stop_reason = "deadline"
                break

            stm = stm.to(device)
            opp = opp.to(device)
            eval_cp = eval_cp.to(device)
            game_result = game_result.to(device)
            has_result = has_result.to(device)

            optimizer.zero_grad()
            output = model(stm, opp)
            loss = wdl_loss(
                output, eval_cp, game_result, has_result, k=k, lambda_=lam
            )
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

        if stopped_early and early_stop_reason == "deadline":
            break

        if not epoch_losses:
            break

        train_loss = sum(epoch_losses) / max(len(epoch_losses), 1)
        train_losses.append(train_loss)

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
                        wdl_loss(
                            output,
                            eval_cp,
                            game_result,
                            has_result,
                            k=k,
                            lambda_=lam,
                        )
                        .detach()
                        .cpu()
                    )
                )
        val_loss = sum(val_epoch_losses) / max(len(val_epoch_losses), 1)
        val_losses.append(val_loss)
        learning_rates.append(float(optimizer.param_groups[0]["lr"]))
        scheduler.step()

        save_checkpoint(
            model,
            optimizer,
            epoch,
            f"{checkpoint_dir}/epoch-{epoch + 1}.pt",
        )

        improved = val_loss < best_val - 1e-8
        if improved:
            best_val = val_loss
            best_epoch = epoch + 1
            epochs_without_improve = 0
            save_checkpoint(
                model,
                optimizer,
                epoch,
                str(best_path),
                extra={"best_val_loss": best_val, "k": k},
            )
        else:
            epochs_without_improve += 1

        if (
            elo_probe_every > 0
            and (epoch + 1) % elo_probe_every == 0
        ):
            probe_net = export_root / f"probe_epoch_{epoch + 1}.safetensors"
            export_checkpoint(
                model,
                k_scale=k,
                path=str(probe_net),
                extra_meta={"epoch": str(epoch + 1), "k": str(k)},
            )
            try:
                from training.elo_probe import probe_summary, run_elo_probe

                report = run_elo_probe(
                    probe_net,
                    n_games=elo_probe_games,
                    out_dir=export_root / f"elo_probe_epoch_{epoch + 1}",
                )
                summary = probe_summary(report)
                summary["epoch"] = epoch + 1
                elo_probes.append(summary)
                elo_val = summary.get("elo")
                if elo_val is not None and float(elo_val) > best_elo:
                    best_elo = float(elo_val)
                    best_elo_epoch = epoch + 1
                    save_checkpoint(
                        model,
                        optimizer,
                        epoch,
                        str(best_elo_path),
                        extra={"best_elo": best_elo, "k": k},
                    )
                    export_checkpoint(
                        model,
                        k_scale=k,
                        path=str(best_elo_net),
                        extra_meta={
                            "best_elo": str(best_elo),
                            "best_elo_epoch": str(best_elo_epoch),
                        },
                    )
            except Exception as exc:  # noqa: BLE001 — probe must not kill training
                elo_probes.append(
                    {
                        "epoch": epoch + 1,
                        "error": str(exc),
                        "status": "failed",
                    }
                )

        _write_metrics(
            metrics_file,
            _metrics_payload(status="running", epoch_num=epoch + 1),
        )

        if (
            early_stop_patience > 0
            and epochs_without_improve >= early_stop_patience
            and best_epoch > 0
        ):
            stopped_early = True
            early_stop_reason = "early_stop_patience"
            break

        if stopped_early:
            break

    # Prefer best-Elo weights when probes produced a champion.
    if best_elo_path.exists():
        load_checkpoint(model, optimizer, str(best_elo_path))
        export_net_path = str(best_elo_net) if best_elo_net.exists() else None
    elif best_path.exists():
        load_checkpoint(model, optimizer, str(best_path))
        export_net_path = None
    else:
        export_net_path = None

    result = {
        "train_losses": train_losses,
        "val_losses": val_losses,
        "learning_rates": learning_rates,
        "lambdas": lambdas,
        "elo_probes": elo_probes,
        "device": device,
        "model": model,
        "optimizer": optimizer,
        "stopped_early": stopped_early,
        "early_stop_reason": early_stop_reason,
        "global_step": global_step,
        "best_val_loss": None if best_epoch < 0 else best_val,
        "best_epoch": best_epoch,
        "best_elo": None if best_elo_epoch < 0 else best_elo,
        "best_elo_epoch": best_elo_epoch,
        "best_checkpoint": str(best_path) if best_path.exists() else None,
        "best_elo_checkpoint": str(best_elo_path) if best_elo_path.exists() else None,
        "export_net_path": export_net_path,
        "batch_size": batch_size,
        "metrics_path": str(metrics_file),
    }
    _write_metrics(
        metrics_file,
        _metrics_payload(status="completed", epoch_num=len(train_losses)),
    )
    return result
