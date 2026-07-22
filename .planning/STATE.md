---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 05
current_phase_name: nnue-swap-in-elo-gauntlet
status: "Executing 05-04 — SF200k smoke 0-20; opening-biased SF150k training"
stopped_at: null
last_updated: "2026-07-22T07:04:11.000Z"
last_activity: 2026-07-22
progress:
  total_phases: 5
  completed_phases: 4
  total_plans: 35
  completed_plans: 34
  percent: 97
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-07-08)

**Core value:** The engine plays legal, tactically sound chess through a clean UCI interface, and gets measurably stronger when a trained NNUE evaluation replaces the handcrafted one.
**Current focus:** Phase 05 — Plan 05-04 gap closure (TOOL-04)

## Current Position

Phase: 05 (nnue-swap-in-elo-gauntlet) — IN PROGRESS (gap)
Plan: 4 of 4 (05-03 SUMMARY written; D-12 failed; 05-04 next)
Status: Clean gauntlet finished 0W–1000L–0D; evidence committed with `gates_failed`
Last activity: 2026-07-22

Progress: [██████████] 97%

## Performance Metrics

**Velocity:**

- Total plans completed: 34
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
| Phase 05 P03 | ~36h gauntlet | 2 tasks | evidence + SUMMARY |

## Accumulated Context

### Decisions

- [Phase 05 / 2026-07-22]: SF 200k depth-12 random-walk net improved material signs but smoke 20-game depth-3 still 0–20; started opening-biased SF 150k retrain.
- [Phase 05 / 2026-07-22]: Plan 05-03 closed with honest failure — 1000-game depth-3 NNUE vs HC = 0–1000–0; `gates_failed: ["D-12","TOOL-04"]`. Do not claim TOOL-04.
- [Phase 05 / 2026-07-20]: Discarded mixed-net checkpoint after PR #5 HF net landed mid-run; restarted clean evidence run.
- [Phase 05]: Acceptance depth N=3 for TOOL-04 overnight gauntlet.
- [Phase 05]: Gap Plan 05-04 opened for stronger training data + re-evidence.

### Pending Todos

See: `.planning/todos/pending/2026-07-22-05-04-retrain-d12.md`

1. Execute Plan 05-04 — retrain/replace net, smoke, re-run D-12 gauntlet until `elo_ci_low > 0`.

### Blockers/Concerns

- HF-trained net (~37k unique) is far weaker than handcrafted at depth 3; material sign/goldens unreliable.
- Depth-3 wall-clock ~130 s/game on this host (~36 h / 1000 games).

## Session Continuity

Last session: 2026-07-22T05:47:00.000Z
Stopped at: null — 05-03 closed; route next to 05-04
Resume file: `.planning/todos/pending/2026-07-22-05-04-retrain-d12.md`
Evidence: `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json`
Summary: `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-03-SUMMARY.md`
