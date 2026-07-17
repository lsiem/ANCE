---
phase: 04-offline-nnue-training-pipeline
plan: 01
subsystem: testing
tags: [pytorch, safetensors, numpy, mps, nnue-format]

requires:
  - phase: 03-search-acceleration-time-management
    provides: optimized search baseline for later NNUE strength comparison
provides:
  - nnue_format zero-torch weights contract (schema + io)
  - training/mps_gate device selection and CPU-vs-MPS parity check
  - tests/training/ scaffold with torch marker and isolation from main suite
affects: [04-02, 05-nnue-evaluator-swap]

tech-stack:
  added: [torch, numpy, safetensors, zstandard, scipy, tqdm, stockfish]
  patterns: [nnue_format shared contract, training/engine import boundary]

key-files:
  created:
    - nnue_format/schema.py
    - nnue_format/io.py
    - training/mps_gate.py
    - tests/training/conftest.py
    - tests/training/test_nnue_format_roundtrip.py
    - tests/training/test_no_torch_leakage.py
    - tests/training/test_mps_gate.py
  modified:
    - pyproject.toml

key-decisions:
  - "Omitted tests/training/__init__.py — an empty package init caused pytest to shadow the project-root training/ package when tests/ was prepended to sys.path"
  - "Recreated .venv with Python 3.14 after the prior 3.13 interpreter path was broken; torch 2.13.0 reports MPS available on this machine"
  - "Added pythonpath = [\".\"] to pyproject.toml so ance/, nnue_format/, and training/ resolve under pytest"

patterns-established:
  - "nnue_format/: zero-torch numpy safetensors contract with fail-loud shape/arch validation"
  - "tests/training/: torch-gated tests isolated from main ance/ suite via pytest marker"

requirements-completed: [TRN-04, TRN-05]

coverage:
  - id: D1
    description: "nnue_format round-trips synthetic weights with zero torch in the call path"
    requirement: TRN-04
    verification:
      - kind: unit
        ref: "tests/training/test_nnue_format_roundtrip.py"
        status: pass
    human_judgment: false
  - id: D2
    description: "Structural tests prove nnue_format/ has no torch dependency and ance/ never imports training/"
    requirement: TRN-04
    verification:
      - kind: unit
        ref: "tests/training/test_no_torch_leakage.py"
        status: pass
    human_judgment: false
  - id: D3
    description: "MPS gate reports device availability and runs CPU-vs-MPS parity when MPS is selected"
    requirement: TRN-05
    verification:
      - kind: unit
        ref: "tests/training/test_mps_gate.py"
        status: pass
    human_judgment: false

duration: 25min
completed: 2026-07-17
status: complete
---

# Phase 04 Plan 01 Summary

**Training toolchain foundation: zero-torch nnue_format contract, MPS gate, and isolated tests/training/ scaffold**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-07-17T16:35:00Z
- **Completed:** 2026-07-17T16:56:00Z
- **Tasks:** 3
- **Files modified:** 12

## Accomplishments

- Installed torch, numpy, safetensors, zstandard, scipy, tqdm into `.venv` and Stockfish 18 via Homebrew
- Built `nnue_format/schema.py` + `io.py` with fail-loud arch/shape validation and numpy safetensors round-trip
- Built `training/mps_gate.py` with `select_device()` and `cpu_vs_mps_parity_check()` using a local sanity model (no `training.model` import)
- Scaffolded `tests/training/` with torch pytest marker; all 7 training tests pass; main suite (238 tests) unaffected

## Task Commits

1. **Task 1: Install training toolchain, register pytest marker, scaffold tests/training/** - `8d07fab`
2. **Task 2: nnue_format contract + roundtrip test + structural torch-leakage test** - `6df7ba6`
3. **Task 3: MPS availability gate** - `3a3218f`

**Plan metadata:** pending (docs: complete plan 04-01)

## Files Created/Modified

- `pyproject.toml` — torch marker + `pythonpath = ["."]`
- `nnue_format/schema.py` — ARCH_ID, FEATURE_SET, EXPECTED_SHAPES (D-07)
- `nnue_format/io.py` — save_net/load_net zero-torch I/O
- `training/mps_gate.py` — select_device, cpu_vs_mps_parity_check (D-09)
- `tests/training/conftest.py` — torch-skip helper convention
- `tests/training/test_*.py` — roundtrip, leakage, and MPS gate tests

## Decisions Made

- Omitted `tests/training/__init__.py` because it caused pytest to resolve `import training` to the test directory instead of the project package (see Deviations)
- Recreated `.venv` with system Python 3.14 after the committed venv pointed at a missing 3.13 interpreter

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Blocking] Omitted tests/training/__init__.py to fix package shadowing**
- **Found during:** Task 1 (pytest collection of training tests)
- **Issue:** With `tests/training/__init__.py` present, pytest prepends `tests/` to `sys.path` and `import training` resolves to the test directory, breaking all `from training.mps_gate import ...` statements
- **Fix:** Removed the empty `__init__.py`; `pytest tests/training/` still discovers and runs all tests cleanly without it
- **Files modified:** tests/training/ (no __init__.py)
- **Verification:** `pytest tests/training/ -x -q` — 7 passed

**2. [Rule 3 - Blocking] Added pythonpath and recreated broken .venv**
- **Found during:** Task 1 (dependency install + test run)
- **Issue:** `.venv/bin/python` symlinked to missing Python 3.13; pytest could not import `ance` or project packages
- **Fix:** Recreated venv with Python 3.14.6; added `pythonpath = ["."]` to pyproject.toml
- **Verification:** `pytest tests/ -q -m "not slow"` — 238 passed

---

**Total deviations:** 2 auto-fixed (2 blocking)
**Impact on plan:** Both required for tests to run; no scope change to deliverables.

## Issues Encountered

- Prior `.venv` was broken (python3.13 path missing); recreated with Python 3.14.6
- MPS is available on this machine with torch 2.13.0 (contrary to 04-RESEARCH macOS 26 regression note — parity test runs when MPS selected)

## User Setup Required

None — Stockfish installed via Homebrew; training deps installed in project `.venv`.

## Next Phase Readiness

- Plan 04-02 can build `training/model.py`, `train.py`, and `export.py` on this foundation
- `select_device()` and `nnue_format` I/O are ready for the vertical-slice smoke in 04-02

## Self-Check: PASSED

- `pytest tests/training/ -x -q` — 7 passed
- `pytest tests/ -q -m "not slow"` — 238 passed

---
*Phase: 04-offline-nnue-training-pipeline*
*Completed: 2026-07-17*
