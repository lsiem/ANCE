---
phase: 01-minimal-uci-engine-evaluator-seam
plan: 02
subsystem: engine-core
tags: [uci, python-chess, position-adapter, pytest, robustness]

# Dependency graph
requires:
  - phase: 01-minimal-uci-engine-evaluator-seam
    provides: "ance/ package, python -m ance entry point, non-blocking UCI reader/worker threading, Position skeleton, subprocess-driving test fixture (Plan 01-01)"
provides:
  - "Position adapter fully built: try_set_startpos/try_set_fen/try_push_uci_moves/has_no_legal_moves/is_check, all with reject-and-keep semantics on malformed input"
  - "position/ucinewgame commands wired for real, replacing no-op token skipping"
  - "Explicit setoption/ponder/ponderhit handlers (forward-compatible, D-09) instead of relying on the generic unknown-token skip"
  - "ance/debug.py stderr-only diagnostic channel toggled by debug on/off or ANCE_DEBUG"
affects: [01-03, 01-04, 01-05, 01-06]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Position.try_set_fen/try_push_uci_moves build a candidate locally first, only committing to self._board on success -- the reject-and-keep contract lives entirely inside the adapter, not in the UCI loop"
    - "has_no_legal_moves() uses is_checkmate()/is_stalemate(), not the broader is_game_over(), so non-zero-legal-move draws still route through search"
    - "Dispatch table handlers take a uniform (tokens) signature so new commands need no special-casing in main()'s loop"
    - "debug.py: module-level _enabled flag seeded from ANCE_DEBUG env var; log() is a no-op unless enabled; never touches stdout"

key-files:
  created:
    - ance/debug.py
  modified:
    - ance/board/position.py
    - ance/uci/parser.py
    - ance/uci/loop.py
    - tests/conftest.py
    - tests/test_position_command.py

key-decisions:
  - "handle_position's moves-list failure leaves the board at the just-set (valid) startpos/fen base, not the pre-command board -- matches the plan's explicit semantics for D-10 (try_push_uci_moves never partially commits, so this is still a fully-defined, non-corrupting state)."
  - "parse_position() returns None (not a raised exception) for grammar-level malformed position commands (missing startpos/fen keyword), keeping the reject path a plain conditional in handle_position rather than another try/except layer."
  - "debug logging is wired at three points (position rejection, worker start, worker stop) plus the debug-toggle event itself, so debug on is immediately observable and useful for a real hang later, not a cosmetic no-op."
  - "Test fixture explicitly strips ANCE_DEBUG from the subprocess env so the debug-off-by-default test is deterministic regardless of the developer's shell."

patterns-established:
  - "Every untrusted stdin field (FEN, move list) crosses into board state through exactly one boundary: a candidate built in a local variable, swapped into self._board only on full success."

requirements-completed: [UCI-03, UCI-04, UCI-05, SRCH-01]

coverage:
  - id: D1
    description: "Position adapter: try_set_startpos/try_set_fen/try_push_uci_moves/has_no_legal_moves/is_check, all reject-and-keep on malformed input"
    requirement: "UCI-04"
    verification:
      - kind: unit
        ref: "tests/test_position_command.py#test_startpos_with_moves_sets_correct_turn_and_fen"
        status: pass
      - kind: unit
        ref: "tests/test_position_command.py#test_has_no_legal_moves_true_for_checkmate"
        status: pass
      - kind: unit
        ref: "tests/test_position_command.py#test_has_no_legal_moves_false_for_normal_position"
        status: pass
      - kind: unit
        ref: "tests/test_position_command.py#test_try_set_fen_rejects_malformed_fen_and_leaves_board_untouched"
        status: pass
      - kind: unit
        ref: "tests/test_position_command.py#test_try_push_uci_moves_rejects_illegal_move_and_leaves_board_untouched"
        status: pass
    human_judgment: false
  - id: D2
    description: "position/ucinewgame wired into the UCI loop with D-10/D-11 robustness; explicit setoption/ponder/ponderhit no-op handlers"
    requirement: "UCI-05"
    verification:
      - kind: integration
        ref: "tests/test_position_command.py#test_malformed_fen_rejected_board_unchanged"
        status: pass
      - kind: integration
        ref: "tests/test_position_command.py#test_unknown_leading_token_ignored"
        status: pass
      - kind: integration
        ref: "tests/test_position_command.py#test_ucinewgame_resets_board_to_startpos"
        status: pass
      - kind: integration
        ref: "tests/test_position_command.py#test_setoption_consumed_without_side_effects"
        status: pass
      - kind: integration
        ref: "tests/test_position_command.py#test_ponder_and_ponderhit_are_noop"
        status: pass
      - kind: manual_procedural
        ref: "printf 'uci\\nisready\\nposition startpos moves e2e4\\nposition fen garbage\\ngo depth 1\\nquit\\n' | .venv/bin/python -m ance"
        status: pass
    human_judgment: false
  - id: D3
    description: "Stderr-only debug channel (D-18), off by default, toggled by debug on/off or ANCE_DEBUG, never touching stdout"
    requirement: "SRCH-01"
    verification:
      - kind: integration
        ref: "tests/test_position_command.py#test_debug_off_by_default_no_stderr_output"
        status: pass
      - kind: integration
        ref: "tests/test_position_command.py#test_debug_on_enables_stderr_logging"
        status: pass
    human_judgment: false

# Metrics
duration: 9min
completed: 2026-07-05
status: complete
---

# Phase 1 Plan 2: Position Adapter & Robust Command Wiring Summary

**Narrow `Position` adapter over `chess.Board` with a strict local-candidate-first commit boundary, wired into `position`/`ucinewgame`/`setoption`/`ponder` handling and a stderr-only debug channel — malformed FEN or illegal moves never touch the live board.**

## Performance

- **Duration:** 9 min
- **Started:** 2026-07-05T22:08:00+02:00 (approx)
- **Completed:** 2026-07-05T22:17:07+02:00
- **Tasks:** 3
- **Files modified:** 6 (1 created + 5 modified)

## Accomplishments

- `Position` now supports `try_set_startpos()`, `try_set_fen()`, `try_push_uci_moves()`, `has_no_legal_moves()`, and `is_check()` — every untrusted-input path builds a candidate board locally and only commits on full success (D-10).
- `ance/uci/parser.py::parse_position()` splits `startpos`/`fen [...]` from an optional `moves` clause into a typed `PositionCommand`.
- `ance/uci/loop.py` gained real `handle_position`/`handle_ucinewgame` handlers plus explicit `handle_setoption`/`handle_ponder` no-ops (cross-AI review finding — explicit handlers rather than relying on the generic D-11 unknown-token skip).
- `ance/debug.py` implements the D-18 stderr-only diagnostic channel, off by default, toggled via `debug on/off` or `ANCE_DEBUG`; wired at position-rejection and worker-start/stop points so it is genuinely useful for future hang diagnosis.
- A full TDD RED→GREEN cycle per task, 15/15 tests green, plus a manual pipe verification matching the plan's `<verification>` block exactly.

## Task Commits

Each task followed the RED → GREEN TDD cycle:

1. **Task 1: Position adapter with startpos/moves and terminal detection**
   - `5d4ab9d` (test, RED) — `test(01-02): add failing tests for Position adapter startpos/fen/moves`
   - `5eb6d9f` (feat, GREEN) — `feat(01-02): implement Position adapter startpos/fen/moves/terminal detection`
2. **Task 2: Wire position/ucinewgame into the UCI loop with D-10/D-11 robustness**
   - `c893f93` (test, RED) — `test(01-02): add failing tests for position/ucinewgame/setoption wiring`
   - `968f96c` (feat, GREEN) — `feat(01-02): wire position/ucinewgame/setoption/ponder into the UCI loop`
3. **Task 3: Stderr-only debug logging channel**
   - `ecb88c2` (test, RED) — `test(01-02): add failing tests for stderr-only debug channel`
   - `37c1385` (feat, GREEN) — `feat(01-02): add stderr-only debug channel wired into the UCI loop`

**Plan metadata:** committed separately per the final-commit step below.

## Files Created/Modified

- `ance/board/position.py` - `try_set_startpos`/`try_set_fen`/`try_push_uci_moves`/`has_no_legal_moves`/`is_check`
- `ance/uci/parser.py` - `parse_position()` + `PositionCommand` dataclass
- `ance/uci/loop.py` - `handle_position`/`handle_ucinewgame`/`handle_setoption`/`handle_ponder`/`handle_debug`, uniform-tokens dispatch table, debug.log() call sites
- `ance/debug.py` - stderr-only diagnostic channel (D-18), new file
- `tests/conftest.py` - stderr reader/queue on `EngineProcess`, `has_stderr_output()`, `send_lines()` helper, ANCE_DEBUG stripped from subprocess env
- `tests/test_position_command.py` - unit tests for `Position` + integration tests for position/ucinewgame/setoption/ponder/debug, new file

## Decisions Made

- Extended Task 1's unit test coverage beyond the plan's 3 named tests with two extra reject-and-keep tests (`test_try_set_fen_rejects_malformed_fen_and_leaves_board_untouched`, `test_try_push_uci_moves_rejects_illegal_move_and_leaves_board_untouched`) — these directly exercise D-10 at the unit level, complementing the plan's Task 2 integration-level proof, at negligible extra cost.
- `parse_position()` returns `None` (not a raised exception) for a grammar-malformed `position` command (no `startpos`/`fen` keyword) — kept the reject path a plain conditional rather than adding another exception layer next to `Position`'s own `ValueError` handling.
- `handle_position`'s moves-list failure leaves the board at the just-set (valid) startpos/fen base rather than the pre-command board, matching the plan's explicit wording for this case; `Position.try_push_uci_moves` never partially commits, so this remains a fully-defined, non-corrupting state.
- Debug logging fires at four points (the `debug on/off` toggle itself, position-command rejection, worker start, worker stop) so `debug on` is immediately observable on stderr and the channel is useful for diagnosing a real hang later, per the plan's intent — not a cosmetic no-op toggle.
- Test fixture explicitly strips `ANCE_DEBUG` from the subprocess environment (rather than relying on the ambient shell not having it set) so the "debug off by default" test is deterministic.

## Deviations from Plan

None - plan executed exactly as written. All `must_haves.truths` and threat-model mitigations (T-01-03, T-01-04, T-01-05) are satisfied by the implementation as built; the two extra unit tests noted above are additive test coverage, not a scope or architecture change.

## Issues Encountered

None - RED phases failed for the expected reason in each task (Task 1: `AttributeError` on missing methods; Task 3: `has_stderr_output()` correctly returned `False` before the debug channel existed). Task 2's RED phase surfaced an expected nuance: 4 of the 5 new integration tests already passed before any new code was written, because the existing D-11 generic unknown-token skip incidentally satisfies "unknown/setoption/ponder don't crash and readyok still arrives promptly." This is the exact situation the plan's own `<action>` text anticipated ("no change needed there, only a test proving it") — the one test that genuinely required new code (`test_malformed_fen_rejected_board_unchanged`) failed as expected and was made to pass by the real `handle_position`/`parse_position` implementation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `Position` is now a complete, hardened adapter; Plan 01-03's negamax substrate can call `try_push_uci_moves`/`has_no_legal_moves`/`is_check`/`legal_moves`/`copy` directly with no further adapter changes needed.
- `handle_go`'s worker is still the Plan 01-01 placeholder (`_trivial_bestmove`, picks the first legal move) — this is Plan 01-03's explicit scope (fixed-depth negamax + Evaluator seam), not a stub introduced or masked by this plan.
- `go`'s sub-parameters (`depth`, `movetime`, etc.) are still unparsed — `ance/uci/parser.py::parse_go()`/`GoCommand` is Plan 01-03 scope per the phase artifact table; this plan's tests send `go depth 1` only to exercise the trivial worker's response cadence, not to assert depth is honored.
- The stderr debug channel is wired at generically useful points (position rejection, worker lifecycle) and ready for Plan 01-03 to add further log points (e.g. node counts, stop-flag polling) without any interface changes.

## Known Stubs

- `ance/uci/loop.py::_trivial_bestmove` still picks `moves[0]` with no evaluator or negamax call — unchanged from Plan 01-01, explicitly resolved by Plan 01-03. Not a stub introduced by this plan.

---
*Phase: 01-minimal-uci-engine-evaluator-seam*
*Completed: 2026-07-05*

## Self-Check: PASSED

All created/modified files verified present on disk: `ance/debug.py`, `ance/board/position.py`, `ance/uci/parser.py`, `ance/uci/loop.py`, `tests/conftest.py`, `tests/test_position_command.py`. All commit hashes verified present in `git log`: `5d4ab9d`, `5eb6d9f`, `c893f93`, `968f96c`, `ecb88c2`, `37c1385`. Full suite: `.venv/bin/python -m pytest -q` -> 15 passed. Manual pipe verification matches plan `<verification>` block exactly (malformed FEN rejected via `info string`, subsequent `bestmove` consistent with the last valid position, clean exit code 0).
