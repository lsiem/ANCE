---
phase: 02-core-alpha-beta-search
plan: 10
subsystem: testing
tags: [search, deterministic-evidence, deadlines, process-groups]
requires:
  - phase: 02-core-alpha-beta-search
    provides: corrected search, UCI, and harness contracts from Plans 02-07 through 02-09
provides:
  - Bounded deterministic mate, tactic, horizon, telemetry, and deadline evidence
  - Runtime calibration proving statistical games are infeasible in Phase 2
affects: [phase-03, verify-work, strength-validation]
tech-stack:
  added: []
  patterns: [absolute monotonic supervisor deadline, atomic terminal artifacts]
key-files:
  created:
    - ance/tools/phase2_deterministic_evidence.py
    - tests/test_phase2_deterministic_evidence.py
    - .planning/phases/02-core-alpha-beta-search/02-STRENGTH-EVIDENCE.json
    - .planning/phases/02-core-alpha-beta-search/02-10-SUMMARY.md
  modified: []
key-decisions:
  - "Classify the interrupted game run only as runtime calibration and defer statistical strength evidence to Phase 3."
patterns-established:
  - "Evidence work, cleanup, reporting, and validation share one immutable monotonic hard deadline."
requirements-completed: [SRCH-02, SRCH-03, SRCH-04, SRCH-07, UCI-11]
coverage:
  - id: D1
    description: "Deterministic fixed-position search and fast contract evidence"
    verification:
      - kind: integration
        ref: ".venv/bin/python -m ance.tools.phase2_deterministic_evidence"
        status: passed
    human_judgment: false
duration: 30.498s
completed: 2026-07-10
status: passed
---

# Phase 2 Plan 10: Bounded Deterministic Search Evidence Summary

**Exact deterministic search oracles and fast harness contracts replace infeasible statistical Phase 2 strength claims.**

## Performance
- Monotonic timings: supervisor 30.498s; child 30.346s.
- Hard wall: 870 seconds
- Reporting margin: 60 seconds
- Work allowance: 810 seconds
- Graceful process-group wait: 15 seconds
- Forced reap wait: 5 seconds

## Task Commits
1. Task 1 RED: `ab996ce`
2. Task 2 GREEN: `99888cb`
3. Task 3 collector: `c915011a7a5354997ef0073f595b27e1db96cc52`

## Exact Collector Command
`.venv/bin/python -m ance.tools.phase2_deterministic_evidence --output .planning/phases/02-core-alpha-beta-search/02-STRENGTH-EVIDENCE.json --summary .planning/phases/02-core-alpha-beta-search/02-10-SUMMARY.md --hard-wall-seconds 870 --reporting-margin-seconds 60`

## Automated Evidence
- `.venv/bin/python -m pytest tests/test_phase2_deterministic_evidence.py -m "not slow" -q` — 6 passed in 0.339s.
- `.venv/bin/python -m pytest tests/test_phase2_strength_evidence.py tests/test_depth_vs_depth.py tests/test_random_mover_gauntlet.py tests/test_search_deadline.py tests/test_search_telemetry.py tests/test_iterative_deepening.py tests/test_uci_generation.py tests/test_go_bestmove.py -m "not slow" -q` — 73 passed, 2 deselected in 10.434s.
- `.venv/bin/python -m pytest -m "not slow" -q` — 139 passed, 2 deselected in 19.242s.

## Fixed-FEN Evidence
- rook_mate depth 1: a1a8, score 29999, 29 nodes, 0.001s — passed.
- rook_mate depth 2: a1a8, score 29999, 273 nodes, 0.004s — passed.
- queen_mate depth 1: h1a8, score 29999, 42 nodes, 0.001s — passed.
- queen_mate depth 4: h1a8, score 29999, 8249 nodes, 0.120s — passed.
- hanging_queen depth 1: e1e5, score 500, 30 nodes, 0.001s — passed.
- hanging_queen depth 3: e1e5, score 500, 2890 nodes, 0.029s — passed.
- knight_fork depth 1: e5f7, score 0, 25 nodes, 0.001s — passed.
- knight_fork depth 3: e5f7, score 0, 4729 nodes, 0.146s — passed.
- horizon_rook depth 1: e1e4, score 500, 36 nodes, 0.001s — passed.
- horizon_rook depth 3: e1e4, score 500, 2209 nodes, 0.028s — passed.

All exact fixed-FEN observations and requirement-map entries passed: True.
The exact synthetic telemetry oracle is callbacks nodes `[10, 20, 30]`, NPS `[10, 6, 5]`, completed depths `[1, 2, 3]`, final nodes `30`.
Deadline retention is final depth `1` with completed callbacks `[1]`.

## Runtime Calibration and Statistical Deferral
The interrupted runner completed exactly 2 depth games in 1205.6582282920135 seconds (~602.829 seconds/game), projecting 30 depth games to 18084.8734243802 seconds (~5.02 hours). Zero random games started; SIGTERM was received. These outcomes are a non-statistical smoke/calibration sample only and establish that the depth suite alone cannot fit the old 7200-second combined budget.

Depth-vs-depth Elo and random-gauntlet statistical evidence, including D-01/D-14 acceptance, are explicitly deferred to Phase 3 optimized search and a cutechess harness. No confidence, Elo, win-rate acceptance, or statistical superiority is claimed here.

## Requirement Evidence
SRCH-02, SRCH-03, SRCH-04, SRCH-07, and UCI-11 each map to explicit passed evidence IDs in `02-STRENGTH-EVIDENCE.json`. Plan 02-09's five harness tests are recorded as supporting contracts.

## Evidence Artifact
- Path: `.planning/phases/02-core-alpha-beta-search/02-STRENGTH-EVIDENCE.json`
- Reasons: None
- Artifact status: passed

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Phase 2 deterministic correctness evidence is complete. Statistical strength measurement remains explicitly deferred to Phase 3 optimized search and cutechess.

## Self-Check: PASSED
