"""Self-play gauntlet: ANCE's real `search_root` + evaluator, in-process
(not over a UCI pipe -- this is a measurement tool, not a protocol test),
against a uniformly-random legal-move opponent (TOOL-02).

`GAUNTLET_SEARCH_DEPTH` is deliberately decoupled from
`ance.search.negamax.DEFAULT_DEPTH`: the interactive default is tuned for
sub-second GUI responsiveness (Plans 01-03/01-04) and may be lowered further
for that purpose, while the gauntlet is an offline correctness/strength
proof, independent of interactive-speed tuning.

REPLAN (01-05, approved 2026-07-07): the original acceptance criterion --
wins == 100, losses == 0 out of 100 games at GAUNTLET_SEARCH_DEPTH = 4 --
proved both impractical and unproven in practice. A real run of the
depth-4/100-game suite was killed after 31 minutes without finishing
(pure-Python, unpruned negamax is too slow at depth 4 for a per-commit/
per-wave test), and a depth-3 spot check already produced a draw, so even
the strict 100/0 target at depth 4 was never actually measured green.

The invariant that DOES hold, and is measured, is stronger than it looks:
ANCE never loses to the uniformly-random mover. Deterministic evidence
(seeds 0..29, GAUNTLET_SEARCH_DEPTH = 2, ~31s wall-clock): 25 wins, 0
losses, 5 draws (83% win rate), and all 5 draws are `max_halfmoves` (300)
cap conversions -- shallow search finds a winning material edge but can't
force mate within the cap -- never a loss or a stalemate.

The new, authoritative acceptance criterion (Phase 02-05, depth 4 with alpha-beta):
- HARD invariant: `losses == 0` always. A loss to a uniformly-random mover
  is always a real bug, never acceptable statistical noise.
- `GAUNTLET_SEARCH_DEPTH = 4` — raised from 2 now that alpha-beta +
  quiescence make deeper search practical in wall-clock time.
- The slow test runs `n_games=3` at depth 4 (~30 min measured wall-clock
  on 2026-07-08 with HandcraftedEval). Win-rate floor from Phase 01-05
  (70%) is relaxed at depth 4 — cap-draws are expected; losses==0 is the
  non-negotiable gate per D-01.

DEFERRED (tracked, not asserted here): "100 wins / 0 draws at depth 4" —
converting cap-draws into wins needs further pruning/ordering phases.
See `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md`.
"""

from __future__ import annotations

import random
import threading
import time
from typing import Callable, NamedTuple

import chess

from ance.board.position import Position
from ance.eval.base import Evaluator
from ance.search.negamax import search_root

GAUNTLET_SEARCH_DEPTH = 4


class HarnessTimeout(Exception):
    """Raised when a game harness hits its shared deadline or the shared
    cancellation event is set. Shared by the random-mover gauntlet, the
    depth-vs-depth match, and the Phase 2 evidence runner (Plan 02-10)."""


def check_harness_expiry(
    stop_event: threading.Event | None, deadline: float | None
) -> None:
    """Raise `HarnessTimeout` when the shared cancellation event is set or
    the shared absolute monotonic `deadline` has been reached/passed.

    No-op (and no clock read) when neither bound is supplied, preserving
    the pre-02-10 unbounded behavior for legacy callers.
    """
    if stop_event is not None and stop_event.is_set():
        raise HarnessTimeout("cancelled: shared stop event is set")
    if deadline is not None and time.monotonic() >= deadline:
        raise HarnessTimeout(f"deadline expired (deadline={deadline})")


def _validate_prior_records(
    game_records: list[dict] | None, start_game: int, n_games: int
) -> list[dict]:
    """Validate resume inputs: `game_records` must cover exactly the
    contiguous indices `[0, start_game)` and `start_game` must be a valid
    offset into `[0, n_games]`."""
    if start_game < 0 or start_game > n_games:
        raise ValueError(
            f"start_game must be within [0, {n_games}], got {start_game}"
        )
    records = list(game_records or [])
    indices = [record["index"] for record in records]
    if indices != list(range(start_game)):
        raise ValueError(
            "game_records must cover contiguous indices "
            f"[0, {start_game}), got {indices}"
        )
    return records


class RandomMover:
    """Uniformly-random legal-move chooser, seeded for reproducibility."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def choose(self, board: chess.Board) -> chess.Move:
        return self._rng.choice(list(board.legal_moves))


class GameResult(NamedTuple):
    """Outcome of a single `play_game()` call: the python-chess result
    string plus the final position's FEN, so a non-win game can be
    diagnosed later without replaying it (cross-AI review finding)."""

    result: str
    terminal_fen: str


def play_game(
    ance_depth: int,
    ance_evaluator: Evaluator,
    ance_plays_white: bool,
    seed: int,
    max_halfmoves: int = 300,
    *,
    deadline: float | None = None,
    stop_event: threading.Event | None = None,
) -> GameResult:
    """Plays one game between ANCE (`search_root` + `ance_evaluator`) and a
    seeded `RandomMover`, alternating turns until `pos.board.is_game_over()`
    or the `max_halfmoves` safety cap is hit (T-01-11: guarantees this
    function always terminates even if a bug ever produced a pathological
    non-terminating line; a cap-hit is treated as `"1/2-1/2"` to keep this
    function total).

    When the caller supplies the shared `stop_event`/`deadline` pair
    (Plan 02-10 evidence runs), both bounds are checked before every ply
    and again immediately after every `search_root` return, so an expired
    search result is never pushed, and the same pair is forwarded into
    every `search_root` call for in-tree polling (Plan 02-07). When
    omitted, each ANCE move gets a fresh, un-set `threading.Event()` and
    no deadline, preserving the original unbounded harness behavior.
    """
    pos = Position()
    halfmoves = 0
    ance_color = chess.WHITE if ance_plays_white else chess.BLACK
    event = stop_event if stop_event is not None else threading.Event()

    while not pos.board.is_game_over() and halfmoves < max_halfmoves:
        check_harness_expiry(event, deadline)
        if pos.board.turn == ance_color:
            move = search_root(
                pos, ance_depth, ance_evaluator, event, deadline=deadline
            ).best_move
            check_harness_expiry(event, deadline)
        else:
            move = RandomMover(seed).choose(pos.board)
        if move is None:
            break
        check_harness_expiry(event, deadline)
        pos.board.push(move)
        halfmoves += 1

    result = pos.board.result() if pos.board.is_game_over() else "1/2-1/2"
    return GameResult(result=result, terminal_fen=pos.board.fen())


def run_gauntlet(
    n_games: int,
    ance_depth: int,
    evaluator: Evaluator,
    seed: int = 0,
    max_halfmoves: int = 300,
    start_game: int = 0,
    game_records: list[dict] | None = None,
    deadline: float | None = None,
    stop_event: threading.Event | None = None,
    on_game_complete: Callable[[int, dict, dict], None] | None = None,
) -> dict:
    """Plays `n_games` games of ANCE vs. a seeded `RandomMover`, alternating
    which color ANCE plays each game for fairness, and tallies the result
    from ANCE's perspective.

    Plan 02-10 controls (all backward-compatible keywords):
    - `seed`: game `i` uses RNG seed `seed + i` (default 0 preserves the
      historical `seed=game_index` behavior).
    - `max_halfmoves`: forwarded to every `play_game` call.
    - `start_game`/`game_records`: resume support — prior ordered records
      for contiguous indices `[0, start_game)` are tallied without replay
      and only `range(start_game, n_games)` is played.
    - `deadline`/`stop_event`: one shared absolute monotonic deadline and
      cancellation event, checked before every game and forwarded into
      every game/search; expiry raises `HarnessTimeout`.
    - `on_game_complete(index, record, aggregate)`: invoked exactly once
      per fully classified game, in order, for per-game checkpointing.

    Returns a dict with `wins`, `losses`, `draws`, and `non_win_games` --
    the last a list of `{"seed", "result", "terminal_fen"}` for every game
    ANCE did not win, so a rare non-win is diagnosable without re-running
    all `n_games` games (cross-AI review finding).

    Failure runbook (what to do if the `slow` test asserting
    `losses == 0 and wins >= 0.7 * n_games and wins + draws == n_games`
    fails on a given machine):

    1. FIRST inspect the failed assertion's `non_win_games` entries (seed,
       result, terminal FEN) to understand what actually happened before
       changing anything -- most non-wins are diagnosable from these three
       fields alone (e.g. a halfmove-cap draw vs. an actual tactical
       blunder or, worse, an actual loss).
    2. If `losses > 0`: STOP -- this is a real bug (a loss to a uniformly
       random mover is never acceptable statistical noise, regardless of
       search depth). Do not raise `GAUNTLET_SEARCH_DEPTH` or widen
       `max_halfmoves` to paper over a loss; debug the game via step 4.
    3. If `losses == 0` but `wins < 70%`: the diagnosis is insufficient
       search strength (shallow, non-pruned search finds a winning
       material edge but can't force mate before the `max_halfmoves`
       (currently 300) cap converts it to a draw -- this is expected and
       accounted for by the 70% floor, not a bug). Raising
       `GAUNTLET_SEARCH_DEPTH` further is the fix in principle, but is
       deliberately DEFERRED until alpha-beta pruning makes deeper search
       practical in wall-clock time (see the module docstring's REPLAN
       note and the tracked follow-up todo) -- do not raise the depth as
       an ad hoc fix without pruning, since depth 4 was measured to take
       >31 minutes for a 100-game run unpruned.
    4. Do NOT touch the interactive `DEFAULT_DEPTH` constant in
       `ance/search/negamax.py` to fix a gauntlet failure: it is
       deliberately decoupled from `GAUNTLET_SEARCH_DEPTH` precisely so
       GUI-responsiveness tuning never weakens the gauntlet's proof, and
       adjusting it here would not address a gauntlet-strength issue
       anyway.
    5. As a last resort, reproduce a specific non-win directly via
       `play_game(GAUNTLET_SEARCH_DEPTH, HandcraftedEval(), ...,
       seed=<seed_from_non_win_games>)` outside the full 30-game run for
       focused debugging.

    `losses == 0` must hold regardless of any tuning -- a loss to a uniform
    random mover indicates a real bug, not statistical noise, and is never
    relaxed. The 70%-win floor and "every non-win is a draw" invariant are
    the strength requirement; the strict 100/0 target (zero draws) at
    deeper search is DEFERRED to a future pruning phase, not asserted here.

    Expected wall-clock time: roughly 30 seconds for 30 full games of
    non-pruned negamax at `GAUNTLET_SEARCH_DEPTH = 2` (measured ~31s at
    authoring) -- a run taking well under a minute is expected, not a hang.
    """
    if n_games <= 0:
        raise ValueError("n_games must be positive")
    records = _validate_prior_records(game_records, start_game, n_games)

    wins = sum(record["outcome"] == "win" for record in records)
    losses = sum(record["outcome"] == "loss" for record in records)
    draws = sum(record["outcome"] == "draw" for record in records)
    non_win_games: list[dict] = [
        {
            "seed": record["seed"],
            "result": record.get("result", "*"),
            "terminal_fen": record.get("terminal_fen", ""),
        }
        for record in records
        if record["outcome"] != "win"
    ]

    extra_bounds: dict = {}
    if deadline is not None:
        extra_bounds["deadline"] = deadline
    if stop_event is not None:
        extra_bounds["stop_event"] = stop_event

    for game_index in range(start_game, n_games):
        check_harness_expiry(stop_event, deadline)
        ance_plays_white = game_index % 2 == 0
        game_seed = seed + game_index
        game_result = play_game(
            ance_depth,
            evaluator,
            ance_plays_white,
            seed=game_seed,
            max_halfmoves=max_halfmoves,
            **extra_bounds,
        )

        if game_result.result == "1/2-1/2":
            outcome = "draw"
            draws += 1
        elif (game_result.result == "1-0") == ance_plays_white:
            outcome = "win"
            wins += 1
        else:
            outcome = "loss"
            losses += 1

        record = {
            "index": game_index,
            "seed": game_seed,
            "outcome": outcome,
            "result": game_result.result,
            "terminal_fen": game_result.terminal_fen,
        }
        if outcome != "win":
            non_win_games.append(
                {
                    "seed": game_seed,
                    "result": game_result.result,
                    "terminal_fen": game_result.terminal_fen,
                }
            )
        records.append(record)
        if on_game_complete is not None:
            on_game_complete(
                game_index,
                record,
                {
                    "wins": wins,
                    "losses": losses,
                    "draws": draws,
                    "non_win_games": list(non_win_games),
                    "n_games": game_index + 1,
                },
            )

    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "non_win_games": non_win_games,
        "n_games": n_games,
    }
