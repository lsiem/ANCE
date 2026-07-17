"""By-game train/val split with FEN leakage assertion (TRN-02, D-03)."""

from __future__ import annotations

import random


def split_by_game(
    samples: list[dict],
    val_fraction: float = 0.05,
    seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    game_ids = sorted({sample["game_id"] for sample in samples})
    rng = random.Random(seed)
    rng.shuffle(game_ids)
    cut = int(len(game_ids) * (1 - val_fraction))
    train_ids = set(game_ids[:cut])
    val_ids = set(game_ids[cut:])
    train = [sample for sample in samples if sample["game_id"] in train_ids]
    val = [sample for sample in samples if sample["game_id"] in val_ids]
    return train, val


def assert_no_fen_leakage(train: list[dict], val: list[dict]) -> None:
    train_fens = {sample["fen"] for sample in train}
    val_fens = {sample["fen"] for sample in val}
    overlap = train_fens & val_fens
    if overlap:
        raise AssertionError(
            f"{len(overlap)} FENs leaked across train/val split (TRN-02 violation)"
        )
