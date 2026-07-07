---
phase: 01-minimal-uci-engine-evaluator-seam
plan: 04
subsystem: eval
tags: [chess, evaluation, piece-square-tables, simplified-evaluation-function, python-chess]

# Dependency graph
requires:
  - phase: 01-minimal-uci-engine-evaluator-seam (Plan 01-03)
    provides: the Evaluator seam (ance/eval/base.py), the fixed-depth negamax search (ance/search/negamax.py), and the non-blocking UCI go/stop/quit wiring (ance/uci/loop.py) that this plan swaps its evaluator into
provides:
  - HandcraftedEval, the engine's real M1 evaluator (material + Simplified Evaluation Function PSTs + discrete king mg/eg table switch + mobility + bishop-pair + tempo + pawn-structure terms), wired in as the live default evaluator
  - ance/eval/tables.py: the pinned, transcribed Simplified Evaluation Function piece-square tables
  - A structural re-proof that ance/search/negamax.py never references a concrete evaluator class, now with two real evaluators (MaterialEval, HandcraftedEval)
  - A re-verified sub-second bare-go benchmark with the real, costlier evaluator in the hot path
affects: [phase 05 (NNUE training/quantization), any future evaluator swap]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "White-relative internal composition with a single sign flip at the end of evaluate() (D-07)"
    - "Discrete (non-tapered) game-phase switch via a material threshold, not tapering"
    - "Defensive null-move guard on board.is_check() before probing opponent mobility"

key-files:
  created: [ance/eval/tables.py, ance/eval/handcrafted.py]
  modified: [ance/uci/loop.py, tests/test_eval_seam.py, tests/test_go_bestmove.py]

key-decisions:
  - "DEFAULT_DEPTH stayed at 3 (ance/search/negamax.py untouched) -- the post-wiring bare-go benchmark measured ~0.53s wall-clock with HandcraftedEval in the hot path, comfortably under the 1.0s bound, so no retune was needed"
  - "Positional terms (mobility, bishop pair, pawn structure) are computed white-relative internally and combined with the material+PST subtotal before a single sign flip by board.turn, per D-07; tempo is added after that flip since it is inherently side-to-move relative"
  - "Pawn-structure file counts use int.bit_count() over bitboard masks (not a bin(...).count() string round-trip) per the round-2 cross-AI review's LOW performance finding"

patterns-established:
  - "Positional evaluation terms live as small, independently testable free functions (_bishop_pair_term, _pawn_structure_term, _mobility_term) composed inside HandcraftedEval.evaluate(), keeping the class itself thin"

requirements-completed: [EVAL-02]

coverage:
  - id: D1
    description: "Pinned Simplified Evaluation Function piece-square tables transcribed correctly (orientation-verified via pinned reference cells)"
    requirement: "EVAL-02"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_pst_tables_have_64_entries"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_pawn_pst_is_zero_on_first_and_last_rank"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_pst_reference_cells_match_pinned_appendix"
        status: pass
    human_judgment: false
  - id: D2
    description: "Material+PST helper with a discrete middlegame/endgame king-table switch (threshold-based, not tapered)"
    requirement: "EVAL-02"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_material_and_pst_helper_symmetric_at_startpos"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_king_table_switches_to_endgame_below_threshold"
        status: pass
    human_judgment: false
  - id: D3
    description: "Mobility, bishop-pair, tempo, and pawn-structure positional terms added to HandcraftedEval, all side-to-move relative"
    requirement: "EVAL-02"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_startpos_evaluates_to_exact_tempo_bonus"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_bishop_pair_bonus_applied"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_doubled_and_isolated_pawn_penalty"
        status: pass
      - kind: unit
        ref: "tests/test_eval_seam.py#test_mobility_term_rewards_more_legal_moves"
        status: pass
    human_judgment: false
  - id: D4
    description: "Mobility term never crashes or evaluates an illegal null move when the side to move is in check"
    requirement: "EVAL-02"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_mobility_term_no_crash_when_side_to_move_in_check"
        status: pass
    human_judgment: false
  - id: D5
    description: "HandcraftedEval() wired in as the engine's live default evaluator, replacing MaterialEval(); negamax.py remains free of any concrete evaluator reference"
    requirement: "EVAL-02"
    verification:
      - kind: unit
        ref: "tests/test_eval_seam.py#test_evaluator_swap_handcrafted_vs_material_no_negamax_change"
        status: pass
      - kind: other
        ref: "grep -v '^#' ance/search/negamax.py | grep -cE \"HandcraftedEval|MaterialEval|NaiveEval\" -> 0"
        status: pass
    human_judgment: false
  - id: D6
    description: "Bare-go sub-second benchmark re-verified with the real HandcraftedEval wired in (not just the cheap bootstrap MaterialEval from Plan 01-03)"
    requirement: "EVAL-02"
    verification:
      - kind: e2e
        ref: "tests/test_go_bestmove.py#test_bare_go_completes_under_a_second_with_handcrafted_eval"
        status: pass
      - kind: manual_procedural
        ref: "piped `go` via `python -m ance` subprocess, measured ~0.53s wall-clock across 4 runs"
        status: pass
    human_judgment: false

duration: 20min
completed: 2026-07-07
status: complete
---

# Phase 1 Plan 4: Handcrafted evaluator (Simplified Evaluation Function + positional terms) Summary

**`HandcraftedEval` -- Michniewski Simplified Evaluation Function material+PSTs with a discrete king-table phase switch, plus mobility/bishop-pair/tempo/pawn-structure terms -- replaces the bootstrap `MaterialEval` as ANCE's live default evaluator, with zero structural changes to `ance/search/negamax.py`.**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-07-07T12:55:00+02:00 (approx.)
- **Completed:** 2026-07-07T13:08:12+02:00
- **Tasks:** 3
- **Files modified:** 5 (2 created, 3 modified)

## Accomplishments

- Transcribed the pinned Michniewski Simplified Evaluation Function piece-square tables (`ance/eval/tables.py`) from 01-RESEARCH.md's appendix, with orientation verified against the pinned reference cells (catches a reversed-row transcription error loudly)
- Implemented material+PST scoring with a discrete (threshold-based, non-tapered) middlegame/endgame king-table switch (`ENDGAME_MATERIAL_THRESHOLD = 2600`)
- Added mobility (null-move-guarded against in-check positions), bishop-pair, tempo, and doubled/isolated pawn-structure terms, all composed white-relative with a single sign flip at the end of `evaluate()` (D-07)
- Wired `HandcraftedEval()` in as the engine's real default evaluator in `ance/uci/loop.py`, with a structural test re-proving `ance/search/negamax.py` never references a concrete evaluator class
- Re-benchmarked the bare-`go` sub-second requirement with the real, costlier evaluator in the hot path (measured ~0.53s, well under the 1.0s bound) -- `ance/search/negamax.py`'s `DEFAULT_DEPTH` needed no retune

## Task Commits

Each task followed the RED (failing test) / GREEN (implementation) TDD cycle with separate commits:

1. **Task 1: Pinned SEF piece-square tables**
   - `9de7c28` (test) - failing tests for PST structure/orientation/pinned-cell values
   - `a3a5869` (feat) - `ance/eval/tables.py` with all seven tables
2. **Task 2: Material+PST scoring with discrete king-table switch**
   - `535ceb4` (test) - failing tests for `_material_and_pst`/`_is_endgame`
   - `a748ca3` (feat) - `ance/eval/handcrafted.py` with `HandcraftedEval`, `_is_endgame`, `_material_and_pst`
3. **Task 3: Positional terms, wiring, swap-seam reinforcement, performance re-benchmark**
   - `33659c8` (test) - failing tests for positional terms, in-check mobility guard, swap-seam, and the post-wiring benchmark
   - `0710bbc` (feat) - positional terms added, `HandcraftedEval()` wired into `ance/uci/loop.py` as the live default

**Plan metadata:** committed alongside this SUMMARY.

## Files Created/Modified

- `ance/eval/tables.py` - Pinned Simplified Evaluation Function PSTs: `PAWN_PST`, `KNIGHT_PST`, `BISHOP_PST`, `ROOK_PST`, `QUEEN_PST`, `KING_MG_PST`, `KING_EG_PST`
- `ance/eval/handcrafted.py` - `HandcraftedEval` (material+PST + positional terms), `ENDGAME_MATERIAL_THRESHOLD`, `TEMPO_BONUS`, `BISHOP_PAIR_BONUS`, `MOBILITY_WEIGHT`, `DOUBLED_PAWN_PENALTY`, `ISOLATED_PAWN_PENALTY`
- `ance/uci/loop.py` - Constructs `HandcraftedEval()` as the live default evaluator instead of `MaterialEval()`
- `tests/test_eval_seam.py` - Extended with Task 1-3 tests (PST structure/values, material+PST helper, king-table switch, positional terms, in-check mobility guard, swap-seam reinforcement)
- `tests/test_go_bestmove.py` - Extended with the post-wiring sub-second bare-`go` re-benchmark

## Decisions Made

- `DEFAULT_DEPTH` in `ance/search/negamax.py` stayed at `3` -- the post-wiring benchmark measured ~0.53s wall-clock across repeated runs, well under the 1.0s bound, so `negamax.py` required zero edits this plan (the plan's own allowance to tune it down to `2` was not needed)
- Positional terms are computed white-relative internally, matching the material+PST subtotal's convention, with a single sign flip by `board.turn`; tempo is added after that flip since it is inherently side-to-move relative by definition
- Pawn-structure file counts use `int.bit_count()` over bitboard masks (`board.pieces_mask`), not a `bin(...).count()` string round-trip, per the round-2 cross-AI review's LOW-severity performance finding

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Mobility-term test fixture was confounded by extra material**
- **Found during:** Task 3 (writing `test_mobility_term_rewards_more_legal_moves`)
- **Issue:** The initial test FEN pair boxed a queen in with two extra own pawns to reduce its mobility, but those two pawns' material (200cp) outweighed the mobility-term delta, making the "more legal moves scores higher" assertion fail even though the mobility term itself was correctly implemented
- **Fix:** Rewrote the fixture to hold material exactly constant (one queen, two kings, no pawns) and vary only the queen's square (centralized vs. cornered), isolating the mobility effect
- **Files modified:** `tests/test_eval_seam.py`
- **Verification:** `pytest tests/test_eval_seam.py -k mobility -q` passes; `_mobility_term`'s implementation was not changed
- **Committed in:** `0710bbc` (Task 3 feat commit)

---

**Total deviations:** 1 auto-fixed (1 bug, test-only)
**Impact on plan:** No production code was affected; the fix corrected a test-fixture confound discovered while implementing the acceptance criteria. No scope creep.

## Issues Encountered

None beyond the deviation above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `HandcraftedEval` is EVAL-02's real M1 baseline, fully wired in and covered by tests spot-checking it against the published Simplified Evaluation Function reference values
- The swap-seam is reinforced with two real evaluators (`MaterialEval`, `HandcraftedEval`) plus the original bootstrap `NaiveEval` for tie-break testing -- `ance/search/negamax.py` remains untouched structurally, ready for Phase 5's NNUE evaluator to swap in the same way
- The bare-go sub-second benchmark has real headroom (~0.53s vs. 1.0s bound) with the costlier evaluator, so no immediate performance pressure carries into Plan 01-05
- Plan 01-05 (random-mover gauntlet tooling) can proceed; no blockers

---
*Phase: 01-minimal-uci-engine-evaluator-seam*
*Completed: 2026-07-07*

## Self-Check: PASSED

- All created/modified files verified present on disk (`ance/eval/tables.py`, `ance/eval/handcrafted.py`, `ance/uci/loop.py`, `tests/test_eval_seam.py`, `tests/test_go_bestmove.py`, this SUMMARY.md)
- All 6 task commits (`9de7c28`, `a3a5869`, `535ceb4`, `a748ca3`, `33659c8`, `0710bbc`) verified present in `git log`
- Full suite re-run: `.venv/bin/python -m pytest -q` -> 48 passed
- Plan-level verification re-run: `.venv/bin/python -m pytest tests/test_eval_seam.py tests/test_go_bestmove.py -q` -> 33 passed
- `grep -v '^#' ance/search/negamax.py | grep -cE "HandcraftedEval|MaterialEval|NaiveEval"` -> `0`
- Manual piped `go depth 3` and bare `go` both returned exactly one `bestmove` line, engine wired to `HandcraftedEval`
