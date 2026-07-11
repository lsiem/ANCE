---
phase: 03-search-acceleration-time-management
plan: 04
subsystem: search
tags: [move-ordering, transposition-table, killers, history, pytest]
requires:
  - phase: 03-search-acceleration-time-management
    provides: Pre-TT baseline artifact and Zobrist transposition table
provides:
  - Hash-move, MVV-LVA, killer, and history ordering at every interior node
  - Two shared killer slots per ply and bounded aging butterfly history
  - Per-game UCI heuristic ownership and ucinewgame reset
  - Deterministic and two-second D-21 strength evidence
affects: [03-05-time-management, search-core, uci-loop]
tech-stack:
  added: []
  patterns:
    - Single stable score-band sort for interior move ordering
    - Shared mutable heuristic tables across root and child search contexts
key-files:
  created:
    - ance/search/ordering.py
    - tests/test_move_ordering.py
  modified:
    - ance/search/negamax.py
    - ance/search/types.py
    - ance/uci/loop.py
    - tests/test_phase3_strength_baseline.py
key-decisions:
  - "History aging halves the complete fixed-shape table only when an updated cell exceeds 79,000."
  - "Direct search_root callers receive fresh per-search heuristics; the UCI loop passes process-owned per-game tables."
patterns-established:
  - "Qsearch imports the relocated MVV-LVA helpers but remains isolated from hash, killer, and history ordering."
  - "Quiet beta cutoffs update killers and mover-side history after the board is restored."
requirements-completed: [SRCH-06]
coverage:
  - id: D1
    description: Score-band ordering, killer shift, history aging, and qsearch isolation
    requirement: SRCH-06
    verification:
      - kind: unit
        ref: tests/test_move_ordering.py#ordering primitive contracts
        status: pass
    human_judgment: false
  - id: D2
    description: Ordered negamax with shared per-game heuristics and ucinewgame reset
    requirement: SRCH-06
    verification:
      - kind: integration
        ref: tests/test_move_ordering.py#ordered search integration contracts
        status: pass
      - kind: other
        ref: .venv/bin/python -m pytest -m "not slow" -q
        status: pass
    human_judgment: false
  - id: D3
    description: D-21 fixed-depth node reduction and equal-time completed-depth evidence
    requirement: SRCH-06
    verification:
      - kind: integration
        ref: tests/test_phase3_strength_baseline.py#test_phase3_fixed_depth_nodes_beat_baseline
        status: pass
      - kind: other
        ref: tests/test_phase3_strength_baseline.py#test_phase3_depth_at_2s_meets_baseline
        status: pass
    human_judgment: false
duration: 14 min
completed: 2026-07-11
status: complete
---

# Phase 3 Plan 04: Full Move Ordering Summary

**Hash-first interior move ordering with MVV-LVA, two killers, bounded history, per-game reset, and measured D-21 gains over the Phase 2 baseline.**

## Performance

- **Duration:** 14 min
- **Started:** 2026-07-11T02:05:06Z
- **Completed:** 2026-07-11T02:19:08Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added disjoint hash/capture/killer/history score bands, two killer slots per ply, and a fixed-shape history table with whole-table aging.
- Threaded identical heuristic objects through iterative-deepening root contexts and every child context while keeping qsearch MVV-LVA-only.
- Persisted heuristics across UCI `go` commands within a game and replaced them with fresh tables on `ucinewgame`.
- Reduced the six-position fixed-depth total from 838,304 to 250,005 nodes (29.82% of baseline) and met or exceeded every two-second completed-depth baseline.

## Task Commits

1. **Task 1 RED: ordering primitive contracts** - `99e9362`
2. **Task 1 GREEN: ordering module and MVV-LVA relocation** - `01d81a7`
3. **Task 2 RED: ordered-search integration contracts** - `72ab1c4`
4. **Task 2 GREEN: negamax and per-game heuristic wiring** - `31c24eb`
5. **Task 3: deterministic and timed D-21 evidence** - `a6a1524`

## D-21 Evidence

| Position | Captured depth | Phase 2 nodes | TT + ordering nodes |
|---|---:|---:|---:|
| startpos | 4 | 50,207 | 24,860 |
| kiwipete | 2 | 204,531 | 64,757 |
| italian | 4 | 501,208 | 127,816 |
| rook_endgame | 4 | 47,665 | 12,907 |
| hanging_queen | 4 | 17,598 | 13,610 |
| queen_mate | 4 | 17,095 | 6,055 |
| **Total** | — | **838,304** | **250,005 (29.82%)** |

The deterministic comparison used a fresh TT, killers, and history table for every FEN. Kiwipete honored the artifact's captured depth-2 override.

| Position | Phase 2 depth at 2s | Phase 3 depth at 2s |
|---|---:|---:|
| startpos | 3 | 4 |
| kiwipete | 0 | 0 |
| italian | 2 | 3 |
| rook_endgame | 4 | 5 |
| hanging_queen | 4 | 6 |
| queen_mate | 4 | 5 |

All six met or exceeded baseline depth; three of the four non-mate positions improved.

## Verification

- `tests/test_move_ordering.py`: **10 passed**.
- `tests/test_move_ordering.py tests/test_transposition_table.py`: **26 passed**.
- Updated internal adapters plus ordering/TT suites: **49 passed**.
- D-21 non-slow file gate: **6 passed, 1 deselected**.
- D-21 slow two-second gate (single prescribed run): **1 passed, 6 deselected** in 12.33s.
- Final fast suite: **185 passed, 4 deselected** in 64.63s.
- `git diff --check 282fbee..HEAD`: passed.

## Files Created/Modified

- `ance/search/ordering.py` - Unified score bands, relocated MVV-LVA, killer helpers, and aging history.
- `ance/search/negamax.py` - Hash-move ordering, cutoff updates, and shared heuristic propagation.
- `ance/search/types.py` - Optional killer and history references on `SearchContext`.
- `ance/uci/loop.py` - Per-game heuristic ownership and `ucinewgame` reset.
- `tests/test_move_ordering.py` - D-07 through D-10 primitive and integration tests.
- `tests/test_phase3_strength_baseline.py` - Fast deterministic and slow two-second D-21 gates.
- `tests/test_go_bestmove.py`, `tests/test_search_telemetry.py`, `tests/test_uci_generation.py` - Internal test adapters for explicit heuristic propagation.

## Decisions Made

- Followed the plan's exact score bands and aging policy.
- Created default heuristic tables once per `search_root` call, preserving backward compatibility without silently resetting them between root moves.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated internal test adapters for new search state parameters**
- **Found during:** Task 2 full fast-suite gate
- **Issue:** Existing direct `_run_search` and `_search_at_depth` test adapters still used the pre-ordering signatures.
- **Fix:** Forwarded loop-owned killers/history and asserted fresh tables in telemetry coverage.
- **Files modified:** `tests/test_go_bestmove.py`, `tests/test_search_telemetry.py`, `tests/test_uci_generation.py`
- **Verification:** Targeted 49-test set and final 185-test fast suite pass.
- **Committed in:** `31c24eb`

### Verification-only Adjustment

The plan's unfiltered baseline-file command would execute the slow test and its following `-m slow` command would execute it a second time. To honor the explicit instruction to run the prescribed slow comparison once, the file was split into `-m "not slow"` and `-m slow` runs. Together they selected every test in the file exactly once.

---

**Total deviations:** 1 auto-fixed compatibility bug and 1 verification-only command adjustment.
**Impact on plan:** Production scope is unchanged; every acceptance behavior and D-21 gate passed.

## Issues Encountered

None.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

- Required created artifacts exist.
- All five atomic task commits exist in order.
- Every task acceptance gate and the plan-level fast/slow verification passed.
- Existing unstaged `.planning/STATE.md` and unrelated `.codegraph/`, `.cursor/`, and `.serena/` were preserved and excluded from commits.

## Next Phase Readiness

- SRCH-06 is complete and provides the search-efficiency foundation for Plan 03-05 time management.
- No blockers.

---
*Phase: 03-search-acceleration-time-management*
*Completed: 2026-07-11*
