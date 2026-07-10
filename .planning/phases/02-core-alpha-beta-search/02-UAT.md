---
status: complete
phase: 02-core-alpha-beta-search
source: 02-01-SUMMARY.md, 02-02-SUMMARY.md, 02-03-SUMMARY.md, 02-04-SUMMARY.md, 02-05-SUMMARY.md, 02-06-SUMMARY.md
started: 2026-07-08T19:50:00Z
updated: 2026-07-10T15:15:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Search thinking is visible (info lines + bestmove)
expected: Piped UCI session (uci/isready/position startpos/go) emits one `info depth <d> score cp <x> nodes <n> nps <n> pv <moves>` line per completed depth, then `bestmove` within ~2s; pv[0] of last info line matches bestmove
result: pass

### 2. go infinite deepens until stop
expected: `go infinite` emits info lines with increasing depth (no idle hang); sending `stop` promptly yields `bestmove` from the last completed depth — the En Croissant "Unlimited" fix
result: pass
note: Claude-run piped test — depths 1-4 emitted, stop→bestmove latency 0.02s, pv[0]==bestmove, clean exit. Observation: PV is only ever 1 move long (root-only PV tracking) — spec-minimal, noted for Phase 3

### 3. Tactical soundness (fast pytest suite)
expected: Fast tactical tests pass — mate-in-1 and mate-in-2 found, hanging queen not left en prise, knight fork found, horizon capture not misplayed (quiescence working)
result: pass
note: Claude-run — 5/5 passed in 0.32s

### 4. Mate score wire format (full moves)
expected: A mate-in-2 position reports `score mate 2` (full moves per UCI spec / D-18) — NOT `mate 3` (plies). Being mated shows a negative mate score. (Known filed gap: protocol.py currently emits plies)
result: pass
source: automated
verification: ".venv/bin/python -m pytest tests/test_uci_info.py tests/test_quiescence.py -q — 18 passed"

### 5. Draw handling in search
expected: ID/draw-detection tests pass — engine scores twofold repetition / 50-move / insufficient material as 0 inside search and does not repeat a won position (takes the winning line instead of shuffling)
result: pass
note: Claude-run — 6/6 passed (twofold path, game-history repetition, 50-move, insufficient material, mate-beats-draw, ID abort retention)

### 6. Depth-4 random-mover gauntlet (slow)
expected: Gauntlet at GAUNTLET_SEARCH_DEPTH=4 completes with losses == 0 (hard invariant). Note: reduced to 3 games (~8-10 min/game measured); marked "not run" in 02-05 summary — needs an actual run
result: pass
note: Claude-run 2026-07-10 — test_ance_never_loses_and_wins_majority_vs_random_mover PASSED in 26:06 (3 games, depth 4, HandcraftedEval); losses==0 invariant held

### 7. Depth-vs-depth mini-match (slow)
expected: depth_vs_depth_match harness: deeper ANCE scores >= 50% vs shallower ANCE ("deeper never plays measurably worse"). Marked "not run" in 02-05 summary — needs an actual run
result: pass
note: Claude-run 2026-07-10 — test_deeper_search_scores_at_least_fifty_percent PASSED in 2:25:23 (5 games); deeper side scored >= 50%

### 8. Watched En Croissant validation game (D-19)
expected: ANCE loads in En Croissant, plays a full legal game at a fixed time-per-move preset with live info depth/score/pv visible in the GUI; game reaches a natural result. Separately, "Unlimited" mode now visibly deepens instead of hanging
result: pass
note: User-confirmed 2026-07-10

## Summary

total: 8
passed: 8
issues: 0
pending: 0
skipped: 0
blocked: 0

## Gaps

[none]
