---
created: 2026-07-08T18:15:00Z
title: "UCI `score mate` must report full moves, not plies (+ clamp eval cp below the mate window)"
area: uci
files:
  - ance/uci/protocol.py
  - tests/test_uci_info.py
resolves_phase: 2
---

## Problem

Phase 2 round-2 discussion locked D-18 (see `02-CONTEXT.md` addendum): mate
scores on the wire are **full moves, signed** — the UCI spec's `score mate <y>`
counts moves, and Stockfish reports `(plies + 1) // 2` so gauntlet logs stay
comparable.

`ance/uci/protocol.py::send_info_depth` (lines ~57-60) currently emits the raw
internal ply distance:

```python
mate_distance = MATE - abs(score)          # this is PLIES
mate_score = mate_distance if score > 0 else -mate_distance
score_part = f"score mate {mate_score}"
```

A mate-in-3-plies position prints `score mate 3` instead of `score mate 2`.
GUIs display the wrong mate distance and log diffs vs Stockfish disagree.

Secondary, lower-risk half of D-18: evaluator centipawn output is not clamped
below the mate window (`MATE - MAX_PLY`), so a pathological eval value could in
principle be misclassified as a mate score. `HandcraftedEval` can't realistically
reach ~29k cp, but the clamp is cheap insurance at the seam boundary.

## Solution

1. In `send_info_depth`, convert plies → full moves:
   `mate_moves = (mate_distance + 1) // 2`, keep the sign convention
   (positive = ANCE mates, negative = ANCE is being mated).
2. Clamp non-mate scores (search/eval cp) to stay strictly below the mate
   window before formatting, or clamp at the eval seam — implementer's choice.
3. Extend the UCI info tests: mate-in-1 (1 ply) → `mate 1`; mate-in-2
   (3 plies) → `mate 2`; being mated in 1 ply → `mate -1`.

Must land before Phase 2 verification — success criterion 3 (UCI-11 info
format) and the D-18 locked decision both depend on it.
