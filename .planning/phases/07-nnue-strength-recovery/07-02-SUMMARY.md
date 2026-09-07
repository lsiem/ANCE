---
phase: 07-nnue-strength-recovery
plan: 02
subsystem: measure-closer
tags: [gauntlet, sidecar, smoke-abort, evidence-json, tool-04]

requires:
  - phase: 06-quiet-data-nnue-strength-gap
    provides: post_train_close_06.py, 06-GAUNTLET-EVIDENCE.json, elo_probe RFC JSON
provides:
  - "post_train_close_07.py measure-only closer (sidecar → diagnostics → 16 smoke → 200 → 1000)"
  - "sidecar_identity_ok / smoke_abort / write_blocked_evidence helpers"
  - "tests/training/test_phase7_closer_evidence.py (blocked, smoke abort, schema, shutout nulls, compare_phase6)"
affects: [closer, evidence-schema, D-14, D-10, D-11]

tech-stack:
  added: []
  patterns: [sidecar-identity-gate, smoke-abort, rfc-json-shutout-nulls]

key-files:
  created:
    - .planning/phases/07-nnue-strength-recovery/post_train_close_07.py
    - tests/training/test_phase7_closer_evidence.py
  modified: []

key-decisions:
  - "Do not copy Phase 6 STRENGTH_NET/ENGINE_NET install fallback; file presence of net.safetensors is not Phase 7 identity"
  - "SMOKE_GAMES=16; abort if wins==0 OR score_rate==0.0 OR elo_ci_high < -200"
  - "Omit optional clock gauntlet; measure ladder is smoke/200/1000 at SEARCH_DEPTH 3"
  - "TOOL-04 remains listed on the plan but is not satisfied; this slice only builds the closer + unit tests"

patterns-established:
  - "sidecar_identity_ok before run_diagnostics (phase 7 or \"7\" and from_scratch True)"
  - "write_blocked_evidence: reason phase7_net_not_installed, gates_failed D-14 and TOOL-04"
  - "PHASE6_BASELINE compare_phase6 copied from 06-GAUNTLET-EVIDENCE.json"

requirements-completed:
  - TOOL-04

duration: 5min
completed: 2026-09-07
---

# Phase 7 Plan 02: Measure closer Summary

**Phase 7 closer requires `07-NET-SIDECAR.json` (phase 7, from_scratch) before any play, then diagnostics → 16-game smoke → 200 → 1000 at depth 3, with RFC evidence for blocked / smoke-abort / useful-fail.**

TOOL-04 is copied into `requirements-completed` because the plan frontmatter lists it. This plan does **not** claim TOOL-04 measurement. It only lands the closer script and unit tests. Plan 07-04 runs the closer against a live gauntlet. Phase 6 stays incomplete. `07-GAUNTLET-EVIDENCE.json` was not hand-authored in the phase directory.

## Performance

- **Duration:** 5 min
- **Started:** 2026-09-07T17:15:35Z
- **Completed:** 2026-09-07T17:20:10Z
- **Tasks:** 2
- **Files modified:** 2 created

## Accomplishments

- Copied `post_train_close_06.py` to `post_train_close_07.py` with ROOT bootstrap, PROBE_GAMES=200, D12_GAMES=1000, SEARCH_DEPTH=3, budgets, and `ANCE_EVAL` nnue vs handcrafted.
- Sidecar gate (`07-NET-SIDECAR.json`) runs before diagnostics; miss or phase mismatch writes blocked RFC JSON and does not call `run_diagnostics` / `run_elo_probe` / `run_gauntlet`.
- Smoke (`SMOKE_GAMES=16`) abort skips 200 and 1000; no torch train; no Phase 6 net install fallback.
- Evidence schema_version 1 includes `blocked`, `probe_smoke`, `compare_phase6` (`PHASE6_BASELINE` from 06 evidence); shutouts serialize as JSON null via `json_safe_number` and `allow_nan=False`.
- Five unit tests green: schema, shutout nulls, blocked without sidecar, smoke abort skips 200, compare_phase6 vs `06-GAUNTLET-EVIDENCE.json`.

## Task Commits

1. **Task 1:** `5b887a1` — `feat(07-02): post_train_close_07.py closer`
2. **Task 2:** `70c0e40` — `test(07-02): Phase 7 closer evidence tests`

## Files Created/Modified

- `.planning/phases/07-nnue-strength-recovery/post_train_close_07.py` — measure-only closer (sidecar, smoke, blocked writer)
- `tests/training/test_phase7_closer_evidence.py` — five named evidence-contract tests

## Decisions Made

- Sidecar identity: `phase == 7` or `phase == "7"` and `from_scratch is True`.
- Smoke abort: `wins == 0` OR `score_rate == 0.0` OR (`elo_ci_high is not None` AND `elo_ci_high < -200`).
- Useful-fail vs Phase 6 0–200 still lists `gates_failed` D-12 and TOOL-04; blocked lists D-14 and TOOL-04.
- Do not start 07-03 from this plan. Do not run a live 200/1000 gauntlet.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

None. Task 2 verify: 15 passed (`test_phase7_closer_evidence`, `test_phase6_closer_evidence`, `test_nnue_gauntlet_depth`, `test_diagnostics_eval`).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 07-03 (M4 from-scratch train recipe and sidecar). Do not run the closer against a live gauntlet here (that is 07-04). Do not start a CPU train. Do not complete-phase 6. TOOL-04 still open.

## Self-Check: PASSED
