"""Depth-vs-depth self-play mini-match (D-14).

Measures whether deeper search never plays measurably worse than a shallower
counterpart on the same evaluator, alternating colors for fairness.

Plan 02-10 adds shared-bound and resume controls so the Phase 2 evidence
runner can drive this harness under one monotonic deadline with per-game
atomic checkpointing: `deadline`/`stop_event` are checked before every ply,
immediately after every `search_root` return (so an expired search result is
never pushed), and before every game; `start_game`/`game_records` skip
already-completed games on resume; `on_game_complete` fires exactly once per
classified game.
"""

from __future__ import annotations

import threading
import time  # noqa: F401  (re-exported: tests patch depth_match.time.monotonic)
from typing import Callable, Literal

import chess

from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.search.negamax import search_root
from ance.tools.random_mover_gauntlet import (
    HarnessTimeout,
    _validate_prior_records,
    check_harness_expiry,
)

__all__ = [
    "DepthMatchOutcome",
    "HarnessTimeout",
    "OPENING_LINES",
    "play_depth_match_game",
    "run_depth_match",
]

DepthMatchOutcome = Literal["win", "draw", "loss"]

OPENING_LINES: tuple[tuple[str, ...], ...] = (
    ("e2e4", "e7e5", "g1f3", "b8c6"),
    ("d2d4", "d7d5", "c2c4", "e7e6"),
    ("c2c4", "e7e5", "b1c3", "g8f6"),
    ("g1f3", "d7d5", "d2d4", "g8f6"),
    ("b2b3", "e7e5", "c1b2", "b8c6"),
    ("g2g3", "d7d5", "f1g2", "g8f6"),
    ("f2f4", "d7d5", "g1f3", "g8f6"),
    ("b1c3", "d7d5", "e2e4", "d5e4"),
)


def _opening_for_seed(seed: int) -> tuple[str, ...]:
    """Select one reproducible opening line for ``seed``."""
    return OPENING_LINES[seed % len(OPENING_LINES)]


def _apply_opening(pos: Position, line: tuple[str, ...]) -> None:
    """Validate and apply a predefined UCI opening line."""
    for move_uci in line:
        pos.board.push_uci(move_uci)


def play_depth_match_game(
    shallow_depth: int,
    deep_depth: int,
    evaluator: Evaluator,
    deep_plays_white: bool,
    seed: int,
    max_halfmoves: int = 300,
    *,
    deadline: float | None = None,
    stop_event: threading.Event | None = None,
) -> DepthMatchOutcome:
    """Returns game result from the deeper side's perspective.

    When the shared `stop_event`/`deadline` pair is supplied, both bounds
    are checked before every ply and again immediately after every
    `search_root` return so an expired result is never pushed, and the same
    pair is forwarded into every search. When omitted, each move gets a
    fresh un-set Event and no deadline (pre-02-10 behavior).
    """
    pos = Position()
    _apply_opening(pos, _opening_for_seed(seed))
    halfmoves = 0
    deep_color = chess.WHITE if deep_plays_white else chess.BLACK
    event = stop_event if stop_event is not None else threading.Event()

    while not pos.board.is_game_over() and halfmoves < max_halfmoves:
        check_harness_expiry(event, deadline)
        depth = deep_depth if pos.board.turn == deep_color else shallow_depth
        move = search_root(
            pos,
            max_depth=depth,
            evaluator=evaluator,
            stop_flag=event,
            deadline=deadline,
        ).best_move
        check_harness_expiry(event, deadline)
        if move is None:
            break
        check_harness_expiry(event, deadline)
        pos.board.push(move)
        halfmoves += 1

    if not pos.board.is_game_over():
        return "draw"

    result = pos.board.result()
    if result == "1/2-1/2":
        return "draw"
    deep_won = (deep_color == chess.WHITE and result == "1-0") or (
        deep_color == chess.BLACK and result == "0-1"
    )
    return "win" if deep_won else "loss"


def run_depth_match(
    shallow_depth: int,
    deep_depth: int,
    n_games: int,
    evaluator: Evaluator,
    seed: int = 0,
    max_halfmoves: int = 300,
    start_game: int = 0,
    game_records: list[dict] | None = None,
    deadline: float | None = None,
    stop_event: threading.Event | None = None,
    on_game_complete: Callable[[int, dict, dict], None] | None = None,
) -> dict:
    """Play ``n_games`` games and return deeper-side scoring stats.

    Game ``i`` uses opening seed ``seed + i`` and the deeper side plays
    white when ``i`` is even. Resume (`start_game`/`game_records`) tallies
    prior contiguous records without replay; `deadline`/`stop_event` are
    checked before every game and forwarded into every game/search;
    `on_game_complete(index, record, aggregate)` fires once per game.
    """
    if n_games <= 0:
        raise ValueError("n_games must be positive")
    records = _validate_prior_records(game_records, start_game, n_games)

    wins = sum(record["outcome"] == "win" for record in records)
    draws = sum(record["outcome"] == "draw" for record in records)
    losses = sum(record["outcome"] == "loss" for record in records)

    extra_bounds: dict = {}
    if deadline is not None:
        extra_bounds["deadline"] = deadline
    if stop_event is not None:
        extra_bounds["stop_event"] = stop_event

    for game_index in range(start_game, n_games):
        check_harness_expiry(stop_event, deadline)
        deep_white = game_index % 2 == 0
        game_seed = seed + game_index
        outcome = play_depth_match_game(
            shallow_depth,
            deep_depth,
            evaluator,
            deep_white,
            seed=game_seed,
            max_halfmoves=max_halfmoves,
            **extra_bounds,
        )
        if outcome == "win":
            wins += 1
        elif outcome == "draw":
            draws += 1
        else:
            losses += 1

        record = {"index": game_index, "seed": game_seed, "outcome": outcome}
        records.append(record)
        if on_game_complete is not None:
            games_so_far = game_index + 1
            on_game_complete(
                game_index,
                record,
                {
                    "wins": wins,
                    "draws": draws,
                    "losses": losses,
                    "n_games": games_so_far,
                    "score_rate": (wins + 0.5 * draws) / games_so_far,
                },
            )

    score_rate = (wins + 0.5 * draws) / n_games
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score_rate": score_rate,
        "n_games": n_games,
    }
