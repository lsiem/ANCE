---
phase: 01-minimal-uci-engine-evaluator-seam
plan: 03
subsystem: search
tags: [uci, negamax, evaluator-seam, threading, pytest, material-eval, preemption]

# Dependency graph
requires:
  - phase: 01-minimal-uci-engine-evaluator-seam
    provides: "Position adapter (try_set_startpos/try_set_fen/try_push_uci_moves/has_no_legal_moves/is_check), real position/ucinewgame/setoption/ponder wiring, stderr-only debug channel (Plan 01-02)"
provides:
  - "Evaluator Protocol seam (ance/eval/base.py) -- the one contract a future NNUE evaluator must satisfy; MATE=30000 shared sentinel"
  - "MaterialEval (Simplified Evaluation Function piece values, D-05) and NaiveEval bootstrap evaluators proving the seam is real, not cosmetic"
  - "Fixed-depth negamax (ance/search/negamax.py) with sampled node-count + per-root-move stop_flag polling, seeded tie-break RNG, and a structural proof it never imports a concrete evaluator class"
  - "Real go/stop/quit wiring: GoCommand parses every documented go sub-parameter (depth/movetime/infinite/wtime/btime/winc/binc/nodes); handle_go spawns a search worker gated by a monotonic search_generation counter"
  - "Preemption policy (_stop_active_worker): stop -> join(timeout) -> clear -> cancel movetime_timer, shared by handle_go/handle_position/handle_ucinewgame/handle_quit"
  - "search_generation gating: a superseded go's worker result is unconditionally dropped (logged, never sent to stdout) independent of join(timeout) success -- closes the round-2 HIGH cross-AI-review finding (T-01-13)"
  - "movetime_timer held at module scope and cancelled both by _stop_active_worker() and in the search-runner's own finally block, so a stale movetime deadline can never bleed into a later, unrelated search (T-01-16)"
  - "ucinewgame reseeds the tie-break RNG from ANCE_SEED (D-17)"
affects: [01-04, 01-05, 01-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Evaluator Protocol (typing.Protocol) is the sole coupling point between ance/search/negamax.py and any evaluator -- proven by a structural test reading negamax.py's source text and asserting no concrete evaluator class name appears in it"
    - "search_generation is a monotonic counter bumped before preemption, not join() timing, as the single correctness mechanism gating send_bestmove -- deliberately rejects 'block until not worker.is_alive()' as unbounded/deadlock-prone"
    - "position/ucinewgame preemption does NOT bump search_generation (their preempted worker's flush is legitimate), while go DOES bump it (their preempted worker's result is stale) -- two different preemption semantics sharing one _stop_active_worker() helper"
    - "threading.Timer for movetime is held at module scope specifically so a later, unrelated preemption can reach and cancel it; also cancelled in a finally block on every worker exit path"
    - "sampled node-count polling (NODE_POLL_INTERVAL=2048) plus a per-root-move stop_flag check bounds worst-case stop/quit latency without checking every negamax call"

key-files:
  created:
    - ance/eval/__init__.py
    - ance/eval/base.py
    - ance/eval/material.py
    - ance/search/__init__.py
    - ance/search/negamax.py
    - tests/test_eval_seam.py
    - tests/test_go_bestmove.py
  modified:
    - ance/uci/parser.py
    - ance/uci/loop.py

key-decisions:
  - "DEFAULT_DEPTH=3 benchmarked (Task 3) to keep a bare go under 1.0s wall-clock with MaterialEval in pure Python -- resolves 01-RESEARCH.md Open Question #1."
  - "movetime is a single search_root call per worker with the deadline fired by threading.Timer through the exact same stop_flag path as an external stop -- never a manual polling loop wrapped around search_root."
  - "Search (not the Evaluator) remains the sole mate scorer in Phase 1: negamax returns a flat -(MATE)/0 at terminal nodes with no ply-adjustment; documented as a Phase 1 tradeoff, not a gap, since no Phase 1 evaluator ever exercises the Evaluator Protocol's ±(MATE-ply) contract."
  - "test_overlapping_go_yields_two_bestmoves_in_order's plan-authored title/prose describes a 'two bestmoves' expectation that predates (or was left stale relative to) the plan's own round-2 search_generation hardening. The plan's must_haves.truths, success_criteria, and threat-model T-01-13 entry all consistently specify 'never emits a duplicate/stale bestmove' and 'at most one bestmove... per go, guaranteed by search_generation gating.' I implemented and verified the hardened, internally-consistent contract: exactly ONE bestmove (the second go's) appears, with the first go's superseded result unconditionally dropped -- confirmed both by the subprocess test and by direct manual verification showing the dropped-stale-bestmove debug log line. See Deviations."

requirements-completed: [UCI-06, UCI-07, UCI-09, UCI-10, EVAL-01]

coverage:
  - id: D1
    description: "Evaluator Protocol seam (MATE constant, Evaluator Protocol) plus MaterialEval/NaiveEval bootstrap evaluators, side-to-move relative"
    requirement: "EVAL-01"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_material_eval_symmetric_position_scores_zero"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_material_eval_reflects_material_difference_stm_relative"
        status: pass
    human_judgment: false
  - id: D2
    description: "Fixed-depth negamax with seeded tie-break RNG and a structural proof that negamax.py never imports a concrete evaluator class"
    requirement: "EVAL-01"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_search_root_finds_mate_in_one"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_search_root_zero_legal_moves_returns_none"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_search_root_tie_break_uses_seeded_rng"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_negamax_module_never_imports_a_concrete_evaluator"
        status: pass
    human_judgment: false
  - id: D3
    description: "go depth/movetime/bare-default/infinite/clock-params all yield exactly one legal bestmove promptly, including bestmove (none) on zero legal moves; stop/quit never hang"
    requirement: "UCI-06"
    verification:
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_go_depth_honored"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_bare_go_uses_default_depth_and_completes_under_a_second"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_go_movetime_aborts_promptly"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_go_clock_params_parsed_without_crash"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_stop_is_prompt_during_go_infinite"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_quit_never_deadlocks_during_go_infinite"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_zero_legal_move_position_returns_bestmove_none"
        status: pass
    human_judgment: false
  - id: D4
    description: "Overlapping go/position/ucinewgame commands never spawn concurrent search workers and never emit a duplicate/stale bestmove; search_generation gates output independent of join(timeout) success; movetime timers cannot bleed into a later, unrelated search"
    requirement: "UCI-07"
    verification:
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_overlapping_go_yields_two_bestmoves_in_order"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_position_during_active_search_yields_exactly_one_bestmove_and_stays_responsive"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_ucinewgame_during_active_search"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_isready_returns_promptly_during_active_search"
        status: pass
      - kind: unit
        ref: "tests/test_go_bestmove.py#test_stale_generation_worker_never_emits_bestmove_after_being_superseded"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_go_movetime_timer_cancelled_on_preemption_does_not_stop_next_search"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_go_movetime_short_timer_cancelled_before_next_search_completes"
        status: pass
      - kind: integration
        ref: "tests/test_go_bestmove.py#test_ucinewgame_reseeds_tie_break_rng"
        status: pass
      - kind: manual_procedural
        ref: "piped go depth 5\\ngo depth 1\\n -> exactly one bestmove, isready still responsive; stderr debug log shows 'dropped stale bestmove from generation 1 (current generation 2)'"
        status: pass
    human_judgment: false

# Metrics
duration: ~35min (resumed session only; Tasks 1-2 were completed in a prior session before an unrelated session-limit interruption mid-Task-3)
completed: 2026-07-07
status: complete
---

# Phase 1 Plan 3: Evaluator Seam, Fixed-Depth Negamax, and Real go/stop/quit Wiring Summary

**Formal `Evaluator` Protocol seam with `MaterialEval`/`NaiveEval` bootstrap evaluators, a fixed-depth negamax proven to depend only on that Protocol, and real `go`/`stop`/`quit` handling gated by a monotonic `search_generation` counter so overlapping commands never race a stale worker's `bestmove` onto stdout.**

## Performance

- **Duration:** ~35 min for this resumed session (Task 3 completion + SUMMARY). Tasks 1-2 (Evaluator seam, negamax) were completed and committed in a prior session (2026-07-05) before the executing agent was terminated by a session limit partway through Task 3's implementation.
- **Started (this session):** 2026-07-07T10:44:00Z (approx)
- **Completed:** 2026-07-07T10:50:56Z
- **Tasks:** 3 (all complete: 1 and 2 pre-existing from prior session, 3 completed this session)
- **Files modified this session:** 3 (2 modified: `ance/uci/loop.py`, `ance/uci/parser.py`; 1 created: `tests/test_go_bestmove.py`)

## Session Interruption and Resume

A prior executor agent was terminated mid-Task-3 by a session limit, leaving `ance/uci/loop.py` (+184 lines) and `ance/uci/parser.py` (+67 lines) **uncommitted and unverified** in the working tree, and `tests/test_go_bestmove.py` **never created**. This session:

1. Reviewed the uncommitted partial rewrite line-by-line against the plan's Task 3 `<action>` spec (search wiring, `search_generation` gating, `movetime_timer` cancellation, preemption policy for `go`/`position`/`ucinewgame`/`quit`).
2. Found the partial implementation **already correct and complete** against the spec -- no corrections were needed. `GoCommand` had all documented sub-parameters (`depth`/`movetime`/`infinite`/`wtime`/`btime`/`winc`/`binc`/`nodes`); `handle_go` bumped `search_generation` before `_stop_active_worker()`; `movetime_timer` was held at module scope and cancelled both in `_stop_active_worker()` and the search-runner's own `finally` block; `handle_position`/`handle_ucinewgame` called `_stop_active_worker()` without touching `search_generation`; `handle_quit` reused the same helper at `timeout=2.0`.
3. Wrote `tests/test_go_bestmove.py` from scratch (15 tests exactly as specified in the plan's `<behavior>` block), ran the full suite, and iterated until green.
4. Committed a `test(01-03)` commit for the test file, then a `feat(01-03)` commit for the (already-authored, now-verified) `loop.py`/`parser.py` changes. Strict RED-before-GREEN ordering was compromised by the interruption (implementation existed in the working tree before its test was ever run) -- this is acknowledged per the task instructions rather than hidden. Both commits are atomic and independently revertable; the test commit failing against `main` (pre-Task-3) would have shown a `NameError`/`ImportError` for `GoCommand`/`_run_search`/etc., which is RED-equivalent even though it wasn't executed as a literal git-history RED step in this exact sequence.

## Accomplishments

- `ance/eval/base.py` defines the `Evaluator` Protocol (the swap seam, D-00a/EVAL-01) and `MATE = 30000`; `ance/eval/material.py` defines `MaterialEval` (Simplified Evaluation Function piece values, D-05) and `NaiveEval` (always `0`, proves the seam structurally).
- `ance/search/negamax.py` implements fixed-depth `negamax`/`search_root` (D-01) with sampled node-count polling (`NODE_POLL_INTERVAL=2048`) plus a per-root-move `stop_flag` check (D-13), a seeded tie-break RNG (D-04), and a structural test proving it imports zero concrete evaluator classes.
- `ance/uci/parser.py::parse_go()`/`GoCommand` parses every documented `go` sub-parameter (including `wtime`/`btime`/`winc`/`binc`/`nodes`, unimplemented-but-tolerated this phase) so a real GUI's clock params never crash the parser (D-11).
- `ance/uci/loop.py` replaces the Walking Skeleton's "first legal move" worker with a real search worker gated by a monotonic `search_generation` counter: `handle_go` bumps it before preempting any prior worker, and the search-runner only calls `send_bestmove` if its captured generation still matches -- a superseded worker's result is dropped and logged, never raced onto stdout (round-2 HIGH cross-AI-review hardening, closes threat T-01-13).
- `movetime_timer` is held at module scope so a later, unrelated `go` can cancel a leftover deadline from a preempted `movetime` search; the search-runner also cancels its own timer in a `finally` block on every exit path (closes threat T-01-16).
- `handle_position`/`handle_ucinewgame` share the same `_stop_active_worker()` preemption helper as `handle_go`, but do not bump `search_generation` -- their preempted worker's best-so-far result is legitimately flushed, not dropped, before the position it was searching becomes outdated.
- `handle_ucinewgame` reseeds the tie-break RNG from `ANCE_SEED` (D-17); `handle_quit` reuses `_stop_active_worker(timeout=2.0)` in place of an ad hoc join, so `quit` never deadlocks on a running search (UCI-10).
- `tests/test_go_bestmove.py`: 15 tests covering every `go` variant's timing, clock-param tolerance, `stop`/`quit` promptness, `bestmove (none)` on zero legal moves, `ucinewgame`'s deterministic RNG reseed, all overlapping-command preemption scenarios (`go`/`go`, `position`-during-search, `ucinewgame`-during-search, `isready`-during-search), a unit-level proof of the `search_generation` gate itself, and both movetime-timer-cancellation-on-preemption directions.

## Task Commits

1. **Task 1: Evaluator Protocol seam and bootstrap evaluators** (prior session, 2026-07-05)
   - `d98ef48` (test, RED) — `test(01-03): add failing tests for MaterialEval seam symmetry`
   - `2f07823` (feat, GREEN) — `feat(01-03): add Evaluator Protocol seam and bootstrap evaluators`
2. **Task 2: Fixed-depth negamax with tie-break RNG and structural swap-seam proof** (prior session, 2026-07-05)
   - `ee2d7a8` (test, RED) — `test(01-03): add failing tests for search_root/negamax and swap-seam proof`
   - `242dfd0` (feat, GREEN) — `feat(01-03): add fixed-depth negamax with seeded tie-break RNG`
3. **Task 3: Wire go/stop/quit through real search with clock-param tolerance** (this session, resumed after session-limit interruption)
   - `c8c0676` (test) — `test(01-03): add tests for go/stop/quit wired through real search`
   - `8e4ae79` (feat) — `feat(01-03): wire go/stop/quit through real search with clock-param tolerance`

**Plan metadata:** committed separately per the final-commit step below.

## Files Created/Modified

- `ance/eval/__init__.py`, `ance/eval/base.py` - `Evaluator` Protocol, `MATE` constant
- `ance/eval/material.py` - `MaterialEval`, `NaiveEval`, `PIECE_VALUES`
- `ance/search/__init__.py`, `ance/search/negamax.py` - `negamax()`, `search_root()`, `DEFAULT_DEPTH`, `NODE_POLL_INTERVAL`, `SearchAborted`
- `ance/uci/parser.py` - `GoCommand` dataclass, `parse_go()`
- `ance/uci/loop.py` - `_stop_active_worker()`, `_run_search()`, real `handle_go`/`handle_stop`, `search_generation`/`movetime_timer` module state, `handle_position`/`handle_ucinewgame`/`handle_quit` updated to preempt via the shared helper
- `tests/test_eval_seam.py` - Task 1/2 tests (prior session)
- `tests/test_go_bestmove.py` - Task 3's 15 tests (this session)

## Decisions Made

- `DEFAULT_DEPTH = 3` confirmed via this session's test suite to keep a bare `go` well under 1.0s (observed ~0.2s locally) with `MaterialEval` in pure Python -- resolves 01-RESEARCH.md Open Question #1 as documented in the plan.
- `test_overlapping_go_yields_two_bestmoves_in_order`'s literal plan-authored expectation ("exactly two bestmove lines") was resolved in favor of the plan's own internally-consistent, more-authoritative round-2 hardening contract (`must_haves.truths`, `success_criteria`, and threat `T-01-13` all state a superseded worker's result is dropped, not raced onto stdout). Implemented and verified: exactly ONE bestmove (the second `go`'s) appears; the first `go`'s result is silently dropped and logged. See Deviations below for full reasoning and manual verification evidence.
- Kept the test file scoped to `tests/test_go_bestmove.py` only (no `tests/conftest.py` changes) -- the one non-standard fixture need (an `ANCE_SEED`-injecting subprocess for the `ucinewgame` RNG-reseed test) was implemented as a local `seeded_engine` fixture inside the test file itself, mirroring `tests/conftest.py::engine` rather than modifying the shared fixture (plan's `files_modified` for Task 3 lists only `tests/test_go_bestmove.py`, not `tests/conftest.py`).

## Deviations from Plan

### Auto-fixed / Resolved Issues

**1. [Rule 1 - Spec inconsistency, resolved in favor of the more consistent contract] `test_overlapping_go_yields_two_bestmoves_in_order`'s literal description contradicts the plan's own round-2 hardening**
- **Found during:** Task 3 (writing `tests/test_go_bestmove.py`)
- **Issue:** The plan's `<behavior>` prose for this test says "exactly two `bestmove` lines appear, in that order." Tracing the plan's own `handle_go` design (bump `search_generation` *before* `_stop_active_worker()`; search-runner only emits if `my_generation == search_generation`) shows the first `go`'s worker will *always* see a stale generation by the time it finishes, in any back-to-back-no-delay overlap -- its result is unconditionally dropped, not emitted. This is also exactly what the plan's `must_haves.truths` ("never emits a duplicate/stale bestmove"), `success_criteria` ("at most one bestmove is ever emitted per go... guaranteed by search_generation gating"), and threat register entry T-01-13 ("closing the round-2 HIGH finding that join-timeout-then-clear alone could still let a stale worker emit a stray bestmove") all independently and consistently specify. The "two bestmoves" framing reads as a leftover from the round-1-only preemption policy (before `search_generation` gating was added) that was not updated in this one test's prose when round-2 hardening was layered on.
- **Fix:** Implemented the test to assert the hardened, consistently-documented behavior: exactly ONE `bestmove` line appears (the second `go`'s), no further/stale `bestmove` follows, and the engine stays responsive (`isready` -> `readyok`) afterward. Kept the plan's exact test function name for traceability to the behavior list.
- **Verification:** `tests/test_go_bestmove.py::test_overlapping_go_yields_two_bestmoves_in_order` passes; additionally confirmed manually via a piped subprocess with `debug on` -- stderr shows `worker started (generation 1, depth 3)` followed by `dropped stale bestmove from generation 1 (current generation 2)`, then `worker started (generation 2, depth 1)` and `worker (generation 2) sending bestmove`, with exactly one `bestmove` line on stdout.
- **Files modified:** `tests/test_go_bestmove.py`
- **Committed in:** `c8c0676`

---

**Total deviations:** 1 resolved (a documentation/spec inconsistency within the plan itself, resolved in favor of the plan's own more heavily cross-referenced and internally consistent design). No production code, architecture, or scope changes.
**Impact on plan:** None on delivered functionality -- the implementation matches every other part of the plan's Task 3 spec exactly (acceptance criteria, threat mitigations, `must_haves`). Only this one test's literal wording needed reconciling against the plan's own contradictory internal statements.

## Issues Encountered

- **Session-limit interruption mid-Task-3** (see "Session Interruption and Resume" above): the prior executor was terminated after authoring `ance/uci/loop.py`/`ance/uci/parser.py`'s Task 3 changes but before writing `tests/test_go_bestmove.py`, running any tests, or committing. This session verified the uncommitted code was correct as-is, wrote the missing test file, ran the full suite to green, and committed both. No functional issues resulted from the interruption -- only the git-history TDD ordering (test commit before feat commit) does not literally reflect "test failed, then implementation was written," since the implementation already existed. This is noted for transparency per the task's explicit instructions, not hidden.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- The Evaluator seam, negamax substrate, and full `go`/`stop`/`quit` wiring are complete and hardened against every cross-AI review finding raised in both review rounds (T-01-06, T-01-07, T-01-08, T-01-13, T-01-16 all mitigated and tested).
- Plan 01-04 can now swap in `HandcraftedEval` (PST/positional terms, D-06) as the default evaluator in `ance/uci/loop.py` with zero changes to `ance/search/negamax.py` -- the seam is proven real, not cosmetic, by `test_negamax_module_never_imports_a_concrete_evaluator`.
- Plan 01-04 Task 3 should re-run the `DEFAULT_DEPTH` sub-second benchmark once the costlier `HandcraftedEval` replaces `MaterialEval` as the default, per this plan's inline documentation in `ance/search/negamax.py`.
- `go infinite` currently has no idle `info string` output while holding its result (D-16 as specified; `info` output is explicitly out of Phase 1 scope per 01-CONTEXT.md's Phase Boundary) -- this is a documented, deliberate deferral, not a gap.

## Known Stubs

None. `handle_go`'s worker now performs a real fixed-depth search through the Evaluator seam; no placeholder/mock data paths remain in the files this plan touched.

## Threat Flags

None. All new surface introduced by this plan (`parse_go`'s untrusted stdin tokens, the `stop_flag`/`rng`/`search_generation`/`movetime_timer` shared cross-thread state) is already covered by the plan's own threat register (T-01-06, T-01-07, T-01-08, T-01-13, T-01-16).

---
*Phase: 01-minimal-uci-engine-evaluator-seam*
*Completed: 2026-07-07*

## Self-Check: PASSED

All created/modified files verified present on disk: `ance/eval/__init__.py`, `ance/eval/base.py`, `ance/eval/material.py`, `ance/search/__init__.py`, `ance/search/negamax.py`, `ance/uci/parser.py`, `ance/uci/loop.py`, `tests/test_eval_seam.py`, `tests/test_go_bestmove.py`. All commit hashes verified present in `git log`: `d98ef48`, `2f07823`, `ee2d7a8`, `242dfd0`, `c8c0676`, `8e4ae79`. Full suite: `.venv/bin/python -m pytest -q` -> 36 passed (21 pre-existing + 15 new), stable across repeated runs. Plan-level verification command `tests/test_eval_seam.py tests/test_go_bestmove.py -q` -> 36 passed in ~3.5-4.4s. Manual pipe verifications match the plan's `<verification>` block: `position fen <Fool's Mate>\ngo\n` prints exactly `bestmove (none)`; `go infinite` + `stop` yields a prompt `bestmove`; two back-to-back `go`s yield exactly one `bestmove` with no crash; `go movetime 100` immediately followed by `go depth 3` yields a second `bestmove` at ~0.20s (not suspiciously close to the 100ms mark), consistent across 5 repeated runs.
