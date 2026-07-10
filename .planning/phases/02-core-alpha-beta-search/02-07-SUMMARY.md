---
phase: 02-core-alpha-beta-search
plan: 07
subsystem: search
tags: [negamax, repetition, deadlines, telemetry, tdd]

requires:
  - phase: 02-core-alpha-beta-search
    provides: iterative-deepening negamax, quiescence, UCI info callbacks
provides:
  - Full move-stack reconstruction for game-history repetition detection
  - Bounded in-tree stop and monotonic-deadline polling
  - Exact cumulative completed-iteration node and NPS telemetry
affects: [phase-03, uci, verify-work]

tech-stack:
  added: []
  patterns:
    - "Search tree cancellation uses one shared bounded node-poll helper"
    - "Depth helpers return iteration-local node deltas; search_root owns cumulative telemetry"

key-files:
  created:
    - tests/test_search_deadline.py
    - tests/test_search_telemetry.py
  modified:
    - ance/search/negamax.py
    - tests/test_iterative_deepening.py

key-decisions:
  - "Repetition history is reconstructed by popping a stack-preserving board copy, never by mutating the caller"
  - "Only fully completed iterations contribute nodes or emit info callbacks"

patterns-established:
  - "Deadline and stop checks share NODE_POLL_INTERVAL cadence in negamax and quiescence"
  - "NPS uses cumulative completed nodes divided by total root-search elapsed time"

requirements-completed: [SRCH-02, SRCH-03, SRCH-04, SRCH-07, UCI-11]

coverage:
  - id: D1
    description: "Real python-chess move history drives repetition detection without mutating the root board"
    requirement: SRCH-07
    verification:
      - kind: unit
        ref: tests/test_iterative_deepening.py#test_build_game_history_keys_reconstructs_every_prior_position
        status: pass
      - kind: integration
        ref: tests/test_iterative_deepening.py#test_real_game_history_repetition_from_root_child_scores_draw
        status: pass
    human_judgment: false
  - id: D2
    description: "Expired deadlines abort inside negamax and quiescence while preserving the last completed depth"
    requirement: SRCH-03
    verification:
      - kind: unit
        ref: tests/test_search_deadline.py#test_negamax_aborts_at_poll_boundary_for_expired_deadline
        status: pass
      - kind: unit
        ref: tests/test_search_deadline.py#test_quiescence_aborts_at_poll_boundary_for_expired_deadline
        status: pass
      - kind: integration
        ref: tests/test_search_deadline.py#test_deadline_during_iteration_retains_last_completed_depth
        status: pass
    human_judgment: false
  - id: D3
    description: "Completed-depth callbacks and final results report exact cumulative nodes and root-elapsed NPS"
    requirement: UCI-11
    verification:
      - kind: unit
        ref: tests/test_search_telemetry.py#test_completed_iterations_report_exact_cumulative_nodes_and_nps
        status: pass
    human_judgment: false

duration: 8min
completed: 2026-07-10
status: complete
---

# Phase 2 Plan 07: Search Correctness Gap Closure Summary

**Real move-stack repetition, bounded in-tree deadline cancellation, and exact completed-iteration node/NPS accounting**

## Performance

- **Duration:** 8 min
- **Started:** 2026-07-10T16:18:47Z
- **Completed:** 2026-07-10T16:26:32Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Reconstructed all predecessor Zobrist keys from a stack-preserving python-chess board copy, enabling real game-history draw cuts.
- Enforced stop and monotonic deadlines inside both negamax and quiescence on the existing bounded polling cadence.
- Corrected iterative-deepening telemetry to report 10/20/30 cumulative nodes, root-elapsed NPS, and no aborted-depth callback.

## Task Commits

Each task was committed atomically:

1. **Task 1: Pin history, deadline, and telemetry defects (RED)** - `654ab94` (test)
2. **Task 2: Reconstruct history and correct search polling/accounting (GREEN)** - `1b056d8` (fix)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `ance/search/negamax.py` - Preserves move history, polls deadlines in-tree, and aggregates local iteration node deltas.
- `tests/test_iterative_deepening.py` - Proves real legal-move history reconstruction and root-child repetition scoring.
- `tests/test_search_deadline.py` - Pins negamax/qsearch poll boundaries and completed-depth retention.
- `tests/test_search_telemetry.py` - Pins exact cumulative nodes, NPS, and aborted-iteration callback suppression.

## Decisions Made

- Repetition reconstruction operates on `board.copy(stack=True)` so the caller's FEN and move stack remain unchanged.
- `_search_at_depth` owns only iteration-local work; `search_root` owns cumulative totals, elapsed time, and callback emission.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reconciled stale STATE.md plan position**
- **Found during:** Plan close-out
- **Issue:** Phase execution initialization had set the current position to Plan 1 of 10 even though summaries for Plans 01-06 already existed, so a single required `state.advance-plan` left the project at Plan 2.
- **Fix:** Advanced the state handler through the six already-completed plans and corrected generated progress fields to 13/16 plans (81%), leaving Plan 8 as the next executable plan.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE reports Plan 8 of 10 and ROADMAP reports 7/10 Phase 2 plans complete.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 blocking planning-state inconsistency).
**Impact on plan:** Planning metadata only; production scope and tests were unchanged.

## Issues Encountered

- The pre-existing Phase 2 state position was stale after gap-closure plans were added; reconciled during the required state update.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Search history, cancellation, and telemetry gaps are closed for Phase 2 verification.
- Ready for `02-08-PLAN.md`; no blocker introduced by this plan.

## Self-Check: PASSED

- Focused suite: 24 passed.
- Full fast suite: 91 passed, 2 deselected.
- RED and GREEN commits exist and contain no tracked-file deletions.
- Slow strength gauntlets were intentionally not run per plan.

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-10*
