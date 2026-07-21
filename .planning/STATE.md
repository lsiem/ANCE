---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 05
current_phase_name: nnue-swap-in-elo-gauntlet
status: "Executing 05-03 — clean gauntlet ~502/1000 (0W; D-12 fail expected)"
stopped_at: null
last_updated: "2026-07-21T11:53:10.000Z"
last_activity: 2026-07-21
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 34
  completed_plans: 33
  percent: 97
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-08)

**Core value:** The engine plays legal, tactically sound chess through a clean UCI interface, and gets measurably stronger when a trained NNUE evaluation replaces the handcrafted one.
**Current focus:** Phase 05 — nnue-swap-in-elo-gauntlet / Plan 05-03

## Current Position

Phase: 05 (nnue-swap-in-elo-gauntlet) — IN PROGRESS
Plan: 3 of 3 (05-03 Task 1 complete; Task 2 gauntlet restarted clean)
Status: Executing 05-03 — clean gauntlet ~502/1000 (0W–502L–0D)
Last activity: 2026-07-20

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
| Phase 05 P01 | 9 min | 3 tasks | 8 files |
| Phase 05 P02 | 10min | 3 tasks | 4 files |

## Accumulated Context

### Decisions

- [Phase 05 / 2026-07-20]: Discarded in-flight gauntlet checkpoint after PR #5 HF net landed mid-run (~game 684). Restarted clean ≥1000-game depth-3 evidence with installed `ance/eval/nnue/net.safetensors` (HF-primary scale export). Prior partial score ~46–637–11 / Elo≈−438 was not evidence-quality.
- [Phase 05]: D-14 exact-0 golden may fail with HF net (startpos ≠ 0); TOOL-04 evidence still proceeds; document in SUMMARY.
- [Phase 05]: Acceptance depth N=3 for TOOL-04 overnight gauntlet.

### Pending Todos

See: `.planning/todos/pending/2026-07-18-scale-train-and-05-03.md`

1. Complete clean 05-03 ≥1000-game D-12 gauntlet evidence (honest `gates_failed` if Elo still bad) — **RESTARTED**.
2. Write `05-03-SUMMARY.md` + sync ROADMAP/STATE; gap plan if D-12 fails.

### Blockers/Concerns

- Current HF-trained net shows inverted material sign on sample rook-up positions and fails startpos exact-0 golden; D-12 fail expected; evidence will be honest.
- Depth-3 wall-clock ~150 s/game → ~40 h for 1000 games on this host.

## Session Continuity

Last session: 2026-07-20T17:56:41.000Z
Stopped at: null — clean gauntlet restart in progress
Resume file: `.planning/todos/pending/2026-07-18-scale-train-and-05-03.md`
Gauntlet checkpoint: `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json`
