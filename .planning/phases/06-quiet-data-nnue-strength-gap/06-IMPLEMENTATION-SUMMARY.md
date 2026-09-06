---
phase: 06-quiet-data-nnue-strength-gap
status: complete_with_failed_gates
completed: 2026-09-06
---

# Phase 6 implementation summary

Harness (06-01..06-05) plus the 06-06 measurement closer are done. The
installed quiet-data net lost the 200-game depth-3 probe 0–200. TOOL-04
was not re-run at 1000 games. See `06-06-SUMMARY.md` and
`06-GAUNTLET-EVIDENCE.json`.

## Delivered

| Workstream | Artifacts |
|------------|-----------|
| 06-01 Quiet corpus | `training/data/quiet_filter.py`, `cp_clamp.py`, pipeline mix guards, tests |
| 06-02 Trainer recipe | λ schedule, fen-skipping, `--resume-from-checkpoint` via `run_training` / CLI |
| 06-03 Elo probes | `training/elo_probe.py`, best_elo export, dashboard Probe Elo chart |
| 06-04 Measurement | `diagnostics_eval.py`, `post_train_close_06.py`, evidence schema test |
| 06-05 Accumulator | Random-game parity test + `06-NPS-BENCH.json` / `06-DIAGNOSTICS.json` |
| 06-06 Closer | `06-GAUNTLET-EVIDENCE.json`, `06-06-SUMMARY.md` — probe 0–200, gates_failed |

## Evidence snapshots (this environment)

- Diagnostics on packaged net: **ok** (`06-DIAGNOSTICS.json`)
- NPS bench depth 2: NNUE ≈1.28× handcrafted nps (`06-NPS-BENCH.json`)
- Phase 6 probe: **0–200** at depth 3; honest `gates_failed` in `06-GAUNTLET-EVIDENCE.json`
