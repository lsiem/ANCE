---
phase: 02-core-alpha-beta-search
plan: 08
subsystem: uci
tags: [threading, cancellation, generation-gating, concurrency, tdd]

requires:
  - phase: 02-core-alpha-beta-search
    provides: non-blocking UCI search workers and completed-depth info callbacks
provides:
  - Per-generation search cancellation and movetime timer ownership
  - Generation-locked info and bestmove output
  - Deterministic stale-worker and current-stop regressions
affects: [phase-03, uci, verify-work]

tech-stack:
  added: []
  patterns:
    - "Each SearchJob owns one never-cleared cancellation Event"
    - "Generation checks and UCI output share one lock-protected critical section"

key-files:
  created:
    - tests/test_uci_generation.py
  modified:
    - ance/uci/loop.py
    - tests/test_go_bestmove.py

key-decisions:
  - "A new go advances generation before bounded preemption and always allocates a fresh cancellation Event"
  - "stop preserves the active generation, while state-changing commands invalidate only workers that survive their bounded join"

patterns-established:
  - "Stale output is prevented by generation identity, not successful thread joins"
  - "Concurrency tests use Events for ordering rather than scheduler sleeps"

requirements-completed: [UCI-11]

coverage:
  - id: D1
    description: "Timed-out stale workers retain a set private token while replacement workers receive a fresh unset token and exclusive output rights"
    requirement: UCI-11
    verification:
      - kind: integration
        ref: tests/test_uci_generation.py#test_timed_out_worker_keeps_unique_cancel_token_and_cannot_emit_after_replacement
        status: pass
    human_judgment: false
  - id: D2
    description: "Info and bestmove emission recheck generation while holding the same lock used to advance generations"
    requirement: UCI-11
    verification:
      - kind: unit
        ref: tests/test_uci_generation.py#test_info_gate_rechecks_generation_after_waiting_for_lock
        status: pass
    human_judgment: false
  - id: D3
    description: "stop signals the active generation without invalidating it and yields exactly one legal bestmove"
    requirement: UCI-11
    verification:
      - kind: unit
        ref: tests/test_go_bestmove.py#test_stop_signals_current_search_and_emits_exactly_one_legal_bestmove
        status: pass
    human_judgment: false

duration: 11min
completed: 2026-07-10
status: complete
---

# Phase 2 Plan 08: UCI Search Generation Isolation Summary

**Per-search cancellation ownership and lock-atomic generation gating prevent timed-out workers from resuming or contaminating replacement UCI output**

## Performance

- **Duration:** 11 min
- **Started:** 2026-07-10T16:30:00Z
- **Completed:** 2026-07-10T16:41:08Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Replaced shared worker cancellation and timer globals with a `SearchJob` that owns one immutable-generation Event, thread, and optional Timer.
- Applied one lock across generation advancement and both `info` and `bestmove` check-plus-send operations.
- Added deterministic forced-timeout, lock-boundary, and current-stop regressions; removed scheduler sleeps from the pre-existing stale-worker test.

## Task Commits

Each task was committed atomically:

1. **Task 1: Reproduce stale token reuse and ungated info (RED)** - `1db0341` (test)
2. **Task 2: Isolate SearchJob cancellation and gate all output (GREEN)** - `58559f4` (fix)
3. **Acceptance cleanup: deterministic stale-worker ordering** - `622d702` (refactor)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `ance/uci/loop.py` - Owns cancellation per generation and generation-gates all search output under one lock.
- `tests/test_uci_generation.py` - Forces join timeout and output-gate races with deterministic Events.
- `tests/test_go_bestmove.py` - Proves current stop emits one bestmove and uses Event-controlled stale-worker ordering.

## Decisions Made

- Kept `_run_search`'s explicit event/timer/generation arguments so existing direct runner tests remain valid while ownership moves into `SearchJob`.
- Left completed jobs as `active_job` until replacement; their set token is harmless and preserves inspectable thread ownership without token reuse.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reconciled inconsistent generated progress fields**
- **Found during:** Plan close-out
- **Issue:** `state.update-progress` reported 88% but wrote 20% to frontmatter and left the body at 81%; session recording also left the last-activity description on Plan 07.
- **Fix:** Reconciled STATE.md to 14/16 completed plans (88%), Plan 9 as next, and Plan 08 as the latest activity.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE reports 14 completed plans, 88% in frontmatter/body, and `Completed 02-08-PLAN.md`.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 blocking planning-state inconsistency).
**Impact on plan:** Planning metadata only; production behavior and test evidence were unchanged.

## Issues Encountered

- The state updater emitted internally inconsistent progress fields; reconciled during the required close-out update.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- UCI output is generation-consistent even when bounded worker joins time out.
- Ready for `02-09-PLAN.md`; no blocker introduced by this plan.

## Self-Check: PASSED

- Focused suite: 31 passed.
- Full fast suite: 94 passed, 2 deselected.
- Concurrency suite: 2 passed in 0.05s; forced timeout completed in 0.01s.
- RED, GREEN, and deterministic cleanup commits exist with no tracked-file deletions.
- Slow strength gauntlets were intentionally not run per plan.

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-10*
