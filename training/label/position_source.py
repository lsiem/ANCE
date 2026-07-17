"""Deterministic targeted-position generation for fresh Stockfish labeling."""

from __future__ import annotations

import random

import chess


def synthetic_game_id(game_index: int) -> str:
    return f"fresh-{game_index:06d}"


def generate_position_set(
    n_games: int = 50,
    plies_per_game: int = 40,
    seed: int = 42,
) -> list[dict[str, str]]:
    rng = random.Random(seed)
    samples: list[dict[str, str]] = []
    sample_interval = max(1, plies_per_game // 8)

    for game_index in range(n_games):
        board = chess.Board()
        game_id = synthetic_game_id(game_index)

        for ply in range(1, plies_per_game + 1):
            if board.is_game_over(claim_draw=True):
                break

            if ply > 4 and (ply - 4) % sample_interval == 0:
                samples.append({"fen": board.fen(), "game_id": game_id})

            legal_moves = list(board.legal_moves)
            if not legal_moves:
                break
            board.push(rng.choice(legal_moves))

    return samples
