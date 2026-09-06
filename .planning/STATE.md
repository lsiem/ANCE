---
gsd_state_version: "1.0"
milestone: v1.0
current_phase: 7
current_phase_name: NNUE strength recovery
status: Phase 06 verified — TOOL-04 failed; next is Phase 7 discuss/plan
stopped_at: Phase 7 context gathered
last_updated: "2026-09-06T16:38:27.690Z"
last_activity: 2026-09-06
last_activity_desc: /gsd-progress --next → verify-work 06; 3/4 criteria, TOOL-04 failed
state_head: ef9ffadaf6931507f0a1c5994e44b8aefe2d369b
progress:
  total_phases: 7
  completed_phases: 4
  total_plans: 39
  completed_plans: 35
milestone_name: milestone
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-08)

**Core value:** The engine plays legal, tactically sound chess through a clean UCI interface, and gets measurably stronger when a trained NNUE evaluation replaces the handcrafted one.
**Current focus:** Phase 06 — quiet-data NNUE strength gap

## Current Position

Phase: 7 (NNUE strength recovery) — READY TO EXECUTE
Prior: Phase 05 GAP (D-12 failed)
Plan: 06-VERIFICATION.md written; do not complete-phase
Status: Harness 3/4 pass; 200-game probe 0–200; next is Phase 7 discuss/plan
Last activity: 2026-09-06 — `/gsd-progress --next` ran verify-work

Progress: [██████████] 97%

## Performance Metrics

**Velocity:**

- Total plans completed: 32
- Average duration: — min
- Total execution time: 0.0 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 6 | - | - |
| 2 | 12 | - | - |
| 3 | 6 | - | - |
| 04 | 7 | - | - |

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
| Phase 04 P07 | ~2 days (3 run attempts) | 2 tasks | 4 files |
| Phase 05 P01 | 9 min | 3 tasks | 8 files |
| Phase 05 P02 | 10min | 3 tasks | 4 files |

## Accumulated Context

### Roadmap Evolution

- Phase 7 added: NNUE strength recovery

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Fix the `evaluate(position)->cp` seam (side-to-move relative) and the non-blocking reader/worker threading model in Phase 1 — both are painful to retrofit and gate everything downstream.
- [Roadmap]: Stage the transposition table (SRCH-05) before move ordering (SRCH-06), and both before any pruning; move ordering is the multiplier and pruning on bad ordering loses strength.
- [Roadmap]: Offline training (Phase 4) binds to the engine only through the shared `nnue_format` weights contract, so it can run in parallel with Phases 2–3.
- [Phase 05]: D-14 exact-0 golden uses startpos (Phase 4 net bias on king-only) — Approved net scores ~-20 on king-only; startpos is exact 0 for both STMs
- [Phase 05]: Acceptance depth N=3 for TOOL-04 overnight gauntlet — 05-RESEARCH wall-clock projection (~4-8h with NNUE at d3)
- [Phase 05]: Phase 3 popen_uci mocks accept **kwargs for EngineSpec.env merge — Required so env= kwarg does not break clock-mode harness tests
- [Phase 05 / 2026-07-19]: Cloud resume used HF-primary train (`--fresh-n-games 0`, 250k positions) as scale-label substitute; resulting net failed D-14/D-16 goldens and lost 4/4 smoke games. Restored Phase-4 / later scale-run nets for evidence. Expect honest `gates_failed` without quiet/result-bearing data (Phase 6).
- [Phase 06]: Quiet-data strength gap — Lichess primary + quiet filter + λ schedule; re-gate TOOL-04 after strength-run.

### Pending Todos

See: `.planning/todos/done/2026-09-06-phase06-quiet-data-closer.md`

1. ~~05-03 evidence~~ — committed with `gates_failed` (honest).
2. ~~Phase 6 harness + strength-run train~~ — quiet-data net installed.
3. ~~Run `post_train_close_06.py`~~ — 200-game probe 0–200; ≥1000 skipped.
4. ~~Write `06-06-SUMMARY` / evidence~~ — honest `gates_failed` (D-12, TOOL-04).

### Blockers/Concerns

- [Phase 4] MPS `torch.backends.mps.is_available()` has regressed on recent macOS majors — a smoke test + CPU-vs-MPS numeric parity check must be the first task of the training harness (CPU training is a viable fallback for this tiny net).
- [Phase 4/5] WDL scaling constant K (~360–400) and the exact Stockfish labeling command (normalized UCI cp ≠ internal eval) must be pinned/measured before generating the dataset.
- [Phase 5] Prior nets too weak for D-12 at depth 3. Phase 6 quiet corpus was the recovery path; 200-game probe still 0–200.
- [Phase 6] Quiet 2013-01 corpus (`n_merged=19866`) is diagnostically signed but far weaker than handcrafted at depth 3. Next strength attempt needs a much larger result-bearing dump or a different recipe.
- [Phase 5] Depth-3 NNUE vs HC wall-clock on some hosts ~150 s/game → ~41 h for 1000 games (above RESEARCH 4–8 h).

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Milestone v1.1 | Local web-app GUI (live eval, games, search metrics) — see `todos/pending/2026-07-07-v1_1-gui-local-web-app.md` | Backlog — kick off after v1.0 ships | 2026-07-07 |

## Session Continuity

Last session: 2026-09-06T16:04:06.436Z
Stopped at: Phase 7 context gathered
Resume file: .planning/phases/07-nnue-strength-recovery/07-CONTEXT.md
Phase 6 evidence: `.planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json`
Next: `/gsd-discuss-phase` or `/gsd-plan-phase` for Phase 7 strength recovery
