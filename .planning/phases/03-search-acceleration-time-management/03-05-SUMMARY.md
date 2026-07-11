---
phase: 03-search-acceleration-time-management
plan: 05
subsystem: search
tags: [uci, clock-management, iterative-deepening, arbiter, pytest]
requires:
  - phase: 03-search-acceleration-time-management
    provides: Gauntlet clock referee, transposition table, and full move ordering
provides:
  - Pure side-aware soft/hard UCI clock budget computation
  - Clock deadline and soft-budget threading with preserved go-limit precedence
  - Soft iterative-deepening gate and 512-node hard-stop polling
  - Real 5+0.1 zero-forfeit arbiter evidence with per-move timing audit
affects: [03-06-phase-evidence, search-core, uci-loop, gauntlet]
tech-stack:
  added: []
  patterns:
    - Pure clock budget calculation separated from UCI dispatch
    - Soft iteration boundary plus independently enforced hard deadline
    - Arbiter records per-move clock-before and elapsed timing
key-files:
  created:
    - ance/uci/clock.py
    - tests/test_time_management.py
  modified:
    - ance/uci/loop.py
    - ance/search/negamax.py
    - ance/tools/gauntlet.py
    - tests/test_search_deadline.py
key-decisions:
  - "Use remaining/25 plus 60% increment credit for soft time, capped by four-times-soft, one-third remaining, and a 200ms flag margin for hard time."
  - "Only the existing bare-go branch computes clock budgets, preserving infinite, depth, and movetime precedence."
  - "Persist per-move arbiter timing so hard-budget overshoot is auditable rather than inferred from game totals."
patterns-established:
  - "Clock budgets are milliseconds at the UCI boundary and seconds inside search."
  - "Depth one always starts; later iterations stop at half the soft budget once a completed result exists."
requirements-completed: [SRCH-08, UCI-08]
coverage:
  - id: D1
    description: Pure clock budgets satisfy formula, margin, floor, side-selection, and garbage-input invariants.
    requirement: SRCH-08
    verification:
      - kind: unit
        ref: "tests/test_time_management.py#clock budget tests"
        status: pass
      - kind: other
        ref: ".venv/bin/python -c clock budget assertions"
        status: pass
    human_judgment: false
  - id: D2
    description: UCI clock fields drive hard deadlines and soft iteration limits without changing explicit go-limit precedence.
    requirement: UCI-08
    verification:
      - kind: integration
        ref: "tests/test_time_management.py#test_go_limit_precedence_and_clock_budget_threading"
        status: pass
      - kind: integration
        ref: "tests/test_time_management.py#test_clocked_uci_go_returns_one_legal_bestmove_quickly"
        status: pass
      - kind: other
        ref: ".venv/bin/python -m pytest -m 'not slow' -q"
        status: pass
    human_judgment: false
  - id: D3
    description: One real arbiter-refereed 5+0.1 game completes without a time forfeit or excessive hard-budget overshoot.
    requirement: SRCH-08
    verification:
      - kind: e2e
        ref: "tests/test_time_management.py#test_clocked_game_never_flags"
        status: pass
      - kind: other
        ref: "/tmp/ance-03-05-clock-smoke-20260711.json"
        status: pass
    human_judgment: false
duration: 17 min
completed: 2026-07-11
status: complete
---

# Phase 3 Plan 05: Clock Time Management Summary

**Clock-aware UCI search now computes bounded soft/hard budgets, avoids doomed deepening iterations, polls deadlines every 512 nodes, and completes a real 5+0.1 game without flagging.**

## Performance

- **Duration:** 17 min
- **Started:** 2026-07-11T02:21:43Z
- **Completed:** 2026-07-11T02:38:59Z
- **Tasks:** 3
- **Files modified:** 9

## Accomplishments

- Added pure, side-aware budget math with a 20ms floor, 200ms safety margin, increment credit, and exhaustive invariant coverage.
- Threaded hard deadline and soft budget from `handle_go` through the worker into iterative deepening while preserving `infinite`, `depth`, and `movetime` behavior.
- Reduced node polling from 2048 to 512 and proved a real 5+0.1 arbiter game had zero forfeits and at most 16.67ms hard-budget overshoot.

## Task Commits

1. **Task 1 RED: Clock budget invariants** - `01db6e0`
2. **Task 1 GREEN: Pure soft/hard budget computation** - `9b50751`
3. **Task 2 RED: Clock wiring, soft gate, and poll cadence** - `c46cd1d`
4. **Task 2 GREEN: End-to-end clock time management** - `75907f7`
5. **Task 3 RED: Auditable arbiter move timing** - `331043d`
6. **Task 3: Real 5+0.1 zero-forfeit smoke** - `640f66d`

## Clock and Arbiter Evidence

- Nominal budget: `wtime=60000 winc=1000` produced `(soft_ms, hard_ms) = (3000.0, 12000.0)`.
- Defensive floor: `wtime=-500` produced `(20.0, 20.0)`; depth-only commands returned no clock budget.
- Exact real command: `.venv/bin/python -m ance.tools.gauntlet --games 1 --tc 5+0.1 --max-halfmoves 60 --output /tmp/ance-03-05-clock-smoke-20260711.json --runner arbiter --restart`.
- Game result: completed after 34 plies by threefold repetition in `11.976549002924003s`.
- Time forfeits: `{"engine-a": 0, "engine-b": 0}`.
- Maximum move elapsed: White `0.8035148750059307s`; Black `0.8853169590001926s`.
- Maximum hard-budget overshoot: White `0.016154875005930602s`; Black `0.01667079134689023s`, both below the `0.300s` allowance.

## Verification

- Budget and clock/search target: **45 passed, 1 deselected in 0.27s**.
- Real slow clock smoke: **1 passed, 41 deselected in 12.18s**.
- Full fast suite: **227 passed, 5 deselected in 62.78s**.
- `git diff --check a57504f..HEAD`: passed.

## Files Created/Modified

- `ance/uci/clock.py` - Pure budget constants and `compute_clock_budget`.
- `ance/uci/loop.py` - Clock branch, deadline construction, and soft-budget worker threading.
- `ance/search/negamax.py` - Half-soft-budget iteration gate and 512-node polling.
- `ance/tools/gauntlet.py` - Per-move elapsed timing and per-color maxima in game records.
- `tests/test_time_management.py` - Budget, precedence, soft-gate, UCI, and real-game contracts.
- `tests/test_search_deadline.py` - Explicit 512-node cadence contract.
- `tests/test_gauntlet_harness.py` - Arbiter timing-record contract.
- `tests/test_go_bestmove.py`, `tests/test_uci_generation.py` - Updated worker adapters and active-clock expectation.

## Decisions Made

- Kept clock budgeting inside the pre-existing bare-go branch so explicit limit precedence remains structural rather than duplicated.
- Recorded full per-move timing evidence because total game elapsed cannot prove the 300ms overshoot bound.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Updated pre-existing direct worker test adapters**
- **Found during:** Task 2 full fast-suite gate
- **Issue:** Direct `_run_search` callers still used the old argument list, and the old parser-only clock test used a 300-second clock that no longer returns within four seconds once clocks are honored.
- **Fix:** Added the soft-budget argument to both adapters, changed the parser smoke to a one-second clock, and isolated the new dormant-thread spy's `active_job`.
- **Files modified:** `tests/test_go_bestmove.py`, `tests/test_uci_generation.py`, `tests/test_time_management.py`
- **Verification:** Targeted compatibility set passed 83 tests; final fast suite passed 227 tests.
- **Committed in:** `75907f7`

**2. [Rule 2 - Missing Critical] Added arbiter per-move timing records**
- **Found during:** Task 3 overshoot assertion
- **Issue:** Plan 03-05 assumed Plan 03-02 persisted per-move maxima, but the harness only persisted total game elapsed time, making the required overshoot assertion impossible.
- **Fix:** Persisted each mover's clock-before and elapsed time plus per-color maxima, then audited every move against the computed hard budget.
- **Files modified:** `ance/tools/gauntlet.py`, `tests/test_gauntlet_harness.py`, `tests/test_time_management.py`
- **Verification:** RED contract failed on missing fields; unit contract, real slow smoke, and final fast suite all passed.
- **Committed in:** `331043d`, `640f66d`

---

**Total deviations:** 2 auto-fixed (1 compatibility bug, 1 missing evidence field).
**Impact on plan:** Both changes were required to preserve prior contracts and make the mandated arbiter evidence auditable; production scope remained limited to clock/time management.

## Issues Encountered

- The first full-suite run found four compatibility failures after `_run_search` gained `soft_budget`; all were resolved before Task 2 was committed.

## Manual Follow-up

- En Croissant blitz-preset clock observation: **not run**. This remains a non-blocking developer follow-up; use a clocked blitz preset, not Unlimited/infinite.

## User Setup Required

None - no external service configuration required.

## Self-Check: PASSED

- Required artifacts exist and all six task commits are reachable from `HEAD`.
- Every task and plan-level automated gate passed, including the real arbiter smoke.
- Existing unstaged `.planning/STATE.md` and unrelated `.codegraph/`, `.cursor/`, and `.serena/` remain unmodified by plan commits.
- ROADMAP.md and phase-level STATE.md were not updated.

## Next Phase Readiness

- UCI-08 and SRCH-08 are implemented and clock-safe at the Plan 03-05 smoke scale.
- Plan 03-06 can run the statistical 100-game D-14 acceptance gate.
- No blockers.

---
*Phase: 03-search-acceleration-time-management*
*Completed: 2026-07-11*
