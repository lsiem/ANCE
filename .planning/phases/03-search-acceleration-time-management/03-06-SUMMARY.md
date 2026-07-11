---
phase: 03-search-acceleration-time-management
plan: 06
subsystem: phase-evidence
tags: [gauntlet, clocks, wilson-ci, statistical-evidence]
requires:
  - plan: 03-02
    provides: Resumable arbiter gauntlet harness
  - plan: 03-05
    provides: Soft and hard clock management
provides:
  - 100-game zero-forfeit clock evidence
  - Identical-engine statistical sanity evidence
affects: [phase-03-verification, phase-05-gauntlet]
requirements-completed: [SRCH-08, UCI-08, TOOL-03]
completed: 2026-07-11
status: complete
---

# Phase 3 Plan 06: Gauntlet Evidence Summary

The identical-engine 100-game blitz gate completed from its resumable
checkpoint and passed both Phase 3 evidence requirements.

## Commits

- `3849881` — assertion-helper contracts (RED)
- `5dc359b` — evidence assertion helpers (GREEN)
- `29bf2ec` — slow combined D-14/D-17 gate

## Result

- Time control: `30+0.3`
- Games: 100
- ANCE-A W-L-D: 36-37-27
- Score rate: 49.5%
- Draw rate: 27.0%
- Wilson 95% score interval: 39.90%–59.14%
- Time forfeits: 0 for both engines
- Aggregate engine time: 8,675.37 seconds
- Final resumed test segment: 3,512.77 seconds

The interval contains 50%, satisfying the identical-engine sanity gate, and
the run recorded no time forfeits.

## Verification

- Slow evidence gate: 1 passed in 58m32s for the resumed segment
- Fast suite: 231 passed, 6 deselected
- `git diff --check`: passed

Evidence is committed in `03-GAUNTLET-EVIDENCE.json`, including the exact
argv-safe command, source commit, time control, result, interval, and forfeit
counts.

## Deviation

The executor connection was interrupted twice during the long run. The
gauntlet resumed from its atomic checkpoint and completed the remaining games
without replaying already-recorded results, directly exercising the intended
checkpoint/resume behavior.
