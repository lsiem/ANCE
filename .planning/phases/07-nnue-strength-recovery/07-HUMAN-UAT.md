---
status: partial
phase: 07-nnue-strength-recovery
source: [07-VERIFICATION.md]
started: 2026-09-07T17:40:00Z
updated: 2026-09-07T17:40:00Z
---

## Current Test

Awaiting M4 from-scratch train and sidecar commit (D-13 / D-16). Cloud closer already wrote blocked evidence (D-14).

## Tests

### 1. M4 MPS from-scratch train + sidecar
expected: `07-NET-SIDECAR.json` exists with `phase` 7 and `from_scratch` true; `ance/eval/nnue/net.safetensors` is the from-scratch export (`768x2-256-1` / `board768`); no `--resume-from-checkpoint`
result: [pending]
instructions: Follow `.planning/phases/07-nnue-strength-recovery/07-USER-SETUP.md`

### 2. Cloud closer after sidecar (smoke → 200 → maybe 1000)
expected: `post_train_close_07.py` runs diagnostics then 16-game smoke at depth 3; abort if wins==0 OR score_rate==0.0 OR elo_ci_high < -200; honest `07-GAUNTLET-EVIDENCE.json` (pass, useful-fail, or smoke abort). Do not raise depth. Do not start a second train.
result: [pending]
note: Current committed evidence is blocked (no sidecar). Re-run closer after test 1.

## Summary

total: 2
passed: 0
issues: 0
pending: 2
skipped: 0
blocked: 0

## Gaps

- TOOL-04 not measured: Phase 7 net not installed on this host (D-14 blocked).
