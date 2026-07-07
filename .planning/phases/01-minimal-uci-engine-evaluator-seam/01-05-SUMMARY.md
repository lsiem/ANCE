---
phase: 01-minimal-uci-engine-evaluator-seam
plan: 05
subsystem: testing
tags: [self-play, gauntlet, random-mover, pytest, tool-02]

# Dependency graph
requires:
  - phase: 01-minimal-uci-engine-evaluator-seam plan 04
    provides: HandcraftedEval as the default evaluator (material+PST+positional terms)
provides:
  - ance/tools/random_mover_gauntlet.py — RandomMover, GameResult, play_game(), run_gauntlet(), GAUNTLET_SEARCH_DEPTH
  - tests/test_random_mover_gauntlet.py — fast unit tests (RandomMover, play_game) plus a slow-marked 30-game proof gauntlet
  - REPLANNED TOOL-02 acceptance criterion (losses==0 hard invariant + wins>=70% floor, non-wins all draws) replacing the original 100/100 target
affects: [future search/pruning phases (deferred 100/0-at-depth-4 follow-up), verify-work UAT for TOOL-02]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Self-play gauntlet harness drives search_root + a real Evaluator in-process (no UCI pipe) for fast, deterministic measurement"
    - "Gauntlet search depth (GAUNTLET_SEARCH_DEPTH) kept decoupled from the interactive DEFAULT_DEPTH so GUI-responsiveness tuning never weakens the strength proof"
    - "Non-win games captured with seed/result/terminal-FEN in a non_win_games list for diagnosis without a full re-run"

key-files:
  created:
    - .planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md
  modified:
    - ance/tools/random_mover_gauntlet.py
    - tests/test_random_mover_gauntlet.py
    - .planning/phases/01-minimal-uci-engine-evaluator-seam/01-05-PLAN.md
    - .planning/REQUIREMENTS.md

key-decisions:
  - "REPLANNED 01-05's acceptance criterion mid-execution (approved 2026-07-07): the original wins==100/losses==0-at-depth-4 target was both impractical (a real depth-4/100-game run was killed after 31 min without finishing) and unproven (depth-3 already drew)"
  - "New criterion: losses==0 is a HARD invariant (a loss to a uniformly-random mover is always a bug); wins>=70% of games is the strength floor; every non-win must be a draw"
  - "GAUNTLET_SEARCH_DEPTH lowered from 4 to 2, and n_games lowered from 100 to 30 for the slow test — measured deterministic at 25 wins/0 losses/5 draws (83%), ~31s wall-clock"
  - "The strict 100/0-at-depth-4 target is DEFERRED (not deleted) — tracked as a pending todo, actionable once alpha-beta pruning makes deeper search practical in wall-clock time"

patterns-established:
  - "In-code failure runbook on run_gauntlet: distinguish losses>0 (always a bug, never masked by tuning) from wins<floor (expected shallow-search draw pattern, principled fix is deferred pending pruning)"

requirements-completed: [TOOL-02]

coverage:
  - id: D1
    description: "RandomMover picks a uniformly-random legal move, deterministic per seed"
    requirement: "TOOL-02"
    verification:
      - kind: unit
        ref: "tests/test_random_mover_gauntlet.py#test_random_mover_picks_legal_move"
        status: pass
      - kind: unit
        ref: "tests/test_random_mover_gauntlet.py#test_random_mover_is_deterministic_per_seed"
        status: pass
    human_judgment: false
  - id: D2
    description: "play_game() always terminates with a valid GameResult (result string + terminal FEN)"
    requirement: "TOOL-02"
    verification:
      - kind: unit
        ref: "tests/test_random_mover_gauntlet.py#test_play_game_terminates_with_a_valid_result"
        status: pass
    human_judgment: false
  - id: D3
    description: "ANCE (search_root + HandcraftedEval) never loses to the random mover and wins at least 70% of games at GAUNTLET_SEARCH_DEPTH=2, with every non-win a draw (REPLANNED acceptance criterion for TOOL-02, replacing the original 100/100-at-depth-4 target)"
    requirement: "TOOL-02"
    verification:
      - kind: integration
        ref: "tests/test_random_mover_gauntlet.py#test_ance_never_loses_and_wins_majority_vs_random_mover"
        status: pass
    human_judgment: false
  - id: D4
    description: "100 wins / 0 draws at GAUNTLET_SEARCH_DEPTH>=4 (the original, stronger TOOL-02 goal) — DEFERRED, not asserted by this plan"
    verification: []
    human_judgment: true
    rationale: "Deliberately deferred to a future alpha-beta pruning phase (depth 4 unpruned measured >31 min for a 100-game run); tracked as a pending todo, no automated coverage exists for this deferred goal by design"

# Metrics
duration: 35min
completed: 2026-07-07
status: complete
---

# Phase 1 Plan 5: Self-play gauntlet vs. random mover (TOOL-02, replanned) Summary

**Self-play gauntlet harness proving ANCE never loses to a uniformly-random mover and wins >=70% of games at a measured, deterministic depth-2/30-game configuration — replacing the original, unverified 100/100-at-depth-4 target.**

## Performance

- **Duration:** 35 min (includes replan analysis, code/test/plan revision, and verification)
- **Started:** 2026-07-07T12:05:00Z (approx.)
- **Completed:** 2026-07-07T12:43:56Z
- **Tasks:** 2 (both originally completed under the old criterion; Task 2 revised under this replan)
- **Files modified:** 4 (gauntlet module, test module, PLAN.md, REQUIREMENTS.md) + 1 created (pending todo)

## Accomplishments

- `ance/tools/random_mover_gauntlet.py`: `RandomMover`, `GameResult`, `play_game()` (Task 1, previously committed) and `run_gauntlet()` (Task 2, committed for the first time in this session — it existed uncommitted in the working tree from a prior session)
- Gauntlet acceptance criterion REPLANNED (approved 2026-07-07) from "wins==100, losses==0 @ depth 4, n=100" to "losses==0 (hard) + wins>=70% + every non-win is a draw, @ depth 2, n=30" — verified GREEN in ~31s wall-clock (25 wins / 0 losses / 5 draws measured)
- `tests/test_random_mover_gauntlet.py`'s slow test renamed to `test_ance_never_loses_and_wins_majority_vs_random_mover` with the revised assertions; fast (`not slow`) unit tests untouched and still green
- `01-05-PLAN.md` updated end-to-end (must_haves, objective, Task 2, threat register, verification, success_criteria) to state the new criterion and flag the original 100/0-at-depth-4 goal as DEFERRED
- Deferred follow-up filed at `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md`, actionable once alpha-beta pruning makes depth>=4 practical

## Task Commits

Each change was committed atomically:

1. **Gauntlet depth replan (Task 2 revision)** — `f988523` (feat) — lowered `GAUNTLET_SEARCH_DEPTH` to 2, rewrote module docstring + failure runbook; this commit also captures `run_gauntlet()` in git history for the first time (was uncommitted from a prior session)
2. **Slow test assertion replan (Task 2 revision)** — `1e33610` (test) — renamed and revised the slow test's assertions to the new criterion
3. **PLAN.md acceptance criterion replan** — `5b45e3b` (docs) — must_haves/objective/Task 2/threat-register/verification/success_criteria updated
4. **Deferred follow-up todo** — `5e137f2` (docs) — filed the depth-4/100-game follow-up

Prior-session commits for this plan (Task 1, unaffected by this replan):
- `e4d4765` (test): failing tests for random mover and single-game referee
- `daeecaa` (feat): RandomMover and play_game implementation
- `68d07c1` (test): originally-failing slow test (now superseded by `1e33610`)

**Plan metadata:** (this commit) — docs: complete plan

## Files Created/Modified

- `ance/tools/random_mover_gauntlet.py` — `GAUNTLET_SEARCH_DEPTH = 2` (was 4); rewrote module docstring and `run_gauntlet`'s failure runbook for the new criterion; `run_gauntlet()`'s tallying logic unchanged
- `tests/test_random_mover_gauntlet.py` — slow test renamed and reassert to `losses==0`, `wins>=21` (70% of 30), `wins+draws==30`
- `.planning/phases/01-minimal-uci-engine-evaluator-seam/01-05-PLAN.md` — acceptance criterion, objective, Task 2, threat register, verification, and success_criteria all updated to the replanned criterion
- `.planning/REQUIREMENTS.md` — TOOL-02 requirement text updated to reflect the replanned criterion
- `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md` — created, tracking the deferred 100/0-at-depth-4 goal

## Decisions Made

- **Replanned TOOL-02's acceptance criterion mid-execution** (user-approved): the original "100/100 wins at depth 4" target was both impractical (a real run was killed after 31 minutes without finishing) and unverified (depth-3 already drew). The new criterion — `losses==0` hard invariant, `wins>=70%` floor, every non-win a draw — is the invariant that was actually measured and holds deterministically (25W/0L/5D @ depth 2, seeds 0-29, ~31s).
- **Lowered `GAUNTLET_SEARCH_DEPTH` from 4 to 2** and `n_games` from 100 to 30 for the slow test, trading the (unproven) stronger target for a fast (~31s), deterministic, provably-green one.
- **Deferred rather than deleted** the original 100/0-at-depth-4 goal: filed as a pending todo, to be revisited once alpha-beta pruning (a later search phase per ROADMAP.md) makes deeper search practical in wall-clock time.
- **Kept `GAUNTLET_SEARCH_DEPTH` decoupled from the interactive `DEFAULT_DEPTH`** (unchanged design decision from the original plan) so GUI-responsiveness tuning never affects the gauntlet's strength proof, and vice versa.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 4 - Architectural/acceptance-criterion change, user-approved] Replanned TOOL-02's acceptance criterion**
- **Found during:** Resuming Task 2 execution in a fresh session
- **Issue:** The original acceptance criterion (wins==100, losses==0 at GAUNTLET_SEARCH_DEPTH=4, n_games=100) was measured to be impractical (a real run took >31 minutes without finishing) and unverified (depth-3 already drew, so 100/0 at depth 4 was never actually proven).
- **Fix:** User approved a replan to the criterion that IS measured and holds: losses==0 (hard invariant) + wins>=70% + every non-win is a draw, at GAUNTLET_SEARCH_DEPTH=2, n_games=30. This is not a Rule 1-3 auto-fix (it changes an acceptance criterion, which is an architectural/scope decision) — it was explicitly presented to and approved by the user before this executor ran.
- **Files modified:** `ance/tools/random_mover_gauntlet.py`, `tests/test_random_mover_gauntlet.py`, `01-05-PLAN.md`, `.planning/REQUIREMENTS.md`
- **Verification:** `.venv/bin/python -m pytest tests/test_random_mover_gauntlet.py -q -m slow` passes (25W/0L/5D, ~31s); full fast suite (`-m "not slow"`) passes (51 tests, 6.83s)
- **Committed in:** `f988523`, `1e33610`, `5b45e3b`

---

**Total deviations:** 1 (user-approved replan of the plan's acceptance criterion, not an autonomous Rule 1-3 fix)
**Impact on plan:** TOOL-02's proof point is now weaker in absolute terms (70% win floor + zero-loss invariant, vs. the original literal "100/100") but is the first version of this criterion that has actually been measured green, is fast (~31s vs. an unfinished >31min run), and preserves the strongest, most important part of the original intent (a correct engine never loses to a uniformly-random opponent). The stronger goal is deferred, not abandoned.

## Issues Encountered

None beyond the replan itself (documented above under Deviations).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Phase 01 (minimal-uci-engine-evaluator-seam) plan 05 of 6 complete under the replanned TOOL-02 criterion.
- Ready for the final plan (01-06) in this phase.
- Deferred follow-up (100/0-at-depth-4) tracked at `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md` for a future search/pruning phase — not a blocker for phase completion.

## Self-Check: PASSED

- `ance/tools/random_mover_gauntlet.py` exists and contains `GAUNTLET_SEARCH_DEPTH = 2` and `def run_gauntlet(` — confirmed via grep.
- `tests/test_random_mover_gauntlet.py` exists and contains `def test_ance_never_loses_and_wins_majority_vs_random_mover` — confirmed via grep.
- `.planning/todos/pending/2026-07-07-tool-02-depth-4-gauntlet-deferred.md` exists — confirmed via file read.
- Commits `f988523`, `1e33610`, `5b45e3b`, `5e137f2` all present in `git log --oneline`.
- `.venv/bin/python -m pytest tests/test_random_mover_gauntlet.py -q -m slow` exits 0 (1 passed).
- `.venv/bin/python -m pytest -q -m "not slow"` exits 0 (51 passed, 1 deselected).

---
*Phase: 01-minimal-uci-engine-evaluator-seam*
*Completed: 2026-07-07*
