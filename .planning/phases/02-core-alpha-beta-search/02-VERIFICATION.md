---
status: gaps_found
score: "19/25 must-have truths verified"
phase: "02-core-alpha-beta-search"
verified: "2026-07-10"
requirements:
  passed: [SRCH-02, SRCH-03, SRCH-04]
  gaps: [SRCH-07, UCI-11]
---

# Phase 2 Verification

## Goal

Phase 2 is substantially implemented: the engine uses iterative-deepening
alpha-beta negamax with quiescence and correct terminal scoring. It is not fully
verified. Actual-code review and focused probes confirm six gaps spanning
repetition history, depth-match result accounting, deadline enforcement, worker
generation isolation, node accounting, and undersized/over-budget strength runs.

## Requirement Traceability

| Requirement | Result | Evidence |
|---|---|---|
| SRCH-02 | PASS | `negamax()` carries alpha/beta, returns the cutoff score (true fail-soft behavior), applies negamax windows recursively, and scores mate as `-(MATE - ply)` and stalemate as 0. Alpha-beta, mate, stalemate, and deterministic-root tests pass. |
| SRCH-03 | PASS | `search_root()` iterates depths `1..N`, updates `last_completed` only after a completed iteration, preserves it on `SearchAborted`, and searches the previous iteration's best move first. Abort-retention tests pass. |
| SRCH-04 | PASS | Depth-zero search enters bounded quiescence; quiet nodes use clamped stand-pat, captures/queen promotions are MVV-LVA sorted, delta pruning is active, and in-check nodes search all evasions without stand-pat. Tactical and quiescence tests pass. |
| SRCH-07 | GAP | Path repetition, 50-move, and insufficient-material checks exist, but `_build_game_history_keys()` calls `board.copy(stack=False)` and therefore cannot traverse prior positions. A direct probe showed a five-ply board retaining 1 history key instead of 5; a return to an earlier position scored 123 with the actual builder versus draw score 0 with complete history. |
| UCI-11 | GAP | Formatting and mate conversion pass, but info callbacks are not generation-gated and iterative node totals are overcounted. A stale worker can therefore emit lines into a newer search, and reported `nodes`/`nps` cease to represent actual cumulative work. |

All five Phase 2 requirement IDs are accounted for: three pass; SRCH-07 and
UCI-11 have confirmed implementation gaps.

## Must-Have Results

### 02-01 — Fail-soft alpha-beta

- Truths: **4/4 pass** — alpha-beta negamax, ply-adjusted mate, stalemate zero,
  and deterministic root selection are present in actual code.
- Artifacts: **3/3 pass** — `ance/search/types.py`,
  `ance/search/negamax.py`, and `tests/test_alpha_beta.py` exist and contain the
  planned types/search/tests.
- Key link: **pass** — search imports the evaluator protocol from
  `ance.eval.base`, with no concrete evaluator import.

### 02-02 — Quiescence

- Truths: **4/4 pass** — captures/queen promotions only, stand-pat and delta
  pruning, qsearch-only MVV-LVA, and all-evasion in-check handling are present.
- Artifacts: **2/2 pass** — quiescence implementation and regression tests exist.
- Key link: **pass** — `negamax(depth == 0)` calls `quiescence_search()`.

### 02-03 — Iterative deepening and draws

- Truths: **3/4 pass** — iterative deepening retention, 50-move/insufficient
  material handling, and prior-best root ordering pass. Game-history repetition
  does not work because historical keys are discarded; path repetition does work.
- Artifacts: **2/2 pass** — ID implementation and draw tests exist.
- Key link: **pass** — completed iterations update `last_completed`; stop/deadline
  aborts return it.

### 02-04 — UCI info and go modes

- Truths: **3/6 pass** — `Position.copy()` is passed to the worker,
  `go infinite` deepens until stop/MAX_PLY, and partial iterations do not invoke
  the callback.
- **Gap:** deadline checks occur only before iterations and root moves; negamax
  and quiescence node polling ignores `ctx.deadline`, so a root subtree can run
  beyond the nominal 2-second bare-`go` budget.
- **Gap:** after a timed-out join, `_stop_active_worker()` clears the one shared
  stop event while the stale worker is still alive. The stale worker can resume.
- **Gap:** only `bestmove` is generation-gated. `_emit_info()` is shared and
  unconditional, so stale completed-depth lines can contaminate a newer search;
  iterative node arithmetic also overcounts telemetry.
- Artifacts: **3/3 pass** — formatter, loop dispatch, and subprocess tests exist.
- Key link: **structurally present but behaviorally incomplete** —
  `_run_search()` passes `_emit_info` to `search_root()`, but the callback carries
  no generation identity or gate.

### 02-05 — Strength validation

- Truths: **1/3 pass** — the five tactical tests pass.
- **Gap:** `play_depth_match_game()` normalizes a deeper-black win from `0-1`
  to `1-0`, then `run_depth_match()` applies color-dependent interpretation a
  second time. A probe feeding two normalized deeper-side wins tallied 1 win and
  1 loss. The `seed` parameter is never read, so no opening/game variation exists.
- **Gap:** the depth-vs-depth must-have specifies 30–50 games; the implemented
  test and UAT evidence cover 5 games.
- **Gap:** the depth-4 random-mover must-have specifies completion within a
  10-minute budget; the recorded 3-game UAT run took 26:06. Its `losses == 0`
  invariant passed, but the budget/sample intent did not.
- Artifacts: **3/3 pass** — tactical tests, depth-match harness, and slow test exist.
- Key link: **pass** — `GAUNTLET_SEARCH_DEPTH = 4` is supplied to `search_root()`.

### 02-06 — Mate-score gap closure

- Truths: **4/4 pass** — positive and negative mate scores use signed full moves,
  evaluator output is clamped below the mate window, and the fast suite is green.
- Artifacts: **4/4 pass** — formatter conversion, shared threshold, clamped eval
  seam, and regression tests exist.
- Key links: **2/2 pass** — formatter imports `MATE_THRESHOLD`; both evaluator
  call sites route through `_clamped_eval()`.

Artifacts and key links: **17/17 artifacts** and all **7 declared links** are
structurally present; the 02-04 callback link is behaviorally unsafe because it
lacks generation isolation.

## Automated Test Evidence

- `.venv/bin/python -m pytest -m "not slow" -q`
  — **85 passed, 2 deselected in 26.30s**.
- Focused regression set:
  `pytest tests/test_iterative_deepening.py tests/test_uci_info.py
  tests/test_depth_vs_depth.py -m "not slow" -q`
  — **18 passed, 1 deselected in 5.25s**. Existing tests do not cover the
  confirmed edge cases below.
- Direct history-key probe on a board with five plies:
  `expected_unique_history_keys 5`, `actual_history_keys 1`.
- Functional repetition probe after `...Nf6-g8` returned
  `score_with_actual_builder 123` versus
  `score_with_complete_history 0`.
- Depth-match normalization probe: two normalized deeper-side wins were tallied
  as `1W/1L`, score rate 0.5; AST probe found zero uses of `seed` in the game body.
- Past-deadline internal poll probe: `_poll_stop()` returned `NOT_ABORTED`.
- Stale-worker probe after a failed 0.01-second join:
  `stale_worker_alive_after_join True`,
  `shared_stop_flag_after_failed_join False`.
- Deterministic node-accounting probe with three 10-node iterations:
  iteration seeds were `[0, 10, 30]` and final reported nodes were 70, not 30.

Slow tests were not repeated because current UAT records runs of 26:06 and
2:25:23. That evidence is reused for runtime/sample facts, but its depth-match
conclusion is discounted because the harness defect directly undermines it.

## UAT Evidence

`02-UAT.md` is complete with **8/8 passed**:

- live info/PV and `bestmove` behavior passed;
- `go infinite` deepened and stopped in 0.02s with the retained best move;
- tactical, mate wire-format, and draw test groups passed;
- depth-4 random-mover test passed in 26:06 over 3 games with zero losses;
- depth-vs-depth test passed in 2:25:23 over 5 games;
- the user confirmed a full En Croissant game with visible search information.

This supports tactical and GUI-visible behavior, but the depth-vs-depth pass is
not trustworthy because black-side outcomes can be inverted and all games begin
from the same deterministic start position. The evidence also does not cure the
source-level repetition, deadline, worker-isolation, telemetry, sample-size, or
time-budget gaps.

## Gaps

### 1. Prior game history is discarded

- **Severity:** BLOCKER
- **Linkage:** SRCH-07; D-06/D-07; Roadmap success criterion 4.
- **Evidence:** `_build_game_history_keys()` uses `board.copy(stack=False)`, so
  `temp.move_stack` is empty. Probes retained 1 of 5 expected unique keys and
  changed an actual repeated-position score from 0 to 123.
- **Affected artifacts:** `ance/search/negamax.py`,
  `tests/test_iterative_deepening.py`.
- **Missing work:** preserve/reconstruct the full move stack, count relevant
  occurrences correctly, and add a root-to-interior repetition integration test
  using real board history rather than a manually injected key set.

### 2. Depth-match outcomes are mis-normalized and seed is inert

- **Severity:** BLOCKER
- **Linkage:** D-14; Roadmap success criterion 5; 02-05 strength truth.
- **Evidence:** deeper-black outcomes are color-normalized in
  `play_depth_match_game()` and interpreted by color again in
  `run_depth_match()`. Two normalized wins produced `1W/1L`. The `seed`
  parameter has zero body uses.
- **Affected artifacts:** `ance/tools/depth_vs_depth_match.py`,
  `tests/test_depth_vs_depth.py`, recorded UAT test 7 evidence.
- **Missing work:** choose one result convention and test white/black win, loss,
  and draw cases; use `seed` for deterministic opening variation or remove it and
  introduce a reproducible opening set; rerun the strength proof.

### 3. Search does not poll deadlines inside the tree

- **Severity:** HIGH
- **Linkage:** D-09; UCI-07 time-budget behavior; 02-04 bare-`go` truth.
- **Evidence:** `_poll_stop()` checks only `stop_flag`; `ctx.deadline` is ignored.
  A past-deadline context did not abort. Deadline checks occur only between ID
  iterations and root moves.
- **Affected artifacts:** `ance/search/negamax.py`, `ance/uci/loop.py`,
  `tests/test_uci_info.py`, `tests/test_go_bestmove.py`.
- **Missing work:** poll monotonic deadline together with stop at bounded node
  intervals in negamax and quiescence; add a slow-subtree deadline regression
  test proving bounded overrun and last-completed-depth retention.

### 4. Stale workers can resume and emit ungated info

- **Severity:** BLOCKER
- **Linkage:** D-00b; UCI-09/UCI-12 responsiveness; UCI-11 stream integrity.
- **Evidence:** after a join timeout `_stop_active_worker()` unconditionally
  clears the shared event. Probe result: stale worker alive, event cleared.
  `bestmove` checks `search_generation`, but `_emit_info()` does not.
- **Affected artifacts:** `ance/uci/loop.py`, `tests/test_uci_info.py`,
  `tests/test_go_bestmove.py`.
- **Missing work:** give each search an immutable/per-generation cancellation
  token, never clear a token still owned by a live worker, generation-gate info
  and bestmove output, and add overlapping-`go`/forced-stale-worker tests.

### 5. Iterative node totals are double-counted

- **Severity:** MEDIUM
- **Linkage:** UCI-11; D-11 (`nodes`/`nps` info correctness).
- **Evidence:** `_search_at_depth()` seeds `counter` with `nodes_at_start` and
  returns that cumulative value; `search_root()` then adds it to
  `total_nodes`. Three synthetic 10-node iterations reported 70 rather than 30.
- **Affected artifacts:** `ance/search/negamax.py`, `ance/uci/loop.py`,
  `tests/test_uci_info.py`.
- **Missing work:** use per-iteration counters and add deltas, or treat returned
  counters as cumulative and assign rather than add; test exact cumulative
  callback/final totals and derive NPS from corrected counts.

### 6. Strength runs miss planned sample and time bounds

- **Severity:** HIGH
- **Linkage:** D-01/D-14/D-15; Roadmap success criterion 5; 02-05 must-haves.
- **Evidence:** the depth-4 gauntlet ran 3 games instead of the planned 30–100
  and took 26:06, exceeding the intended 10-minute budget. The depth match ran
  5 games instead of 30–50 and took 2:25:23.
- **Affected artifacts:** `tests/test_random_mover_gauntlet.py`,
  `tests/test_depth_vs_depth.py`, `02-UAT.md`.
- **Missing work:** after fixing the harness, optimize or formally re-plan the
  evidence design, then execute statistically meaningful reproducible samples
  within an explicitly approved budget.

Three BLOCKER issues and three additional confirmed gaps remain. The canonical
phase status therefore remains `gaps_found`.
