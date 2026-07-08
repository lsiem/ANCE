---
phase: 02-core-alpha-beta-search
plan: 04
subsystem: uci
tags: [uci-info, movetime, go-infinite, iterative-deepening]

requires:
  - phase: 02-core-alpha-beta-search
    provides: iterative deepening, SearchResult with PV
provides:
  - send_info_depth UCI formatter
  - Bare go ~2s movetime budget (D-09)
  - go infinite deepens until stop (D-12)
  - info_callback per completed ID depth (D-11)
affects: [02-05]

tech-stack:
  added: []
  patterns:
    - "Partial depths emit no info line"
    - "pv[0] matches eventual bestmove"
    - "Module-level rng removed from loop.py"

key-files:
  created:
    - tests/test_uci_info.py
  modified:
    - ance/uci/protocol.py
    - ance/uci/loop.py
    - tests/test_go_bestmove.py
    - tests/test_eval_seam.py

key-decisions:
  - "Bare go uses DEFAULT_BARE_GO_MOVETIME_MS ~2000 instead of sub-1s fixed depth"
  - "go infinite replaces Phase 1 idle wait with continuous ID until stop"

patterns-established:
  - "nps = nodes*1000 // max(elapsed_ms, 1) in info lines"

requirements-completed: [UCI-11]

duration: 30min
completed: 2026-07-08
---

# Phase 2 Plan 04: UCI Info and Go Modes Summary

**GUI-visible info depth lines with movetime bare-go and responsive go infinite**

## Performance

- **Duration:** ~30 min (prior executor session)
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- `send_info_depth` formats cp/mate scores with PV in UCI info lines
- Bare `go` iterates deeper under ~2s movetime budget
- `go infinite` emits increasing depth info until stop, no post-search idle hang
- Removed RNG from UCI loop; deterministic root per D-10

## Task Commits

1. **Task 1: Failing UCI info and go-mode tests** - `cccc683` (test)
2. **Task 2: Implement info emission and go dispatch** - `66427e5` (feat)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Legacy UCI tests failed after info line emission**
- **Found during:** Plan 02-05 verification (continuation session)
- **Issue:** `test_uci_handshake`, `test_position_command` read first stdout line expecting bestmove; bare go now emits info lines first
- **Fix:** Use `_read_bestmove` helper to skip info lines
- **Files modified:** tests/test_uci_handshake.py, tests/test_position_command.py
- **Committed in:** c9d5a4b (02-05 commit, regression fix bundled)

## Self-Check: PASSED

- FOUND: tests/test_uci_info.py
- FOUND: cccc683
- FOUND: 66427e5

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-08*
