---
status: complete
phase: 01-minimal-uci-engine-evaluator-seam
source: [01-01-SUMMARY.md, 01-02-SUMMARY.md, 01-03-SUMMARY.md, 01-04-SUMMARY.md, 01-05-SUMMARY.md, 01-06-SUMMARY.md]
started: 2026-07-08T13:46:31Z
updated: 2026-07-08T13:49:59Z
---

## Current Test

[testing complete]

## Tests

### 1. Cold Start Smoke Test
expected: `python -m ance` boots from scratch and completes the UCI handshake (uci → uciok, isready → readyok) with no errors.
result: pass
source: automated
note: Verified this session — clean handshake via `python -m ance`; full fast suite green (51 passed).

### 2. UCI loop never hangs (go always returns bestmove)
expected: Every `go` (bare, depth, movetime, wtime/btime) returns exactly one `bestmove` line and never blocks the reader; `isready`/`quit` answered even during search.
result: pass
source: automated
note: tests/test_go_bestmove.py + test_uci_handshake.py green; session tests confirm go wtime/btime and go movetime both return promptly (only `go infinite` waits for stop, by design).

### 3. Beats a uniformly-random mover (TOOL-02)
expected: Self-play gauntlet vs a seeded RandomMover — 0 losses always, ≥70% wins, every non-win a draw.
result: pass
source: automated
note: Slow gauntlet re-run this session — 1 passed (~30s): 0 losses, ≥70% wins at depth 2.

### 4. Evaluator seam is swappable (EVAL-02)
expected: Search routes every leaf through evaluate(position)->cp with no concrete evaluator class referenced in negamax; HandcraftedEval is the live default and can be swapped without touching search.
result: pass
source: automated
note: tests/test_eval_seam.py structural proof green; HandcraftedEval wired as default, bare-go ~0.53s < 1.0s bound.

### 5. Plays a full legal game in a real GUI (TOOL-01)
expected: In En Croissant, both players = ANCE, real time control (not "Unlimited"), ANCE plays a complete legal game to a natural result with no hang/crash/illegal move.
result: pass
note: User watched ANCE-vs-ANCE play a full clean game live in En Croissant (mac-native GUI, 2026-07-08) — the literal-GUI TOOL-01 confirmation Cute Chess could not provide on macOS.

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
