---
status: passed
score: "5/5 phase requirements fully verified"
phase: "02-core-alpha-beta-search"
date: "2026-07-10"
requirements:
  SRCH-02: passed
  SRCH-03: passed
  SRCH-04: passed
  SRCH-07: passed
  UCI-11: passed
---

# Phase 2 Verification

## Goal

The engine plays real, tactically sound chess via iterative-deepening fail-soft negamax with quiescence and correct draw/terminal handling, reporting its thinking each iteration. Gap-closure Plans 02-11 and 02-12 closed the three confirmed correctness defects from the prior verification pass. All five Phase 2 requirement IDs are now fully verified.

## Requirement Traceability

| Requirement | Result | Actual-code evidence |
|---|---|---|
| SRCH-02 | PASS | `negamax()` propagates negated alpha/beta windows, returns the actual fail-high score, scores checkmate as `-(MATE - ply)`, and scores stalemate as zero. Alpha-beta and tactical tests pass. |
| SRCH-03 | PASS | `search_root()` iterates depths in order, changes `last_completed` only after a complete iteration, prioritizes the previous best root move, and returns the retained result on stop/deadline abort. Deadline-retention and exact-telemetry tests pass. |
| SRCH-04 | PASS | `quiescence_search()` applies stand-pat, captures/queen promotions, delta pruning, and qsearch-only MVV-LVA on quiet nodes; in-check nodes search all evasions. Terminal resolution (zero legal moves → mate/stalemate; in-check → evasions) runs before any quiet `MAX_QDEPTH` static return. Capped fool's mate probe returns mate (`-30000`), not evaluator centipawns `123`. |
| SRCH-07 | PASS | Main negamax and `quiescence_search()` both call `_is_draw_position()` at entry and maintain balanced `path_keys` push/pop across recursive descent. Historical current key in `game_history_keys` scores draw `0`, not static eval `123`. Path-repetition and rule-draw regressions pass. |
| UCI-11 | PASS | Completed iterations report depth, signed cp/full-move mate score, exact cumulative nodes, root-elapsed NPS, and PV. Info and bestmove writes are generation-gated under one lock. Unexpected worker exceptions now emit exactly one generation-gated fallback `bestmove` (Plan 02-12). |

All five Phase 2 requirement IDs are traced and pass.

## Plan Must-Have Verification

| Plan | Result | Verification |
|---|---|---|
| 02-01 | PASS | Fail-soft alpha-beta, deterministic root choice, mate/stalemate scoring, and evaluator seam are present. |
| 02-02 | PASS | Qsearch behavior present; terminal-before-cap contract restored by Plan 02-11. |
| 02-03 | PASS | Iterative deepening and draw handling pass in main tree and qsearch descendants (Plan 02-11). |
| 02-04 | PASS | Bare-go deadline, infinite search, completed-depth callbacks, and copied worker position are present on normal paths. |
| 02-05 | PASS (deterministic scope) | Fixed tactical/mate/horizon tests pass. Statistical acceptance superseded by Plan 02-10. |
| 02-06 | PASS | Mate scores use signed full moves and evaluator cp values are clamped below `MATE_THRESHOLD`. |
| 02-07 | PASS | Real history reconstruction, in-tree deadline polling, and exact cumulative nodes/NPS are present and tested. |
| 02-08 | PASS | Per-generation cancellation tokens and lock-atomic info/bestmove gates are present. |
| 02-09 | PASS | Depth-match outcomes are normalized once and seeded legal openings vary reproducibly. |
| 02-10 | PASS (deterministic evidence scope) | Fixed-FEN and fast contract evidence is recorded; no statistical strength claim is accepted. |
| 02-11 | PASS | Qsearch draw detection and terminal-before-cap gaps closed; four focused regressions green. |
| 02-12 | PASS | Worker exception fallback emits one generation-gated legal `bestmove`; stale generation drops output. |

## Gap Closure (Plans 02-11 and 02-12)

| Prior gap | Resolution | Probe result |
|---|---|---|
| Qsearch descendants bypass draw detection (SRCH-07) | `quiescence_search()` calls `_is_draw_position()` at entry; balanced `path_keys`; depth-0 handoff before negamax append | `quiescence_search` with `game_history_keys` → **0** (not 123) |
| Qsearch cap precedes check/terminal (SRCH-04) | Terminals and in-check evasions resolved before quiet `MAX_QDEPTH` static eval | Fool's mate at `MAX_QDEPTH` → **-30000** (mate, not 123) |
| UCI worker exception omits bestmove | `_run_search` catches unexpected `Exception`, logs, `_fallback_root_move`, generation-gated `send_bestmove` | Raising `search_root` → **exactly one** bestmove (`g1h3` from startpos) |

## Confirmed Blocking Gaps

None. The three high-severity defects from the prior verification report are closed with focused regressions and passing probes.

## Review-Only Advisories

These findings remain confirmed but do not affect the five-requirement score:

- **Collector descendant cleanup:** `phase2_deterministic_evidence.py` supervisor may leave descendant engines alive after timeout; deferred to evidence-harness work.
- **Collector artifact reuse:** Existing passed JSON/summary files short-circuit without source-identity binding; deferred.
- **Random-opponent RNG lifecycle:** `RandomMover(seed)` per opponent turn does not preserve one PRNG sequence per game; deferred to Phase 3 statistical use.

## Phase 3 Statistical Deferral

Elo, depth-vs-depth superiority, and random-opponent rate claims remain explicitly deferred to Phase 3 optimized search plus a cutechess harness. Plan 02-10 validly replaces those claims with deterministic tactical, relative-depth, deadline, telemetry, and harness-contract evidence. This deferral is not a Phase 2 requirement gap.

## Automated Evidence

- `.venv/bin/python -m pytest -m "not slow" -q` — **146 passed, 2 deselected in 17.50s**.
- Verification probe 1 (historical draw): score **0**, not 123.
- Verification probe 2 (capped checkmate): score **-30000** (mate), not 123.
- Verification probe 3 (worker exception): **1** generation-gated `bestmove` emitted on `RuntimeError`.
- Focused regressions: `test_qsearch_game_history_repetition_scores_draw`, `test_qsearch_at_cap_checkmate_scores_mate`, `test_worker_exception_emits_generation_gated_fallback_bestmove`, `test_stale_worker_exception_emits_no_fallback_bestmove` — all pass.
- Slow and statistical game suites were intentionally not run for this verification pass.

## UAT Evidence

Recorded UAT remains valid for normal-path behavior: visible iteration info, responsive `go infinite`/`stop`, tactical play, signed mate output, draw handling, and watched En Croissant game. Slow match results are historical smoke observations only, not statistical acceptance.

## Verdict

**Status: `passed`.** All five Phase 2 requirements are verified. Gap-closure Plans 02-11 and 02-12 resolved the remaining blocking defects. Phase 2 may be marked complete.
