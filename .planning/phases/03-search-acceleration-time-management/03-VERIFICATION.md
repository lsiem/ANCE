---
status: passed
score: "5/5 roadmap success criteria fully verified; 5/5 requirements passed"
phase: "03-search-acceleration-time-management"
date: "2026-07-11"
requirements:
  SRCH-05: passed
  SRCH-06: passed
  SRCH-08: passed
  UCI-08: passed
  TOOL-03: passed
---

# Phase 3 Verification

## Goal

Phase 3 delivers a Zobrist transposition table, hash/capture/killer/history move ordering, real UCI clock budgeting, and a resumable fixed-opening self-play gauntlet. Actual production code, tests, git provenance, both committed evidence artifacts, and the locked Phase 3 decisions were inspected. All five roadmap criteria and all five requirements are verified. Per D-15, `cutechess-cli` is primary only when available on PATH; the python-chess external arbiter is the mandatory, completion-valid fallback. `cutechess-cli` is absent on this machine, so the completed 100-game fallback run is the accepted evidence path.

## Requirement Assessment

| Requirement | Result | Actual evidence |
|---|---|---|
| SRCH-05 | PASS | `ance/search/transposition.py` implements a fixed `2^20` Zobrist table with full-key collision checks, depth-preferred replacement, EXACT/LOWER/UPPER flags, and centralized mate-ply conversion. `ance/search/negamax.py` probes after draw/depth-zero handling, applies valid bound cutoffs, stores only completed nodes, and shares one table through child/root contexts. The 16 focused TT tests pass, including collision rejection, bound storage, mate conversion, cold reproducibility, tactical invariance, abort safety, node reduction, and `ucinewgame` clearing. |
| SRCH-06 | PASS | `ance/search/ordering.py` uses disjoint score bands in the required order: hash move, MVV-LVA captures/promotions, killer 0, killer 1, then history. Quiet beta cutoffs update two killers and bounded aging history; qsearch remains MVV-LVA-only. Deterministic D-21 testing reduces the six-position total from 838,304 to 250,005 nodes (29.82% of baseline), with every position strictly improved. |
| SRCH-08 | PASS | `ance/uci/clock.py` computes side-aware soft/hard budgets with increment credit, a 20 ms floor, a 200 ms safety margin when feasible, and defensive clamping. Search polls every 512 nodes and retains the last completed iteration. The committed 100-game `30+0.3` evidence records zero time forfeits for both engines. |
| UCI-08 | PASS | `handle_go()` applies clock budgeting only when `depth`, `movetime`, and `infinite` are absent, preserving explicit-limit precedence. A real piped UCI clock command returns exactly one legal best move, and the 100-game gauntlet exercises translated `wtime/btime/winc/binc` end-to-end. |
| TOOL-03 | PASS | `ance/tools/gauntlet.py` implements two argv-safe engine builds, a fixed 30-position opening book, paired colors, wall-clock refereeing, atomic checkpoint/resume, W-L-D/draw-rate/Wilson reporting, and optional `cutechess-cli` command generation/execution. D-15 explicitly makes the python-chess external arbiter the required fallback when `cutechess-cli` is unavailable and says this must not block Phase 3. `command -v cutechess-cli` is absent; the accepted fallback completed 100 identical-build games and produced auditable evidence. |

## Roadmap Success Criteria

| # | Criterion | Result | Evidence |
|---|---|---|---|
| 1 | Correct Zobrist TT bounds, mate-ply handling, reproducible fixed-depth search, stable mate reporting | PASS | TT code and focused tests verify full-key lookup, replacement, all bound flags, score conversion, cold reproducibility, tactical best-move invariance, and stable mate score across completed depths. The wire formatter separately verifies full-move mate notation. |
| 2 | Ordering measurably improves cutoffs/depth over Phase 2 at equal time | PASS | Fresh-state deterministic comparison: 250,005 vs 838,304 nodes (29.82%). Re-run timed gate: Phase 3 depths `{startpos: 4, kiwipete: 0, italian: 3, rook_endgame: 5, hanging_queen: 6, queen_mate: 5}` meet every baseline and improve three of four non-mate positions. |
| 3 | Clock budget with soft/hard limits; no time losses over 100 blitz games; explicit modes honored | PASS | Production clock branch and precedence tests pass. `03-GAUNTLET-EVIDENCE.json`: 100 games at `30+0.3`, status completed, zero forfeits. Dedicated real `5+0.1` smoke also records zero forfeits and bounded deadline overshoot. |
| 4 | `ucinewgame` clears TT and per-game heuristics | PASS | `handle_ucinewgame()` stops the worker, clears the TT, and replaces killer/history tables. Tests prove warm-TT reduction followed by exact cold-node restoration and fresh zeroed heuristics. |
| 5 | Fixed-book identical-build gauntlet reports an approximately 50% score with error bars using the D-15-selected backend | PASS | D-15 selects `cutechess-cli` only when available and requires the python-chess arbiter fallback otherwise. With `cutechess-cli` absent, the accepted fallback ran identical engine argv with fixed openings and paired colors: 36-37-27, score 49.5%, Wilson 95% CI 39.90%-59.14%, zero forfeits. |

**Roadmap score:** 5/5 fully verified. Criterion 5 is satisfied through D-15's mandatory fallback semantics.

## Evidence Integrity

- `03-BASELINE.json` records source commit `035af126...`; git history shows the artifact commit before `transposition.py` and `ordering.py` were introduced.
- The baseline contains six fixed positions, a 2,000 ms timed measurement, deterministic fixed-depth records, and a documented Kiwipete depth-2 override.
- `03-GAUNTLET-EVIDENCE.json` records source commit `29bf2ec...`, identical engine argv, exact command line, 100 completed games, raw W-L-D, Wilson bounds, and zero per-engine forfeits.
- The evidence artifact was committed separately at `b690215`; its assertions revalidate successfully from the current tree.
- The 100-game run resumed from atomic checkpoints after interruptions, exercising the intended recovery path.

## Test Results

| Command | Result |
|---|---|
| Focused Phase 3 non-slow tests across TT, ordering, clocks, gauntlet, baseline, and evidence modules | **84 passed, 4 deselected in 48.88s** |
| Full fast suite: `.venv/bin/python -m pytest -m "not slow" -q` | **231 passed, 6 deselected in 62.73s** |
| Timed D-21 gate: `test_phase3_depth_at_2s_meets_baseline` | **1 passed in 12.10s** |
| Loaded committed gauntlet evidence through D-14/D-17 assertion helpers | **passed** |

The multi-hour 100-game test was not re-run; its completed machine-readable artifact, git provenance, raw statistics, and assertion helpers were independently checked.

## Human Verification Required

None. D-15 explicitly prevents unavailable `cutechess-cli` from blocking completion and accepts the completed external-arbiter run. The En Croissant blitz clock observation from Plan 03-05 remains optional and non-blocking because real subprocess and 100-game arbiter evidence already verify clock safety.

## Non-Blocking Concerns

- Kiwipete cannot complete a Phase 2 iteration within two seconds and uses a deterministic depth-2 override. This is disclosed and comparisons honor the recorded depth, but it weakens breadth at the hardest benchmark position.
- The default Python TT allocates `2^20` slots and documents a potentially large saturated memory footprint; no memory-pressure benchmark is part of Phase 3.
- ROADMAP and REQUIREMENTS bookkeeping still show Phase 3 plans/requirements as pending despite completed summaries and evidence. This report intentionally does not modify those files.
- Stable mate-depth coverage uses the existing forced-mate queen position; there is no separate stable mate-in-3 search fixture.
- A future `cutechess-cli` run would provide optional backend-parity evidence if the binary becomes available, but D-15 explicitly makes it non-blocking.

## Gaps Summary

No gaps. The implementation, focused tests, full fast suite, timed baseline comparison, and committed 100-game evidence establish all five requirements and roadmap criteria. D-15 resolves the apparent backend mismatch by making the external python-chess arbiter the mandatory fallback and explicitly forbidding unavailable `cutechess-cli` from blocking Phase 3.

## Verdict

**Status: `passed`.** SRCH-05, SRCH-06, SRCH-08, UCI-08, and TOOL-03 pass. All five roadmap success criteria are verified. The completed 100-game python-chess external-arbiter run is the correct D-15 evidence path on this machine because `cutechess-cli` is unavailable; a future cutechess run is optional only.
