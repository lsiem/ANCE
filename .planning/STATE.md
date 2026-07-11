---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 4
current_phase_name: Offline NNUE Training Pipeline
status: ready_to_plan
stopped_at: Phase 3 complete (6/6) — ready to discuss Phase 4
last_updated: 2026-07-11T17:39:14.046Z
last_activity: 2026-07-11
last_activity_desc: Completed Phase 3 (6/6 plans)
progress:
  total_phases: 5
  completed_phases: 3
  total_plans: 24
  completed_plans: 24
  percent: 60
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-08)

**Core value:** The engine plays legal, tactically sound chess through a clean UCI interface, and gets measurably stronger when a trained NNUE evaluation replaces the handcrafted one.
**Current focus:** Phase 4 — offline nnue training pipeline

## Current Position

Phase: 4
Plan: Not started
Status: Ready to plan
Last activity: 2026-07-11

Progress: [██████░░░░] 60%

## Performance Metrics

**Velocity:**

- Total plans completed: 24
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 6 | - | - |
| 2 | 12 | - | - |
| 3 | 6 | - | - |

**Recent Trend:**

- Last 5 plans: —
- Trend: —

*Updated after each plan completion*
| Phase 01 P01 | 20min | 3 tasks | 12 files |
| Phase 01-minimal-uci-engine-evaluator-seam P02 | 9min | 3 tasks | 6 files |
| Phase 01 P03 | 35min | 3 tasks | 9 files |
| Phase 01 P04 | 20 min | 3 tasks | 5 files |
| Phase 01-minimal-uci-engine-evaluator-seam P05 | 35min | 2 tasks | 5 files |
| Phase 02 P07 | 8 min | 2 tasks | 4 files |
| Phase 02 P08 | 11min | 2 tasks | 3 files |
| Phase 02 P09 | 5 min | 2 tasks | 3 files |
| Phase 02 P10 | 7 min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Fix the `evaluate(position)->cp` seam (side-to-move relative) and the non-blocking reader/worker threading model in Phase 1 — both are painful to retrofit and gate everything downstream.
- [Roadmap]: Stage the transposition table (SRCH-05) before move ordering (SRCH-06), and both before any pruning; move ordering is the multiplier and pruning on bad ordering loses strength.
- [Roadmap]: Offline training (Phase 4) binds to the engine only through the shared `nnue_format` weights contract, so it can run in parallel with Phases 2–3.
- [Phase 01]: python3.13 (native arm64) used as venv interpreter -- Python 3.12 itself is not installed on this machine, but 3.13 satisfies the project's 3.12+ floor
- [Phase 01]: quit performs a bounded (2s) join() on the daemon worker thread before sys.exit(0), closing a race where an immediate exit could kill the worker before it prints its bestmove line
- [Phase 01]: Position adapter's moves-list failure leaves the board at the just-set valid startpos/fen base, not the pre-command board — try_push_uci_moves never partially commits, so this remains a fully-defined non-corrupting state; matches plan wording
- [Phase 01]: setoption/ponder/ponderhit have explicit no-op handlers rather than relying on the generic unknown-token skip — cross-AI review finding; forward-compatible with a real setoption handler in v2 without risking dispatcher misparse
- [Phase 01]: search_generation gating: a monotonic counter bumped before preemption (not join() timing) is the single correctness mechanism gating send_bestmove for overlapping go commands
- [Phase 01]: DEFAULT_DEPTH=3 confirmed via test suite to keep a bare go under 1.0s with MaterialEval in pure Python
- [Phase 01]: DEFAULT_DEPTH stayed at 3 (ance/search/negamax.py untouched) — Post-wiring bare-go benchmark measured ~0.53s with HandcraftedEval in the hot path, comfortably under the 1.0s bound, so no retune was needed
- [Phase 01]: Positional terms computed white-relative internally, single sign flip by board.turn at the end of evaluate() (D-07) — Matches material+PST subtotal convention; tempo is added after the flip since it is inherently side-to-move relative
- [Phase 01]: Pawn-structure file counts use int.bit_count() over bitboard masks — Avoids a bin(...).count() string round-trip since this runs per leaf at every search node (round-2 cross-AI review LOW finding)
- [Phase 01]: 01-05 acceptance replanned — losses==0 + >=70% wins @ depth2; 100/0@depth4 deferred to pruning
- [Phase 02]: A new go advances generation before bounded preemption and always allocates a fresh cancellation Event — Prevents stale worker token reuse and establishes replacement before old-worker shutdown.
- [Phase 02]: stop preserves the active generation, while state-changing commands invalidate only workers that survive their bounded join — Preserves one current bestmove while preventing timed-out workers from emitting after state changes.
- [Phase 02]: Normalize raw python-chess results once inside play_depth_match_game and tally typed deeper-side outcomes directly. — Eliminates color-dependent double interpretation and makes one-game semantics explicit.
- [Phase 02]: Use game-index parity for color and seed plus game index for deterministic opening selection. — Keeps color assignment independent from reproducible opening variation.
- [Phase 02]: Classify the interrupted 30+30 run only as runtime calibration and defer statistical strength evidence to Phase 3 optimized search and cutechess. — Two depth games consumed 1205.6582282920135 seconds, projecting the depth suite alone to about 5.02 hours; deterministic evidence is reproducible within the bounded hard wall.

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 4] MPS `torch.backends.mps.is_available()` has regressed on recent macOS majors — a smoke test + CPU-vs-MPS numeric parity check must be the first task of the training harness (CPU training is a viable fallback for this tiny net).
- [Phase 4/5] WDL scaling constant K (~360–400) and the exact Stockfish labeling command (normalized UCI cp ≠ internal eval) must be pinned/measured before generating the dataset.

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Milestone v1.1 | Local web-app GUI (live eval, games, search metrics) — see `todos/pending/2026-07-07-v1_1-gui-local-web-app.md` | Backlog — kick off after v1.0 ships | 2026-07-07 |

## Session Continuity

Last session: 2026-07-10T20:10:53.768Z
Stopped at: Completed 02-10-PLAN.md
Resume file: None
