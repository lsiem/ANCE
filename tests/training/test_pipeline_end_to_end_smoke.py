"""Capstone end-to-end pipeline smoke using real modules."""

from __future__ import annotations

import chess
import pytest

pytest.importorskip("torch")

from nnue_format import io as nnue_io
from nnue_format import schema
from training.data.kfit import fit_k_from_samples, sigmoid
from training.data.shards import build_shard
from training.data.split import assert_no_fen_leakage, split_by_game
from training.export import export_checkpoint
from training.label.position_source import generate_position_set
from training.train import run_training


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

    white = side_material(chess.WHITE)
    black = side_material(chess.BLACK)
    cp = float(white - black)
    return cp if board.turn == chess.WHITE else -cp


def test_full_pipeline_smoke_tiny_dataset(tmp_path) -> None:
    raw = generate_position_set(n_games=8, seed=7)
    samples: list[dict] = []
    for index, sample in enumerate(raw):
        board = chess.Board(sample["fen"])
        cp = _material_cp(board)
        samples.append(
            {
                **sample,
                "cp": cp,
                "game_result": float(sigmoid(__import__("numpy").array([cp]), 400.0)[0]),
                "source": "synthetic",
            }
        )

    train, val = split_by_game(samples, val_fraction=0.25, seed=7)
    assert_no_fen_leakage(train, val)
    fitted_k = fit_k_from_samples(train, min_result_rows=10)

    train_shard = tmp_path / "train.npz"
    val_shard = tmp_path / "val.npz"
    build_shard(train, str(train_shard))
    build_shard(val, str(val_shard))

    result = run_training(
        str(train_shard),
        str(val_shard),
        k=fitted_k,
        epochs=2,
        checkpoint_dir=str(tmp_path),
    )
    assert len(result["val_losses"]) == 2

    net_path = tmp_path / "net.safetensors"
    export_checkpoint(result["model"], k_scale=fitted_k, path=str(net_path))
    arrays, meta = nnue_io.load_net(str(net_path))
    assert arrays["ft.weight"].shape == schema.EXPECTED_SHAPES["ft.weight"]
    assert meta["arch_id"] == schema.ARCH_ID
