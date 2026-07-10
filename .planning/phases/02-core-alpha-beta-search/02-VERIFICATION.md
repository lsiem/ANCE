---
status: gaps_found
score: "3/5 phase requirements fully verified"
phase: "02-core-alpha-beta-search"
date: "2026-07-10"
requirements:
  SRCH-02: passed
  SRCH-03: passed
  SRCH-04: gaps_found
  SRCH-07: gaps_found
  UCI-11: passed
---

# Phase 2 Verification

## Goal

The core engine is substantially present and the normal search path works: fail-soft alpha-beta negamax iteratively deepens, retains the last completed depth, runs quiescence, handles main-tree draws and terminals, and emits generation-gated UCI information for each completed iteration. The phase cannot be marked passed because quiescence does not preserve draw correctness below its entry node and can statically evaluate an unresolved check/checkmate at its depth cap. A separate worker-failure path can also omit the required final `bestmove`.

## Requirement Traceability

| Requirement | Result | Actual-code evidence |
|---|---|---|
| SRCH-02 | PASS | `negamax()` propagates negated alpha/beta windows, returns the actual fail-high score, scores checkmate as `-(MATE - ply)`, and scores stalemate as zero. Alpha-beta and tactical tests pass. |
| SRCH-03 | PASS | `search_root()` iterates depths in order, changes `last_completed` only after a complete iteration, prioritizes the previous best root move, and returns the retained result on stop/deadline abort. Deadline-retention and exact-telemetry tests pass. |
| SRCH-04 | GAP | Quiet qsearch uses stand-pat, captures/queen promotions, delta pruning, and qsearch-only MVV-LVA; in-check nodes normally search all evasions. However, `qdepth >= MAX_QDEPTH` returns static evaluation before terminal/check handling, so a capped checked or checkmated node is evaluated as ordinary centipawns. |
| SRCH-07 | GAP | Main negamax reconstructs the real move stack and checks repetition, 50-move, and insufficient-material draws. Recursive `quiescence_search()` calls perform none of those checks and do not push/pop path keys, so qsearch descendants can miss rule/history draws. |
| UCI-11 | PASS | Completed iterations report depth, signed cp/full-move mate score, exact cumulative nodes, root-elapsed NPS, and PV. Info and bestmove writes are generation-gated under one lock; normal subprocess and concurrency tests pass. Unexpected worker exceptions remain a separate UCI lifecycle gap described below. |

All five Phase 2 requirement IDs are traced. Three are fully verified; SRCH-04 and SRCH-07 have confirmed correctness gaps.

## Plan Must-Have Verification

| Plan | Result | Verification |
|---|---|---|
| 02-01 | PASS | Fail-soft alpha-beta, deterministic root choice, mate/stalemate scoring, and evaluator seam are present. |
| 02-02 | GAP | Core qsearch behavior is present, but the check/terminal contract fails at `MAX_QDEPTH`. |
| 02-03 | GAP | Iterative deepening and main-tree draw handling pass; qsearch descendants do not inherit draw handling. |
| 02-04 | PASS | Bare-go deadline, infinite search, completed-depth callbacks, and copied worker position are present on normal paths. |
| 02-05 | PASS (deterministic scope) | Fixed tactical/mate/horizon tests pass. Its original statistical acceptance is superseded by Plan 02-10 and deferred below. |
| 02-06 | PASS | Mate scores use signed full moves and evaluator cp values are clamped below `MATE_THRESHOLD`. |
| 02-07 | PASS | Real history reconstruction, in-tree deadline polling, and exact cumulative nodes/NPS are present and tested. |
| 02-08 | PASS (generation scope) | Per-generation cancellation tokens and lock-atomic info/bestmove gates are present. Exception fallback was not part of the plan and remains a gap. |
| 02-09 | PASS | Depth-match outcomes are normalized once and seeded legal openings vary reproducibly. |
| 02-10 | PASS (deterministic evidence scope) | Fixed-FEN and fast contract evidence is recorded; no statistical strength claim is accepted. Collector robustness advisories remain below. |

## Confirmed Gaps

### 1. Qsearch descendants bypass draw detection

- **Severity:** high
- **Requirement:** SRCH-07; phase goal's correct draw handling
- **Evidence:** `negamax()` calls `_is_draw_position()` and owns balanced `path_keys`, but `quiescence_search()` recursively calls itself without either operation. A focused probe supplied a historical current key directly to qsearch and returned evaluator score `123`, not draw score `0`.
- **Missing work:** apply draw/terminal checks and balanced path-key tracking at every qsearch node; add real descendant regressions for history/path repetition and rule draws.

### 2. Qsearch cap precedes check and terminal handling

- **Severity:** high
- **Requirement:** SRCH-04; phase goal's correct terminal handling
- **Evidence:** the `qdepth >= MAX_QDEPTH` return executes before `pos.is_check()` and legal-evasion handling. A direct checkmated-position probe at the cap returned evaluator score `123` instead of a mate score.
- **Missing work:** resolve terminal/check state before applying a quiet-node cap, with a bounded check-evasion policy and a cap-in-check regression.

### 3. Unexpected UCI worker exceptions emit no fallback bestmove

- **Severity:** high
- **Requirement linkage:** regression against UCI-06's one-bestmove-per-go contract; affects Phase 2 worker integration, not the normal UCI-11 formatter path
- **Evidence:** `_run_search()` only has `try/finally`; an exception from search/evaluation/info callback propagates before the generation-gated `send_bestmove`. A focused raising-search probe propagated `RuntimeError` and captured zero bestmove writes.
- **Missing work:** catch worker failures, log to stderr, and emit exactly one generation-gated legal fallback or `bestmove (none)` according to an explicit policy; add a deterministic raising-worker test.

## Review-Only Advisories

These findings are confirmed but do not change the five-requirement score because they concern evidence tooling or deferred statistical semantics rather than the running engine's Phase 2 requirement paths.

- **Collector descendant cleanup:** confirmed. `_run_command()` uses `subprocess.run(timeout=...)`, which terminates only the direct pytest process. If that child writes failed artifacts and exits nonzero, the supervisor returns at the existing-artifact branch without process-group cleanup, then disables the watchdog. Descendant engines can therefore outlive the advertised bound. The current tests use a fake direct child and do not cover a real pytest descendant.
- **Collector artifact reuse:** confirmed. Existing passed JSON/summary files cause an early return after weak terminal validation; validation does not bind the artifact to current source/test identity, command inventory, or current commit.
- **Random-opponent RNG lifecycle:** confirmed. `play_game()` constructs `RandomMover(seed)` on every opponent turn, repeatedly consuming the first sample from a new PRNG instead of one seeded sequence per game. Determinism holds, but the stated uniformly-random trajectory does not. This does not invalidate Plan 02-10 because it makes no random-gauntlet statistical claim.

## Phase 3 Statistical Deferral

The previous 3-game random gauntlet and 5-game depth match are not accepted as statistical strength evidence. The corrected 30-game depth suite projected to about 5.02 hours by itself, and no 30-game random suite completed. Plan 02-10 validly replaces those claims with deterministic tactical, relative-depth, deadline, telemetry, and harness-contract evidence. Elo, depth-vs-depth superiority, and random-opponent rate claims remain explicitly deferred to Phase 3 optimized search plus a cutechess harness; this deferral is not counted as a Phase 2 requirement gap.

## Automated Evidence

- `.venv/bin/python -m pytest -m "not slow" -q` — **139 passed, 2 deselected in 17.69s**.
- Focused probes independently reproduced all three engine gaps: qsearch historical draw returned `123`; capped checkmate returned `123`; raising worker propagated `RuntimeError` and emitted no bestmove.
- Existing fast regressions verify real history reconstruction, deadline retention, exact cumulative telemetry, mate wire format, stale-generation isolation, tactical moves, and deterministic opening/result semantics.
- Slow and statistical game suites were intentionally not run.

## UAT Evidence

The recorded UAT remains useful for normal-path behavior: visible iteration info, responsive `go infinite`/`stop`, tactical play, signed mate output, and the watched En Croissant game all passed. Its slow match results are treated only as historical runtime/smoke observations, not as statistical acceptance, and UAT does not cover the three confirmed failure paths above.

## Verdict

**Status: `gaps_found`.** Fix the two qsearch correctness defects and the UCI worker exception fallback, add focused regressions, then rerun the bounded fast suite and replace this verification. Collector cleanup/artifact identity should be repaired before relying on a future collector rerun; random-mover RNG state should be fixed before Phase 3 statistical use.
