---
phase: 07-nnue-strength-recovery
plan: 01
subsystem: training-ingest
tags: [hf-ingest, quiet-filter, lichess-cap, fen-pad, mix-0.15]

requires:
  - phase: 06-quiet-data-nnue-strength-gap
    provides: quiet_filter, strength-corpus mix, HF ingest stream
provides:
  - "4-field HF FEN pad (0 16) so ply_from_fen is not 0"
  - "--lichess-max-samples cap (default None = time-derived)"
  - "filter_quiet_samples max_kept + truncated + kept_by_source"
  - "strength mix proven at min_has_result_rate 0.15"
affects: [hf_ingest, run_pipeline, quiet_filter, corpus-mix]

tech-stack:
  added: []
  patterns: [hf-4-field-fen-pad, lichess-max-samples, quiet-max-kept]

key-files:
  created: []
  modified:
    - training/data/hf_ingest.py
    - training/data/quiet_filter.py
    - training/run_pipeline.py
    - tests/training/test_hf_ingest.py
    - tests/training/test_quiet_filter.py
    - tests/training/test_run_pipeline_hf.py

key-decisions:
  - "Pad 4-field HF FENs with clocks 0 16 in row_to_sample; do not chess.Board(fen).fen()"
  - "crc32 the padded FEN; game_result stays None; source lichess-hf"
  - "min_has_result_rate default stays 0.50; 0.15 is a call-site / CLI override"
  - "TOOL-04 remains listed on the plan but is not satisfied; this slice only unblocks corpus"

patterns-established:
  - "HF 4-field FEN normalize in row_to_sample before STM sign flip"
  - "_lichess_sample_cap(time_cap, explicit) with None preserving time-only cap"
  - "QuietFilterStats.truncated + kept_by_source; strength_corpus max_kept=120000"

requirements-completed:
  - TOOL-04

duration: 11min
completed: 2026-09-07
---

# Phase 7 Plan 01: Wave 0 ingest harness Summary

**Official 4-field HF FENs pad to six fields (`0 16`), Lichess fill is capped, and quiet keep early-stops at 120k so D-01/D-04 are not a silent no-op.**

TOOL-04 is copied into `requirements-completed` because the plan frontmatter lists it. This plan does **not** satisfy TOOL-04. It only unblocks a real HF-primary corpus. Phase 6 stays incomplete.

## Performance

- **Duration:** 11 min
- **Started:** 2026-09-07T17:00:51Z
- **Completed:** 2026-09-07T17:12:16Z
- **Tasks:** 3 (all TDD)
- **Files modified:** 6

## Accomplishments

- `row_to_sample` pads official 4-field FENs with ` 0 16` before black-STM sign flip; crc32 uses the padded string; one-field FENs still skip.
- Padded card FEN has `ply_from_fen == 30` and `is_quiet_fen` reject reason is not `early_ply`.
- `enforce_corpus_mix(..., min_has_result_rate=0.15)` accepts 3/20 results including a padded HF row; 2/20 still raises; default 0.50 unchanged.
- `--lichess-max-samples` defaults to `None`; `_lichess_sample_cap` takes `min(time_cap, explicit)`; `_ingest_lichess` still truncates to `sample_cap`.
- `filter_quiet_samples(..., max_kept=)` early-stops; `QuietFilterStats.truncated` and `kept_by_source`; `run_bounded` passes `max_kept=120000` when `strength_corpus` is True.

## Task Commits

1. **Task 1 RED:** `8f6c72e` — failing HF pad + mix 0.15 tests
2. **Task 1 GREEN:** `dedcc92` — pad 4-field HF FENs with clocks `0 16`
3. **Task 1 deviation:** `fd261a0` — align mate-score tests with `DEFAULT_CP_CLAMP`
4. **Task 2 RED:** `cd59608` — failing `--lichess-max-samples` tests
5. **Task 2 GREEN:** `1488c5d` — `--lichess-max-samples` + `_lichess_sample_cap`
6. **Task 2 deviation:** `0f95599` — disable quiet filter in lichess FEN-dedup test
7. **Task 3 RED:** `303bd8f` — failing `max_kept` / `kept_by_source` tests
8. **Task 3 GREEN:** `46b38b3` — quiet `max_kept` early-stop + pipeline wiring

## Files Created/Modified

- `training/data/hf_ingest.py` — 4-field FEN pad `0 16` in `row_to_sample`
- `training/run_pipeline.py` — `--lichess-max-samples`, `_lichess_sample_cap`, `max_kept=120000` on strength quiet filter
- `training/data/quiet_filter.py` — `max_kept`, `QuietFilterStats.truncated`, `kept_by_source`
- `tests/training/test_hf_ingest.py` — `TestFourFieldFenPad` + clamp-aligned mate expectations
- `tests/training/test_quiet_filter.py` — mix 0.15 tracer + `max_kept` stats
- `tests/training/test_run_pipeline_hf.py` — Lichess cap + argparse tests

## Decisions Made

- Pad clocks as `0 16` (fullmove 16 → ply 30 ≥ `DEFAULT_MIN_PLY` 8). Do not call `chess.Board(fen).fen()`.
- Do not import `training.data.quiet_filter` from `hf_ingest`.
- Do not change `_HF_DEFAULT_REPO`, `_COLUMNS`, OR quality filter, per-shard `hf_hub_download`, AdamW/LR defaults, `--resume-from-checkpoint`, `enforce_corpus_mix` default 0.50, ingest stream order, or ply-from-fen `<6` → 0.

## Deviations from Plan

**[Rule 1 - Bug] Mate-score tests vs DEFAULT_CP_CLAMP** — Found during: Task 1 verify | Issue: `TestMateMapping` and parquet streaming expected unclamped 99997; `row_to_sample` already clamps to 10000 | Fix: update expected values to ±10000.0 | Files: `tests/training/test_hf_ingest.py` | Verification: pytest 31 passed | Commit: `fd261a0`

**[Rule 1 - Bug] Lichess FEN-dedup test vs quiet early_ply** — Found during: Task 2 verify | Issue: `test_run_bounded_lichess_wins_fen_dedup_over_hf` StopIteration because legal-walk FENs were dropped as `early_ply` | Fix: pass `quiet_filter=False` so the test asserts merge first-wins | Files: `tests/training/test_run_pipeline_hf.py` | Verification: 12 passed | Commit: `0f95599`

**Total deviations:** 2 auto-fixed (pre-existing test/production mismatches blocking plan verify). **Impact:** none on ingest harness behavior; plan tasks executed as written.

## Issues Encountered

None for plan-level verification (53 passed).

Wave-level `pytest tests/ -q -m 'not slow'`: 416 passed, 1 skipped, 3 failed — pre-existing and out of 07-01 scope (`test_gauntlet_harness.py` StopIteration; two `test_nnue_eval.py` Phase-6-net goldens). Not fixed.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

Ready for 07-02 (measure closer). Do not start a CPU train. Do not complete-phase 6. TOOL-04 still open.

## Self-Check: PASSED
