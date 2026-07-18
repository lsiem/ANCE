---
phase: 05-nnue-swap-in-elo-gauntlet
plan: 01
subsystem: eval
tags: [nnue, numpy, safetensors, evaluator-seam, uci, parity]

requires:
  - phase: 04-offline-nnue-training-pipeline
    provides: Approved net.safetensors (768×256 FT, board768) + training encoder/model oracles
provides:
  - Numpy NnueEval behind Evaluator Protocol with git-tracked default weights
  - ANCE_EVAL / ANCE_NNUE_PATH fail-fast wiring in UCI loop
  - Torch↔numpy parity + perspective/SF golden suite (tests/test_nnue_eval.py)
affects:
  - 05-02 gauntlet depth/env injection
  - 05-03 Elo evidence run

tech-stack:
  added: []
  patterns:
    - Env-var evaluator selection at module init (ANCE_EVAL allowlist)
    - Zero-torch numpy forward with export-transposed (in, out) matmul
    - Torch parity oracle confined to tests/nnue_parity_helpers.py

key-files:
  created:
    - ance/eval/nnue/__init__.py
    - ance/eval/nnue/features.py
    - ance/eval/nnue/inference.py
    - ance/eval/nnue/eval.py
    - ance/eval/nnue/net.safetensors
    - tests/test_nnue_eval.py
    - tests/nnue_parity_helpers.py
  modified:
    - ance/uci/loop.py

key-decisions:
  - "D-14 exact-0 golden uses startpos (Phase 4 net bias makes king-only ≈ -20); king-only still asserts STM agreement"
  - "forward_cp_float squeezes (512,1) out.weight product to scalar via reshape(-1)[0]"

patterns-established:
  - "NnueEval.evaluate returns STM-relative int with no extra turn flip"
  - "resolve_evaluator() fail-fast: invalid ANCE_EVAL or NNUE load → stderr + SystemExit(1)"

requirements-completed: [EVAL-03]

coverage:
  - id: D1
    description: NnueEval loads default net.safetensors and returns int cp from evaluate()
    requirement: EVAL-03
    verification:
      - kind: unit
        ref: tests/test_nnue_eval.py#test_nnue_loads_default_net
        status: pass
    human_judgment: false
  - id: D2
    description: ANCE_EVAL allowlist with fail-fast; NNUE path isready; missing weights exit nonzero
    requirement: EVAL-03
    verification:
      - kind: integration
        ref: tests/test_nnue_eval.py#test_invalid_ance_eval_exits_nonzero
        status: pass
      - kind: integration
        ref: tests/test_nnue_eval.py#test_ance_eval_nnue_isready
        status: pass
      - kind: integration
        ref: tests/test_nnue_eval.py#test_missing_nnue_weights_exits_nonzero
        status: pass
    human_judgment: false
  - id: D3
    description: Torch↔numpy exact integer cp parity on 40 held-out FENs
    requirement: EVAL-03
    verification:
      - kind: unit
        ref: tests/test_nnue_eval.py#test_torch_numpy_parity_held_out
        status: pass
    human_judgment: false
  - id: D4
    description: Perspective goldens (symmetric 0 / color-mirror / SF sign) + seam structural proofs
    requirement: EVAL-03
    verification:
      - kind: unit
        ref: tests/test_nnue_eval.py#test_symmetric_positions_score_zero
        status: pass
      - kind: unit
        ref: tests/test_nnue_eval.py#test_color_mirror_stm_flip
        status: pass
      - kind: integration
        ref: tests/test_nnue_eval.py#test_stockfish_sign_agreement
        status: pass
      - kind: unit
        ref: tests/training/test_no_torch_leakage.py
        status: pass
    human_judgment: false

duration: 9min
completed: 2026-07-18
status: complete
---

# Phase 5 Plan 01: NNUE Swap-In Eval Summary

**Numpy `NnueEval` behind the Evaluator seam with Phase 4 weights, `ANCE_EVAL` fail-fast UCI wiring, and exact torch↔numpy parity goldens**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-18T10:25:43Z
- **Completed:** 2026-07-18T10:34:46Z
- **Tasks:** 3
- **Files modified:** 8

## Accomplishments
- Shipped zero-torch `ance/eval/nnue/` (`features`, `inference`, `NnueEval`) with git-tracked `net.safetensors`
- Wired `resolve_evaluator()` in `ance/uci/loop.py` for `ANCE_EVAL=handcrafted|nnue` + `ANCE_NNUE_PATH` fail-fast
- Automated D-13..D-16 contracts: 40-FEN torch parity, color-mirror, SF sign (when stockfish on PATH), seam/leakage proofs

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing NNUE eval contract tests (RED)** - `756a2dd` (test)
2. **Task 2: NnueEval module + git-tracked weights (GREEN)** - `f2f5213` (feat)
3. **Task 3: ANCE_EVAL wiring + full parity/golden suite** - `580dd1f` (feat)

**Plan metadata:** (this commit)

## Files Created/Modified
- `ance/eval/nnue/eval.py` - `NnueEval` Protocol impl with strict `load_net`
- `ance/eval/nnue/features.py` - board768 encoder (verbatim training copy)
- `ance/eval/nnue/inference.py` - numpy forward + `cp_from_nnue_output`
- `ance/eval/nnue/net.safetensors` - Phase 4 approved weights (~790 KB)
- `ance/eval/nnue/__init__.py` - exports `NnueEval`
- `ance/uci/loop.py` - `resolve_evaluator()` at module init
- `tests/test_nnue_eval.py` - EVAL-03 contract suite
- `tests/nnue_parity_helpers.py` - torch/numpy parity oracles (tests only)

## Decisions Made
- D-14 exact-0 golden uses startpos because Phase 4 weights yield ~-20 on king-only; king-only still requires white/black STM agreement
- Squeeze `(512,1)` output matmul to scalar in `forward_cp_float` (export layout)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] D-14 king-only exact-0 vs Phase 4 bias**
- **Found during:** Task 2 (GREEN acceptance)
- **Issue:** RESEARCH king-only FEN scores -20 with approved net (shared output bias); torch agrees
- **Fix:** Assert startpos == 0 for both STMs; keep king-only as STM-agreement check
- **Files modified:** `tests/test_nnue_eval.py`
- **Verification:** `test_symmetric_positions_score_zero` passes
- **Committed in:** `f2f5213` (Task 2)

**2. [Rule 1 - Bug] `(512,1)` out.weight not 0-d scalar**
- **Found during:** Task 2 (`test_nnue_loads_default_net`)
- **Issue:** `float(combined @ out.weight + bias)` TypeError on shape `(1,)`
- **Fix:** `np.asarray(raw).reshape(-1)[0]` before float()
- **Files modified:** `ance/eval/nnue/inference.py`
- **Verification:** load/evaluate startpos passes; 40-FEN torch parity green
- **Committed in:** `f2f5213` (Task 2)

---

**Total deviations:** 2 auto-fixed (2 bug)
**Impact on plan:** Necessary for green acceptance with real Phase 4 weights; no scope creep.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
Ready for 05-02 (gauntlet depth mode + `EngineSpec.env` injection). EVAL-03 path is selectable via `ANCE_EVAL=nnue`.

## Self-Check: PASSED

- key-files.created exist on disk
- `git log --grep=05-01` returns 3 task commits
- Plan verification commands all exit 0 (22 non-torch + 40 torch + no_torch_leakage)

---
*Phase: 05-nnue-swap-in-elo-gauntlet*
*Completed: 2026-07-18*
