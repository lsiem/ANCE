---
phase: 02-core-alpha-beta-search
plan: 11
subsystem: search
tags: [quiescence, draw-detection, negamax, alpha-beta, SRCH-04, SRCH-07]
requires:
  - phase: 02-core-alpha-beta-search
    provides: core negamax, iterative deepening, and qsearch from Plans 02-02 through 02-10
provides:
  - Draw-aware quiescence_search with balanced path_keys push/pop
  - Terminal-first resolution before quiet MAX_QDEPTH static eval
  - Four focused regressions for verification gaps 1 and 2
affects: [phase-02-verification, phase-03]
tech-stack:
  added: []
  patterns: [qsearch owns path_keys at depth-0 handoff, terminal-before-cap quiet nodes]
key-files:
  created:
    - .planning/phases/02-core-alpha-beta-search/02-11-SUMMARY.md
  modified:
    - ance/search/negamax.py
    - tests/test_quiescence.py
    - tests/test_iterative_deepening.py
key-decisions:
  - "negamax depth-0 calls quiescence_search before path_keys append so qsearch owns the subtree"
  - "MAX_QDEPTH static eval applies only to quiet (not-in-check) nodes with legal moves"
patterns-established:
  - "quiescence_search mirrors negamax draw/terminal/path-key discipline at every node"
requirements-completed: [SRCH-04, SRCH-07]
duration: 15min
completed: 2026-07-10
status: passed
---

# Phase 2 Plan 11: Qsearch Draw and Terminal Cap Summary

**Quiescence search now inherits main-tree draw detection and resolves checkmate/stalemate before quiet depth-cap static evaluation.**

## Performance

- **Tasks:** 2 (RED + GREEN)
- **Files modified:** 3

## Accomplishments

- Added four regressions using `_ConstantEval(123)` to expose historical draw, path draw, capped checkmate, and in-check-at-cap gaps.
- Restructured `quiescence_search` to call `_is_draw_position` at entry, maintain balanced `path_keys`, resolve terminals before cap, and always search evasions when in check.
- Moved negamax depth-0 handoff before `path_keys` append so qsearch owns path-key semantics for its subtree.

## Task Commits

1. **Task 1 RED:** `ade67cad2a64c9d5583855a430ffaf581ea58065`
2. **Task 2 GREEN:** `d698434f9cc7d4e5f19347e7260a73ae229706b6`

## Automated Evidence

- `.venv/bin/python -m pytest tests/test_quiescence.py tests/test_iterative_deepening.py tests/test_alpha_beta.py -q` — **23 passed** in 0.91s
- `.venv/bin/python -m pytest -m "not slow" -q` — **146 passed, 2 deselected** in 17.28s

## Files Created/Modified

- `ance/search/negamax.py` — draw-aware, terminal-first `quiescence_search`; depth-0 path-key handoff
- `tests/test_quiescence.py` — Tests A, C, D (game history draw, capped checkmate, in-check at cap)
- `tests/test_iterative_deepening.py` — Test B (path repetition at qsearch descendant)

## Decisions Made

- Depth-0 negamax returns to qsearch before appending the current zobrist key (one-line comment in source).
- Test B probes the post-capture child node with `path_keys` pre-seeded to avoid stand-pat (123) masking the draw score at the parent.

## Deviations from Plan

### Auto-fixed Issues

**1. Test B probe refined for stand-pat interaction**
- **Found during:** Task 2 GREEN
- **Issue:** Root-level path-repetition probe returned 123 because stand-pat beat the draw score (0) on a winning static eval stub.
- **Fix:** Probe at the child position after `e1e5` with `path_keys` containing the child zobrist.
- **Files modified:** `tests/test_iterative_deepening.py`
- **Verification:** All 146 fast tests pass.
- **Committed in:** `d698434` (GREEN commit)

---

**Total deviations:** 1 auto-fixed (test correctness)
**Impact on plan:** Test still validates SRCH-07 path-key draw detection in qsearch descendants; no production scope change.

## Issues Encountered

None beyond Test B stand-pat interaction noted above.

## Next Phase Readiness

- SRCH-04 and SRCH-07 qsearch gaps closed per verification probes.
- UCI worker exception fallback (verification gap 3) remains out of scope for Plan 02-11.

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-10*
