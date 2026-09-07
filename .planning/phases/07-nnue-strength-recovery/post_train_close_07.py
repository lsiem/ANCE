#!/usr/bin/env python3
"""Phase 7 measure-only closer: sidecar → diagnostics → 16 smoke → 200 → ≥1000.

D-14: refuse to play unless 07-NET-SIDECAR.json says phase 7 and from_scratch.
D-10/D-11: smoke abort skips 200/1000 and does not start a train.
Never copies a prior-phase net and never launches torch training.
"""

from __future__ import annotations

import json
import os
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
from training.elo_probe import json_safe_number, probe_summary, run_elo_probe  # noqa: E402

PHASE_DIR = ROOT / ".planning/phases/07-nnue-strength-recovery"
ENGINE_NET = ROOT / "ance/eval/nnue/net.safetensors"
EVIDENCE = PHASE_DIR / "07-GAUNTLET-EVIDENCE.json"
CHECKPOINT = PHASE_DIR / "07-gauntlet-checkpoint.json"
LIVE = PHASE_DIR / "07-gauntlet-live.json"
LOG = PHASE_DIR / "07-post-train-close.log"
STATE = PHASE_DIR / "07-post-train-close-state.json"
SIDECAR = PHASE_DIR / "07-NET-SIDECAR.json"

PROBE_GAMES = 200
D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
BUDGET_SECONDS = 172_800
PROBE_BUDGET_SECONDS = 64_800
SMOKE_GAMES = 16

PHASE6_BASELINE = {
    "probe_200_wins": 0,
    "probe_200_losses": 200,
    "probe_200_draws": 0,
    "elo_ci_high": -686.6071411804116,
    "n_merged": "19866",
    "best_elo": "None",
}


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


def sidecar_identity_ok() -> bool:
    """True only when the sidecar file is Phase 7 from-scratch (D-14)."""
    if not SIDECAR.is_file():
        return False
    try:
        data = json.loads(SIDECAR.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, TypeError):
        return False
    if not isinstance(data, dict):
        return False
    phase = data.get("phase")
    phase_ok = phase == 7 or phase == "7"
    return phase_ok and data.get("from_scratch") is True


def smoke_abort(agg: dict) -> bool:
    """Skip 200 when smoke is hopeless (D-10)."""
    if agg.get("wins") == 0:
        return True
    if agg.get("score_rate") == 0.0:
        return True
    elo_ci_high = agg.get("elo_ci_high")
    return elo_ci_high is not None and elo_ci_high < -200


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
        command_line=f"phase7 depth={SEARCH_DEPTH} games={n_games}",
        search_depth=SEARCH_DEPTH,
    )


def _write_evidence(
    *,
    diagnostics: list,
    probe: dict | None,
    depth_report: dict | None,
    clock_report: dict | None,
    corpus_meta: dict | None,
    probe_smoke: dict | None = None,
    blocked: dict | None = None,
    gates_failed: list | None = None,
    gates_passed: list | None = None,
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
    if blocked is not None:
        gauntlet_block: dict = {
            "games": None,
            "mode": "fixed_depth",
            "depth": SEARCH_DEPTH,
            "status": "blocked",
        }
    else:
        gauntlet_block = {
            "games": depth_agg.get("n_games"),
            "mode": "fixed_depth",
            "depth": SEARCH_DEPTH,
            "wins": depth_agg.get("wins"),
            "losses": depth_agg.get("losses"),
            "draws": depth_agg.get("draws"),
            "score_rate": json_safe_number(depth_agg.get("score_rate")),
            "elo": json_safe_number(depth_agg.get("elo")),
            "elo_ci_low": json_safe_number(depth_agg.get("elo_ci_low")),
            "elo_ci_high": json_safe_number(depth_agg.get("elo_ci_high")),
            "status": (depth_report or {}).get("status"),
            "checkpoint": str(CHECKPOINT),
        }
    if gates_passed is None:
        gates_passed = ["D-12", "TOOL-04"] if d12_pass else []
    if gates_failed is None:
        gates_failed = [] if d12_pass else ["D-12", "TOOL-04"]
    evidence = {
        "schema_version": 1,
        "git_commit": git_commit,
        "captured_utc": datetime.now(UTC).isoformat(),
        "corpus": corpus_meta or {},
        "diagnostics": [
            {"name": d.name, "ok": d.ok, "detail": d.detail} for d in diagnostics
        ],
        "blocked": blocked,
        "probe_smoke": probe_summary(probe_smoke) if probe_smoke else None,
        "probe_200": probe_summary(probe) if probe else None,
        "compare_phase6": dict(PHASE6_BASELINE),
        "gauntlet": gauntlet_block,
        "clock_gauntlet": probe_summary(clock_report) if clock_report else None,
        "gates_passed": gates_passed,
        "gates_failed": gates_failed,
    }
    EVIDENCE.parent.mkdir(parents=True, exist_ok=True)
    EVIDENCE.write_text(
        json.dumps(evidence, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    _log(f"wrote {EVIDENCE} d12_pass={d12_pass} blocked={blocked is not None}")
    return evidence


def write_blocked_evidence() -> dict:
    """RFC JSON when the Phase 7 sidecar is missing or mismatched (D-14)."""
    return _write_evidence(
        diagnostics=[],
        probe=None,
        depth_report=None,
        clock_report=None,
        corpus_meta=None,
        probe_smoke=None,
        blocked={
            "reason": "phase7_net_not_installed",
            "detail": (
                "missing 07-NET-SIDECAR.json or phase mismatch; "
                "refusing to measure the prior net"
            ),
            "engine_net": "ance/eval/nnue/net.safetensors",
        },
        gates_passed=[],
        gates_failed=["D-14", "TOOL-04"],
    )


def main() -> int:
    PHASE_DIR.mkdir(parents=True, exist_ok=True)
    _log(f"phase7 closer starting root={ROOT}")

    if not sidecar_identity_ok():
        _log("sidecar identity failed; writing blocked evidence (D-14)")
        write_blocked_evidence()
        _save_state("blocked", reason="phase7_net_not_installed")
        return 2

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
            probe_smoke=None,
            gates_failed=["D-10", "TOOL-04"],
        )
        _save_state("diagnostics_failed")
        return 2

    _save_state("probe_smoke")
    try:
        smoke = run_elo_probe(
            ENGINE_NET,
            n_games=SMOKE_GAMES,
            out_dir=PHASE_DIR / "probe-smoke",
            budget_seconds=PROBE_BUDGET_SECONDS,
            search_depth=SEARCH_DEPTH,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"smoke probe raised: {type(exc).__name__}: {exc}")
        ckpt = PHASE_DIR / "probe-smoke" / "probe-checkpoint.json"
        smoke = json.loads(ckpt.read_text(encoding="utf-8")) if ckpt.is_file() else {}
        evidence = _write_evidence(
            diagnostics=diagnostics,
            probe=None,
            depth_report=None,
            clock_report=None,
            corpus_meta={"error": str(exc)},
            probe_smoke=smoke or None,
            gates_failed=["D-10", "D-11", "TOOL-04"],
        )
        _save_state("smoke_error", error=str(exc))
        return 2 if evidence.get("gates_failed") else 1

    smoke_agg = smoke.get("aggregate") or {}
    if smoke_abort(smoke_agg):
        _log(
            f"smoke abort wins={smoke_agg.get('wins')} "
            f"score_rate={smoke_agg.get('score_rate')} "
            f"elo_ci_high={smoke_agg.get('elo_ci_high')}"
        )
        evidence = _write_evidence(
            diagnostics=diagnostics,
            probe=None,
            depth_report=None,
            clock_report=None,
            corpus_meta=None,
            probe_smoke=smoke,
            gates_failed=["D-10", "D-11", "TOOL-04"],
        )
        _save_state("smoke_abort", wins=smoke_agg.get("wins"))
        return 2 if evidence.get("gates_failed") else 0

    _save_state("probe_200")
    try:
        probe = run_elo_probe(
            ENGINE_NET,
            n_games=PROBE_GAMES,
            out_dir=PHASE_DIR / "probe-200",
            budget_seconds=PROBE_BUDGET_SECONDS,
            search_depth=SEARCH_DEPTH,
        )
    except Exception as exc:  # noqa: BLE001
        _log(f"200-game probe raised: {type(exc).__name__}: {exc}")
        ckpt = PHASE_DIR / "probe-200" / "probe-checkpoint.json"
        probe = json.loads(ckpt.read_text(encoding="utf-8")) if ckpt.is_file() else {}
        evidence = _write_evidence(
            diagnostics=diagnostics,
            probe=probe,
            depth_report=None,
            clock_report=None,
            corpus_meta={"net_source": str(ENGINE_NET), "error": str(exc)},
            probe_smoke=smoke,
        )
        _save_state("probe_error", error=str(exc))
        return 2 if evidence.get("gates_failed") else 1
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
            probe_smoke=smoke,
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
            probe_smoke=smoke,
        )
        return 1

    evidence = _write_evidence(
        diagnostics=diagnostics,
        probe=probe,
        depth_report=depth_report,
        clock_report=None,
        corpus_meta={"net_source": str(ENGINE_NET)},
        probe_smoke=smoke,
    )
    _save_state("done", d12_pass=bool(evidence.get("gates_passed")))
    return 0 if evidence.get("gates_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
