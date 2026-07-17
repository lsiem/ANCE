---
phase: 04-offline-nnue-training-pipeline
plan: 02
subsystem: testing
tags: [pytorch, nnue, safetensors, wdl-loss, mps]

requires:
  - phase: 04-offline-nnue-training-pipeline
    provides: nnue_format contract and mps_gate from Plan 04-01
provides:
  - NNUE (768→256)×2→1 model, train loop, export path
  - End-to-end synthetic train→export→load smoke proof
affects: [04-03, 04-06, 04-07, 05-nnue-evaluator-swap]

tech-stack:
  added: []
  patterns: [sigmoid-WDL loss, transposed Linear export, fixed-minibatch smoke training]

key-files:
  created:
    - training/model.py
    - training/train.py
    - training/export.py
    - tests/training/test_model_forward.py
    - tests/training/test_train_loop_smoke.py
    - tests/training/test_float32_only.py
    - tests/training/test_export_pipeline_smoke.py
  modified:
    - training/mps_gate.py

key-decisions:
  - "train_smoke reuses one fixed minibatch so WDL loss decrease is deterministic on synthetic data"
  - "mps_gate parity check tries dual-input forward when single-input call raises TypeError (NNUE)"

requirements-completed: [TRN-03, TRN-04, TRN-05]

coverage:
  - id: D1
    description: "NNUE forward pass produces one scalar output per position in a batch"
    requirement: TRN-03
    verification:
      - kind: unit
        ref: "tests/training/test_model_forward.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Smoke training reduces sigmoid-WDL loss; MPS gate runs against real NNUE"
    requirement: TRN-03
    verification:
      - kind: unit
        ref: "tests/training/test_train_loop_smoke.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "Trained model exports to valid zero-torch-loadable safetensors with transposed weights"
    requirement: TRN-04
    verification:
      - kind: integration
        ref: "tests/training/test_export_pipeline_smoke.py"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 02 Summary

**Vertical slice: NNUE model → sigmoid-WDL smoke train → transposed safetensors export → zero-torch load**

## Performance

- **Duration:** ~20 min
- **Tasks:** 3
- **Files modified:** 7 created, 1 modified

## Accomplishments

- `(768→256)×2→1` NNUE with ClippedReLU and dual-perspective forward (D-06)
- `wdl_loss`, `preflight_mps_gate`, `train_smoke` with real NNUE MPS parity wiring (TRN-03/TRN-05)
- `export_checkpoint` transposes Linear weights into `nnue_format` layout (D-07)
- End-to-end smoke: 5 train steps → export → `load_net` shape validation

## Task Commits

1. **Task 1: NNUE model architecture** - `5afe8fa`
2. **Task 2: Training loop + MPS gate** - `f9ff427`
3. **Task 3: Export + E2E smoke** - `3aca0a6`

**Plan metadata:** pending

## Deviations from Plan

**1. mps_gate dual-input support + fixed-minibatch train_smoke**
- Extended `cpu_vs_mps_parity_check` to call `model(x, x)` when single-arg forward raises `TypeError`
- `train_smoke` holds one synthetic minibatch fixed across steps so loss decrease is reproducible

## Self-Check: PASSED

- `pytest tests/training/ -x -q` — 14 passed
- `pytest tests/ -q -m "not slow"` — 245 passed

---
*Phase: 04-offline-nnue-training-pipeline*
*Completed: 2026-07-17*
