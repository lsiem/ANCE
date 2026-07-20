#!/usr/bin/env python3
"""After scale-run trains a net: install weights, run 05-03 gauntlet, close GSD.

Waits for ``scale-run/net.safetensors``, then:
1. Copies it into ``ance/eval/nnue/net.safetensors``
2. Runs / finishes the ≥1000-game fixed-depth gauntlet (fresh checkpoint)
3. Writes honest ``05-GAUNTLET-EVIDENCE.json`` (gates_failed if D-12 fails)
4. Writes ``05-03-SUMMARY.md`` and syncs STATE/ROADMAP

Designed to run unattended in ``screen`` alongside the scale pipeline.
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

SCALE_NET = ROOT / (
    ".planning/phases/04-offline-nnue-training-pipeline/scale-run/net.safetensors"
)
ENGINE_NET = ROOT / "ance/eval/nnue/net.safetensors"
PHASE_DIR = ROOT / ".planning/phases/05-nnue-swap-in-elo-gauntlet"
CHECKPOINT = PHASE_DIR / "05-gauntlet-checkpoint.json"
LIVE = PHASE_DIR / "05-gauntlet-live.json"
EVIDENCE = PHASE_DIR / "05-GAUNTLET-EVIDENCE.json"
SUMMARY = PHASE_DIR / "05-03-SUMMARY.md"
LOG = PHASE_DIR / "post-train-close.log"
WATCHER_STATE = PHASE_DIR / "post-train-close-state.json"

D12_GAMES = 1000
SEARCH_DEPTH = 3
ENGINE_ARGV = [sys.executable, "-m", "ance"]
MAX_HALFMOVES = 160
BUDGET_SECONDS = 172_800
POLL_S = 30


def _log(msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())} {msg}"
    print(line, flush=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _save_state(phase: str, **extra: object) -> None:
    payload = {"phase": phase, "updated_utc": datetime.now(UTC).isoformat(), **extra}
    tmp = WATCHER_STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp.replace(WATCHER_STATE)


def _wait_for_net() -> None:
    _log(f"waiting for {SCALE_NET}")
    _save_state("waiting_for_net")
    while not SCALE_NET.is_file():
        time.sleep(POLL_S)
    # Stable size: two consecutive identical sizes
    prev = -1
    while True:
        size = SCALE_NET.stat().st_size
        if size > 0 and size == prev:
            break
        prev = size
        time.sleep(5)
    _log(f"net ready size={SCALE_NET.stat().st_size}")


def _install_net() -> None:
    ENGINE_NET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SCALE_NET, ENGINE_NET)
    _log(f"installed {ENGINE_NET}")
    _save_state("net_installed", bytes=ENGINE_NET.stat().st_size)


def _run_gauntlet(*, fresh_checkpoint: bool) -> dict:
    # New net ⇒ discard any prior checkpoint from the weak Phase-4 net.
    # On watcher restart mid-gauntlet, keep the checkpoint and resume.
    if fresh_checkpoint and CHECKPOINT.exists():
        bak = CHECKPOINT.with_suffix(".json.pre-scale-bak")
        CHECKPOINT.replace(bak)
        _log(f"archived old checkpoint → {bak.name}")

    import shlex

    openings_path = gauntlet.DEFAULT_OPENINGS
    spec_nnue = gauntlet.EngineSpec(
        "nnue", list(ENGINE_ARGV), env={"ANCE_EVAL": "nnue"}
    )
    spec_hc = gauntlet.EngineSpec(
        "handcrafted", list(ENGINE_ARGV), env={"ANCE_EVAL": "handcrafted"}
    )
    runner = gauntlet.detect_runner()
    command = [
        sys.executable,
        "-m",
        "ance.tools.gauntlet",
        "--games",
        str(D12_GAMES),
        "--tc",
        "30+0.3",
        "--depth",
        str(SEARCH_DEPTH),
        "--openings",
        str(openings_path),
        "--output",
        str(CHECKPOINT),
        "--max-halfmoves",
        str(MAX_HALFMOVES),
        "--engine-a",
        shlex.join(ENGINE_ARGV),
        "--engine-b",
        shlex.join(ENGINE_ARGV),
        "--engine-a-name",
        spec_nnue.name,
        "--engine-b-name",
        spec_hc.name,
        "--runner",
        runner,
        "--budget-seconds",
        str(BUDGET_SECONDS),
    ]
    # Dashboard clocks/board read this sidecar (also auto-set inside run_gauntlet).
    os.environ.setdefault("ANCE_GAUNTLET_LIVE_PATH", str(LIVE))
    _save_state("gauntlet_running", runner=runner)
    _log(f"starting 05-03 gauntlet (≥1000 games, depth 3) live={LIVE}")
    started = time.monotonic()
    report = gauntlet.run_gauntlet(
        spec_nnue,
        spec_hc,
        gauntlet.load_openings(openings_path),
        n_games=D12_GAMES,
        tc_base_s=30.0,
        tc_inc_s=0.3,
        max_halfmoves=MAX_HALFMOVES,
        output_path=CHECKPOINT,
        deadline=time.monotonic() + BUDGET_SECONDS,
        openings_path=openings_path,
        command_line=shlex.join(command),
        search_depth=SEARCH_DEPTH,
    )
    report["_wall_clock_elapsed_s"] = time.monotonic() - started
    report["_runner"] = runner
    _log(
        f"gauntlet status={report.get('status')} "
        f"games={report.get('aggregate', {}).get('n_games')}"
    )
    return report


def _write_evidence(report: dict) -> dict:
    aggregate = report["aggregate"]
    git_commit = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], text=True
    ).strip()
    d12_pass = (
        aggregate["n_games"] >= D12_GAMES
        and aggregate["elo"] > 0
        and aggregate["elo_ci_low"] > 0
    )
    env_a = report["parameters"]["engine_a"]["env"]
    env_b = report["parameters"]["engine_b"]["env"]
    evidence = {
        "schema_version": 1,
        "git_commit": git_commit,
        "captured_utc": datetime.now(UTC).isoformat(),
        "gauntlet": {
            "games": aggregate["n_games"],
            "mode": report["parameters"]["mode"],
            "depth": SEARCH_DEPTH,
            "wins": aggregate["wins"],
            "losses": aggregate["losses"],
            "draws": aggregate["draws"],
            "score_rate": aggregate["score_rate"],
            "wilson_low": aggregate["wilson_low"],
            "wilson_high": aggregate["wilson_high"],
            "elo": aggregate["elo"],
            "elo_ci_low": aggregate["elo_ci_low"],
            "elo_ci_high": aggregate["elo_ci_high"],
            "runner": report["_runner"],
            "command_line": report["command_line"],
            "elapsed_s": aggregate["elapsed_s"],
            "wall_clock_elapsed_s": report["_wall_clock_elapsed_s"],
            "status": report["status"],
            "checkpoint": str(CHECKPOINT),
            "engine_a_env": env_a,
            "engine_b_env": env_b,
            "net_source": str(SCALE_NET),
        },
        "gates_passed": ["D-12", "TOOL-04"] if d12_pass else [],
    }
    if not d12_pass:
        evidence["gates_failed"] = ["D-12", "TOOL-04"]
    EVIDENCE.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    _log(f"wrote evidence d12_pass={d12_pass} → {EVIDENCE}")
    return evidence


def _write_summary(evidence: dict) -> None:
    g = evidence["gauntlet"]
    passed = evidence.get("gates_passed") or []
    failed = evidence.get("gates_failed") or []
    status = "complete" if passed else "complete_with_failed_gates"
    SUMMARY.write_text(
        f"""---
phase: 05-nnue-swap-in-elo-gauntlet
plan: 03
subsystem: tools
tags: [gauntlet, elo, tool-04, nnue, scale-train]

requires:
  - phase: 05-nnue-swap-in-elo-gauntlet
    provides: NnueEval + fixed-depth gauntlet harness (05-01, 05-02)
  - phase: 04-offline-nnue-training-pipeline
    provides: scale-run net.safetensors (1M SF depth-12 labels)
provides:
  - Committed 05-GAUNTLET-EVIDENCE.json (≥1000 games, honest D-12 result)
  - Engine weights replaced from scale-run export
affects:
  - Phase 5 / milestone TOOL-04 verification

key-files:
  created:
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/05-03-SUMMARY.md
  modified:
    - ance/eval/nnue/net.safetensors
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Installed scale-run net into ance/eval/nnue/net.safetensors before 05-03"
  - "Fresh gauntlet checkpoint after net swap (no resume of weak-net games)"
  - "Evidence records gates_failed when Elo CI gate fails (honest TOOL-04)"

requirements-completed: {"[TOOL-04]" if passed else "[]  # TOOL-04 not met — see gates_failed"}

duration: —
completed: {datetime.now(UTC).date().isoformat()}
status: {status}
---

# Phase 05 Plan 03 Summary

**TOOL-04 ≥1000-game NNUE vs handcrafted Elo evidence (post scale-train)**

## Result

| Field | Value |
|-------|-------|
| games | {g["games"]} |
| mode / depth | {g["mode"]} / {g["depth"]} |
| W / L / D | {g["wins"]} / {g["losses"]} / {g["draws"]} |
| score_rate | {g["score_rate"]:.4f} |
| Elo | {g["elo"]:.2f} (CI {g["elo_ci_low"]:.2f} … {g["elo_ci_high"]:.2f}) |
| runner | {g["runner"]} |
| gates_passed | {passed} |
| gates_failed | {failed} |
| git_commit | `{evidence["git_commit"]}` |

## Command

```
{g["command_line"]}
```

## Net install

```
cp {SCALE_NET} {ENGINE_NET}
```

## Notes

- Scale labeling + train completed under
  `.planning/phases/04-offline-nnue-training-pipeline/scale-run/`.
- Evidence is honest: D-12 / TOOL-04 listed under `gates_failed` when
  `elo_ci_low` is not strictly positive.
""",
        encoding="utf-8",
    )
    _log(f"wrote {SUMMARY}")


def _sync_state_roadmap(evidence: dict) -> None:
    passed = bool(evidence.get("gates_passed"))
    g = evidence["gauntlet"]
    now = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    state_path = ROOT / ".planning/STATE.md"
    roadmap_path = ROOT / ".planning/ROADMAP.md"

    state = state_path.read_text(encoding="utf-8")
    # Front-matter status
    import re

    state = re.sub(r"(?m)^status:.*$", f"status: {'complete' if passed else 'gap'}", state, count=1)
    state = re.sub(
        r"(?m)^stopped_at:.*$",
        "stopped_at: —",
        state,
        count=1,
    )
    state = re.sub(r"(?m)^last_updated:.*$", f'last_updated: "{now}"', state, count=1)
    state = re.sub(
        r"(?m)^last_activity:.*$",
        f"last_activity: {datetime.now(UTC).date().isoformat()}",
        state,
        count=1,
    )
    state = re.sub(
        r"(?m)^last_activity_desc:.*$",
        f'last_activity_desc: "05-03 closed: {g["games"]} games Elo={g["elo"]:.1f} '
        f'ci_low={g["elo_ci_low"]:.1f} gates_passed={evidence.get("gates_passed")}"',
        state,
        count=1,
    )
    if passed:
        state = re.sub(
            r"(?m)^  completed_phases:.*$",
            "  completed_phases: 5",
            state,
            count=1,
        )
        state = re.sub(
            r"(?m)^  completed_plans:.*$",
            "  completed_plans: 34",
            state,
            count=1,
        )
        state = re.sub(r"(?m)^  percent:.*$", "  percent: 100", state, count=1)

    # Current Position block
    if passed:
        state = state.replace(
            "Phase: 05 (nnue-swap-in-elo-gauntlet) — PAUSED",
            "Phase: 05 (nnue-swap-in-elo-gauntlet) — COMPLETE",
        )
        state = re.sub(
            r"(?m)^Plan:.*$",
            "Plan: 3 of 3 (05-03 complete)",
            state,
            count=1,
        )
        state = re.sub(
            r"(?m)^Status:.*$",
            "Status: Complete — TOOL-04 evidence committed",
            state,
            count=1,
        )
        state = state.replace("Progress: [██████████] 97%", "Progress: [██████████] 100%")
    else:
        state = state.replace(
            "Phase: 05 (nnue-swap-in-elo-gauntlet) — PAUSED",
            "Phase: 05 (nnue-swap-in-elo-gauntlet) — GAP (D-12 failed)",
        )
        state = re.sub(
            r"(?m)^Plan:.*$",
            "Plan: 3 of 3 (05-03 evidence written; D-12 failed honestly)",
            state,
            count=1,
        )
        state = re.sub(
            r"(?m)^Status:.*$",
            "Status: Gap — 05-GAUNTLET-EVIDENCE.json has gates_failed",
            state,
            count=1,
        )

    # Pending todos → mark done note
    pending_block = """### Pending Todos

See: `.planning/todos/pending/2026-07-18-scale-train-and-05-03.md`

1. Resume 1M SF depth-12 scale labeling (~150k done; resumable progress JSON local).
2. Finish train/export → install new `net.safetensors` into `ance/eval/nnue/`.
3. Complete 05-03 ≥1000-game D-12 gauntlet evidence (honest `gates_failed` if Elo still bad).
4. Write `05-03-SUMMARY.md` + sync ROADMAP/STATE; gap plan if D-12 fails."""
    replacement = f"""### Pending Todos

Scale-train + 05-03 closed {datetime.now(UTC).date().isoformat()}.
Evidence: `05-GAUNTLET-EVIDENCE.json` (gates_passed={evidence.get("gates_passed")}, gates_failed={evidence.get("gates_failed")}).
{"Gap plan needed if strength still insufficient." if not passed else "Ready for /gsd-verify-work."}"""
    if pending_block in state:
        state = state.replace(pending_block, replacement)

    state_path.write_text(state, encoding="utf-8")
    _log(f"updated {state_path}")

    roadmap = roadmap_path.read_text(encoding="utf-8")
    if passed:
        roadmap = roadmap.replace(
            "- [ ] **Phase 5: NNUE Swap-In & Elo Gauntlet**",
            "- [x] **Phase 5: NNUE Swap-In & Elo Gauntlet**",
        )
        roadmap = roadmap.replace(
            "- [ ] 05-03-PLAN.md — ≥1000-game depth-3 evidence run + D-12 Elo CI gate + committed evidence JSON (TOOL-04 proof)",
            "- [x] 05-03-PLAN.md — ≥1000-game depth-3 evidence run + D-12 Elo CI gate + committed evidence JSON (TOOL-04 proof)",
        )
    else:
        # Leave checkbox open but annotate
        roadmap = roadmap.replace(
            "- [ ] 05-03-PLAN.md — ≥1000-game depth-3 evidence run + D-12 Elo CI gate + committed evidence JSON (TOOL-04 proof)",
            "- [ ] 05-03-PLAN.md — ≥1000-game depth-3 evidence run + D-12 Elo CI gate + committed evidence JSON (TOOL-04 proof) — evidence written; gates_failed (honest)",
        )
    roadmap_path.write_text(roadmap, encoding="utf-8")
    _log(f"updated {roadmap_path}")


def main() -> int:
    _log(f"post-train closer starting root={ROOT}")
    prior = {}
    if WATCHER_STATE.exists():
        try:
            prior = json.loads(WATCHER_STATE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            prior = {}
    if prior.get("phase") == "done" and EVIDENCE.is_file() and SUMMARY.is_file():
        _log("already done; exiting 0")
        return 0

    need_install = prior.get("phase") not in {
        "net_installed",
        "gauntlet_running",
        "gauntlet_incomplete",
        "done",
    }
    if need_install or not ENGINE_NET.is_file():
        _wait_for_net()
        _install_net()
        fresh_checkpoint = True
    else:
        _log(f"resuming with existing engine net phase={prior.get('phase')}")
        fresh_checkpoint = False

    report = _run_gauntlet(fresh_checkpoint=fresh_checkpoint)
    if report.get("status") != "completed":
        _save_state("gauntlet_incomplete", status=report.get("status"))
        _log("gauntlet did not complete; exiting 1 (re-run this script to resume)")
        return 1
    evidence = _write_evidence(report)
    _write_summary(evidence)
    _sync_state_roadmap(evidence)
    _save_state("done", d12_pass=bool(evidence.get("gates_passed")))
    _log("05-03 close sequence finished")
    return 0 if evidence.get("gates_passed") else 2


if __name__ == "__main__":
    raise SystemExit(main())
