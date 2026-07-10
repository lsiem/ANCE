---
phase: 02-core-alpha-beta-search
plan: 09
subsystem: testing
tags: [self-play, result-normalization, seeded-openings, python-chess, tdd]

requires:
  - phase: 02-core-alpha-beta-search
    provides: iterative-deepening search and the depth-vs-depth strength harness
provides:
  - Single deeper-side win/draw/loss convention for depth-match games
  - Deterministic legal four-ply opening variation selected by seed
  - Independent color alternation and opening-seed progression
affects: [02-10, strength-validation, verify-work]

tech-stack:
  added: []
  patterns:
    - "Normalize external result formats once at the game boundary"
    - "Derive reproducible opening variation from seed + game index"

key-files:
  created:
    - .planning/phases/02-core-alpha-beta-search/02-09-SUMMARY.md
  modified:
    - ance/tools/depth_vs_depth_match.py
    - tests/test_depth_vs_depth.py

key-decisions:
  - "play_depth_match_game owns the only raw python-chess result conversion; run_depth_match tallies typed deeper-side outcomes directly"
  - "Game index controls color parity while seed + game index controls opening selection, keeping the dimensions independent"

patterns-established:
  - "DepthMatchOutcome is the contract between one-game execution and match aggregation"
  - "Checked-in legal UCI lines make strength evidence reproducible without random state"

requirements-completed: [SRCH-02, SRCH-03, SRCH-04]

coverage:
  - id: D1
    description: "Every terminal color/result combination and capped game maps to a deeper-side win, draw, or loss exactly once"
    requirement: SRCH-02
    verification:
      - kind: unit
        ref: tests/test_depth_vs_depth.py#test_game_outcome_is_from_deeper_side_perspective
        status: pass
      - kind: unit
        ref: tests/test_depth_vs_depth.py#test_halfmove_cap_is_a_deeper_perspective_draw
        status: pass
      - kind: integration
        ref: tests/test_depth_vs_depth.py#test_two_deeper_side_wins_tally_as_two_wins
        status: pass
    human_judgment: false
  - id: D2
    description: "Seeds reproducibly select distinct checked-in opening lines that apply as exactly four legal plies"
    requirement: SRCH-03
    verification:
      - kind: unit
        ref: tests/test_depth_vs_depth.py#test_opening_selection_is_reproducible_and_varies_by_seed
        status: pass
      - kind: integration
        ref: tests/test_depth_vs_depth.py#test_every_configured_opening_is_legal_and_four_plies
        status: pass
    human_judgment: false
  - id: D3
    description: "Match execution alternates deeper-side color independently from advancing opening seeds and forwards bounded game length"
    requirement: SRCH-04
    verification:
      - kind: integration
        ref: tests/test_depth_vs_depth.py#test_two_deeper_side_wins_tally_as_two_wins
        status: pass
      - kind: unit
        ref: tests/test_depth_vs_depth.py#test_non_positive_game_count_is_rejected
        status: pass
    human_judgment: false

duration: 5min
completed: 2026-07-10
status: complete
---

# Phase 2 Plan 09: Trustworthy Depth-Match Semantics Summary

**Typed deeper-side outcomes and deterministic legal seeded openings remove result inversion and start-position repetition from the strength harness**

## Performance

- **Duration:** 5 min
- **Started:** 2026-07-10T16:47:16Z
- **Completed:** 2026-07-10T16:52:56Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Exhaustively pinned six terminal color/result mappings plus two capped-draw cases to the deeper side's perspective.
- Replaced double color interpretation with a single `DepthMatchOutcome` conversion and direct match aggregation.
- Added eight legal four-ply openings with deterministic seed selection independent of alternating deeper-side color.

## Task Commits

Each task was committed atomically:

1. **Task 1: Exhaust result and seed semantics (RED)** - `bd0122e` (test)
2. **Task 2: Normalize once and apply deterministic openings (GREEN)** - `fd4e991` (fix)

**Plan metadata:** pending docs commit

## Files Created/Modified

- `ance/tools/depth_vs_depth_match.py` - Defines typed outcomes, legal opening lines, deterministic selection, and direct aggregation.
- `tests/test_depth_vs_depth.py` - Covers eight result cases, two-win aggregation, seed determinism, legal openings, scheduling, and input validation.
- `.planning/phases/02-core-alpha-beta-search/02-09-SUMMARY.md` - Records execution and verification evidence.

## Decisions Made

- Raw `1-0`/`0-1`/`1/2-1/2` values remain local to `play_depth_match_game`; callers receive only `win`/`draw`/`loss`.
- Color alternation uses game-index parity, while opening selection uses `seed + game_index`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Reconciled inconsistent generated progress fields**
- **Found during:** Plan close-out
- **Issue:** `state.update-progress` reported 94% but wrote 20% to frontmatter and left the body at 88%; session recording also left the last-activity description on Plan 08.
- **Fix:** Reconciled STATE.md to 15/16 completed plans (94%), Plan 10 as next, and Plan 09 as the latest activity.
- **Files modified:** `.planning/STATE.md`
- **Verification:** STATE reports 15 completed plans, 94% in frontmatter/body, and `Completed 02-09-PLAN.md`.
- **Committed in:** Plan metadata commit.

---

**Total deviations:** 1 auto-fixed (1 blocking planning-state inconsistency).
**Impact on plan:** Planning metadata only; production behavior and test evidence were unchanged.

## Issues Encountered

- The state updater emitted internally inconsistent progress fields; reconciled during the required close-out update.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The depth-match harness is trustworthy and configured for the 30-game depth-2-versus-depth-3 evidence run.
- Ready for `02-10-PLAN.md`; the intentionally slow strength test was not run in this plan.

## Self-Check: PASSED

- Focused fast suite: 12 passed, 1 deselected in 0.04s.
- Full fast suite: 106 passed, 2 deselected in 21.65s.
- RED and GREEN commits exist in order with no tracked-file deletions.
- Eight result cases, two-win aggregation, deterministic legal openings, and bounded scheduling all pass.
- No stubs or new trust-boundary surface were introduced.

---
*Phase: 02-core-alpha-beta-search*
*Completed: 2026-07-10*
