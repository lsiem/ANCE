#!/usr/bin/env python3
"""Phase 6 closer: diagnostics → 200-game probe → ≥1000 TOOL-04 + optional clock note.

Honest gates_failed when elo_ci_low is not strictly positive.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from ance.tools import gauntlet  # noqa: E402
from training.diagnostics_eval import run_diagnostics  # noqa: E402
from training.elo_probe import probe_summary, run_elo_probe  # noqa: E402

PHASE_DIR = ROOT / ".planning/phases/06-quiet-data-nnue-strength-gap"
STRENGTH_NET = PHASE_DIR / "strength-run" / "net.safetensors"
ENGINE_NET = ROOT / "ance/eval/nnue/net.safetensors"
EVIDENCE = PHASE_DIR / "06-GAUNTLET-EVIDENCE.json"
CHECKPOINT = PHASE_DIR / "06-gauntlet-checkpoint.json"
LIVE = PHASE_DIR / "06-gauntlet-live.json"
CLOCK_CHECKPOINT = PHASE_DIR / "06-gauntlet-clock-checkpoint.json"
LOG = PHASE_DIR / "post-train-close.log"
STATE = PHASE_DIR / "post-train-close-state.json"

PROBE_GAMES = 200
D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
BUDGET_SECONDS = 172_800
# Depth-3 Python search has historically been ~150–250 s/game in cloud.
# 200 games therefore need ~14–18 h; the elo_probe default (4 h) is too short.
PROBE_BUDGET_SECONDS = 64_800


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _save_state(phase: str, **extra: object) -> None:
    payload = {"phase": phase, "updated_utc": datetime.now(UTC).isoformat(), **extra}
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(STATE)


def _install_net(src: Path) -> None:
    ENGINE_NET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, ENGINE_NET)
    _log(f"installed {ENGINE_NET} from {src}")


def _run_depth_gauntlet(n_games: int, checkpoint: Path) -> dict:
    openings_path = gauntlet.DEFAULT_OPENINGS
    spec_nnue = gauntlet.EngineSpec(
        "nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}
    )
    spec_hc = gauntlet.EngineSpec(
        "handcrafted", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
    )
    os.environ.setdefault("ANCE_GAUNTLET_LIVE_PATH", str(LIVE))
    return gauntlet.run_gauntlet(
        spec_nnue,
        spec_hc,
        gauntlet.load_openings(openings_path),
        n_games=n_games,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=MAX_HALFMOVES,
        output_path=checkpoint,
        deadline=time.monotonic() + BUDGET_SECONDS,
        openings_path=openings_path,
        command_line=f"phase6 depth={SEARCH_DEPTH} games={n_games}",
        search_depth=SEARCH_DEPTH,
    )


def _run_clock_gauntlet(n_games: int = 50) -> dict:
    openings_path = gauntlet.DEFAULT_OPENINGS
    spec_nnue = gauntlet.EngineSpec(
        "nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}
    )
    spec_hc = gauntlet.EngineSpec(
        "handcrafted", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
    )
    return gauntlet.run_gauntlet(
        spec_nnue,
        spec_hc,
        gauntlet.load_openings(openings_path),
        n_games=n_games,
        tc_base_s=5.0,
        tc_inc_s=0.05,
        max_halfmoves=MAX_HALFMOVES,
        output_path=CLOCK_CHECKPOINT,
        deadline=time.monotonic() + 14_400,
        openings_path=openings_path,
        command_line=f"phase6 clock 5+0.05 games={n_games}",
        search_depth=None,
    )


def _write_evidence(
    *,
    diagnostics: list,
    probe: dict | None,
    depth_report: dict | None,
    clock_report: dict | None,
    corpus_meta: dict | None,
) -> dict:
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    depth_agg = (depth_report or {}).get("aggregate") or {}
    d12_pass = bool(
        depth_agg
        and depth_agg.get("n_games", 0) >= D12_GAMES
        and depth_agg.get("elo", 0) > 0
        and depth_agg.get("elo_ci_low", 0) > 0
    )
    evidence = {
        "schema_version": 1,
        "git_commit": git_commit,
        "captured_utc": datetime.now(UTC).isoformat(),
        "corpus": corpus_meta or {},
        "diagnostics": [
            {"name": d.name, "ok": d.ok, "detail": d.detail} for d in diagnostics
        ],
        "probe_200": probe_summary(probe) if probe else None,
        "gauntlet": {
            "games": depth_agg.get("n_games"),
            "mode": "fixed_depth",
            "depth": SEARCH_DEPTH,
            "wins": depth_agg.get("wins"),
            "losses": depth_agg.get("losses"),
            "draws": depth_agg.get("draws"),
            "score_rate": depth_agg.get("score_rate"),
            "elo": depth_agg.get("elo"),
            "elo_ci_low": depth_agg.get("elo_ci_low"),
            "elo_ci_high": depth_agg.get("elo_ci_high"),
            "status": (depth_report or {}).get("status"),
            "checkpoint": str(CHECKPOINT),
        },
        "clock_gauntlet": probe_summary(clock_report) if clock_report else None,
        "gates_passed": ["D-12", "TOOL-04"] if d12_pass else [],
        "gates_failed": [] if d12_pass else ["D-12", "TOOL-04"],
    }
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    _log(f"wrote {EVIDENCE} d12_pass={d12_pass}")
    return evidence


def main() -> int:
    PHASE_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"phase6 closer starting root={ROOT}")

    net_src = STRENGTH_NET if STRENGTH_NET.is_file() else ENGINE_NET
    if not net_src.is_file():
        _log(f"no net at {STRENGTH_NET} or {ENGINE_NET}")
        return 1
    if net_src != ENGINE_NET:
        _install_net(net_src)

    _save_state("diagnostics")
    diagnostics = run_diagnostics(str(ENGINE_NET))
    if not all(d.ok for d in diagnostics):
        _log(f"diagnostics failed: {diagnostics}")
        _write_evidence(
            diagnostics=diagnostics,
            probe=None,
            depth_report=None,
            clock_report=None,
            corpus_meta=None,
        )
        _save_state("diagnostics_failed")
        return 2

    _save_state("probe_200")
    probe = run_elo_probe(
        ENGINE_NET,
        n_games=PROBE_GAMES,
        out_dir=PHASE_DIR / "probe-200",
        budget_seconds=PROBE_BUDGET_SECONDS,
    )
    probe_agg = probe.get("aggregate") or {}
    if not (
        probe_agg.get("n_games", 0) >= PROBE_GAMES
        and probe_agg.get("elo_ci_low", -1e9) > 0
    ):
        _log(
            f"200-game probe gate failed elo={probe_agg.get('elo')} "
            f"ci_low={probe_agg.get('elo_ci_low')}"
        )
        evidence = _write_evidence(
            diagnostics=diagnostics,
            probe=probe,
            depth_report=None,
            clock_report=None,
            corpus_meta=None,
        )
        _save_state("probe_failed", elo=probe_agg.get("elo"))
        return 2 if evidence.get("gates_failed") else 0

    _save_state("gauntlet_1000")
    depth_report = _run_depth_gauntlet(D12_GAMES, CHECKPOINT)
    if depth_report.get("status") != "completed":
        _save_state("gauntlet_incomplete", status=depth_report.get("status"))
        _write_evidence(
            diagnostics=diagnostics,
            probe=probe,
            depth_report=depth_report,
            clock_report=None,
            corpus_meta=None,
        )
        return 1

    clock_report = None
    try:
        _save_state("clock_gauntlet")
        clock_report = _run_clock_gauntlet(50)
    except Exception as exc:  # noqa: BLE001
        _log(f"clock gauntlet skipped: {exc}")

    evidence = _write_evidence(
        diagnostics=diagnostics,
        probe=probe,
        depth_report=depth_report,
        clock_report=clock_report,
        corpus_meta={"net_source": str(net_src)},
    )
    _save_state("done", d12_pass=bool(evidence.get("gates_passed")))
    return 0 if evidence.get("gates_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
