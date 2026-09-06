"""Mid-train Elo probes (NNUE vs handcrafted) for best-by-Elo export."""

from __future__ import annotations

import math
import os
import sys
import tempfile
import time
from pathlib import Path

from ance.tools import gauntlet


def run_elo_probe(
    net_path: str | Path,
    *,
    n_games: int = 100,
    search_depth: int = 3,
    out_dir: str | Path | None = None,
    max_halfmoves: int = 160,
    budget_seconds: float = 14_400.0,
) -> dict:
    """Install net via ANCE_NNUE_PATH env on engine-a; return gauntlet report."""
    net_path = Path(net_path).resolve()
    if not net_path.is_file():
        raise FileNotFoundError(net_path)

    work = Path(out_dir) if out_dir is not None else Path(tempfile.mkdtemp(prefix="elo-probe-"))
    work.mkdir(parents=True, exist_ok=True)
    checkpoint = work / "probe-checkpoint.json"

    engine_argv = [sys.executable, "-m", "ance"]
    spec_nnue = gauntlet.EngineSpec(
        "nnue",
        list(engine_argv),
        env={"ANCE_EVAL": "nnue", "ANCE_NNUE_PATH": str(net_path)},
    )
    spec_hc = gauntlet.EngineSpec(
        "handcrafted",
        list(engine_argv),
        env={"ANCE_EVAL": "handcrafted"},
    )
    openings_path = gauntlet.DEFAULT_OPENINGS
    os.environ.setdefault(
        "ANCE_GAUNTLET_LIVE_PATH", str(work / "probe-live.json")
    )
    started = time.monotonic()
    report = gauntlet.run_gauntlet(
        spec_nnue,
        spec_hc,
        gauntlet.load_openings(openings_path),
        n_games=n_games,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=max_halfmoves,
        output_path=checkpoint,
        deadline=time.monotonic() + budget_seconds,
        openings_path=openings_path,
        command_line=f"elo_probe games={n_games} depth={search_depth} net={net_path}",
        search_depth=search_depth,
    )
    report["_wall_clock_elapsed_s"] = time.monotonic() - started
    report["_probe_out_dir"] = str(work)
    return report


def json_safe_number(value):
    """RFC JSON cannot encode NaN/±Inf; shutouts use null + score_rate=0."""
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    return value


def probe_summary(report: dict) -> dict:
    agg = report.get("aggregate") or {}
    elapsed = report.get("_wall_clock_elapsed_s")
    if elapsed is None:
        elapsed = agg.get("elapsed_s")
    return {
        "n_games": agg.get("n_games"),
        "wins": agg.get("wins"),
        "losses": agg.get("losses"),
        "draws": agg.get("draws"),
        "score_rate": json_safe_number(agg.get("score_rate")),
        "wilson_low": json_safe_number(agg.get("wilson_low")),
        "wilson_high": json_safe_number(agg.get("wilson_high")),
        "elo": json_safe_number(agg.get("elo")),
        "elo_ci_low": json_safe_number(agg.get("elo_ci_low")),
        "elo_ci_high": json_safe_number(agg.get("elo_ci_high")),
        "status": report.get("status"),
        "elapsed_s": json_safe_number(elapsed),
    }
