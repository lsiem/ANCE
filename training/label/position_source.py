"""Synthetic / random-walk position generation for labeling."""

from __future__ import annotations

import random
from collections.abc import Callable

import chess


def synthetic_game_id(game_index: int) -> str:
    return f"fresh-{game_index:06d}"


def generate_position_set(
    n_games: int = 50,
    plies_per_game: int = 40,
    seed: int = 42,
    *,
    target_positions: int | None = None,
    skip_checks: bool = True,
    max_games: int | None = None,
    progress_callback: Callable[[int, int | None], None] | None = None,
) -> list[dict[str, str]]:
    """Generate FENs via random legal play.

    If ``target_positions`` is set, keep generating games until that many
    samples are collected (or ``max_games`` is hit). ``n_games`` is used when
    ``target_positions`` is None.

    ``progress_callback(done, total)`` is invoked periodically when provided.
    """
    rng = random.Random(seed)
    samples: list[dict[str, str]] = []
    sample_interval = max(1, plies_per_game // 8)

    if target_positions is not None:
        game_limit = max_games if max_games is not None else max(n_games, target_positions)
    else:
        game_limit = n_games

    game_index = 0
    last_report = 0
    report_every = 5_000 if target_positions and target_positions >= 50_000 else 500
    while game_index < game_limit:
        if target_positions is not None and len(samples) >= target_positions:
            break

        board = chess.Board()
        game_id = synthetic_game_id(game_index)

        for ply in range(1, plies_per_game + 1):
            if board.is_game_over(claim_draw=True):
                break

            take = (
                ply > 4
                and (
                    target_positions is not None
                    or (ply - 4) % sample_interval == 0
                )
            )
            if take:
                if not (skip_checks and board.is_check()):
                    samples.append({"fen": board.fen(), "game_id": game_id})
                    if target_positions is not None and len(samples) >= target_positions:
                        break

            legal_moves = list(board.legal_moves)
            if not legal_moves:
                break
            board.push(rng.choice(legal_moves))

        game_index += 1
        done = len(samples)
        if progress_callback is not None and (
            done - last_report >= report_every
            or (target_positions is not None and done >= target_positions)
            or game_index >= game_limit
        ):
            progress_callback(done, target_positions)
            last_report = done

    if target_positions is not None:
        return samples[:target_positions]
    return samples
