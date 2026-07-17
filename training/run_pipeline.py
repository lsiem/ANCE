"""Bounded, resumable NNUE training pipeline CLI (D-08)."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import chess
import numpy as np

from nnue_format import io as nnue_io
from nnue_format import schema
from training.data.kfit import fit_k_from_samples, sigmoid
from training.data.merge import merge_and_dedup
from training.data.shards import build_shard
from training.data.split import assert_no_fen_leakage, split_by_game
from training.export import export_checkpoint
from training.label.position_source import generate_position_set
from training.run_manifest import record_event
from training.train import preflight_mps_gate, run_training


def _git_sha() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _material_cp(board: chess.Board) -> float:
    values = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
    }

    def side_material(color: bool) -> int:
        total = 0
        for piece in board.piece_map().values():
            if piece.color != color or piece.piece_type == chess.KING:
                continue
            total += values[piece.piece_type]
        return total

    cp = float(side_material(chess.WHITE) - side_material(chess.BLACK))
    return cp if board.turn == chess.WHITE else -cp


def _synthetic_samples(n_games: int, seed: int) -> list[dict]:
    raw = generate_position_set(n_games=n_games, seed=seed)
    samples: list[dict] = []
    for sample in raw:
        board = chess.Board(sample["fen"])
        cp = _material_cp(board)
        samples.append(
            {
                **sample,
                "cp": cp,
                "game_result": float(sigmoid(np.array([cp]), 400.0)[0]),
                "source": "synthetic",
            }
        )
    return samples


def run_smoke(out_dir: Path, seed: int = 7) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = out_dir / "run_manifest.json"

    device = preflight_mps_gate()
    record_event(str(manifest), event="preflight", device=device, git_sha=_git_sha())

    samples = _synthetic_samples(n_games=8, seed=seed)
    train, val = split_by_game(samples, val_fraction=0.25, seed=seed)
    assert_no_fen_leakage(train, val)

    fitted_k = fit_k_from_samples(train, min_result_rows=10)
    record_event(str(manifest), event="k_fit", k_scale=fitted_k)

    train_shard = out_dir / "train.npz"
    val_shard = out_dir / "val.npz"
    if not train_shard.exists():
        build_shard(train, str(train_shard))
    if not val_shard.exists():
        build_shard(val, str(val_shard))

    result = run_training(
        str(train_shard),
        str(val_shard),
        k=fitted_k,
        epochs=1,
        checkpoint_dir=str(out_dir / "checkpoints"),
    )
    record_event(
        str(manifest),
        event="training_complete",
        val_losses=result["val_losses"],
        device=result["device"],
    )

    net_path = out_dir / "net.safetensors"
    if not net_path.exists():
        export_checkpoint(
            result["model"],
            k_scale=fitted_k,
            path=str(net_path),
            extra_meta={"git_sha": _git_sha(), "mode": "smoke"},
        )

    return {"k": fitted_k, "val_losses": result["val_losses"], "net_path": str(net_path)}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ANCE offline NNUE training pipeline")
    parser.add_argument("--smoke", action="store_true", help="Tiny synthetic run")
    parser.add_argument("--lichess-zst", type=str, default=None)
    parser.add_argument("--fresh-n-games", type=int, default=200)
    parser.add_argument("--depth", type=int, default=None)
    parser.add_argument("--max-hours", type=float, default=10.0)
    parser.add_argument("--out-dir", type=str, default="./training-run-output")
    args = parser.parse_args(argv)

    out_dir = Path(args.out_dir)

    if args.smoke:
        run_smoke(out_dir)
        return 0

    if args.lichess_zst is None:
        print(
            "Real pipeline requires --lichess-zst or use --smoke for wiring test.",
            file=sys.stderr,
        )
        return 2

    print(
        "Full bounded run is configured but not launched from this automated session. "
        "Use the human checkpoint in Plan 04-07 Task 2.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
