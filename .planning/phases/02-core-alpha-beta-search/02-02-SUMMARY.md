---
phase: 02-core-alpha-beta-search
plan: 02
subsystem: search
tags: [quiescence, mvv-lva, delta-pruning, horizon]

requires:
  - phase: 02-core-alpha-beta-search
    provides: alpha-beta negamax, SearchContext
provides:
  - quiescence_search at depth-0 boundary
  - MVV-LVA capture ordering (qsearch only)
  - Stand-pat and delta pruning (D-03)
affects: [02-03, 02-04, 02-05]

tech-stack:
  added: []
  patterns:
    - "Quiet depth-0 → qsearch; in-check → evasions only (D-05)"
    - "MAX_QDEPTH=8, DELTA_MARGIN=200 cp"

key-files:
  created:
    - tests/test_quiescence.py
  modified:
    - ance/search/negamax.py

key-decisions:
  - "MVV-LVA ordering confined to qsearch per D-04; main search remains unordered"

patterns-established:
  - "Queen promotion detection via move.promotion == chess.QUEEN"

requirements-completed: [SRCH-04]

duration: 20min
completed: 2026-07-08
---

# Phase 2 Plan 02: Quiescence Search Summary

**Horizon-stable quiescence with stand-pat, delta pruning, and MVV-LVA capture ordering**

## Performance

- **Duration:** ~20 min (prior executor session)
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `quiescence_search` wired at negamax depth==0 for quiet nodes
- In-check path searches all evasions without stand-pat; zero evasions → mate
- Captures + queen promotions only in qsearch; delta pruning skips futile captures
- Regression tests for hanging queen, stand-pat, delta, in-check paths

## Task Commits

1. **Task 1: Failing quiescence horizon tests** - `63dd00e` (test)
2. **Task 2: Implement quiescence search** - `6e09298` (feat)

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- FOUND: tests/test_quiescence.py
- FOUND: 63dd00e
- FOUND: 6e09298

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-08*
