---
phase: 03-search-acceleration-time-management
plan: 02
subsystem: tooling
tags: [python-chess, uci, gauntlet, clocks, checkpointing, wilson-ci]

requires:
  - phase: 02-core-alpha-beta-search
    provides: UCI engine subprocess, bounded harness controls, and atomic checkpoint pattern
provides:
  - Arbiter-refereed two-engine UCI gauntlet with explicit time forfeits
  - Fixed 30-position balanced opening book with per-opening color parity
  - Atomic checkpoint/resume and D-19 W-L-D, draw-rate, and Wilson CI reports
  - Optional argv-safe cutechess-cli passthrough
affects: [03-05-clock-management, 03-06-phase-evidence, phase-05-nnue-gauntlet]

tech-stack:
  added: []
  patterns:
    - Arbiter charges measured wall time before crediting increment
    - Every completed game is persisted via sibling tmp, fsync, and os.replace

key-files:
  created:
    - ance/tools/gauntlet.py
    - ance/tools/openings.epd
    - tests/test_gauntlet_harness.py
  modified: []

key-decisions:
  - "Use python-chess as the default local arbiter while retaining cutechess-cli autodetection and argv generation."
  - "Store ordered per-game records and recompute aggregate statistics from those records on every checkpoint."

patterns-established:
  - "Opening parity: game i uses opening (i // 2) % count and engine A is white iff i is even."
  - "Clock referee: subtract measured move wall time, forfeit below zero, then credit increment only to a surviving move."

requirements-completed: [TOOL-03]

coverage:
  - id: D1
    description: Arbiter harness provides clocks, parity, checkpoint/resume, reporting, and runner selection.
    requirement: TOOL-03
    verification:
      - kind: unit
        ref: "tests/test_gauntlet_harness.py (7 fast contract tests)"
        status: pass
      - kind: integration
        ref: ".venv/bin/python -m pytest -m 'not slow' -q"
        status: pass
    human_judgment: false
  - id: D2
    description: Real ANCE subprocesses demonstrably flag at 5+0.1 and complete cleanly at 60+1.
    requirement: TOOL-03
    verification:
      - kind: integration
        ref: "tests/test_gauntlet_harness.py#test_two_game_arbiter_smoke_completes"
        status: pass
      - kind: integration
        ref: "python -m ance.tools.gauntlet --games 2 --tc 5+0.1 --max-halfmoves 30"
        status: pass
    human_judgment: false

duration: 15min
completed: 2026-07-10
status: complete
---

# Phase 3 Plan 02: Gauntlet Harness Summary

**A resumable two-engine UCI gauntlet now referees real wall clocks, pairs fixed openings by color, and emits auditable W-L-D statistics with Wilson confidence intervals.**

## Performance

- **Duration:** 15 min
- **Started:** 2026-07-10T23:35:00Z
- **Completed:** 2026-07-10T23:49:47Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- Added the TOOL-03 arbiter with two independent engine argv lists, per-move clock charging, explicit flag adjudication, paired opening parity, and subprocess cleanup.
- Added atomic per-game checkpoints, compatible resume validation, status inspection, complete D-19 aggregate reports, and cutechess-cli command generation/execution.
- Added 30 checked-in balanced FEN positions plus seven fast contract tests and one slow real-engine integration test.

## Task Commits

1. **Task 1 RED: Specify gauntlet arbiter contract** - `92184b4`
2. **Task 1 GREEN: Add TOOL-03 gauntlet harness** - `3802ef3`
3. **Task 2: Add real-engine gauntlet smoke** - `3280fa7`

## Files Created/Modified
- `ance/tools/gauntlet.py` - Clock-refereed arbiter, checkpoint/report logic, cutechess passthrough, and CLI.
- `ance/tools/openings.epd` - Thirty deterministic, equal-material opening FENs.
- `tests/test_gauntlet_harness.py` - Mocked fast contracts and slow two-game real-engine smoke.
- `.planning/phases/03-search-acceleration-time-management/03-02-SUMMARY.md` - Plan evidence and handoff.

## Verification Evidence

### Fast contracts and suite

- `.venv/bin/python -m pytest tests/test_gauntlet_harness.py -q`
  - `7 passed in 0.07s` before the slow test was added.
- `.venv/bin/python -m ance.tools.gauntlet --help`
  - Exit 0; lists all required CLI flags.
- `.venv/bin/python -m pytest -m "not slow" -q`
  - Final result: `158 passed, 3 deselected in 18.21s`.

### Forfeit-detection smoke

Exact command:

`SCRATCH="/tmp/ance-03-02-forfeit-$$.json" && .venv/bin/python -m ance.tools.gauntlet --games 2 --tc 5+0.1 --max-halfmoves 30 --output "$SCRATCH"`

Report:

`1W-1L-0D; score_rate=0.5; draw_rate=0.0; Wilson95=[0.0945286548, 0.9054713452]; time_forfeits={engine-a: 1, engine-b: 1}; elapsed_s=20.6008847090; status=completed`

### Clean real-engine smoke

Committed test command:

`.venv/bin/python -m pytest tests/test_gauntlet_harness.py -m slow -q`

Result: `1 passed, 7 deselected in 83.09s`.

Exact report-capture command:

`REPORT="/tmp/ance-03-02-clean-smoke-$$.json" && .venv/bin/python -m ance.tools.gauntlet --games 2 --tc 60+1 --max-halfmoves 20 --output "$REPORT" --runner arbiter`

Report:

`0W-0L-2D; score_rate=0.5; draw_rate=1.0; Wilson95=[0.0945286548, 0.9054713452]; time_forfeits={engine-a: 0, engine-b: 0}; elapsed_s=83.0015881650; status=completed`

Parity evidence: `[(index=0, a_is_white=true, opening=0), (index=1, a_is_white=false, opening=0)]`.

## Decisions Made
- The arbiter path is fully self-sufficient and remains explicitly selectable even if cutechess-cli later appears on PATH.
- Checkpoint compatibility includes both engine argv lists, time control, game count, halfmove cap, opening path, and opening contents.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- The initial opening test equated balanced material with all 32 pieces remaining. It was corrected during GREEN to compare actual material values, allowing balanced mainline capture/recapture positions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Plan 03-05 can use the referee to validate clock management.
- Plan 03-06 and Phase 5 can reuse the two-command API and checkpointed D-19 report without harness changes.

## Self-Check: PASSED

- All three implementation artifacts exist.
- RED, GREEN, and slow-smoke commits exist.
- All task acceptance criteria and plan verification commands passed.
- No ROADMAP.md or global phase-completion state was modified by this executor.

---
*Phase: 03-search-acceleration-time-management*
*Completed: 2026-07-10*
