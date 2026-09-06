---
phase: 06-quiet-data-nnue-strength-gap
plan: 06
subsystem: tools
tags: [gauntlet, elo, tool-04, nnue, quiet-data]

requires:
  - phase: 06-quiet-data-nnue-strength-gap
    provides: quiet-data harness (06-01..06-05) + installed strength-run net
provides:
  - Committed 06-GAUNTLET-EVIDENCE.json (honest D-12 / TOOL-04 result)
affects:
  - Phase 6 / milestone TOOL-04 verification

key-files:
  created:
    - .planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json
    - .planning/phases/06-quiet-data-nnue-strength-gap/06-06-SUMMARY.md
    - .planning/phases/06-quiet-data-nnue-strength-gap/06-06-PLAN.md
    - .planning/phases/06-quiet-data-nnue-strength-gap/finalize_06_evidence.py
  modified:
    - training/diagnostics_eval.py
    - training/elo_probe.py
    - tests/training/test_diagnostics_eval.py
    - tests/training/test_phase6_closer_evidence.py
    - .planning/STATE.md
    - .planning/ROADMAP.md

key-decisions:
  - "Material diagnostic is polarity-only (both edges > +100 cp), not queen>rook"
  - "200-game probe is a hard gate; 0–200 shutout skips the ≥1000 TOOL-04 run"
  - "Logistic Elo ±Inf from a 0.0 score rate serializes as JSON null"

requirements-completed: []  # TOOL-04 not met — see gates_failed

duration: ~16h wall (200-game depth-3 probe)
completed: 2026-09-06
status: complete_with_failed_gates
---

# Phase 06 Plan 06 Summary

**Quiet-data NNUE vs handcrafted 200-game depth-3 probe (TOOL-04 re-gate)**

## Result

| Field | Value |
|-------|-------|
| diagnostics | pass (startpos +13, rook-up +160, queen-up +138, color-flip 12/12) |
| probe games | 200 / 200 completed |
| mode / depth | fixed_depth / 3 |
| W / L / D | 0 / 200 / 0 (all checkmate; 0 time forfeits) |
| score_rate | 0.0 (Wilson 0.00 … 0.0188) |
| Elo | −∞ (JSON `null`; CI high −686.6) |
| ≥1000 gauntlet | skipped (probe gate failed) |
| gates_passed | [] |
| gates_failed | [D-12, TOOL-04] |

## Net

Installed `ance/eval/nnue/net.safetensors` from the Lichess 2013-01 quiet-data strength run: `n_merged=19866`, `n_train=19013`, `best_epoch=18`, fitted `K≈451.45`, arch `768x2-256-1`.

## Notes

- Harness plans 06-01..06-05 were already on `main`. This plan only measured.
- Quiet-data net is diagnostically signed but much weaker than handcrafted at depth 3 — worse than the Phase 5 incomplete 2–15 snapshot.
- Honest `gates_failed`. A larger result-bearing corpus (or a different trainer recipe) is required before another TOOL-04 attempt.
- Command: `.venv/bin/python -u .planning/phases/06-quiet-data-nnue-strength-gap/post_train_close_06.py`

## Automated Evidence

- `.venv/bin/python -m pytest tests/training/test_diagnostics_eval.py tests/training/test_phase6_closer_evidence.py -q` — polarity + RFC-JSON shutout serialization
- `.planning/phases/06-quiet-data-nnue-strength-gap/06-GAUNTLET-EVIDENCE.json` — committed closer output
