"""Phase 2 bounded, resumable strength-evidence runner (Plan 02-10).

Replaces the invalid undersized/over-budget strength claims with one
reproducible 30+30 game evidence run under an explicit shared budget:

- 30 opening-varied depth-2 vs depth-3 games (D-14 original sample bound):
  deeper side must score >= 0.50.
- 30 depth-4 games vs the seeded random mover (D-01 executable replacement):
  losses must be 0, reported with the one-sided 95% upper loss-rate bound
  ``1 - 0.05 ** (1 / n)``.

D-01's original acceptance — 100 depth-4 games within 600 seconds — is
recorded as infeasible rather than silently weakened: 3 games measured at
1566 seconds projects to about 52,200 seconds (~14.5 hours) for 100 games.

One absolute monotonic deadline is derived from the remaining budget and
forwarded, together with one shared cancellation Event, through both game
harnesses into every ``search_root`` call. The evidence state is atomically
checkpointed (tmp file + flush + fsync + ``os.replace``) after every
completed game and every suite transition; a compatible rerun resumes at the
first missing game and never replays completed games or suites. Deadline
expiry, SIGINT/SIGTERM, KeyboardInterrupt, and the supervisor's forced-kill
fallback (``--mark-interrupted``) all leave ``status="failed"`` with
``completion="incomplete"`` and exit non-zero, so no partial run can be
classified as passed.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from ance.eval.handcrafted import HandcraftedEval
from ance.tools.depth_vs_depth_match import run_depth_match
from ance.tools.random_mover_gauntlet import HarnessTimeout, run_gauntlet

__all__ = [
    "EvidenceInterrupted",
    "EvidenceParameters",
    "HarnessTimeout",
    "append_game_checkpoint",
    "atomic_write_json",
    "main",
    "new_checkpoint",
]

SCHEMA_VERSION = 1
MIN_GAMES = 30
SHALLOW_DEPTH = 2
DEEP_DEPTH = 3
RANDOM_DEPTH = 4
SUITE_KEYS = ("depth_match", "random_gauntlet")

DECISION_REPLACEMENT = {
    "original": (
        "D-01 original acceptance: 100 depth-4 games vs the random mover "
        "within a 600-second budget"
    ),
    "measured": "3 depth-4 games measured at 1566 seconds wall-clock",
    "projection": (
        "about 52200 seconds (~14.5 hours) for 100 games — infeasible "
        "within 600 seconds"
    ),
    "replacement": (
        "30 games at depth 4, max 80 halfmoves, within one combined "
        "7200-second budget, losses == 0, with a one-sided 95% upper "
        "loss-rate bound"
    ),
}


class EvidenceInterrupted(Exception):
    """Controlled interruption raised by the SIGINT/SIGTERM handlers."""


_ACTIVE_EVENT: threading.Event | None = None


@dataclass(frozen=True)
class EvidenceParameters:
    """User-controllable evidence parameters (fixed depths are appended by
    `new_checkpoint` so the persisted parameter set is complete)."""

    seed: int
    depth_games: int
    random_games: int
    max_halfmoves: int
    budget_seconds: float


def _parameters_dict(params: EvidenceParameters) -> dict[str, Any]:
    return {
        **asdict(params),
        "shallow_depth": SHALLOW_DEPTH,
        "deep_depth": DEEP_DEPTH,
        "random_depth": RANDOM_DEPTH,
    }


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat()


def _git_commit() -> str | None:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=5,
        )
    except Exception:
        return None
    return completed.stdout.strip() or None


def atomic_write_json(path: Path, state: dict[str, Any]) -> None:
    """Write ``state`` to ``path`` via a sibling temporary file with
    flush + fsync + ``os.replace`` so a crash can never leave a torn or
    partially written report (T-02-10d)."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(state, handle, indent=2)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp, path)


def new_checkpoint(params: EvidenceParameters) -> dict[str, Any]:
    """Fresh evidence checkpoint: both suites pending, no games, zero
    consumed elapsed, current-attempt monotonic/UTC start metadata."""
    return {
        "schema_version": SCHEMA_VERSION,
        "created_utc": _utc_now_iso(),
        "git_commit": _git_commit(),
        "parameters": _parameters_dict(params),
        "suites": {
            key: {
                "status": "pending",
                "completed_games": 0,
                "games": [],
                "aggregate": {},
            }
            for key in SUITE_KEYS
        },
        "elapsed_seconds": {"depth_match": 0.0, "random_gauntlet": 0.0, "total": 0.0},
        "remaining_budget_seconds": params.budget_seconds,
        "confidence": {},
        "decision_replacement": dict(DECISION_REPLACEMENT),
        "status": "running",
        "completion": "incomplete",
        "reasons": [],
        "attempt": {
            "started_monotonic": time.monotonic(),
            "started_utc": _utc_now_iso(),
            "base_elapsed_total": 0.0,
        },
    }


def append_game_checkpoint(
    state: dict[str, Any],
    suite_key: str,
    index: int,
    record: dict[str, Any],
    aggregate: dict[str, Any],
    output: Path,
) -> None:
    """Append exactly the next game record for ``suite_key`` and atomically
    persist the checkpoint. Duplicate or out-of-order callbacks are rejected
    rather than double-counted (T-02-10e)."""
    suite = state["suites"][suite_key]
    expected = suite["completed_games"]
    if index != expected:
        raise ValueError(
            f"duplicate or out-of-order game callback for {suite_key}: "
            f"expected game index {expected}, got {index}"
        )
    suite["games"].append(record)
    suite["completed_games"] = expected + 1
    suite["status"] = "running"
    suite["aggregate"] = aggregate
    atomic_write_json(output, state)


def _checkpoint_is_compatible(
    state: dict[str, Any], params: EvidenceParameters
) -> bool:
    """Validate the persisted schema, parameters, suite states, and ordered
    records before any resumed play can begin."""
    if state.get("schema_version") != SCHEMA_VERSION:
        return False
    if state.get("parameters") != _parameters_dict(params):
        return False
    try:
        suites = state["suites"]
        elapsed = state["elapsed_seconds"]
        float(elapsed["total"])
        for suite_key in SUITE_KEYS:
            suite = suites[suite_key]
            if suite["status"] not in {"pending", "running", "completed"}:
                return False
            completed = int(suite["completed_games"])
            games = suite["games"]
            expected_total = (
                params.depth_games
                if suite_key == "depth_match"
                else params.random_games
            )
            if completed < 0 or completed > expected_total:
                return False
            if len(games) != completed:
                return False
            if [game["index"] for game in games] != list(range(completed)):
                return False
            if [game["seed"] for game in games] != [
                params.seed + index for index in range(completed)
            ]:
                return False
            if suite["status"] == "completed" and completed != expected_total:
                return False
    except (KeyError, TypeError, ValueError):
        return False
    return True


def _handle_signal(signum: int, frame: Any) -> None:
    """SIGINT/SIGTERM handler: set the shared cancellation event so every
    in-flight search stops, then raise a controlled interruption handled on
    the main thread."""
    event = _ACTIVE_EVENT
    if event is not None:
        event.set()
    raise EvidenceInterrupted(
        f"interrupted by signal {signal.Signals(signum).name}"
    )


def _charge_elapsed(
    state: dict[str, Any],
    suite_key: str,
    last_mark: list[float],
    budget_seconds: float,
) -> None:
    """Attribute wall-clock time since the previous mark to ``suite_key``
    and the total, then refresh the persisted remaining budget."""
    now = time.monotonic()
    delta = max(0.0, now - last_mark[0])
    last_mark[0] = now
    elapsed = state["elapsed_seconds"]
    elapsed[suite_key] += delta
    elapsed["total"] += delta
    state["remaining_budget_seconds"] = max(
        0.0, budget_seconds - elapsed["total"]
    )


def _mark_interrupted(output: Path, reason: str) -> int:
    """Supervisor forced-kill fallback: atomically transition the last
    checkpoint to failed/incomplete without playing, preserving all
    completed records and charging elapsed time since the checkpointed
    attempt start so a forced kill cannot restore budget."""
    if not output.exists():
        print(f"error: no checkpoint found at {output}", file=sys.stderr)
        return 1
    state = json.loads(output.read_text(encoding="utf-8"))
    attempt = state.get("attempt") or {}
    candidates: list[float] = []
    started_monotonic = attempt.get("started_monotonic")
    if isinstance(started_monotonic, (int, float)):
        mono_delta = time.monotonic() - float(started_monotonic)
        if mono_delta >= 0:
            candidates.append(mono_delta)
    started_utc = attempt.get("started_utc")
    if isinstance(started_utc, str):
        try:
            utc_delta = (
                dt.datetime.now(dt.timezone.utc)
                - dt.datetime.fromisoformat(started_utc)
            ).total_seconds()
        except ValueError:
            utc_delta = -1.0
        if utc_delta >= 0:
            candidates.append(utc_delta)

    elapsed = state["elapsed_seconds"]
    base = float(attempt.get("base_elapsed_total", elapsed["total"]))
    charged = max(candidates, default=0.0)
    new_total = max(elapsed["total"], base + charged)
    extra = new_total - elapsed["total"]
    if extra > 0:
        active = next(
            (
                key
                for key in SUITE_KEYS
                if state["suites"][key]["status"] != "completed"
            ),
            SUITE_KEYS[-1],
        )
        elapsed[active] += extra
        elapsed["total"] = new_total
    budget = float(state["parameters"]["budget_seconds"])
    state["remaining_budget_seconds"] = max(0.0, budget - elapsed["total"])
    state["status"] = "failed"
    state["completion"] = "incomplete"
    state["reasons"].append(reason)
    atomic_write_json(output, state)
    return 1


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="phase2_strength_evidence",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--output", required=True, help="evidence JSON path")
    parser.add_argument("--seed", type=int, default=20260710)
    parser.add_argument("--depth-games", type=int, default=30)
    parser.add_argument("--random-games", type=int, default=30)
    parser.add_argument("--max-halfmoves", type=int, default=80)
    parser.add_argument("--budget-seconds", type=float, default=7200.0)
    parser.add_argument(
        "--restart",
        action="store_true",
        help="discard any existing checkpoint and start over "
        "(the ONLY way to drop incompatible or completed state)",
    )
    parser.add_argument(
        "--mark-interrupted",
        metavar="REASON",
        default=None,
        help="supervisor recovery: atomically mark the last checkpoint "
        "failed/incomplete without playing",
    )
    return parser


def _run_suites(
    state: dict[str, Any],
    params: EvidenceParameters,
    output: Path,
    deadline: float,
    stop_event: threading.Event,
    last_mark: list[float],
) -> None:
    """Run (or resume) both suites under the one shared deadline/Event,
    checkpointing after every game and every suite transition."""
    evaluator = HandcraftedEval()
    for suite_key in SUITE_KEYS:
        suite = state["suites"][suite_key]
        if suite["status"] == "completed":
            continue
        suite["status"] = "running"
        atomic_write_json(output, state)

        def on_game_complete(
            index: int,
            record: dict[str, Any],
            aggregate: dict[str, Any],
            _suite_key: str = suite_key,
        ) -> None:
            _charge_elapsed(state, _suite_key, last_mark, params.budget_seconds)
            append_game_checkpoint(
                state, _suite_key, index, record, aggregate, output
            )

        common = {
            "evaluator": evaluator,
            "seed": params.seed,
            "max_halfmoves": params.max_halfmoves,
            "start_game": suite["completed_games"],
            # Snapshot: callbacks append to the live state list; the runner
            # must see only the prior contiguous records.
            "game_records": list(suite["games"]),
            "deadline": deadline,
            "stop_event": stop_event,
            "on_game_complete": on_game_complete,
        }
        if suite_key == "depth_match":
            run_depth_match(
                shallow_depth=SHALLOW_DEPTH,
                deep_depth=DEEP_DEPTH,
                n_games=params.depth_games,
                **common,
            )
        else:
            run_gauntlet(
                n_games=params.random_games,
                ance_depth=RANDOM_DEPTH,
                **common,
            )
        _charge_elapsed(state, suite_key, last_mark, params.budget_seconds)
        suite["status"] = "completed"
        atomic_write_json(output, state)


def _classify(
    state: dict[str, Any], params: EvidenceParameters, output: Path
) -> int:
    """Final classification: passed only when both suites are completed with
    their full requested samples, depth score_rate >= 0.50, random
    losses == 0, and total consumed elapsed strictly within the budget."""
    reasons: list[str] = []
    depth_suite = state["suites"]["depth_match"]
    random_suite = state["suites"]["random_gauntlet"]

    samples_complete = (
        depth_suite["status"] == "completed"
        and random_suite["status"] == "completed"
        and depth_suite["completed_games"] == params.depth_games
        and random_suite["completed_games"] == params.random_games
    )
    state["completion"] = "complete" if samples_complete else "incomplete"
    if not samples_complete:
        reasons.append(
            "samples incomplete: depth "
            f"{depth_suite['completed_games']}/{params.depth_games}, random "
            f"{random_suite['completed_games']}/{params.random_games}"
        )

    depth_score = depth_suite["aggregate"].get("score_rate", 0.0)
    if depth_score < 0.5:
        reasons.append(
            f"depth-match score_rate {depth_score:.3f} is below the "
            "required 0.50"
        )

    random_losses = random_suite["aggregate"].get("losses")
    if random_losses == 0:
        state["confidence"]["zero_loss_upper_95"] = 1 - 0.05 ** (
            1 / params.random_games
        )
    else:
        reasons.append(
            f"random-mover gauntlet losses {random_losses} violate the "
            "losses == 0 invariant"
        )

    total = state["elapsed_seconds"]["total"]
    if total >= params.budget_seconds:
        reasons.append(
            f"consumed elapsed {total:.1f}s reached/exceeded the "
            f"{params.budget_seconds:.0f}s budget"
        )

    state["reasons"] = reasons
    state["status"] = "passed" if not reasons else "failed"
    atomic_write_json(output, state)
    return 0 if state["status"] == "passed" else 1


def main(argv: list[str] | None = None) -> int:
    global _ACTIVE_EVENT
    args = _build_parser().parse_args(argv)
    output = Path(args.output)

    if args.mark_interrupted is not None:
        return _mark_interrupted(output, args.mark_interrupted)

    params = EvidenceParameters(
        seed=args.seed,
        depth_games=args.depth_games,
        random_games=args.random_games,
        max_halfmoves=args.max_halfmoves,
        budget_seconds=float(args.budget_seconds),
    )

    if params.depth_games < MIN_GAMES or params.random_games < MIN_GAMES:
        state = new_checkpoint(params)
        state["status"] = "failed"
        state["completion"] = "incomplete"
        state["reasons"] = [
            f"depth_games and random_games must each be at least {MIN_GAMES} "
            f"(got depth_games={params.depth_games}, "
            f"random_games={params.random_games})"
        ]
        atomic_write_json(output, state)
        print(state["reasons"][0], file=sys.stderr)
        return 1

    if output.exists() and not args.restart:
        try:
            state = json.loads(output.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            state = {}
        if not _checkpoint_is_compatible(state, params):
            print(
                f"error: existing checkpoint at {output} has an incompatible "
                "schema or parameter set; pass --restart to explicitly "
                "discard it",
                file=sys.stderr,
            )
            return 1
        if state.get("completion") == "complete":
            # A finished run is never replayed; only --restart starts over.
            return 0 if state.get("status") == "passed" else 1
    else:
        state = new_checkpoint(params)
        atomic_write_json(output, state)

    print(
        "Phase 2 strength evidence: "
        f"shallow_depth={SHALLOW_DEPTH} deep_depth={DEEP_DEPTH} "
        f"random_depth={RANDOM_DEPTH} seed={params.seed} "
        f"depth_games={params.depth_games} random_games={params.random_games} "
        f"max_halfmoves={params.max_halfmoves} "
        f"budget_seconds={params.budget_seconds:.0f}"
    )

    # One new-process absolute deadline from the remaining budget: persisted
    # consumed elapsed reduces it across resumes, so interruption can never
    # restore spent time. The deadline is never reset between games/suites.
    base_elapsed = float(state["elapsed_seconds"]["total"])
    remaining_budget = params.budget_seconds - base_elapsed
    attempt_start = time.monotonic()
    state["attempt"] = {
        "started_monotonic": attempt_start,
        "started_utc": _utc_now_iso(),
        "base_elapsed_total": base_elapsed,
    }
    state["status"] = "running"
    deadline = attempt_start + remaining_budget
    stop_event = threading.Event()
    last_mark = [attempt_start]

    _ACTIVE_EVENT = stop_event
    previous_handlers: dict[int, Any] = {}
    try:
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                previous_handlers[sig] = signal.signal(sig, _handle_signal)
            except ValueError:
                pass  # not on the main thread; harness checks still bound us

        active_suite = SUITE_KEYS[0]
        try:
            for suite_key in SUITE_KEYS:
                if state["suites"][suite_key]["status"] != "completed":
                    active_suite = suite_key
                    break
            _run_suites(state, params, output, deadline, stop_event, last_mark)
            for suite_key in SUITE_KEYS:
                if state["suites"][suite_key]["status"] != "completed":
                    active_suite = suite_key
        except (HarnessTimeout, EvidenceInterrupted, KeyboardInterrupt) as exc:
            stop_event.set()
            for suite_key in SUITE_KEYS:
                if state["suites"][suite_key]["status"] != "completed":
                    active_suite = suite_key
                    break
            _charge_elapsed(state, active_suite, last_mark, params.budget_seconds)
            if isinstance(exc, KeyboardInterrupt):
                reason = "KeyboardInterrupt received during evidence run"
            elif isinstance(exc, HarnessTimeout):
                reason = f"harness deadline/cancellation: {exc}"
            else:
                reason = str(exc)
            state["status"] = "failed"
            state["completion"] = "incomplete"
            state["reasons"].append(reason)
            atomic_write_json(output, state)
            return 1

        return _classify(state, params, output)
    finally:
        _ACTIVE_EVENT = None
        for sig, handler in previous_handlers.items():
            signal.signal(sig, handler)


if __name__ == "__main__":
    raise SystemExit(main())
