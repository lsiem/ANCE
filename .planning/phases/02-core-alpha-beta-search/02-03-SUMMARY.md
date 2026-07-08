---
phase: 02-core-alpha-beta-search
plan: 03
subsystem: search
tags: [iterative-deepening, draw-detection, repetition, zobrist]

requires:
  - phase: 02-core-alpha-beta-search
    provides: quiescence search, SearchContext
provides:
  - Iterative deepening loop in search_root
  - Twofold repetition and game-history draw cuts (D-06, D-07)
  - 50-move and insufficient-material draw detection (D-08)
  - Root move ordering from previous ID iteration (D-10)
affects: [02-04, 02-05]

tech-stack:
  added: []
  patterns:
    - "ID returns last completed depth on stop/deadline abort"
    - "path_keys zobrist stack for in-search repetition"
    - "Draw score plain 0 (no contempt)"

key-files:
  created:
    - tests/test_iterative_deepening.py
  modified:
    - ance/search/negamax.py
    - ance/search/types.py

key-decisions:
  - "MAX_PLY=64 for infinite-mode prep; DEFAULT_BARE_GO_MOVETIME_MS=2000"

patterns-established:
  - "game_history_keys built once at root from board move stack"

requirements-completed: [SRCH-03, SRCH-07]

duration: 25min
completed: 2026-07-08
---

# Phase 2 Plan 03: Iterative Deepening Summary

**Iterative deepening with draw detection and last-completed-depth retention on abort**

## Performance

- **Duration:** ~25 min (prior executor session)
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- `search_root` loops depths 1..N, keeping best from last completed iteration
- Draw cuts: twofold in path/history, fifty-move, insufficient material → score 0
- Mate still beats draw when winning capture exists
- Previous iteration's best move searched first at root

## Task Commits

1. **Task 1: Failing ID and draw-detection tests** - `aa3bce0` (test)
2. **Task 2: Iterative deepening + draw cuts** - `823c448` (feat)

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- FOUND: tests/test_iterative_deepening.py
- FOUND: aa3bce0
- FOUND: 823c448

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-08*
