---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: milestone
current_phase: 05
current_phase_name: nnue-swap-in-elo-gauntlet
status: "HF-primary scale train complete — net installed; 05-03 gauntlet next"
stopped_at: Ready for 05-03 gauntlet with HF-trained net (36.7k unique positions)
last_updated: "2026-07-19T16:50:00.000Z"
last_activity: 2026-07-19
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
Plan: 3 of 3 (05-03 incomplete; stronger net trained + installed)
Status: HF-primary scale train complete — net installed; 05-03 gauntlet next
Last activity: 2026-07-19

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

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [Roadmap]: Fix the `evaluate(position)->cp` seam (side-to-move relative) and the non-blocking reader/worker threading model in Phase 1 — both are painful to retrofit and gate everything downstream.
- [Roadmap]: Stage the transposition table (SRCH-05) before move ordering (SRCH-06), and both before any pruning; move ordering is the multiplier and pruning on bad ordering loses strength.
- [Roadmap]: Offline training (Phase 4) binds to the engine only through the shared `nnue_format` weights contract, so it can run in parallel with Phases 2–3.
- [Phase 05]: D-14 exact-0 golden uses startpos (Phase 4 net bias on king-only) — Approved net scores ~-20 on king-only; startpos is exact 0 for both STMs
- [Phase 05]: Acceptance depth N=3 for TOOL-04 overnight gauntlet — 05-RESEARCH wall-clock projection (~4-8h with NNUE at d3)
- [Phase 05]: Phase 3 popen_uci mocks accept **kwargs for EngineSpec.env merge — Required so env= kwarg does not break clock-mode harness tests
- [Phase 05 / 2026-07-19]: Cloud resume used HF-primary train (`--fresh-n-games 0`, 250k positions) as scale-label substitute; resulting net failed D-14/D-16 goldens and lost 4/4 smoke games. Restored Phase-4 `run-output/net.safetensors` for 05-03 evidence run. Incremental NNUE vs fresh parity checked clean (0 mismatches / 2111). Early gauntlet score 0–5 NNUE.

### Pending Todos

See: `.planning/todos/pending/2026-07-18-scale-train-and-05-03.md`

1. ~~Resume scale labeling / train+export / install net~~ — done via HF-primary cloud run (250k ingest → 36.7k unique; 50 epochs; best val 0.02422).
2. Complete 05-03 ≥1000-game D-12 gauntlet evidence (honest `gates_failed` if Elo still bad).
3. Write `05-03-SUMMARY.md` + sync ROADMAP/STATE; gap plan if D-12 fails.

### Blockers/Concerns

- [Phase 4] MPS `torch.backends.mps.is_available()` has regressed on recent macOS majors — a smoke test + CPU-vs-MPS numeric parity check must be the first task of the training harness (CPU training is a viable fallback for this tiny net).
- [Phase 4/5] WDL scaling constant K (~360–400) and the exact Stockfish labeling command (normalized UCI cp ≠ internal eval) must be pinned/measured before generating the dataset.
- [Phase 5] Current Phase-4 net is too weak for D-12 at depth 3 (early gauntlet 0–N). Cloud HF retrain did not produce a stronger installable net. Expect honest `gates_failed` unless a stronger net lands mid-run (would require restart).
- [Phase 5] Depth-3 NNUE vs HC wall-clock on this host ~150 s/game → ~41 h for 1000 games (above RESEARCH 4–8 h).

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260718-tpm | Add Hugging Face Lichess chess-position-evaluations parquet ingest path as pre-labeled NNUE training data stream | 2026-07-18 | 68751ee | [260718-tpm-add-hugging-face-lichess-chess-position-](./quick/260718-tpm-add-hugging-face-lichess-chess-position-/) |

## Deferred Items

Items acknowledged and carried forward from previous milestone close:

| Category | Item | Status | Deferred At |
|----------|------|--------|-------------|
| Milestone v1.1 | Local web-app GUI (live eval, games, search metrics) — see `todos/pending/2026-07-07-v1_1-gui-local-web-app.md` | Backlog — kick off after v1.0 ships | 2026-07-07 |

## Session Continuity

Last session: 2026-07-19T16:50:00.000Z
Stopped at: HF scale train complete; net installed into `ance/eval/nnue/`; 05-03 gauntlet remaining
Resume file: `.planning/todos/pending/2026-07-18-scale-train-and-05-03.md`
Gauntlet checkpoint: `.planning/phases/05-nnue-swap-in-elo-gauntlet/05-gauntlet-checkpoint.json`
Gauntlet runner: `.planning/phases/05-nnue-swap-in-elo-gauntlet/run_gauntlet_05_03.py`
