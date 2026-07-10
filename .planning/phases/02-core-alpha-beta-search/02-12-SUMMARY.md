---
phase: 02-core-alpha-beta-search
plan: 12
subsystem: uci
tags: [threading, exception-handling, generation-gating, fallback, tdd]
gap_closure: true
requires:
  - phase: 02-core-alpha-beta-search
    provides: per-generation UCI worker ownership from Plan 02-08
provides:
  - Exception-safe _run_search with generation-gated fallback bestmove
  - Deterministic first-legal-move / (none) fallback policy on worker failure
  - In-process raising-search and stale-generation regressions
affects: [phase-03, uci, verify-work]

tech-stack:
  added: []
  patterns:
    - "Unexpected search failures log then emit one generation-gated fallback bestmove"
    - "Fallback move chosen only from the worker's copied Position"

key-files:
  created:
    - .planning/phases/02-core-alpha-beta-search/02-12-SUMMARY.md
  modified:
    - ance/uci/loop.py
    - tests/test_uci_generation.py

key-decisions:
  - "SearchAborted is re-raised; only unexpected Exception subclasses trigger fallback"
  - "Fallback uses first legal root move (D-10 spirit) or (none) when pos has zero legal moves"

patterns-established:
  - "Worker exception tests use Events for ordering, not scheduler sleeps"
  - "Stale-generation control bumps search_generation before fallback emission"

requirements-completed: [UCI-06]

coverage:
  - id: D1
    description: "Raising search_root yields exactly one generation-gated legal fallback bestmove"
    requirement: UCI-06
    verification:
      - kind: unit
        ref: tests/test_uci_generation.py#test_worker_exception_emits_generation_gated_fallback_bestmove
        status: pass
    human_judgment: false
  - id: D2
    description: "Zero-legal-move position yields bestmove (none) on worker failure"
    requirement: UCI-06
    verification:
      - kind: unit
        ref: tests/test_uci_generation.py#test_worker_exception_fallback_none_on_mate
        status: pass
    human_judgment: false
  - id: D3
    description: "Superseded generation drops exception fallback output"
    requirement: UCI-06
    verification:
      - kind: unit
        ref: tests/test_uci_generation.py#test_stale_worker_exception_emits_no_fallback_bestmove
        status: pass
    human_judgment: false

duration: 0.07s
completed: 2026-07-10
status: passed
---

# Phase 2 Plan 12: Worker Exception Fallback Summary

**Unexpected search worker failures now emit exactly one generation-gated `bestmove` instead of leaving the GUI hanging.**

## Task Commits
1. Task 1 RED: `e575337`
2. Task 2 GREEN: `cef9cec`

## RED Verification
- `.venv/bin/python -m pytest tests/test_uci_generation.py -q` — 2 failed, 3 passed (zero bestmove captured on `RuntimeError` raise).

## GREEN Verification
- `.venv/bin/python -m pytest tests/test_uci_generation.py tests/test_go_bestmove.py -q` — 22 passed in 9.64s.
- `.venv/bin/python -m pytest -m "not slow" -q` — 142 passed, 2 deselected in 17.91s.

## Implementation
- `_fallback_root_move(pos)` returns `None` when `pos.has_no_legal_moves()`, else `pos.legal_moves()[0]`.
- `_run_search` catches unexpected `Exception`, logs `ERROR: search worker failed: {exc}`, derives fallback from the worker's position copy, then emits via the existing `generation_lock` gate after `finally` timer cleanup.
- `SearchAborted` is re-raised (intentional abort path unchanged).

## Deviations from Plan
None — plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None

## Next Phase Readiness
UCI-06 one-bestmove-per-go contract holds on worker failure paths. Plan 02-08 concurrency regressions remain green.
