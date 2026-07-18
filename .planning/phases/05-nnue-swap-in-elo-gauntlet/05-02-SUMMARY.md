---
phase: 05-nnue-swap-in-elo-gauntlet
plan: 02
subsystem: tools
tags: [gauntlet, fixed-depth, elo, wilson-ci, engine-env, tool-04]

requires:
  - phase: 05-nnue-swap-in-elo-gauntlet
    provides: NnueEval + ANCE_EVAL UCI wiring from Plan 05-01
  - phase: 03-uci-hardening-strength-measurement
    provides: Phase 3 clock gauntlet harness to extend
provides:
  - Fixed-depth gauntlet mode via Limit(depth=N) / --depth
  - EngineSpec.env merged at popen_uci for ANCE_EVAL injection
  - Logistic Elo + Wilson CI fields in aggregate report
  - D-04 automated search-config / env-diff proof
affects:
  - 05-03 TOOL-04 ≥1000-game Elo evidence run

tech-stack:
  added: []
  patterns:
    - Fixed-depth Limit(depth=N) bypasses clock forfeit path
    - Per-engine env merge {**os.environ, **spec.env} at popen_uci
    - Logistic Elo from score_rate via -400*log10(1/p-1)

key-files:
  created:
    - tests/test_nnue_gauntlet_depth.py
  modified:
    - ance/tools/gauntlet.py
    - tests/test_gauntlet_harness.py
    - tests/test_nnue_eval.py

key-decisions:
  - "Acceptance search depth N=3 for TOOL-04 (05-RESEARCH discretion)"
  - "Phase 3 popen_uci mocks accept **kwargs so env= kwarg does not break clock tests"

patterns-established:
  - "Checkpoint parameters record mode/search_depth and per-engine env"
  - "Aggregate always includes elo / elo_ci_low / elo_ci_high from Wilson bounds"

requirements-completed: [TOOL-04]

coverage:
  - id: D1
    description: Fixed-depth play uses Limit(depth=N) with no clock fields
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_nnue_gauntlet_depth.py#test_fixed_depth_uses_limit_depth_not_clocks
        status: pass
    human_judgment: false
  - id: D2
    description: EngineSpec.env merged at popen_uci with distinct ANCE_EVAL values
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_nnue_gauntlet_depth.py#test_run_gauntlet_merges_distinct_engine_envs
        status: pass
    human_judgment: false
  - id: D3
    description: Checkpoint parameters record fixed_depth mode and env-only ANCE_EVAL diff
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_nnue_gauntlet_depth.py#test_checkpoint_parameters_record_depth_mode_and_env_diff
        status: pass
    human_judgment: false
  - id: D4
    description: Aggregate report includes logistic Elo and Wilson-derived CI bounds
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_nnue_gauntlet_depth.py#test_aggregate_includes_logistic_elo_and_wilson_ci_bounds
        status: pass
    human_judgment: false
  - id: D5
    description: CLI --depth sets search_depth; omitting depth preserves clock limits
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_nnue_gauntlet_depth.py#test_cli_depth_sets_search_depth_and_ignores_clock_tc
        status: pass
      - kind: unit
        ref: tests/test_nnue_gauntlet_depth.py#test_omitting_search_depth_preserves_clock_limits
        status: pass
    human_judgment: false
  - id: D6
    description: D-04 search modules omit concrete evals; gauntlet env differs only by ANCE_EVAL
    requirement: TOOL-04
    verification:
      - kind: unit
        ref: tests/test_nnue_eval.py#test_search_config_unchanged_by_eval_env
        status: pass
    human_judgment: false

duration: 10min
completed: 2026-07-18
status: complete
---

# Phase 05 Plan 02: Gauntlet Depth/Env/Elo Summary

**Fixed-depth gauntlet with per-engine `ANCE_EVAL` injection and logistic Elo+Wilson CI — TOOL-04 harness ready for the overnight evidence run**

## Performance

- **Duration:** 10 min
- **Started:** 2026-07-18T10:38:01Z
- **Completed:** 2026-07-18T10:48:18Z
- **Tasks:** 3
- **Files modified:** 4

## Accomplishments

- Gauntlet supports `--depth N` / `search_depth` so both engines get `Limit(depth=N)` with no clock forfeit path (D-11)
- `EngineSpec.env` merges into child env at `popen_uci` so NNUE vs HC differs only by `ANCE_EVAL` (D-04)
- Aggregate report adds `elo`, `elo_ci_low`, `elo_ci_high` via logistic transform of score rate and Wilson bounds (D-12 prep)
- Structural + parameter-diff tests prove search modules stay eval-agnostic

## Task Commits

Each task was committed atomically:

1. **Task 1: Failing gauntlet depth + env contract tests (RED)** - `cb80d74` (test)
2. **Task 2: Gauntlet fixed-depth mode + EngineSpec.env + Elo reporting (GREEN)** - `4edf048` (feat)
3. **Task 3: Search-config diff verification (D-04)** - `cf70c78` (feat)

**Plan metadata:** (this commit)

_Note: TDD Tasks 1–2 used RED → GREEN; Task 3 was auto with structural tests._

## Files Created/Modified

- `tests/test_nnue_gauntlet_depth.py` - Depth/env/checkpoint/Elo/CLI contract tests
- `ance/tools/gauntlet.py` - `EngineSpec.env`, `search_depth`, `score_rate_to_elo`, `--depth`
- `tests/test_gauntlet_harness.py` - `popen_uci` mocks accept `**kwargs` for env merge
- `tests/test_nnue_eval.py` - `test_search_config_unchanged_by_eval_env` + slow smoke stub

## Decisions Made

- Recommend **depth N=3** for Plan 05-03 acceptance (05-RESEARCH wall-clock projection)
- Updated Phase 3 harness mocks to accept `env=` kwargs (required after `popen_uci` env merge)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical] Phase 3 popen_uci mocks needed `**kwargs`**
- **Found during:** Task 2 (GREEN)
- **Issue:** Passing `env=` to `popen_uci` broke `lambda argv:` mocks in `test_gauntlet_harness.py`
- **Fix:** Changed mocks to `lambda argv, **kwargs: ...`
- **Files modified:** `tests/test_gauntlet_harness.py`
- **Verification:** `pytest tests/test_gauntlet_harness.py -m "not slow" -q` passes
- **Committed in:** `4edf048` (Task 2)

---

**Total deviations:** 1 auto-fixed (1 missing critical)
**Impact on plan:** Necessary for Phase 3 regression green; no scope creep.

## Issues Encountered

None

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Harness ready for Plan 05-03 ≥1000-game fixed-depth evidence at depth 3
- Example: `ANCE_EVAL` via EngineSpec env on identical `python -m ance` argv; `--depth 3 --games 1000`

## Verification Results

- `pytest tests/test_nnue_gauntlet_depth.py -x -q` — pass (6 tests)
- `pytest tests/test_gauntlet_harness.py -m "not slow" -x -q` — pass
- `pytest -m "not slow" -q` — **335 passed**, 7 deselected
- Optional 2-game depth-3 smoke — not run locally (Plan 05-03 owns evidence)

## Self-Check: PASSED

- [x] key-files exist on disk
- [x] `git log --grep=05-02` shows ≥1 commit
- [x] Task acceptance criteria verified
- [x] Plan-level verification commands green (non-slow lane)

---
*Phase: 05-nnue-swap-in-elo-gauntlet*
*Completed: 2026-07-18*
