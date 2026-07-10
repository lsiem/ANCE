"""Reusable UCI self-play gauntlet and clock referee (D-14 through D-19).

The default runner drives two external engines with python-chess, charges each
move's measured wall time to the mover, and adjudicates flag falls itself.
Results are atomically checkpointed after every game for safe interruption and
resume.  A cutechess-cli passthrough is available when that binary is on PATH.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shlex
import shutil
import signal
import subprocess
import sys
import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import chess
import chess.engine

from ance.tools.random_mover_gauntlet import HarnessTimeout, check_harness_expiry

SCHEMA_VERSION = 1
DEFAULT_OPENINGS = Path(__file__).with_name("openings.epd")

__all__ = [
    "EngineSpec",
    "HarnessTimeout",
    "build_cutechess_command",
    "detect_runner",
    "load_openings",
    "main",
    "play_gauntlet_game",
    "run_gauntlet",
    "wilson_ci",
]


@dataclass(frozen=True)
class EngineSpec:
    """A display name and an argv-safe UCI engine command."""

    name: str
    argv: list[str]


def load_openings(path: str | Path) -> list[str]:
    """Load full FEN lines, ignoring blank lines and comments."""
    openings = [
        line.strip()
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not openings:
        raise ValueError(f"opening file has no positions: {path}")
    for line_number, fen in enumerate(openings, start=1):
        try:
            chess.Board(fen)
        except ValueError as exc:
            raise ValueError(f"invalid opening FEN {line_number} in {path}: {exc}") from exc
    return openings


def wilson_ci(
    score_points: float, n: int, z: float = 1.96
) -> tuple[float, float]:
    """Return the closed-form Wilson interval for a fractional score."""
    if n <= 0:
        return (0.0, 1.0)
    if not 0.0 <= score_points <= n:
        raise ValueError("score_points must be within [0, n]")
    p = score_points / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(
        p * (1 - p) / n + z * z / (4 * n * n)
    ) / denom
    return center - half, center + half


def _color_name(color: chess.Color) -> str:
    return "white" if color == chess.WHITE else "black"


def play_gauntlet_game(
    engine_white: Any,
    engine_black: Any,
    opening_fen: str,
    tc_base_s: float,
    tc_inc_s: float,
    max_halfmoves: int,
    game_key: object,
    stop_event: threading.Event | None,
    deadline: float | None,
) -> dict[str, Any]:
    """Play one game while independently refereeing both wall clocks."""
    if tc_base_s <= 0 or tc_inc_s < 0:
        raise ValueError("time control must have positive base and non-negative increment")
    if max_halfmoves <= 0:
        raise ValueError("max_halfmoves must be positive")

    board = chess.Board(opening_fen)
    engines = {chess.WHITE: engine_white, chess.BLACK: engine_black}
    clocks = {chess.WHITE: tc_base_s, chess.BLACK: tc_base_s}
    halfmoves = 0
    elapsed_total = 0.0

    while not board.is_game_over(claim_draw=True) and halfmoves < max_halfmoves:
        check_harness_expiry(stop_event, deadline)
        mover = board.turn
        limit = chess.engine.Limit(
            white_clock=clocks[chess.WHITE],
            black_clock=clocks[chess.BLACK],
            white_inc=tc_inc_s,
            black_inc=tc_inc_s,
        )
        started = time.monotonic()
        play_result = engines[mover].play(board, limit, game=game_key)
        elapsed = max(0.0, time.monotonic() - started)
        elapsed_total += elapsed
        clocks[mover] -= elapsed
        if clocks[mover] < 0:
            forfeited_by = _color_name(mover)
            return {
                "outcome": "time_forfeit",
                "result": "0-1" if mover == chess.WHITE else "1-0",
                "reason": "time_forfeit",
                "moves": halfmoves,
                "forfeited_by": forfeited_by,
                "elapsed_s": elapsed_total,
            }

        # Increment is earned only after a move finishes within the clock.
        clocks[mover] += tc_inc_s
        move = play_result.move
        if move is None or move not in board.legal_moves:
            raise ValueError(
                f"engine returned no legal move for {_color_name(mover)}: {move}"
            )
        board.push(move)
        halfmoves += 1

    if halfmoves >= max_halfmoves and not board.is_game_over(claim_draw=True):
        return {
            "outcome": "draw",
            "result": "1/2-1/2",
            "reason": "halfmove_cap",
            "moves": halfmoves,
            "forfeited_by": None,
            "elapsed_s": elapsed_total,
        }

    outcome = board.outcome(claim_draw=True)
    if outcome is None:
        raise RuntimeError("game ended without a classifiable outcome")
    result = outcome.result()
    white_outcome = "draw" if outcome.winner is None else (
        "win" if outcome.winner == chess.WHITE else "loss"
    )
    return {
        "outcome": white_outcome,
        "result": result,
        "reason": outcome.termination.name.lower(),
        "moves": halfmoves,
        "forfeited_by": None,
        "elapsed_s": elapsed_total,
    }


def _format_number(value: float) -> str:
    return format(value, "g")


def _tc_string(base: float, increment: float) -> str:
    return f"{_format_number(base)}+{_format_number(increment)}"


def _parameters(
    spec_a: EngineSpec,
    spec_b: EngineSpec,
    openings: list[str],
    n_games: int,
    tc_base_s: float,
    tc_inc_s: float,
    max_halfmoves: int,
    openings_path: str | Path | None,
) -> dict[str, Any]:
    return {
        "engine_a": {"name": spec_a.name, "argv": list(spec_a.argv)},
        "engine_b": {"name": spec_b.name, "argv": list(spec_b.argv)},
        "n_games": n_games,
        "tc": _tc_string(tc_base_s, tc_inc_s),
        "tc_base_s": tc_base_s,
        "tc_inc_s": tc_inc_s,
        "max_halfmoves": max_halfmoves,
        "openings_path": str(openings_path) if openings_path is not None else "<memory>",
        "openings": list(openings),
    }


def _default_command_line(
    spec_a: EngineSpec,
    spec_b: EngineSpec,
    parameters: dict[str, Any],
    output_path: Path,
) -> str:
    argv = [
        sys.executable,
        "-m",
        "ance.tools.gauntlet",
        "--games",
        str(parameters["n_games"]),
        "--tc",
        parameters["tc"],
        "--openings",
        parameters["openings_path"],
        "--output",
        str(output_path),
        "--max-halfmoves",
        str(parameters["max_halfmoves"]),
        "--engine-a",
        shlex.join(spec_a.argv),
        "--engine-b",
        shlex.join(spec_b.argv),
        "--runner",
        "arbiter",
    ]
    return shlex.join(argv)


def _aggregate(games: list[dict[str, Any]], spec_a: EngineSpec, spec_b: EngineSpec) -> dict[str, Any]:
    wins = sum(game["outcome"] == "win" for game in games)
    losses = sum(game["outcome"] == "loss" for game in games)
    draws = sum(game["outcome"] == "draw" for game in games)
    n = len(games)
    score_points = wins + 0.5 * draws
    low, high = wilson_ci(score_points, n)
    forfeits = {spec_a.name: 0, spec_b.name: 0}
    for game in games:
        forfeited = game.get("forfeited_by")
        if forfeited is None:
            continue
        a_forfeited = (forfeited == "white") == bool(game["a_is_white"])
        forfeits[spec_a.name if a_forfeited else spec_b.name] += 1
    return {
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "score_rate": score_points / n if n else 0.0,
        "draw_rate": draws / n if n else 0.0,
        "wilson_low": low,
        "wilson_high": high,
        "time_forfeits": forfeits,
        "n_games": n,
        "elapsed_s": sum(float(game.get("elapsed_s", 0.0)) for game in games),
    }


def _atomic_write_json(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _validate_checkpoint(
    state: dict[str, Any], parameters: dict[str, Any]
) -> list[dict[str, Any]]:
    if (
        state.get("schema_version") != SCHEMA_VERSION
        or state.get("parameters") != parameters
    ):
        raise ValueError("existing checkpoint has incompatible schema or parameters")
    games = state.get("games")
    if not isinstance(games, list):
        raise ValueError("existing checkpoint has incompatible game records")
    indices = [game.get("index") for game in games]
    if indices != list(range(len(games))) or len(games) > parameters["n_games"]:
        raise ValueError("existing checkpoint has incompatible game records")
    return games


def _new_state(parameters: dict[str, Any], command_line: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "parameters": parameters,
        "command_line": command_line,
        "games": [],
        "aggregate": {},
        "status": "running",
        "completion": "incomplete",
    }


def _a_outcome(raw_outcome: str, a_is_white: bool) -> str:
    if raw_outcome == "draw":
        return "draw"
    if raw_outcome == "time_forfeit":
        raise ValueError("time_forfeit must be classified from forfeited_by")
    if raw_outcome not in {"win", "loss"}:
        raise ValueError(f"unknown game outcome: {raw_outcome}")
    if a_is_white:
        return raw_outcome
    return "loss" if raw_outcome == "win" else "win"


def run_gauntlet(
    spec_a: EngineSpec,
    spec_b: EngineSpec,
    openings: list[str],
    n_games: int,
    tc_base_s: float,
    tc_inc_s: float,
    max_halfmoves: int,
    output_path: str | Path,
    stop_event: threading.Event | None = None,
    deadline: float | None = None,
    on_game_complete: Callable[[int, dict[str, Any], dict[str, Any]], None]
    | None = None,
    restart: bool = False,
    *,
    openings_path: str | Path | None = None,
    command_line: str | None = None,
) -> dict[str, Any]:
    """Run or resume an atomically checkpointed, color-paired gauntlet."""
    if n_games <= 0:
        raise ValueError("n_games must be positive")
    if not openings:
        raise ValueError("openings must not be empty")
    if not spec_a.argv or not spec_b.argv:
        raise ValueError("engine argv lists must not be empty")

    output = Path(output_path)
    parameters = _parameters(
        spec_a,
        spec_b,
        openings,
        n_games,
        tc_base_s,
        tc_inc_s,
        max_halfmoves,
        openings_path,
    )
    exact_command = command_line or _default_command_line(
        spec_a, spec_b, parameters, output
    )
    if output.exists() and not restart:
        try:
            state = json.loads(output.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"existing checkpoint is unreadable: {exc}") from exc
        games = _validate_checkpoint(state, parameters)
        if state.get("status") == "completed" and len(games) == n_games:
            return state
        state["status"] = "running"
        state["completion"] = "incomplete"
        state.pop("error", None)
    else:
        state = _new_state(parameters, exact_command)
        games = state["games"]
    _atomic_write_json(output, state)

    event = stop_event if stop_event is not None else threading.Event()
    engine_a: Any | None = None
    engine_b: Any | None = None
    try:
        check_harness_expiry(event, deadline)
        engine_a = chess.engine.SimpleEngine.popen_uci(spec_a.argv)
        engine_b = chess.engine.SimpleEngine.popen_uci(spec_b.argv)
        for game_index in range(len(games), n_games):
            check_harness_expiry(event, deadline)
            opening_index = (game_index // 2) % len(openings)
            a_is_white = game_index % 2 == 0
            white = engine_a if a_is_white else engine_b
            black = engine_b if a_is_white else engine_a
            raw = play_gauntlet_game(
                white,
                black,
                openings[opening_index],
                tc_base_s,
                tc_inc_s,
                max_halfmoves,
                game_key=f"gauntlet-{game_index}",
                stop_event=event,
                deadline=deadline,
            )
            if raw["outcome"] == "time_forfeit":
                a_forfeited = (raw["forfeited_by"] == "white") == a_is_white
                a_outcome = "loss" if a_forfeited else "win"
            else:
                a_outcome = _a_outcome(str(raw["outcome"]), a_is_white)
            record = {
                "index": game_index,
                "opening_index": opening_index,
                "a_is_white": a_is_white,
                **raw,
                "outcome": a_outcome,
            }
            games.append(record)
            state["aggregate"] = _aggregate(games, spec_a, spec_b)
            _atomic_write_json(output, state)
            if on_game_complete is not None:
                on_game_complete(
                    game_index, dict(record), dict(state["aggregate"])
                )

        state["status"] = "completed"
        state["completion"] = "complete"
        state["aggregate"] = _aggregate(games, spec_a, spec_b)
        _atomic_write_json(output, state)
        return state
    except BaseException as exc:
        state["status"] = "failed"
        state["completion"] = "incomplete"
        state["aggregate"] = _aggregate(games, spec_a, spec_b)
        state["error"] = f"{type(exc).__name__}: {exc}"
        _atomic_write_json(output, state)
        raise
    finally:
        if engine_b is not None:
            with suppress(Exception):
                engine_b.quit()
        if engine_a is not None:
            with suppress(Exception):
                engine_a.quit()


def detect_runner() -> str:
    """Prefer cutechess-cli when available, otherwise use the arbiter."""
    return "cutechess" if shutil.which("cutechess-cli") else "arbiter"


def _engine_arguments(spec: EngineSpec) -> list[str]:
    fields = [
        "-engine",
        f"name={spec.name}",
        f"cmd={spec.argv[0]}",
    ]
    fields.extend(f"arg={argument}" for argument in spec.argv[1:])
    return fields


def build_cutechess_command(
    spec_a: EngineSpec,
    spec_b: EngineSpec,
    tc: str,
    openings_path: str | Path,
    games: int,
    rounds: int,
    pgnout: str | Path,
) -> list[str]:
    """Build an argv-only cutechess-cli paired-opening invocation."""
    return [
        "cutechess-cli",
        *_engine_arguments(spec_a),
        *_engine_arguments(spec_b),
        "-each",
        "proto=uci",
        f"tc={tc}",
        "-openings",
        f"file={openings_path}",
        "format=epd",
        "order=sequential",
        "-games",
        str(games),
        "-rounds",
        str(rounds),
        "-repeat",
        "-pgnout",
        str(pgnout),
    ]


def _parse_tc(value: str) -> tuple[float, float]:
    base_text, separator, increment_text = value.partition("+")
    if not separator:
        raise argparse.ArgumentTypeError("time control must be BASE+INC")
    try:
        base = float(base_text)
        increment = float(increment_text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("time control must be numeric BASE+INC") from exc
    if base <= 0 or increment < 0:
        raise argparse.ArgumentTypeError(
            "time control requires positive BASE and non-negative INC"
        )
    return base, increment


def _build_parser() -> argparse.ArgumentParser:
    default_engine = shlex.join([sys.executable, "-m", "ance"])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--games", type=int, default=2)
    parser.add_argument("--tc", default="30+0.3")
    parser.add_argument("--openings", type=Path, default=DEFAULT_OPENINGS)
    parser.add_argument("--output", type=Path, default=Path("gauntlet.json"))
    parser.add_argument("--max-halfmoves", type=int, default=160)
    parser.add_argument("--engine-a", default=default_engine)
    parser.add_argument("--engine-b", default=default_engine)
    parser.add_argument("--engine-a-name", default="engine-a")
    parser.add_argument("--engine-b-name", default="engine-b")
    parser.add_argument(
        "--runner",
        choices=("auto", "arbiter", "cutechess"),
        default="auto",
    )
    parser.add_argument("--restart", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--budget-seconds", type=float, default=None)
    return parser


def _status(output: Path) -> int:
    if not output.exists():
        print(f"error: checkpoint does not exist: {output}", file=sys.stderr)
        return 1
    try:
        state = json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot read checkpoint: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(state, indent=2))
    if state.get("status") == "completed":
        return 0
    if state.get("status") == "failed":
        return 1
    return 3


def _run_cutechess(
    spec_a: EngineSpec,
    spec_b: EngineSpec,
    tc: str,
    openings_path: Path,
    games: int,
    output: Path,
) -> int:
    if games <= 0 or games % 2:
        raise ValueError("cutechess runner requires a positive even --games count")
    command = build_cutechess_command(
        spec_a,
        spec_b,
        tc,
        openings_path,
        games=2,
        rounds=games // 2,
        pgnout=output.with_suffix(".pgn"),
    )
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    state = {
        "schema_version": SCHEMA_VERSION,
        "runner": "cutechess",
        "command": command,
        "command_line": shlex.join(command),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "returncode": completed.returncode,
        "status": "completed" if completed.returncode == 0 else "failed",
        "completion": "complete" if completed.returncode == 0 else "incomplete",
    }
    _atomic_write_json(output, state)
    return completed.returncode


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.status:
        return _status(args.output)

    try:
        base, increment = _parse_tc(args.tc)
        spec_a = EngineSpec(args.engine_a_name, shlex.split(args.engine_a))
        spec_b = EngineSpec(args.engine_b_name, shlex.split(args.engine_b))
        runner = detect_runner() if args.runner == "auto" else args.runner
        if runner == "cutechess":
            return _run_cutechess(
                spec_a, spec_b, args.tc, args.openings, args.games, args.output
            )

        openings = load_openings(args.openings)
        event = threading.Event()

        def request_stop(signum: int, frame: object) -> None:
            del signum, frame
            event.set()

        previous_handlers: dict[int, Any] = {}
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                previous_handlers[sig] = signal.signal(sig, request_stop)
            except ValueError:
                pass
        try:
            deadline = (
                time.monotonic() + args.budget_seconds
                if args.budget_seconds is not None
                else None
            )
            command_line = shlex.join(
                [sys.executable, "-m", "ance.tools.gauntlet", *(argv or sys.argv[1:])]
            )
            report = run_gauntlet(
                spec_a,
                spec_b,
                openings,
                args.games,
                base,
                increment,
                args.max_halfmoves,
                args.output,
                stop_event=event,
                deadline=deadline,
                restart=args.restart,
                openings_path=args.openings,
                command_line=command_line,
            )
        finally:
            for sig, handler in previous_handlers.items():
                signal.signal(sig, handler)
        print(json.dumps(report["aggregate"], indent=2))
        return 0
    except (HarnessTimeout, ValueError, OSError, chess.engine.EngineError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
