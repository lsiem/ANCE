---
phase: 02-core-alpha-beta-search
plan: 06
subsystem: uci
tags: [uci, mate-score, d-18, gap-closure]

requires:
  - phase: 02-core-alpha-beta-search
    provides: UCI info lines, search mate scoring, quiescence eval seam
provides:
  - Signed full-move mate scores on the UCI wire per D-18
  - Shared MATE_THRESHOLD mate-window classifier
  - Clamped evaluator output below the mate window in quiescence
affects: [phase-03, verify-work]

tech-stack:
  added: []
  patterns:
    - "Mate wire format: mate_moves = (mate_distance + 1) // 2 with sign preserved"
    - "Eval seam clamp: [-(MATE_THRESHOLD - 1), MATE_THRESHOLD - 1]"

key-files:
  created: []
  modified:
    - ance/uci/protocol.py
    - ance/search/types.py
    - ance/search/negamax.py
    - tests/test_uci_info.py
    - tests/test_quiescence.py

key-decisions:
  - "MATE_THRESHOLD = MATE - MAX_PLY is the single mate-window constant for formatter and eval clamp"

patterns-established:
  - "UCI mate scores count full moves (ceil(plies/2)), not raw internal ply distance"

requirements-completed: [UCI-11]

coverage:
  - id: D1
    description: "Mate plies converted to signed full moves on the UCI wire (D-18)"
    requirement: UCI-11
    verification:
      - kind: unit
        ref: tests/test_uci_info.py#test_send_info_depth_mate_in_three_plies_emits_two_full_moves
        status: pass
      - kind: unit
        ref: tests/test_uci_info.py#test_send_info_depth_being_mated_in_two_plies_emits_negative_one
        status: pass
      - kind: unit
        ref: tests/test_uci_info.py#test_send_info_depth_being_mated_in_four_plies_emits_negative_two
        status: pass
      - kind: integration
        ref: tests/test_uci_info.py#test_mate_in_one_position_reports_score_mate_one_on_wire
        status: pass
    human_judgment: false
  - id: D2
    description: "Evaluator centipawn output clamped below the mate window at the quiescence seam"
    requirement: UCI-11
    verification:
      - kind: unit
        ref: tests/test_quiescence.py#test_quiescence_clamps_pathological_evaluator_below_mate_window
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-10
status: complete
---

# Phase 2 Plan 06: UCI Mate Score Full-Move Gap Closure Summary

**UCI `score mate` reports signed full moves via `(plies + 1) // 2`, with evaluator cp clamped below `MATE_THRESHOLD`**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-10T14:40:00Z
- **Completed:** 2026-07-10T15:05:00Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `send_info_depth` converts internal ply distance to signed full moves per D-18 / UCI spec
- `MATE_THRESHOLD` shared constant classifies mate vs cp and bounds eval seam clamp
- Regression tests lock mate-in-1, mate-in-3-plies → mate 2, being-mated negatives, and pathological eval clamp

## Task Commits

1. **Task 1: Failing mate-score full-move wire tests (RED)** - `210c863` (test)
2. **Task 2: Convert mate plies and clamp eval cp (GREEN)** - `f98a716` (fix)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `ance/search/types.py` — `MATE_THRESHOLD = MATE - MAX_PLY`
- `ance/uci/protocol.py` — full-move conversion in mate branch
- `ance/search/negamax.py` — `_clamped_eval` at both quiescence evaluate sites
- `tests/test_uci_info.py` — capsys unit + subprocess mate wire tests
- `tests/test_quiescence.py` — pathological-evaluator clamp seam test

## Decisions Made

- `MATE_THRESHOLD` is the single mate-window classifier for formatter and eval clamp (per plan)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Subprocess mate-in-2 FEN is actually mate-in-1**
- **Found during:** Task 1 (subprocess integration test for 6KQ FEN)
- **Issue:** Plan assumed `6k1/5ppp/8/8/8/8/8/6KQ` reports mate 3 on wire at depth 4; engine finds immediate `h1a8` (mate in 1 ply)
- **Fix:** Renamed subprocess test to assert `score mate 1` / `h1a8`; multi-ply conversion covered by capsys unit tests
- **Files modified:** tests/test_uci_info.py
- **Verification:** `pytest tests/test_uci_info.py -q` — 12 passed
- **Committed in:** 210c863

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** No scope change; unit tests fully cover the diagnosed UAT gap (raw ply on wire).

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 2 UAT gap (test 4) closed — ready for `/gsd-verify-work 2`
- Pending todo `2026-07-08-uci-mate-score-full-moves.md` resolved

## Self-Check: PASSED

- `pytest tests/test_uci_info.py tests/test_quiescence.py -q` — 18 passed
- `pytest -m "not slow" -q` — 85 passed, 2 deselected

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-10*
