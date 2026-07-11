---
phase: 03-search-acceleration-time-management
plan: 03
subsystem: search
tags: [transposition-table, zobrist, negamax, uci, pytest]
requires:
  - phase: 03-search-acceleration-time-management
    provides: Pre-TT baseline and fixed-depth node evidence from Plan 03-01
provides:
  - Fixed 2^20-slot Zobrist transposition table with exact/lower/upper bounds
  - Negamax probe/store integration with node-relative mate-score conversion
  - Persistent process-owned TT cleared by ucinewgame
affects: [03-04-move-ordering, 03-05-time-management, search-core, uci-loop]
tech-stack:
  added: []
  patterns:
    - Single-key-per-node Zobrist reuse across draw detection, path state, and TT
    - Depth-preferred tuple-slot replacement with full-key collision verification
key-files:
  created:
    - ance/search/transposition.py
    - tests/test_transposition_table.py
  modified:
    - ance/search/types.py
    - ance/search/negamax.py
    - ance/uci/loop.py
    - tests/test_search_telemetry.py
    - tests/test_go_bestmove.py
    - tests/test_uci_generation.py
key-decisions:
  - "Mate scores convert between root-relative and node-relative only at the transposition module boundary."
  - "The process-owned TT persists across go commands and is cleared only after worker preemption in ucinewgame."
  - "Kiwipete cold determinism uses the Phase 3 baseline's depth-2 override because depth 3 remains unsuitable for the fast lane."
patterns-established:
  - "Probe after draw and depth-zero handling; store only after a fully completed move loop."
  - "Shared search state is forwarded through both child contexts and per-root-move contexts."
requirements-completed: [SRCH-05]
coverage:
  - id: D1
    description: Fixed-size TT storage, replacement, collision, mate-score, and clear contracts
    requirement: SRCH-05
    verification:
      - kind: unit
        ref: tests/test_transposition_table.py#TT storage contract tests
        status: pass
    human_judgment: false
  - id: D2
    description: Negamax TT cutoffs reduce nodes while preserving tactical best moves and mate scores
    requirement: SRCH-05
    verification:
      - kind: integration
        ref: tests/test_transposition_table.py#search integration tests
        status: pass
      - kind: other
        ref: .venv/bin/python -m pytest -m "not slow" -q
        status: pass
    human_judgment: false
  - id: D3
    description: Persistent UCI TT is warm across searches and reset by ucinewgame
    requirement: SRCH-05
    verification:
      - kind: integration
        ref: tests/test_transposition_table.py#test_ucinewgame_clears_persistent_engine_table
        status: pass
    human_judgment: false
duration: 29 min
completed: 2026-07-11
status: complete
---

# Phase 3 Plan 03: Zobrist Transposition Table Summary

**A fixed-size, mate-safe transposition table now accelerates negamax, persists across UCI searches, and clears cleanly between games.**

## Performance

- **Duration:** 29 min
- **Started:** 2026-07-11T01:33:00Z
- **Completed:** 2026-07-11T02:02:25Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments

- Added a 2^20-slot depth-preferred TT with full-key collision checks, exact/lower/upper flags, and centralized mate-ply conversion.
- Integrated TT cutoffs and stores into fail-soft negamax while computing each node's Zobrist key once per search function and preserving qsearch's no-TT contract.
- Added persistent UCI ownership and an observable `ucinewgame` reset contract, with the full fast suite remaining green.
- Italian depth 4: **501,208 nodes without TT → 475,298 with TT**, a **5.17% reduction**, with best move `g8f6` unchanged.

## Task Commits

1. **Task 1 RED: TT contract tests** - `4633699`
2. **Task 1 GREEN: fixed-size Zobrist table** - `5ec693a`
3. **Task 2 RED: negamax integration tests** - `3f659b2`
4. **Task 2 GREEN: negamax probe/store integration** - `40dba44`
5. **Task 3: persistent UCI ownership and clearing** - `f1210ba`

## Files Created/Modified

- `ance/search/transposition.py` - Fixed-size table, bound flags, depth replacement, collision verification, and mate conversion.
- `ance/search/types.py` - Optional shared TT reference on `SearchContext`.
- `ance/search/negamax.py` - Single-key node flow, bound-aware probing, and completed-node stores.
- `ance/uci/loop.py` - Process-owned table passed to workers and cleared by `ucinewgame`.
- `tests/test_transposition_table.py` - Unit and integration coverage for D-01 through D-06 and D-22.
- `tests/test_search_telemetry.py` - Updated internal search mock for TT propagation.
- `tests/test_go_bestmove.py` - Updated direct worker invocations for explicit TT ownership.
- `tests/test_uci_generation.py` - Updated stale-worker invocation for explicit TT ownership.

## Verification

- `.venv/bin/python -m pytest tests/test_transposition_table.py -q` — **16 passed**.
- `.venv/bin/python -m pytest -m "not slow" -q` — **174 passed, 3 deselected**.
- `zobrist_hash` occurrences in `ance/search/negamax.py` — **4**, as required.
- Italian depth-4 A/B measurement — **5.17% fewer nodes**, same best move.

## Decisions Made

- Tuple slots and single list assignment preserve the stale-worker safety model without adding a hot-path lock.
- Draw checks remain before probes, terminal nodes remain unstored, and abort unwinding bypasses stores.
- The table remains disabled by default (`tt=None`) for baseline A/B comparisons and backward-compatible callers.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Bounded the Kiwipete reproducibility test**
- **Found during:** Task 2
- **Issue:** Kiwipete depth 3 did not complete after two separate three-minute attempts, even with `MaterialEval`; this contradicted the mandatory fast-suite gate and matched Plan 03-01's documented depth-2 override.
- **Fix:** Retained Kiwipete cold-TT reproducibility but used the recorded depth-2 override with `MaterialEval`.
- **Files modified:** `tests/test_transposition_table.py`
- **Verification:** Both cold runs return identical nodes and best move; the exact plan test and fast suite pass.
- **Committed in:** `40dba44`

**2. [Rule 1 - Bug] Updated internal test doubles for new TT parameters**
- **Found during:** Tasks 2 and 3 full-suite gates
- **Issue:** Existing telemetry and direct-worker tests mocked internal functions with their pre-TT signatures.
- **Fix:** Forwarded/asserted the explicit TT argument in those test adapters.
- **Files modified:** `tests/test_search_telemetry.py`, `tests/test_go_bestmove.py`, `tests/test_uci_generation.py`
- **Verification:** Full fast suite passes with 174 tests.
- **Committed in:** `40dba44`, `f1210ba`

---

**Total deviations:** 2 auto-fixed (1 blocking runtime issue, 1 compatibility issue).
**Impact on plan:** Production scope is unchanged; deterministic coverage remains bounded and all SRCH-05 contracts are exercised.

## Issues Encountered

- Kiwipete depth 3 remained computationally infeasible for a fast test. The baseline-authorized depth-2 override resolves this without weakening collision, cutoff, mate, tactical, or cross-game tests.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

- All created key files exist.
- All five task commits are present in order.
- Every task acceptance gate and the plan-level verification commands pass.
- `.planning/STATE.md`, `.planning/ROADMAP.md`, and unrelated tool directories were not modified by this plan.

## Next Phase Readiness

- TT hash moves are retained in entries and ready for Plan 03-04 move ordering.
- No blockers.

---
*Phase: 03-search-acceleration-time-management*
*Completed: 2026-07-11*
