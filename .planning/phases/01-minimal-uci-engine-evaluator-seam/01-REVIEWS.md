---
phase: 1
round: 2
reviewers: [cursor]
reviewed_at: 2026-07-05T18:19:38Z
plans_reviewed: [01-01-PLAN.md, 01-02-PLAN.md, 01-03-PLAN.md, 01-04-PLAN.md, 01-05-PLAN.md, 01-06-PLAN.md]
reviewers_failed: [gemini, codex, antigravity]  # gemini=free-tier 429 quota; codex=model-router/multi_agent_v2 tool-call bug; antigravity=agy -p hang
reviewers_skipped: [claude, coderabbit]  # claude=self; coderabbit=diff-only, no source yet
supersedes_note: 'Round 1 (gemini+codex+cursor) preserved in git at bb7793c; incorporated in d9bd3f4.'
---

# Cross-AI Plan Review — Phase 1 (Round 2, post-revision)

> Single-reviewer round (Cursor). Others unavailable this round — see frontmatter `reviewers_failed`. Round 1's 3-model panel is at git `bb7793c` and was already incorporated in `d9bd3f4`. This file holds the NEW findings for a potential `/gsd-plan-phase 1 --reviews` pass.

## Cursor Review

# Cross-AI Plan Review — Phase 1 (Round 2, Post-Revision)

## 1. Summary

The revised six-plan set is substantially stronger than round 1: the HIGH-consensus items (overlapping-command preemption, post-`HandcraftedEval` re-benchmark, explicit `setoption`/`ponder` handlers, `threading.Timer` movetime, mobility in-check guard, mate-scorer contract note, `isready`-during-search test, gauntlet diagnostics) are present in the right plans with concrete tests, not just prose. Architecture, wave ordering, eval seam, and scope discipline remain excellent. The remaining risk is not “missing sections” but **correctness of the concurrency story under timeout**: `_stop_active_worker()` clears `stop_flag` and spawns a new worker even when `join()` times out, and `movetime` timers are not cancelled at preemption time—both can produce duplicate/stale `bestmove` lines or abort a new search from an old timer. Fix those two edges (or test and document why they cannot happen) and this set is execution-ready; without them, GUI stress paths remain plausible failure modes despite green pytest on the happy path.

## 2. Strengths

- **Round-1 fixes landed in the right places.** Preemption, movetime pin, re-benchmark, mobility guard, `setoption`/`ponder`, mate contract, and gauntlet decoupling are wired into 01-02/01-03/01-04/01-05 with matching tests—not deferred to “executor discretion.”
- **Preemption policy is specified and tested.** `_stop_active_worker()` on `go`/`position`/`ucinewgame`, plus `test_overlapping_go_yields_two_bestmoves_in_order`, `test_position_during_active_search_yields_exactly_one_bestmove_and_stays_responsive`, and `test_isready_returns_promptly_during_active_search` directly cover the round-1 #1 concern.
- **`threading.Timer` movetime is the right pattern.** Single `search_root` per worker, deadline via the same `stop_flag` as external `stop`, timer cancelled on worker completion—avoids a reader-thread polling loop that would violate D-00b.
- **Performance cliff closed in-plan.** `test_bare_go_completes_under_a_second_with_handcrafted_eval` plus permission to tune `DEFAULT_DEPTH` to 2 only in 01-04 addresses the MaterialEval-vs-HandcraftedEval benchmark gap.
- **Mobility in-check guard is correct.** Guarding null-move opponent mobility with `board.is_check()` matches python-chess semantics (null move illegal in check); dedicated FEN test prevents eval crashes on the obvious failure mode.
- **Gauntlet brittleness partially mitigated without weakening the milestone claim.** `GAUNTLET_SEARCH_DEPTH = 4` decoupled from interactive `DEFAULT_DEPTH`, plus `non_win_games` diagnostics, is a sound judgment call while keeping `wins == 100, losses == 0`.
- **Explicit mate-scorer tradeoff documented.** Phase 1 negamax terminals vs D-00a `±(MATE − ply)` in the Protocol is called out in must_haves and negamax docstring—reduces Phase 5 surprise.
- **Wave-1 skeleton honestly scoped.** 01-01 documents missing preemption until 01-03 instead of pretending the trivial worker is production-safe.

## 3. Concerns

- **[HIGH] Preemption can clear `stop_flag` while the prior worker is still alive.** `_stop_active_worker()` always calls `stop_flag.clear()` after `join(timeout=0.5)`, even when the log branch fires for a still-alive worker. A slow-to-poll worker (2048-node interval) may never observe `stop` before `clear()`, resume searching with a cleared flag, and eventually emit a second `bestmove` alongside the new worker. The overlapping-`go` test may pass on fast machines while this race remains latent on loaded CI or deep subtrees.
- **[HIGH] `movetime` timers are not cancelled on preemption—only on normal worker exit.** `movetime_timer` is local to `handle_go` / `_run_search`. If search A is preempted by `go B` before A’s worker finishes, A’s timer can fire after `stop_flag.clear()` and spuriously stop B’s search (or interact with shared `stop_flag` state). No test covers “`go movetime 50` immediately followed by bare `go`” or timer bleed across searches.
- **[MEDIUM] Join timeout does not block spawning the replacement worker.** After a failed join, the plan still starts a new daemon thread. Combined with the two issues above, the “at most one worker alive” invariant is aspirational, not guaranteed. Consider: track `search_generation`, ignore stale `send_bestmove` from superseded workers, hold module-level `movetime_timer` and cancel in `_stop_active_worker`, or refuse to clear `stop_flag` until `worker.is_alive()` is false (with escalation on repeated failure).
- **[MEDIUM] `ucinewgame` during active search is in the preemption policy but untested.** `position`-during-search is covered; `ucinewgame` mid-search (common GUI “New Game”) is not. Same stale-`bestmove`/board-reset race class as position.
- **[MEDIUM] `100/100` gauntlet can still fail on draws at depth 4.** Decoupling depth and diagnostics help, but the assertion remains strict (`draws` fail). A single stalemate vs random at `GAUNTLET_SEARCH_DEPTH=4` blocks the milestone; acceptable if treated as “engine bug,” but executors should expect occasional tuning (depth 5, higher halfmove cap) on slower hardware—not guaranteed first-run green on `-m slow`.
- **[MEDIUM] `position` during search emits `bestmove` for the old position, then applies the new board without `go`.** UCI-legal and tested, but some GUIs assume `position` during think cancels silently until the next `go`. Worth one line in 01-06 manual steps: confirm GUI still accepts the preempted `bestmove` + subsequent `go` on the updated position.
- **[LOW] D-11 whole-line skip remains a deliberate simplification.** Documented implicitly via 01-01/01-02 tests; not a regression from round 1, but still spec-loose if trailing tokens on mixed lines matter later.
- **[LOW] Structural grep seam test still gameable** (acknowledged in-plan). Sufficient for Phase 1.
- **[LOW] Pawn-structure implementation does not pin `int.bit_count()`** over `bin().count()`—minor pure-Python perf nit given mobility dominates cost.

## 4. Suggestions

- **Harden preemption before execution:** In `_stop_active_worker`, cancel any module-level `movetime_timer`; do not call `stop_flag.clear()` unless `not worker.is_alive()` (or bump a `search_id` passed into `_run_search` and gate `send_bestmove` on it). Add tests: (1) `go movetime 2000` + immediate `go depth 1`—second search completes; (2) `go movetime 100` + immediate second `go`—no premature stop of second search.
- **Add `test_ucinewgame_during_active_search`** mirroring the position-during-search test (one `bestmove`, board reset, responsive `isready`).
- **Wrap `_run_search` timer cancel in `finally`** so preemption/stop paths always cancel the timer even if `search_root` raises.
- **If join times out**, log at error severity and either retry join with backoff or set a “poisoned” flag that suppresses stdout from the stale worker—don’t silently proceed as if preemption succeeded.
- **01-05:** On slow-test failure, document expected wall time (~1–3 min stated) and that first action is inspect `non_win_games`, then raise `GAUNTLET_SEARCH_DEPTH` before touching interactive `DEFAULT_DEPTH`.
- **01-06:** Include one GUI run with a clock that sends `wtime`/`btime`/`winc`/`binc` (not movetime-only)—already parsed in 01-03 but not manually gated.
- **01-04 pawn bitboards:** Prefer `(mask & pawns).bit_count()` in the action text to avoid accidental `bin().count()` slowdown—optional, low priority.

## 5. Risk Assessment

**Overall risk: LOW–MEDIUM**

**Justification:** Sequencing, eval seam, protocol hygiene, eval transcription strategy, and test coverage for the common path are among the best pre-execution plan sets you could ask for on a greenfield engine; round-1 feedback was incorporated thoughtfully, not cosmetically. The residual risk concentrates in **threading edge cases the new tests may not stress**: join timeout + `stop_flag.clear()` + uncleared `threading.Timer` can violate the exact invariant the preemption fix was meant to guarantee. Those are localized fixes in `ance/uci/loop.py` (likely <30 lines + 2 tests), not architectural rework. Gauntlet strictness and GUI timing remain secondary operational risks.

**Ready to execute?** **Yes, with the preemption/timer hardening called out above treated as part of Plan 01-03 Task 3 (or a tiny 01-03 follow-up task before GUI checkpoint)—not as optional polish.** If executors implement `_stop_active_worker` literally as written without addressing timer cancel and conditional `clear()`, treat concurrency as **not yet closed** despite passing the overlapping-`go` happy-path test.

---

## Round-2 Summary

**Reviewer availability was degraded this round** — only Cursor completed. Gemini hit its
free-tier quota (429, exhausted from round 1), Codex failed on an internal `model-router` /
`multi_agent_v2` tool-call bug (environment, not prompt), and Antigravity was skipped (its
`agy -p` hung past timeout in round 1 with no persisted transcript). Claude is skipped as self
and CodeRabbit as a diff-only reviewer (no source code yet). So this is a **single-reviewer
round**, not a consensus panel — weight it accordingly. Round 1's 3-model review is preserved
in git at commit `bb7793c` and was incorporated in `d9bd3f4`.

Cursor's verdict: the round-1 fixes landed correctly in the right plans with real tests, and the
plan set is **execution-ready — with two NEW HIGH correctness gaps in the concurrency fix itself
that must be hardened as part of Plan 01-03 Task 3, not left to executor discretion.**

### New Actionable Findings (round 2)
1. **[HIGH] Preemption clears `stop_flag` while a timed-out worker may still be alive.**
   `_stop_active_worker()` calls `stop_flag.clear()` after `join(timeout=0.5)` unconditionally.
   A slow-to-poll worker (2048-node interval) may never observe `stop` before the flag is cleared,
   resume with a cleared flag, and emit a second `bestmove` alongside the new worker. The
   overlapping-`go` happy-path test can pass while this race stays latent on loaded CI / deep subtrees.
   **Fix:** don't `clear()` unless `not worker.is_alive()` — or gate `send_bestmove` on a
   `search_id`/`search_generation` so a superseded worker's output is dropped.
2. **[HIGH] `movetime` timers are not cancelled on preemption.** `movetime_timer` is local to the
   search; if search A is preempted by `go B`, A's timer can fire later and spuriously stop B
   (or corrupt shared `stop_flag` state). No test covers `go movetime 50` immediately followed by
   a bare `go`. **Fix:** hold the timer at module level and cancel it in `_stop_active_worker`;
   wrap the timer cancel in a `finally` so it always fires even if `search_root` raises.
3. **[MEDIUM] `ucinewgame`-during-search is in the preemption policy but untested** (only
   `position`-during-search is). Add `test_ucinewgame_during_active_search` (one `bestmove`,
   board reset, responsive `isready`).
4. **[MEDIUM] `100/100` gauntlet remains strict at `GAUNTLET_SEARCH_DEPTH=4`** — a single
   stalemate vs random still fails the milestone. Acceptable if treated as an engine bug, but
   executors should expect possible tuning (depth 5 / higher halfmove cap) on slower hardware
   rather than guaranteed first-run green. Document: on `-m slow` failure, inspect `non_win_games`
   first, then raise `GAUNTLET_SEARCH_DEPTH` before touching interactive `DEFAULT_DEPTH`.
5. **[MEDIUM] GUI expectation for `position`-during-search** — the engine emits a `bestmove` for
   the old position then applies the new board. UCI-legal, but add a line to 01-06 manual steps
   to confirm the GUI accepts the preempted `bestmove` + subsequent `go`.

### Carried-forward (LOW, unchanged from round 1 — acknowledged, not regressions)
- D-11 whole-line skip is a deliberate Phase-1 simplification.
- Structural grep seam test is gameable but Phase-1-sufficient.
- Pawn-structure perf: prefer `(mask & pawns).bit_count()` over `bin().count()` (minor).

### Risk & Readiness
Cursor rates overall risk **LOW–MEDIUM**. Ready to execute **yes**, provided findings 1–2
(timer cancel + conditional `clear()` / generation-gated `send_bestmove`) are folded into Plan
01-03 Task 3 as required work — "~<30 lines + 2 tests, not architectural rework." If executed
literally as currently written, treat concurrency as **not yet closed** despite the green
overlapping-`go` happy-path test.
