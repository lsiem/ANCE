---
created: 2026-07-07T12:42:09Z
title: "TOOL-02: 100/0 depth-4 gauntlet deferred until alpha-beta pruning makes depth>=4 practical"
area: search
files:
  - ance/tools/random_mover_gauntlet.py
  - tests/test_random_mover_gauntlet.py
  - .planning/phases/01-minimal-uci-engine-evaluator-seam/01-05-PLAN.md
resolves_phase: null
---

## Problem

Plan 01-05's original acceptance criterion for TOOL-02 was "ANCE beats the
random mover 100/100 (wins==100, losses==0) at GAUNTLET_SEARCH_DEPTH=4".
During execution this proved both impractical and unverified:

- A real depth-4/100-game run (pure-Python, unpruned negamax) was killed
  after 31 minutes without finishing.
- A depth-3 spot check already produced a draw, so even the 100/0 target
  at depth 4 was never actually measured green.

This was replanned (approved 2026-07-07) to the criterion that IS measured
and holds: `losses == 0` (hard invariant) + `wins >= 70%` of 30 games at
`GAUNTLET_SEARCH_DEPTH = 2`, with every non-win required to be a draw.
Measured evidence: 25 wins / 0 losses / 5 draws (83%) over seeds 0..29,
~31s wall-clock; all 5 draws are `max_halfmoves`(300) cap conversions —
shallow search finds the winning material edge but can't force mate
within the cap, never a loss or stalemate.

The original, stronger goal — 100 wins / 0 draws out of 100 games at
`GAUNTLET_SEARCH_DEPTH = 4` (or deeper) — remains a legitimate future
strength target. It requires converting the current cap-draws into wins
by searching deep enough to actually find and execute the forced mate
before the halfmove cap, which needs alpha-beta pruning to be practical
in wall-clock time at pure-Python speeds.

## Solution

Once alpha-beta pruning (SRCH phase per ROADMAP.md) lands and search at
depth >= 4 becomes practical in wall-clock time (target: a 100-game run
completing in a few minutes, not tens of minutes):

1. Re-run the gauntlet at increasing depth (e.g. 4, then higher) and
   measure whether the cap-draws convert to wins.
2. If `wins == 100` and `losses == 0` is achieved and reproducible, restore
   the original strict acceptance criterion (or tighten further) in
   `tests/test_random_mover_gauntlet.py` and update
   `ance/tools/random_mover_gauntlet.py`'s `GAUNTLET_SEARCH_DEPTH` and
   docstring accordingly.
3. If it still draws at practical depths, re-evaluate whether `max_halfmoves`
   (currently 300) is the limiting factor, per the in-code failure runbook.

This todo references the 01-05 replan; see
`.planning/phases/01-minimal-uci-engine-evaluator-seam/01-05-SUMMARY.md`
for full rationale and measured evidence.
