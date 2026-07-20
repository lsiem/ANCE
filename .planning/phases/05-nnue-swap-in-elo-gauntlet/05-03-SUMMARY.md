---
phase: 05-nnue-swap-in-elo-gauntlet
plan: 03
subsystem: tools
tags: [gauntlet, elo, tool-04, nnue, scale-train]

requires:
  - phase: 05-nnue-swap-in-elo-gauntlet
    provides: NnueEval + fixed-depth gauntlet harness (05-01, 05-02)
  - phase: 04-offline-nnue-training-pipeline
    provides: scale-run net.safetensors (1M SF depth-12 labels)
provides:
  - Committed 05-GAUNTLET-EVIDENCE.json (honest D-12 result)
  - Engine weights from scale-run export (when present)
affects:
  - Phase 5 / milestone TOOL-04 verification
  - Phase 6 quiet-data strength gap

key-files:
  created:
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/05-GAUNTLET-EVIDENCE.json
    - .planning/phases/05-nnue-swap-in-elo-gauntlet/05-03-SUMMARY.md
  modified:
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Evidence records gates_failed when Elo CI gate fails or gauntlet incomplete (honest TOOL-04)"
  - "Incomplete 17-game snapshot closed as gap; Phase 6 addresses data/training distribution"

requirements-completed: []  # TOOL-04 not met — see gates_failed

duration: —
completed: 2026-07-20
status: complete_with_failed_gates
---

# Phase 05 Plan 03 Summary

**TOOL-04 ≥1000-game NNUE vs handcrafted Elo evidence (post scale-train)**

## Result

| Field | Value |
|-------|-------|
| games | 17 (incomplete; target 1000) |
| mode / depth | fixed_depth / 3 |
| W / L / D | 2 / 15 / 0 |
| score_rate | 0.1176 |
| Elo | −350.02 (CI −587.42 … −112.62) |
| gates_passed | [] |
| gates_failed | [D-12, TOOL-04] |

## Notes

- Gauntlet did not reach 1000 games in the available environment; checkpoint aggregate still shows a crushing NNUE loss vs handcrafted.
- Honest `gates_failed` — measurement harness succeeded; strength did not.
- Follow-on: Phase 6 quiet-data NNUE strength gap (corpus + trainer recipe + re-gate).
