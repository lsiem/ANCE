---
phase: 06-quiet-data-nnue-strength-gap
status: harness_complete
completed: 2026-07-20
---

# Phase 6 implementation summary

Code + tests for the quiet-data strength gap are in place. Overnight
`--strength-corpus` train + 200→1000 gauntlet still need a Lichess `.pgn.zst`
and wall-clock; see `06-NOTES.md` and `post_train_close_06.py`.

## Delivered

| Workstream | Artifacts |
|------------|-----------|
| 06-01 Quiet corpus | `training/data/quiet_filter.py`, `cp_clamp.py`, pipeline mix guards, tests |
| 06-02 Trainer recipe | λ schedule, fen-skipping, `--resume-from-checkpoint` via `run_training` / CLI |
| 06-03 Elo probes | `training/elo_probe.py`, best_elo export, dashboard Probe Elo chart |
| 06-04 Measurement | `diagnostics_eval.py`, `post_train_close_06.py`, evidence schema test |
| 06-05 Accumulator | Random-game parity test + `06-NPS-BENCH.json` / `06-DIAGNOSTICS.json` |

## Evidence snapshots (this environment)

- Diagnostics on packaged net: **ok** (`06-DIAGNOSTICS.json`)
- NPS bench depth 2: NNUE ≈1.28× handcrafted nps (`06-NPS-BENCH.json`)
- Phase 5: honest `gates_failed` in `05-GAUNTLET-EVIDENCE.json`
