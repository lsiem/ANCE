---
phase: 02-core-alpha-beta-search
plan: 01
subsystem: search
tags: [negamax, alpha-beta, mate-scoring, search-result]

requires:
  - phase: 01-minimal-uci-engine-evaluator-seam
    provides: Position adapter, Evaluator Protocol, search_root skeleton
provides:
  - SearchContext and SearchResult dataclasses
  - Fail-soft alpha-beta negamax with ply-adjusted mate
  - Deterministic root move selection (D-10)
affects: [02-02, 02-03, 02-04, 02-05]

tech-stack:
  added: []
  patterns:
    - "Fail-soft alpha-beta: beta cutoff returns beta"
    - "Mate scores ±(MATE−ply) in search only"
    - "Deterministic root tie-break: first best move found"

key-files:
  created:
    - ance/search/types.py
    - tests/test_alpha_beta.py
  modified:
    - ance/search/negamax.py
    - tests/test_eval_seam.py

key-decisions:
  - "Removed RNG from search_root per D-10; ties broken by first legal move order"
  - "SearchContext carries stop_flag, node counter, ply, path keys for later plans"

patterns-established:
  - "Evaluator Protocol-only import in negamax (no concrete eval imports)"

requirements-completed: [SRCH-02]

duration: 25min
completed: 2026-07-08
---

# Phase 2 Plan 01: Fail-Soft Alpha-Beta Summary

**Fail-soft alpha-beta negamax with ply-adjusted mate scoring and deterministic SearchResult root selection**

## Performance

- **Duration:** ~25 min (prior executor session)
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- `SearchContext` / `SearchResult` dataclasses in `ance/search/types.py`
- Fail-soft alpha-beta pruning with node counter proving fewer visits on tactical FENs
- Checkmate ±(MATE−ply), stalemate 0, deterministic root (no RNG)
- Updated UCI loop and gauntlet call sites to `SearchResult.best_move`

## Task Commits

1. **Task 1: Failing alpha-beta and mate-scoring tests** - `ee09e10` (test)
2. **Task 2: Fail-soft alpha-beta + SearchResult types** - `b3285d3` (feat)

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- FOUND: ance/search/types.py
- FOUND: tests/test_alpha_beta.py
- FOUND: ee09e10
- FOUND: b3285d3

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-08*
