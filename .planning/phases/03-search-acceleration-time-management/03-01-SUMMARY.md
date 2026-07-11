---
phase: 03-search-acceleration-time-management
plan: 01
subsystem: search-evidence
tags: [baseline, negamax, performance, evidence]
requires:
  - phase: 02-core-alpha-beta-search
    provides: Pre-TT iterative-deepening search
provides:
  - Pre-TT timed and deterministic search baseline
  - Reusable baseline collector and loader contract
affects: [03-03-transposition-table, 03-04-move-ordering]
requirements-completed: []
completed: 2026-07-11
status: complete
---

# Phase 3 Plan 01: Pre-TT Baseline Summary

Captured a machine-readable Phase 2 search baseline before any transposition
table or move-ordering code was introduced.

## Commits

- `ea0d7af` — baseline collector contract tests (RED)
- `f0abcbd` — baseline collector implementation (GREEN)
- `035af12` — bound the Kiwipete deterministic capture

## Artifacts

- `ance/tools/phase3_baseline.py`
- `tests/test_phase3_strength_baseline.py`
- `.planning/phases/03-search-acceleration-time-management/03-BASELINE.json`

Collector command:

`python -m ance.tools.phase3_baseline --output .planning/phases/03-search-acceleration-time-management/03-BASELINE.json`

The artifact was captured from commit
`035af126c12d91542d3e57ec3062ddf19b3c1415`.

## Verification

- `tests/test_phase3_strength_baseline.py`: 5 passed
- Fast suite: 158 passed, 3 deselected
- All six position IDs, deterministic best moves, node counts, and recorded
  source commit validated.

## Deviation

The planned depth-4 Kiwipete capture was not computationally feasible in the
Phase 2 Python search: it failed to finish depth 3 within the 900-second
watchdog. Kiwipete therefore remains the two-second timed branching stress
case but uses a documented deterministic depth-2 override. At two seconds it
completes no full iteration (`depth=0`, `nodes=0`), which is itself the honest
pre-optimization baseline. Every other position retains deterministic depth 4.
Plan 03-04 must compare each position at the depth recorded in the artifact.
